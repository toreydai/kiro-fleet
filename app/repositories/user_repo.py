"""IC 用户 & 系统用户数据访问层."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aws_account import ICUser
from app.models.system_user import RefreshToken, SystemUser


class ICUserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> ICUser | None:
        return await self.session.get(ICUser, user_id)

    async def get_by_aws_user_id(self, account_id: int, aws_user_id: str) -> ICUser | None:
        stmt = select(ICUser).where(
            and_(
                ICUser.aws_account_id == account_id,
                ICUser.user_id == aws_user_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, account_id: int, user_name: str) -> ICUser | None:
        stmt = select(ICUser).where(
            and_(
                ICUser.aws_account_id == account_id,
                ICUser.user_name == user_name,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_account(
        self,
        account_id: int,
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
    ) -> tuple[list[ICUser], int]:
        stmt = select(ICUser).where(ICUser.aws_account_id == account_id)
        if search:
            stmt = stmt.where(
                ICUser.user_name.ilike(f"%{search}%")
                | ICUser.email.ilike(f"%{search}%")
                | ICUser.display_name.ilike(f"%{search}%")
            )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.session.scalar(count_stmt) or 0

        stmt = stmt.order_by(ICUser.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_with_pending_subscription(self) -> list[ICUser]:
        stmt = select(ICUser).where(ICUser.pending_subscription_type.is_not(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **kwargs: Any) -> ICUser:
        user = ICUser(**kwargs)
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update(self, user: ICUser, **kwargs: Any) -> ICUser:
        for key, value in kwargs.items():
            setattr(user, key, value)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def delete(self, user: ICUser) -> None:
        await self.session.delete(user)
        await self.session.flush()

    async def bulk_upsert(
        self, account_id: int, users_data: list[dict[str, Any]]
    ) -> tuple[int, int]:
        """批量 upsert（同步时用）。返回 (created, updated) 计数."""
        created = updated = 0
        for data in users_data:
            aws_user_id = data.get("UserId", "")
            existing = await self.get_by_aws_user_id(account_id, aws_user_id)
            if existing:
                for field in ("user_name", "display_name", "email", "status"):
                    if field in data:
                        setattr(existing, field, data[field])
                existing.last_synced = datetime.now(timezone.utc)
                updated += 1
            else:
                new_user = ICUser(
                    aws_account_id=account_id,
                    user_id=aws_user_id,
                    user_name=data.get("UserName", ""),
                    display_name=data.get("DisplayName"),
                    email=data.get("Email"),
                    status="active",
                    last_synced=datetime.now(timezone.utc),
                )
                self.session.add(new_user)
                created += 1
        await self.session.flush()
        return created, updated


class SystemUserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> SystemUser | None:
        return await self.session.get(SystemUser, user_id)

    async def get_by_username(self, username: str) -> SystemUser | None:
        stmt = select(SystemUser).where(SystemUser.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> SystemUser | None:
        stmt = select(SystemUser).where(SystemUser.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[SystemUser]:
        stmt = select(SystemUser).order_by(SystemUser.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_admins(self) -> int:
        stmt = (
            select(func.count())
            .select_from(SystemUser)
            .where(and_(SystemUser.is_admin.is_(True), SystemUser.is_active.is_(True)))
        )
        return await self.session.scalar(stmt) or 0

    async def create(self, **kwargs: Any) -> SystemUser:
        user = SystemUser(**kwargs)
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update(self, user: SystemUser, **kwargs: Any) -> SystemUser:
        for key, value in kwargs.items():
            setattr(user, key, value)
        user.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def delete(self, user: SystemUser) -> None:
        await self.session.delete(user)
        await self.session.flush()

    # ── Refresh Token ─────────────────────────────────────────────────────

    async def create_refresh_token(
        self, user_id: int, token: str, expires_at: datetime
    ) -> RefreshToken:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        rt = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(rt)
        await self.session.flush()
        return rt

    async def get_refresh_token(self, token: str) -> RefreshToken | None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, token: str) -> None:
        rt = await self.get_refresh_token(token)
        if rt:
            rt.revoked = True
            await self.session.flush()

    async def revoke_all_user_tokens(self, user_id: int) -> None:
        stmt = update(RefreshToken).where(RefreshToken.user_id == user_id).values(revoked=True)
        await self.session.execute(stmt)
