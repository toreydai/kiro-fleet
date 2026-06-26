"""领域异常定义 — services 层抛出，main.py 统一转 HTTP."""

from __future__ import annotations


class KiroFleetError(Exception):
    """所有领域异常的基类."""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


# ── 认证 / 授权 ───────────────────────────────────────────────────────────


class AuthenticationError(KiroFleetError):
    code = "AUTHENTICATION_FAILED"
    status_code = 401

    def __init__(self, message: str = "用户名或密码错误"):
        super().__init__(message)


class MFAChallengeRequired(KiroFleetError):
    """第一步登录成功，需要 MFA 验证."""

    code = "MFA_CHALLENGE_REQUIRED"
    status_code = 202

    def __init__(self, pre_auth_token: str):
        super().__init__("需要 MFA 验证")
        self.pre_auth_token = pre_auth_token


class InvalidTokenError(KiroFleetError):
    code = "INVALID_TOKEN"
    status_code = 401

    def __init__(self, message: str = "令牌无效或已过期"):
        super().__init__(message)


class PermissionDeniedError(KiroFleetError):
    code = "PERMISSION_DENIED"
    status_code = 403

    def __init__(self, message: str = "权限不足"):
        super().__init__(message)


class MFACodeInvalidError(KiroFleetError):
    code = "MFA_CODE_INVALID"
    status_code = 400

    def __init__(self, message: str = "MFA 验证码无效"):
        super().__init__(message)


# ── 资源不存在 ────────────────────────────────────────────────────────────


class NotFoundError(KiroFleetError):
    code = "NOT_FOUND"
    status_code = 404

    def __init__(self, resource: str = "资源", resource_id: int | str | None = None):
        if resource_id is not None:
            msg = f"{resource} (id={resource_id}) 不存在"
        else:
            msg = f"{resource} 不存在"
        super().__init__(msg)


class AccountNotFoundError(NotFoundError):
    code = "ACCOUNT_NOT_FOUND"

    def __init__(self, account_id: int | str | None = None):
        super().__init__("账号", account_id)


class UserNotFoundError(NotFoundError):
    code = "USER_NOT_FOUND"

    def __init__(self, user_id: int | str | None = None):
        super().__init__("用户", user_id)


class SubscriptionNotFoundError(NotFoundError):
    code = "SUBSCRIPTION_NOT_FOUND"

    def __init__(self, sub_id: int | str | None = None):
        super().__init__("订阅", sub_id)


class SystemUserNotFoundError(NotFoundError):
    code = "SYSTEM_USER_NOT_FOUND"

    def __init__(self, user_id: int | str | None = None):
        super().__init__("系统用户", user_id)


# ── 业务约束 ──────────────────────────────────────────────────────────────


class ConflictError(KiroFleetError):
    code = "CONFLICT"
    status_code = 409

    def __init__(self, message: str):
        super().__init__(message)


class ValidationError(KiroFleetError):
    code = "VALIDATION_ERROR"
    status_code = 422

    def __init__(self, message: str):
        super().__init__(message)


class TokenExportConfigurationError(ValidationError):
    code = "TOKEN_EXPORT_NOT_CONFIGURED"

    def __init__(self, message: str = "未配置 IAM Identity Center Trusted Token Issuer"):
        super().__init__(message)


class AccountNotVerifiedError(KiroFleetError):
    code = "ACCOUNT_NOT_VERIFIED"
    status_code = 400

    def __init__(self, message: str = "账号凭证未验证，请先验证账号"):
        super().__init__(message)


class LastAdminError(KiroFleetError):
    code = "LAST_ADMIN"
    status_code = 400

    def __init__(self):
        super().__init__("不能删除最后一个管理员账户")


class DuplicateUsernameError(ConflictError):
    code = "DUPLICATE_USERNAME"

    def __init__(self, username: str):
        super().__init__(f"用户名 '{username}' 已存在")


class DuplicateEmailError(ConflictError):
    code = "DUPLICATE_EMAIL"

    def __init__(self, email: str):
        super().__init__(f"邮箱 '{email}' 已被注册")


# ── AWS 错误 ──────────────────────────────────────────────────────────────


class AWSOperationError(KiroFleetError):
    code = "AWS_OPERATION_ERROR"
    status_code = 502

    def __init__(self, message: str, operation: str | None = None):
        if operation:
            msg = f"AWS 操作 [{operation}] 失败: {message}"
        else:
            msg = f"AWS 操作失败: {message}"
        super().__init__(msg)
        self.operation = operation


class AWSCredentialsError(AWSOperationError):
    code = "AWS_CREDENTIALS_ERROR"
    status_code = 400

    def __init__(self, message: str = "AWS 凭证无效或权限不足"):
        super().__init__(message)


# ── 任务 ──────────────────────────────────────────────────────────────────


class TaskNotFoundError(NotFoundError):
    code = "TASK_NOT_FOUND"

    def __init__(self, task_id: int | str | None = None):
        super().__init__("批量任务", task_id)
