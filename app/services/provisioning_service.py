"""批量开通业务逻辑."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session_maker
from app.core.exceptions import AccountNotFoundError, AccountNotVerifiedError
from app.repositories.account_repo import AccountRepository
from app.repositories.subscription_repo import BatchTaskRepository
from app.repositories.user_repo import ICUserRepository
from app.services.log_service import LogService

logger = logging.getLogger(__name__)


class ProvisioningService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.account_repo = AccountRepository(session)
        self.user_repo = ICUserRepository(session)
        self.task_repo = BatchTaskRepository(session)
        self.log_svc = LogService(session)

    async def _require_account(self, account_id: int):
        account = await self.account_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        if account.status != "active":
            raise AccountNotVerifiedError()
        return account

    def _generate_usernames(self, prefix: str, count: int, existing_names: set[str]) -> list[str]:
        """生成不重复的用户名列表."""
        names = []
        ts = int(time.time())
        idx = 0
        while len(names) < count:
            candidate = f"{prefix}{ts}{idx:03d}"
            if candidate not in existing_names:
                names.append(candidate)
                existing_names.add(candidate)
            idx += 1
        return names

    async def quick_provision(
        self,
        account_id: int,
        plans: list[dict[str, Any]],
        domain: str,
        prefix: str,
        group_id: str | None = None,
        operator: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """一键批量开通 — 返回异步生成器，逐步 yield 进度事件."""
        # 在返回生成器前校验账号，确保错误在 HTTP 200 发出前抛出
        await self._require_account(account_id)
        return self._run_provision(account_id, plans, domain, prefix, group_id, operator)

    async def _run_provision(
        self,
        account_id: int,
        plans: list[dict[str, Any]],
        domain: str,
        prefix: str,
        group_id: str | None,
        operator: str | None,
    ) -> AsyncGenerator[dict[str, Any], None]:

        # 计算总数
        total = sum(p["count"] for p in plans)

        # 创建 BatchTask 记录
        task = await self.task_repo.create(
            aws_account_id=account_id,
            task_type="quick_provision",
            params={"plans": plans, "domain": domain, "prefix": prefix, "group_id": group_id},
            status="running",
            total_count=total,
            started_at=datetime.now(timezone.utc),
        )
        await self.session.commit()

        # 收集已有用户名（用于冲突检测）
        existing_users, _ = await self.user_repo.list_by_account(account_id, page_size=100000)
        existing_names: set[str] = {u.user_name for u in existing_users}

        success = failed = 0

        try:
            for plan in plans:
                sub_type = plan["subscription_type"]
                count = plan["count"]
                usernames = self._generate_usernames(prefix, count, existing_names)

                for uname in usernames:
                    email = f"{uname}@{domain}"
                    yield {
                        "type": "progress",
                        "task_id": task.id,
                        "status": "running",
                        "progress": int((success + failed) / total * 100),
                        "total": total,
                        "done": success + failed,
                        "success_count": success,
                        "failed_count": failed,
                        "message": f"正在创建用户 {uname}",
                    }

                    try:
                        # 在独立 session 中执行（避免长事务）
                        async with get_session_maker()() as sub_session:
                            from app.services.subscription_service import SubscriptionService
                            from app.services.user_service import UserService

                            user_svc = UserService(sub_session)
                            sub_svc = SubscriptionService(sub_session)

                            new_user, temp_password = await user_svc.create_user(
                                account_id=account_id,
                                user_name=uname,
                                email=email,
                                operator=operator,
                            )
                            try:
                                await sub_svc.assign(
                                    account_id=account_id,
                                    ic_user_id=new_user.id,
                                    subscription_type=sub_type,
                                    operator=operator,
                                )
                            except Exception as sub_err:
                                # 订阅失败写 pending，用户已创建
                                logger.warning("Subscription failed for %s: %s", uname, sub_err)
                            if group_id:
                                try:
                                    await user_svc.add_user_to_group(
                                        account_id=account_id,
                                        user_id=new_user.id,
                                        group_id=group_id,
                                        operator=operator,
                                    )
                                except Exception as grp_err:
                                    logger.warning("Add to group failed for %s: %s", uname, grp_err)
                            await sub_session.commit()
                        success += 1
                        yield {
                            "type": "user_created",
                            "username": uname,
                            "email": email,
                            "plan": sub_type,
                            "password": temp_password,
                        }
                    except Exception as e:
                        logger.error("Provision failed for user %s: %s", uname, e)
                        failed += 1
                        yield {
                            "type": "user_failed",
                            "username": uname,
                            "email": email,
                            "plan": sub_type,
                            "error": str(e),
                        }

            status = "completed"
        except Exception as e:
            logger.error("Provision task %d failed: %s", task.id, e)
            status = "failed"

        # 更新任务状态
        async with get_session_maker()() as fin_session:
            task_repo = BatchTaskRepository(fin_session)
            t = await task_repo.get_by_id(task.id)
            if t:
                await task_repo.update(
                    t,
                    status=status,
                    progress=100,
                    success_count=success,
                    failed_count=failed,
                    completed_at=datetime.now(timezone.utc),
                )
            await fin_session.commit()

        yield {
            "type": "summary",
            "task_id": task.id,
            "status": status,
            "progress": 100,
            "total": total,
            "done": total,
            "success_count": success,
            "failed_count": failed,
            "message": f"完成: 成功 {success} / 失败 {failed}",
        }

    async def batch_import(
        self,
        account_id: int,
        users_data: list[dict[str, Any]],
        default_sub_type: str | None = None,
        operator: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """列表批量导入 — 返回异步生成器."""
        await self._require_account(account_id)
        return self._run_batch_import(account_id, users_data, default_sub_type, operator)

    async def _run_batch_import(
        self,
        account_id: int,
        users_data: list[dict[str, Any]],
        default_sub_type: str | None,
        operator: str | None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        total = len(users_data)

        task = await self.task_repo.create(
            aws_account_id=account_id,
            task_type="batch_import",
            params={"default_sub_type": default_sub_type},
            status="running",
            total_count=total,
            started_at=datetime.now(timezone.utc),
        )
        await self.session.commit()

        success = failed = 0

        for i, ud in enumerate(users_data):
            uname = ud.get("user_name", "")
            yield {
                "task_id": task.id,
                "status": "running",
                "progress": int(i / total * 100),
                "total_count": total,
                "success_count": success,
                "failed_count": failed,
                "current_user": uname,
                "message": f"导入用户 {uname}",
            }

            try:
                async with get_session_maker()() as sub_session:
                    from app.services.subscription_service import SubscriptionService
                    from app.services.user_service import UserService

                    user_svc = UserService(sub_session)
                    sub_svc = SubscriptionService(sub_session)

                    new_user = await user_svc.create_user(
                        account_id=account_id,
                        user_name=uname,
                        email=ud.get("email", ""),
                        given_name=ud.get("given_name"),
                        family_name=ud.get("family_name"),
                        operator=operator,
                    )
                    sub_type = ud.get("subscription_type") or default_sub_type
                    if sub_type:
                        try:
                            await sub_svc.assign(
                                account_id=account_id,
                                ic_user_id=new_user.id,
                                subscription_type=sub_type,
                                operator=operator,
                            )
                        except Exception as sub_err:
                            logger.warning("Sub failed for %s: %s", uname, sub_err)
                    await sub_session.commit()
                success += 1
            except Exception as e:
                logger.error("Import failed for user %s: %s", uname, e)
                failed += 1

        async with get_session_maker()() as fin_session:
            task_repo = BatchTaskRepository(fin_session)
            t = await task_repo.get_by_id(task.id)
            if t:
                await task_repo.update(
                    t,
                    status="completed",
                    progress=100,
                    success_count=success,
                    failed_count=failed,
                    completed_at=datetime.now(timezone.utc),
                )
            await fin_session.commit()

        yield {
            "type": "summary",
            "task_id": task.id,
            "status": "completed",
            "progress": 100,
            "total": total,
            "done": total,
            "success_count": success,
            "failed_count": failed,
            "message": f"完成: 成功 {success} / 失败 {failed}",
        }

    async def list_tasks(
        self, account_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list, int]:
        return await self.task_repo.list_by_account(account_id, page, page_size)

    async def get_task(self, task_id: int):
        from app.core.exceptions import TaskNotFoundError

        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise TaskNotFoundError(task_id)
        return task

    async def export_task_result(self, account_id: int, task_id: int) -> str:
        """导出批量任务结果为 JSON 文件，返回文件路径."""
        from app.services.token_export_service import TokenExportService

        token_svc = TokenExportService(self.session)
        return await token_svc.export_account_json(account_id, task_id=task_id)
