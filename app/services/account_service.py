"""账号业务逻辑."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.aws.client import AsyncAWSClient
from app.aws.identity_center import IdentityCenterClient
from app.core.exceptions import (
    AccountNotFoundError,
    AWSCredentialsError,
    ConflictError,
)
from app.core.security import decrypt, encrypt
from app.repositories.account_repo import AccountRepository
from app.schemas.account import AccountCreate, AccountUpdate

logger = logging.getLogger(__name__)


class AccountService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AccountRepository(session)

    async def create_account(self, data: AccountCreate) -> object:
        existing = await self.repo.get_by_name(data.name)
        if existing:
            raise ConflictError(f"账号名称 '{data.name}' 已存在")

        # 加密 AK/SK
        encrypted_ak = encrypt(data.access_key_id)
        encrypted_sk = encrypt(data.secret_access_key)

        if data.is_default:
            await self.repo.clear_default()

        account = await self.repo.create(
            name=data.name,
            description=data.description,
            access_key_id=encrypted_ak,
            secret_access_key=encrypted_sk,
            sso_region=data.sso_region,
            kiro_region=data.kiro_region,
            instance_arn=data.instance_arn,
            identity_store_id=data.identity_store_id,
            kiro_login_url=data.kiro_login_url,
            sync_interval_minutes=data.sync_interval_minutes,
            is_default=data.is_default,
            status="pending",
        )
        return account

    async def get_account(self, account_id: int) -> object:
        account = await self.repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        return account

    async def list_accounts(self) -> list:
        return await self.repo.list_all()

    async def update_account(self, account_id: int, data: AccountUpdate) -> object:
        account = await self.repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(account_id)

        updates: dict = {}
        if data.name is not None:
            existing = await self.repo.get_by_name(data.name)
            if existing and existing.id != account_id:
                raise ConflictError(f"账号名称 '{data.name}' 已被占用")
            updates["name"] = data.name
        if data.description is not None:
            updates["description"] = data.description
        if data.access_key_id is not None:
            updates["access_key_id"] = encrypt(data.access_key_id)
        if data.secret_access_key is not None:
            updates["secret_access_key"] = encrypt(data.secret_access_key)
        if data.sso_region is not None:
            updates["sso_region"] = data.sso_region
        if data.kiro_region is not None:
            updates["kiro_region"] = data.kiro_region
        if data.instance_arn is not None:
            updates["instance_arn"] = data.instance_arn
        if data.identity_store_id is not None:
            updates["identity_store_id"] = data.identity_store_id
        if data.kiro_login_url is not None:
            updates["kiro_login_url"] = data.kiro_login_url
        if data.sync_interval_minutes is not None:
            updates["sync_interval_minutes"] = data.sync_interval_minutes
        if data.is_default is not None:
            if data.is_default:
                await self.repo.clear_default()
            updates["is_default"] = data.is_default

        return await self.repo.update(account, **updates)

    async def delete_account(self, account_id: int) -> None:
        account = await self.repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        await self.repo.delete(account)

    async def verify_account(self, account_id: int) -> object:
        """验证 AWS 凭证有效性（实际调用 Identity Center List API）."""
        account = await self.repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(account_id)

        try:
            ak = decrypt(account.access_key_id)
            sk = decrypt(account.secret_access_key)
        except Exception as e:
            await self.repo.set_status(account_id, "invalid")
            raise AWSCredentialsError(f"凭证解密失败: {e}") from e

        try:
            aws_client = AsyncAWSClient(ak, sk, account.sso_region)
            ic_client = IdentityCenterClient(
                aws_client, account.sso_region, account.identity_store_id
            )
            # 调用 ListUsers 最多1条验证权限
            await ic_client.list_users(max_results=1)
            await self.repo.set_status(
                account_id, "active", last_verified=datetime.now(timezone.utc)
            )
            logger.info("Account %d verified successfully", account_id)
        except Exception as e:
            await self.repo.set_status(account_id, "invalid")
            raise AWSCredentialsError(f"凭证验证失败: {e}") from e

        return await self.repo.get_by_id(account_id)

    async def get_stats(self) -> dict:
        return await self.repo.get_stats()

    def get_aws_client(self, account) -> AsyncAWSClient:
        """返回解密凭证后的 AWS 客户端."""
        ak = decrypt(account.access_key_id)
        sk = decrypt(account.secret_access_key)
        return AsyncAWSClient(ak, sk, account.sso_region)
