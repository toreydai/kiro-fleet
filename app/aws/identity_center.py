"""Identity Center 操作封装."""

from __future__ import annotations

import logging
from typing import Any

from app.aws.client import AsyncAWSClient

logger = logging.getLogger(__name__)


class IdentityCenterClient:
    """Identity Center 用户/组管理."""

    def __init__(self, client: AsyncAWSClient, sso_region: str, identity_store_id: str):
        self.client = client
        self.sso_region = sso_region
        self.identity_store_id = identity_store_id
        self._base_url = f"https://identitystore.{sso_region}.amazonaws.com/"

    # ── 用户 CRUD ─────────────────────────────────────────────────────────

    async def create_user(
        self,
        user_name: str,
        email: str,
        given_name: str | None = None,
        family_name: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """在 Identity Store 中创建用户."""
        given = given_name or user_name
        family = family_name or user_name
        result = await self.client.boto3_call(
            "identitystore",
            "create_user",
            region=self.sso_region,
            IdentityStoreId=self.identity_store_id,
            UserName=user_name,
            DisplayName=display_name or f"{given} {family}",
            Name={"GivenName": given, "FamilyName": family},
            Emails=[{"Value": email, "Type": "work", "Primary": True}],
        )
        logger.info("Created IC user: %s (id=%s)", user_name, result.get("UserId"))
        return result

    async def get_user(self, user_id: str) -> dict[str, Any]:
        payload = {
            "IdentityStoreId": self.identity_store_id,
            "UserId": user_id,
        }
        return await self.client.sigv4_post(
            url=self._base_url,
            target="AWSIdentityStoreService.DescribeUser",
            payload=payload,
            service="identitystore",
            region=self.sso_region,
        )

    async def delete_user(self, user_id: str) -> None:
        payload = {
            "IdentityStoreId": self.identity_store_id,
            "UserId": user_id,
        }
        await self.client.sigv4_post(
            url=self._base_url,
            target="AWSIdentityStoreService.DeleteUser",
            payload=payload,
            service="identitystore",
            region=self.sso_region,
        )
        logger.info("Deleted IC user: %s", user_id)

    async def list_users(
        self,
        max_results: int = 100,
        next_token: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "IdentityStoreId": self.identity_store_id,
            "MaxResults": max_results,
        }
        if next_token:
            payload["NextToken"] = next_token
        return await self.client.sigv4_post(
            url=self._base_url,
            target="AWSIdentityStoreService.ListUsers",
            payload=payload,
            service="identitystore",
            region=self.sso_region,
        )

    async def search_users_by_email(self, email: str) -> list[dict[str, Any]]:
        """用内部 SearchUsers API 搜索（含邮箱验证状态）."""
        url = f"https://identitystore.{self.sso_region}.amazonaws.com/identitystore/"
        payload = {
            "IdentityStoreId": self.identity_store_id,
            "Filters": [{"AttributePath": "Emails.Value", "AttributeValue": email}],
        }
        result = await self.client.sigv4_post(
            url=url,
            target="AWSIdentityStoreService.SearchUsers",
            payload=payload,
            service="identitystore",
            region=self.sso_region,
        )
        return result.get("Users", [])

    async def list_all_users(self) -> list[dict[str, Any]]:
        """分页获取所有用户."""
        users: list[dict[str, Any]] = []
        next_token: str | None = None
        while True:
            resp = await self.list_users(max_results=100, next_token=next_token)
            users.extend(resp.get("Users", []))
            next_token = resp.get("NextToken")
            if not next_token:
                break
        return users

    # ── 密码 / 邮箱验证 ───────────────────────────────────────────────────

    async def generate_one_time_password(self, user_id: str) -> str:
        """生成一次性临时密码，返回明文密码（供管理员分发）."""
        url = f"https://identitystore.{self.sso_region}.amazonaws.com/"
        payload = {"UserId": user_id, "PasswordMode": "ONE_TIME_PASSWORD"}
        resp = await self.client.sigv4_post(
            url=url,
            target="SWBUPService.UpdatePassword",
            payload=payload,
            service="identitystore",
            region=self.sso_region,
        )
        password = (resp or {}).get("Password", "")
        logger.info("Generated OTP for user: %s", user_id)
        return password

    async def reset_password_by_email(self, user_id: str) -> None:
        """触发邮件重置密码."""
        url = f"https://identitystore.{self.sso_region}.amazonaws.com/"
        payload = {"UserId": user_id, "PasswordMode": "EMAIL"}
        await self.client.sigv4_post(
            url=url,
            target="SWBUPService.UpdatePassword",
            payload=payload,
            service="identitystore",
            region=self.sso_region,
        )
        logger.info("Sent password reset email for user: %s", user_id)

    async def start_email_verification(
        self, user_id: str, identity_store_id: str | None = None
    ) -> None:
        """发送邮箱验证邮件."""
        sid = identity_store_id or self.identity_store_id
        url = f"https://pvs-controlplane.{self.sso_region}.prod.authn.identity.aws.dev/"
        payload = {"UserId": user_id, "IdentityStoreId": sid}
        await self.client.sigv4_post(
            url=url,
            target="AWSPasswordControlPlaneService.StartEmailVerification",
            payload=payload,
            service="sso-directory",
            region=self.sso_region,
        )
        logger.info("Sent email verification for user: %s", user_id)

    # ── 用户组 ────────────────────────────────────────────────────────────

    async def list_groups(
        self, max_results: int = 100, next_token: str | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "IdentityStoreId": self.identity_store_id,
            "MaxResults": max_results,
        }
        if next_token:
            payload["NextToken"] = next_token
        return await self.client.sigv4_post(
            url=self._base_url,
            target="AWSIdentityStoreService.ListGroups",
            payload=payload,
            service="identitystore",
            region=self.sso_region,
        )

    async def add_user_to_group(self, group_id: str, user_id: str) -> dict[str, Any]:
        return await self.client.boto3_call(
            "identitystore",
            "create_group_membership",
            region=self.sso_region,
            IdentityStoreId=self.identity_store_id,
            GroupId=group_id,
            MemberId={"UserId": user_id},
        )

    async def list_user_groups(self, user_id: str) -> list[dict[str, Any]]:
        """列出用户所在的所有组."""
        payload = {
            "IdentityStoreId": self.identity_store_id,
            "MemberId": {"UserId": user_id},
        }
        result = await self.client.sigv4_post(
            url=self._base_url,
            target="AWSIdentityStoreService.ListGroupMembershipsForMember",
            payload=payload,
            service="identitystore",
            region=self.sso_region,
        )
        return result.get("GroupMemberships", [])
