"""Typer CLI — 复用 services 层，替代原 kiro_cli/."""

from __future__ import annotations

import asyncio
import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Kiro Fleet CLI — AWS Identity Center & Kiro 订阅管理")
console = Console()


def _run(coro):
    """运行异步函数的辅助封装."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _get_session():
    """获取同步上下文中可用的 session（用于 CLI 命令）."""
    from app.core.db import get_session_maker

    return get_session_maker()()


# ── 账号命令 ──────────────────────────────────────────────────────────────

account_app = typer.Typer(help="账号管理")
app.add_typer(account_app, name="account")


@account_app.command("list")
def list_accounts():
    """列出所有 AWS 账号."""

    async def _():
        async with _get_session() as session:
            from app.services.account_service import AccountService

            svc = AccountService(session)
            accounts = await svc.list_accounts()
            table = Table(title="AWS 账号列表")
            table.add_column("ID", style="cyan")
            table.add_column("名称")
            table.add_column("SSO Region")
            table.add_column("状态")
            table.add_column("默认")
            for acc in accounts:
                table.add_row(
                    str(acc.id),
                    acc.name,
                    acc.sso_region,
                    acc.status,
                    "✓" if acc.is_default else "",
                )
            console.print(table)

    _run(_())


@account_app.command("verify")
def verify_account(account_id: int = typer.Argument(..., help="账号 ID")):
    """验证账号 AWS 凭证."""

    async def _():
        async with _get_session() as session:
            from app.services.account_service import AccountService

            svc = AccountService(session)
            account = await svc.verify_account(account_id)
            console.print(f"[green]验证成功[/green]: {account.name} (状态: {account.status})")

    _run(_())


# ── 用户命令 ──────────────────────────────────────────────────────────────

user_app = typer.Typer(help="IC 用户管理")
app.add_typer(user_app, name="user")


@user_app.command("list")
def list_users(
    account_id: int = typer.Argument(..., help="账号 ID"),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="搜索用户名/邮箱"),
):
    """列出账号下的 IC 用户."""

    async def _():
        async with _get_session() as session:
            from app.services.user_service import UserService

            svc = UserService(session)
            users, total = await svc.list_users(account_id, page=1, page_size=100, search=search)
            table = Table(title=f"IC 用户 (账号 {account_id}，共 {total} 人)")
            table.add_column("ID")
            table.add_column("用户名")
            table.add_column("邮箱")
            table.add_column("状态")
            table.add_column("邮箱已验证")
            for u in users:
                table.add_row(
                    str(u.id),
                    u.user_name,
                    u.email or "",
                    u.status,
                    "✓" if u.email_verified else "✗",
                )
            console.print(table)

    _run(_())


# ── 同步命令 ──────────────────────────────────────────────────────────────

sync_app = typer.Typer(help="数据同步")
app.add_typer(sync_app, name="sync")


@sync_app.command("all")
def sync_all():
    """同步所有 active 账号的 IC 用户和订阅."""

    async def _():
        async with _get_session() as session:
            from app.services.sync_service import SyncService

            svc = SyncService(session)
            results = await svc.sync_all_accounts()
            console.print_json(json.dumps(results, default=str))

    _run(_())


@sync_app.command("account")
def sync_account(account_id: int = typer.Argument(..., help="账号 ID")):
    """同步指定账号."""

    async def _():
        async with _get_session() as session:
            from app.services.sync_service import SyncService

            svc = SyncService(session)
            result = await svc.sync_account(account_id)
            console.print_json(json.dumps(result, default=str))

    _run(_())


# ── 导出命令 ──────────────────────────────────────────────────────────────

export_app = typer.Typer(help="JSON 导出")
app.add_typer(export_app, name="export")


@export_app.command("account")
def export_account(
    account_id: int = typer.Argument(..., help="账号 ID"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="输出文件路径"),
):
    """导出账号用户为 kiro-account-manager JSON."""

    async def _():
        async with _get_session() as session:
            from app.services.token_export_service import TokenExportService

            svc = TokenExportService(session)
            file_path = await svc.export_account_json(account_id)
            if output:
                import shutil

                shutil.copy(file_path, output)
                console.print(f"[green]导出完成[/green]: {output}")
            else:
                console.print(f"[green]导出完成[/green]: {file_path}")

    _run(_())


# ── 管理员命令 ───────────────────────────────────────────────────────────

admin_app = typer.Typer(help="系统管理")
app.add_typer(admin_app, name="admin")


@admin_app.command("create-user")
def create_admin_user(
    username: str = typer.Option(..., prompt=True),
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True),
    is_admin: bool = typer.Option(False, "--admin"),
):
    """创建系统用户."""

    async def _():
        async with _get_session() as session:
            from app.services.auth_service import AuthService

            svc = AuthService(session)
            user = await svc.create_system_user(username, email, password, is_admin)
            console.print(f"[green]用户已创建[/green]: {user.username} (id={user.id})")

    _run(_())


if __name__ == "__main__":
    app()
