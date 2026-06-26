"""异步 SigV4 AWS 客户端 — 唯一一份 AWS 实现."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import boto3
import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

logger = logging.getLogger(__name__)


class AsyncAWSClient:
    """通用异步 SigV4 HTTP 客户端。

    凭证不跨请求缓存（最短生命周期策略）。
    boto3 调用用 asyncio.to_thread() 包装以防阻塞事件循环。
    """

    def __init__(self, access_key: str, secret_key: str, region: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        # 创建 boto3 Session 用于 SigV4 签名和 SDK 调用
        self._boto_session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        self._credentials = self._boto_session.get_credentials().get_frozen_credentials()

    def _get_sigv4_headers(
        self,
        method: str,
        url: str,
        payload: dict[str, Any],
        target: str,
        service: str,
        region: str,
    ) -> dict[str, str]:
        """构建 SigV4 签名请求头."""
        body = json.dumps(payload, separators=(",", ":"))
        aws_req = AWSRequest(
            method=method.upper(),
            url=url,
            data=body.encode(),
            headers={
                "Content-Type": "application/x-amz-json-1.0",
                "X-Amz-Target": target,
            },
        )
        SigV4Auth(self._credentials, service, region).add_auth(aws_req)
        return dict(aws_req.headers)

    async def sigv4_post(
        self,
        url: str,
        target: str,
        payload: dict[str, Any],
        service: str,
        region: str | None = None,
    ) -> dict[str, Any]:
        """发送 SigV4 签名的 POST 请求，返回解析后的 JSON 响应体."""
        effective_region = region or self.region
        headers = self._get_sigv4_headers("POST", url, payload, target, service, effective_region)
        body = json.dumps(payload, separators=(",", ":"))

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, content=body.encode(), headers=headers)

        logger.debug("SigV4 POST %s target=%s status=%d", url, target, response.status_code)

        if response.status_code not in (200, 201, 202, 204):
            raise _parse_aws_error(response, target)

        if response.content:
            return response.json()
        return {}

    def get_boto3_client(self, service_name: str, region: str | None = None) -> Any:
        """获取 boto3 客户端（同步，需用 asyncio.to_thread 包装调用）."""
        return self._boto_session.client(service_name, region_name=region or self.region)

    async def boto3_call(
        self, service_name: str, method: str, region: str | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """在线程池中执行 boto3 调用，避免阻塞事件循环."""
        client = self.get_boto3_client(service_name, region)

        def _call() -> dict[str, Any]:
            fn = getattr(client, method)
            return fn(**kwargs)

        return await asyncio.to_thread(_call)


def _parse_aws_error(response: httpx.Response, target: str) -> Exception:
    """解析 AWS 错误响应，返回带有详情的异常."""
    from app.core.exceptions import AWSOperationError

    try:
        body = response.json()
        code = body.get("__type", body.get("errorCode", "UnknownError"))
        message = body.get("message", body.get("Message", response.text))
    except Exception:
        code = f"HTTP_{response.status_code}"
        message = response.text[:500]

    logger.warning("AWS error: target=%s code=%s message=%s", target, code, message)
    return AWSOperationError(f"[{code}] {message}", operation=target)
