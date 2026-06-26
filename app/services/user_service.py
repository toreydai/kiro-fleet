"""IC 用户业务逻辑."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.aws.identity_center import IdentityCenterClient
from app.core.exceptions import (
    AccountNotFoundError,
    AccountNotVerifiedError,
    ConflictError,
    UserNotFoundError,
)
from app.core.security import decrypt
from app.repositories.account_repo import AccountRepository
from app.repositories.user_repo import ICUserRepository
from app.services.log_service import LogService

logger = logging.getLogger(__name__)


def _get_ic_client(account) -> IdentityCenterClient:
    from app.aws.client import AsyncAWSClient

    ak = decrypt(account.access_key_id)
    sk = decrypt(account.secret_access_key)
    aws_client = AsyncAWSClient(ak, sk, account.sso_region)
    return IdentityCenterClient(aws_client, account.sso_region, account.identity_store_id)


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.account_repo = AccountRepository(session)
        self.user_repo = ICUserRepository(session)
        self.log_svc = LogService(session)

    async def _require_account(self, account_id: int):
        account = await self.account_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        if account.status != "active":
            raise AccountNotVerifiedError()
        return account

    async def list_users(
        self,
        account_id: int,
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
    ) -> tuple[list, int]:
        account = await self.account_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        return await self.user_repo.list_by_account(account_id, page, page_size, search)

    async def get_user(self, account_id: int, user_id: int):
        account = await self.account_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        user = await self.user_repo.get_by_id(user_id)
        if not user or user.aws_account_id != account_id:
            raise UserNotFoundError(user_id)
        return user

    async def create_user(
        self,
        account_id: int,
        user_name: str,
        email: str,
        given_name: str | None = None,
        family_name: str | None = None,
        display_name: str | None = None,
        operator: str | None = None,
    ):
        account = await self._require_account(account_id)

        # 检查用户名重复
        existing = await self.user_repo.get_by_username(account_id, user_name)
        if existing:
            raise ConflictError(f"用户名 '{user_name}' 已存在")

        ic_client = _get_ic_client(account)
        try:
            result = await ic_client.create_user(
                user_name=user_name,
                email=email,
                given_name=given_name,
                family_name=family_name,
                display_name=display_name,
            )
            aws_user_id = result.get("UserId", "")
        except Exception as e:
            await self.log_svc.log(
                operation="create_user",
                status="failed",
                account_id=account_id,
                target=user_name,
                message=str(e),
                operator=operator,
            )
            raise

        user = await self.user_repo.create(
            aws_account_id=account_id,
            user_id=aws_user_id,
            user_name=user_name,
            display_name=display_name or f"{given_name or ''} {family_name or ''}".strip(),
            email=email,
            given_name=given_name,
            family_name=family_name,
            status="active",
        )

        await self.log_svc.log(
            operation="create_user",
            status="success",
            account_id=account_id,
            target=user_name,
            message=f"创建 IC 用户 {user_name}",
            operator=operator,
        )
        return user

    async def delete_user(self, account_id: int, user_id: int, operator: str | None = None) -> None:
        account = await self._require_account(account_id)
        user = await self.user_repo.get_by_id(user_id)
        if not user or user.aws_account_id != account_id:
            raise UserNotFoundError(user_id)

        ic_client = _get_ic_client(account)
        try:
            await ic_client.delete_user(user.user_id)
        except Exception as e:
            await self.log_svc.log(
                operation="delete_user",
                status="failed",
                account_id=account_id,
                target=user.user_name,
                message=str(e),
                operator=operator,
            )
            raise

        await self.user_repo.delete(user)
        await self.log_svc.log(
            operation="delete_user",
            status="success",
            account_id=account_id,
            target=user.user_name,
            operator=operator,
        )

    async def reset_password(
        self, account_id: int, user_id: int, operator: str | None = None
    ) -> None:
        account = await self._require_account(account_id)
        user = await self.user_repo.get_by_id(user_id)
        if not user or user.aws_account_id != account_id:
            raise UserNotFoundError(user_id)

        ic_client = _get_ic_client(account)
        await ic_client.reset_password_by_email(user.user_id)
        await self.log_svc.log(
            operation="reset_password",
            status="success",
            account_id=account_id,
            target=user.user_name,
            operator=operator,
        )

    async def send_email_verification(
        self, account_id: int, user_id: int, operator: str | None = None
    ) -> None:
        account = await self._require_account(account_id)
        user = await self.user_repo.get_by_id(user_id)
        if not user or user.aws_account_id != account_id:
            raise UserNotFoundError(user_id)

        ic_client = _get_ic_client(account)
        await ic_client.start_email_verification(user.user_id, account.identity_store_id)
        await self.log_svc.log(
            operation="send_email_verification",
            status="success",
            account_id=account_id,
            target=user.user_name,
            operator=operator,
        )

    async def list_groups(self, account_id: int) -> list[dict]:
        account = await self._require_account(account_id)
        ic_client = _get_ic_client(account)
        result = await ic_client.list_groups()
        return result.get("Groups", [])

    async def add_user_to_group(
        self,
        account_id: int,
        user_id: int,
        group_id: str,
        operator: str | None = None,
    ) -> None:
        account = await self._require_account(account_id)
        user = await self.user_repo.get_by_id(user_id)
        if not user or user.aws_account_id != account_id:
            raise UserNotFoundError(user_id)

        ic_client = _get_ic_client(account)
        await ic_client.add_user_to_group(group_id=group_id, user_id=user.user_id)
        await self.log_svc.log(
            operation="add_to_group",
            status="success",
            account_id=account_id,
            target=f"{user.user_name}@{group_id}",
            operator=operator,
        )
