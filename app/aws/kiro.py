"""Kiro 订阅操作封装."""

from __future__ import annotations

import logging
from typing import Any

from app.aws.client import AsyncAWSClient
from app.core.exceptions import AWSOperationError

logger = logging.getLogger(__name__)

# 新订阅类型 → 旧订阅类型自动降级映射
SUBSCRIPTION_TYPE_FALLBACKS: dict[str, str] = {
    "KIRO_ENTERPRISE_PRO": "Q_DEVELOPER_STANDALONE_PRO",
    "KIRO_ENTERPRISE_PRO_PLUS": "Q_DEVELOPER_STANDALONE_PRO_PLUS",
    "KIRO_ENTERPRISE_PRO_POWER": "Q_DEVELOPER_STANDALONE_POWER",
}


class KiroSubscriptionClient:
    """Kiro 订阅管理."""

    def __init__(self, client: AsyncAWSClient, kiro_region: str, sso_region: str):
        self.client = client
        self.kiro_region = kiro_region
        self.sso_region = sso_region
        self._codewhisperer_url = f"https://codewhisperer.{kiro_region}.amazonaws.com/"
        self._list_url = f"https://service.user-subscriptions.{sso_region}.amazonaws.com/"

    # ── 分配订阅 ──────────────────────────────────────────────────────────

    async def create_assignment(
        self,
        instance_arn: str,
        principal_id: str,
        subscription_type: str,
    ) -> dict[str, Any]:
        """分配 Kiro 订阅（如旧类型失败，自动重试新类型）."""
        payload = {
            "instanceArn": instance_arn,
            "principalId": principal_id,
            "principalType": "USER",
            "subscriptionType": subscription_type,
        }
        try:
            result = await self.client.sigv4_post(
                url=self._codewhisperer_url,
                target="AmazonQDeveloperService.CreateAssignment",
                payload=payload,
                service="q",
                region=self.kiro_region,
            )
            logger.info("Created assignment: principal=%s type=%s", principal_id, subscription_type)
            return result
        except AWSOperationError as e:
            # 自动重试：旧类型 → 新类型
            fallback = SUBSCRIPTION_TYPE_FALLBACKS.get(subscription_type)
            if fallback and "ValidationException" in str(e):
                logger.info(
                    "Retrying assignment with fallback type: %s -> %s",
                    subscription_type,
                    fallback,
                )
                payload["subscriptionType"] = fallback
                result = await self.client.sigv4_post(
                    url=self._codewhisperer_url,
                    target="AmazonQDeveloperService.CreateAssignment",
                    payload=payload,
                    service="q",
                    region=self.kiro_region,
                )
                return result
            raise

    async def delete_assignment(
        self,
        instance_arn: str,
        principal_id: str,
    ) -> dict[str, Any]:
        """取消 Kiro 订阅."""
        payload = {
            "instanceArn": instance_arn,
            "principalId": principal_id,
            "principalType": "USER",
        }
        result = await self.client.sigv4_post(
            url=self._codewhisperer_url,
            target="AmazonQDeveloperService.DeleteAssignment",
            payload=payload,
            service="q",
            region=self.kiro_region,
        )
        logger.info("Deleted assignment: principal=%s", principal_id)
        return result

    async def update_assignment(
        self,
        instance_arn: str,
        principal_id: str,
        subscription_type: str,
    ) -> dict[str, Any]:
        """更新订阅类型."""
        payload = {
            "instanceArn": instance_arn,
            "principalId": principal_id,
            "principalType": "USER",
            "subscriptionType": subscription_type,
        }
        try:
            result = await self.client.sigv4_post(
                url=self._codewhisperer_url,
                target="AmazonQDeveloperService.UpdateAssignment",
                payload=payload,
                service="q",
                region=self.kiro_region,
            )
            logger.info("Updated assignment: principal=%s type=%s", principal_id, subscription_type)
            return result
        except AWSOperationError as e:
            fallback = SUBSCRIPTION_TYPE_FALLBACKS.get(subscription_type)
            if fallback and "ValidationException" in str(e):
                payload["subscriptionType"] = fallback
                result = await self.client.sigv4_post(
                    url=self._codewhisperer_url,
                    target="AmazonQDeveloperService.UpdateAssignment",
                    payload=payload,
                    service="q",
                    region=self.kiro_region,
                )
                return result
            raise

    # ── 查询订阅 ──────────────────────────────────────────────────────────

    async def list_user_subscriptions(
        self,
        instance_arn: str,
        next_token: str | None = None,
        max_results: int = 100,
    ) -> dict[str, Any]:
        """列出账号下所有用户的订阅（含 usage 字段）."""
        payload: dict[str, Any] = {
            "instanceArn": instance_arn,
            "maxResults": max_results,
            "subscriptionRegion": self.kiro_region,
        }
        if next_token:
            payload["nextToken"] = next_token
        return await self.client.sigv4_post(
            url=self._list_url,
            target="AWSZornControlPlaneService.ListUserSubscriptions",
            payload=payload,
            service="user-subscriptions",
            region=self.sso_region,
        )

    async def list_all_user_subscriptions(self, instance_arn: str) -> list[dict[str, Any]]:
        """分页获取所有订阅."""
        subscriptions: list[dict[str, Any]] = []
        next_token: str | None = None
        while True:
            resp = await self.list_user_subscriptions(
                instance_arn=instance_arn, next_token=next_token
            )
            subscriptions.extend(resp.get("UserSubscriptions", []))
            next_token = resp.get("NextToken")
            if not next_token:
                break
        return subscriptions
