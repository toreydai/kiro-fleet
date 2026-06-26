"""批量开通路由（含 SSE 流式进度）."""

from __future__ import annotations

import json
import os

from fastapi import APIRouter, BackgroundTasks, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.schemas.provisioning import (
    BatchImportRequest,
    BatchTaskResponse,
    QuickProvisionRequest,
)
from app.services.provisioning_service import ProvisioningService

router = APIRouter(tags=["批量开通"])


@router.post("/accounts/{account_id}/provisioning")
async def quick_provision(
    account_id: int,
    body: QuickProvisionRequest,
    admin: AdminUser,
    session: SessionDep,
):
    """一键按套餐数量批量开通，SSE 流式进度."""
    svc = ProvisioningService(session)
    plans = [p.model_dump() for p in body.plans]
    gen = await svc.quick_provision(
        account_id=account_id,
        plans=plans,
        domain=body.domain,
        prefix=body.prefix,
        group_id=body.group_id,
        operator=admin.username,
    )

    async def event_stream():
        async for event in gen:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/accounts/{account_id}/provisioning/import")
async def batch_import(
    account_id: int,
    body: BatchImportRequest,
    admin: AdminUser,
    session: SessionDep,
):
    """列表批量导入用户，SSE 流式进度."""
    svc = ProvisioningService(session)
    users_data = [u.model_dump() for u in body.users]
    gen = await svc.batch_import(
        account_id=account_id,
        users_data=users_data,
        default_sub_type=body.default_subscription_type,
        operator=admin.username,
    )

    async def event_stream():
        async for event in gen:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/accounts/{account_id}/provisioning/csv")
async def batch_import_csv(
    account_id: int,
    file: UploadFile,
    admin: AdminUser,
    session: SessionDep,
    subscription_type: str | None = None,
):
    """CSV 批量导入用户，SSE 流式进度。CSV 列：user_name,email,given_name,family_name,subscription_type."""
    import csv
    import io

    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    users_data = []
    for row in reader:
        users_data.append(
            {
                "user_name": row.get("user_name", "").strip(),
                "email": row.get("email", "").strip(),
                "given_name": row.get("given_name", "").strip() or None,
                "family_name": row.get("family_name", "").strip() or None,
                "subscription_type": row.get("subscription_type", "").strip() or None,
            }
        )

    svc = ProvisioningService(session)
    gen = await svc.batch_import(
        account_id=account_id,
        users_data=users_data,
        default_sub_type=subscription_type,
        operator=admin.username,
    )

    async def event_stream():
        async for event in gen:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/accounts/{account_id}/provisioning/tasks", response_model=dict)
async def list_tasks(
    account_id: int,
    current_user: CurrentUser,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    svc = ProvisioningService(session)
    items, total = await svc.list_tasks(account_id, page, page_size)
    return {
        "items": [BatchTaskResponse.model_validate(t) for t in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/provisioning/tasks/{task_id}", response_model=BatchTaskResponse)
async def get_task(task_id: int, admin: AdminUser, session: SessionDep):
    svc = ProvisioningService(session)
    return await svc.get_task(task_id)


@router.post("/accounts/{account_id}/provisioning/tasks/{task_id}/export")
async def export_task(
    account_id: int,
    task_id: int,
    admin: AdminUser,
    session: SessionDep,
    background_tasks: BackgroundTasks,
):
    """导出批量任务结果为 kiro-account-manager JSON 文件."""
    svc = ProvisioningService(session)
    file_path = await svc.export_task_result(account_id, task_id)
    file_name = os.path.basename(file_path)
    background_tasks.add_task(os.unlink, file_path)
    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type="application/json",
    )


@router.post("/accounts/{account_id}/export")
async def export_account(
    account_id: int,
    admin: AdminUser,
    session: SessionDep,
    background_tasks: BackgroundTasks,
):
    """导出整个账号的用户 JSON."""
    from app.services.token_export_service import TokenExportService

    svc = TokenExportService(session)
    file_path = await svc.export_account_json(account_id)
    file_name = os.path.basename(file_path)
    background_tasks.add_task(os.unlink, file_path)
    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type="application/json",
    )
