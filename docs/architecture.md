# Kiro Fleet 架构与关键决策

## 定位与迁移边界

Kiro Fleet 是单机部署的 AWS IAM Identity Center 与 Kiro 订阅管控平台，负责多 AWS 账号、Identity Center 用户、订阅、批量开通、Credit 和账户 JSON 导出。

它是 `kiro-honcho` 的重构继任项目，而不是并行维护的第二个产品。旧仓只用于历史行为对照、迁移验收和紧急回溯；新功能、修复和部署都在本仓完成。

重构保留 honcho 已验证的 Identity Center、Kiro 订阅和同步逻辑，同时解决重复 AWS 客户端、同步 I/O、路由承载业务逻辑、配置重复和缺少测试/迁移的问题。

## 系统组件

```text
Browser
  │ HTTP（HTTPS 由部署边界之外处理）
  ▼
Nginx frontend
  ├─ React/Vite 静态资源
  └─ /api → FastAPI backend
                 ├─ API / 认证、权限、SSE
                 ├─ services / 业务编排
                 ├─ repositories / 数据访问
                 ├─ aws / 异步 AWS 集成
                 ├─ workers / 同步与重试
                 └─ MySQL（默认）
```

Compose 包含 frontend、backend 和本地 MySQL 8.4。backend 启动时执行 `alembic upgrade head`、确保初始管理员存在、启动调度器，再提供 API。

## 后端边界

| 层 | 目录 | 责任 |
|---|---|---|
| HTTP | `app/api/v1` | 参数校验、认证依赖、调用 service、HTTP/SSE 响应 |
| 业务 | `app/services` | 账号、用户、订阅、开通、导出、同步、Credit 编排 |
| 数据/集成 | `app/repositories`、`app/aws` | SQLAlchemy 查询；唯一 AWS 客户端和服务封装 |
| 基础设施 | `app/core`、`app/workers` | 配置、加密、数据库、异常、日志、限流、调度 |
| 模型 | `app/models`、`app/schemas` | ORM 持久化模型和 API DTO |

Service 抛出领域异常，`app/main.py` 统一生成标准错误体。AWS 凭证只在调用时解密；同步 boto3 调用被包装为线程任务，SigV4 HTTP 请求使用 `httpx.AsyncClient`。

## 代码结构

```text
kiro-fleet/
├── app/
│   ├── main.py                 # FastAPI 入口、生命周期、异常处理、健康/指标
│   ├── cli.py                  # Typer 运维 CLI，复用 service 层
│   ├── api/
│   │   ├── deps.py             # session、当前用户、管理员依赖
│   │   └── v1/                 # auth、accounts、users、subscriptions 等 HTTP 路由
│   ├── services/               # 业务编排与事务边界
│   ├── repositories/           # SQLAlchemy 查询与写入封装
│   ├── aws/                    # AsyncAWSClient、Identity Center、Kiro API
│   ├── workers/                # APScheduler、同步、订阅重试任务
│   ├── models/                 # SQLAlchemy ORM：账号、用户、订阅、日志、任务
│   ├── schemas/                # Pydantic 请求/响应 DTO
│   └── core/                   # config、db、security、exceptions、logging、metrics、限流
├── alembic/                    # schema 迁移环境与版本文件
├── frontend/                   # React + Vite + Ant Design 管理界面
│   └── src/
│       ├── pages/              # Login、Dashboard、Accounts、Provisioning 等页面
│       ├── components/         # Layout、鉴权路由等公共 UI
│       ├── services/           # Axios API 调用封装
│       └── stores/             # Zustand 认证和界面状态
├── deploy/                     # Compose、Dockerfile、Nginx 配置
├── scripts/                    # 备份等可执行运维脚本
├── infra/iam/                  # AWS 最小权限策略模板
├── tests/                      # pytest 异步集成/服务测试
└── docs/                       # 架构、部署、管理员、测试手册
```

### 依赖方向

依赖只能自上而下：`api → services → repositories/aws → models/core`。`workers` 与 `cli` 是入口适配层，调用 service，不复制业务逻辑。

| 要修改的能力 | 首选位置 | 说明 |
|---|---|---|
| 新增 HTTP endpoint | `app/api/v1/<domain>.py` | 只处理协议、依赖与响应，不直连 AWS |
| 新增业务规则 | `app/services/<domain>_service.py` | 编排仓储、AWS 调用、日志和领域异常 |
| 新增数据库查询 | `app/repositories/<domain>_repo.py` | 避免在 service 或 route 中拼 SQLAlchemy 查询 |
| 新增 AWS API | `app/aws/identity_center.py` 或 `app/aws/kiro.py` | 复用 `AsyncAWSClient`，不得另建 SDK 客户端 |
| 新增表或字段 | `app/models/` + Alembic migration | 同时更新 schema、repository 和测试 |
| 新增后台周期任务 | `app/workers/tasks.py` + `scheduler.py` | 参数传标量 ID，在任务内创建独立 session |
| 新增前端页面 | `frontend/src/pages/` | API 调用置于 `services/`，全局状态置于 `stores/` |

### 典型请求链路

```text
POST /api/v1/accounts/{id}/provisioning
  → api/v1/provisioning.py       参数验证、管理员鉴权、SSE 响应
  → ProvisioningService          用户名生成、任务编排、失败处理
  → UserService / SubscriptionService
  → IdentityCenterClient / KiroSubscriptionClient
  → repositories + MySQL         保存用户、订阅、任务和操作日志
```

该分层的目标是让 AWS 集成可 mock、业务逻辑可独立测试、CLI/HTTP/后台任务复用同一套 service。

## 关键决策

### 认证与安全

- JWT access token + 数据库存储并轮换的 refresh token。
- MFA 登录必须携带 5 分钟有效的 `mfa_challenge` pre-auth token；禁用 MFA 必须验证当前 TOTP。
- 禁止删除最后一个管理员；refresh 时核验用户是否存在、启用且 token 未吊销。
- AWS 访问密钥以 AES-256-GCM 加密存储；配置拒绝占位密钥、生产默认管理员密码和通配 CORS。
- 登录使用进程内滑动窗口限流。单机部署无需 Redis；横向扩容时应替换为共享存储。

### 账户 JSON 与 access token

导出文件写入 `data/exports/` 并由 API 下载；账号管理页面每行还提供"导出"按钮，直接触发浏览器下载，无需进入任务历史。

导出 access token 使用 IAM Identity Center Trusted Token Issuer（TTI）结合动态 JWT 签发：

1. 服务为每个用户用 RSA 私钥签发一个 RS256 JWT assertion（`sub` / `email` 设为用户邮箱，`jti` UUID 防重放，有效期 1 小时）。
2. 以账号 AWS 凭证调用 `sso-oidc:CreateTokenWithIAM`（`jwt-bearer` 授权类型），用该 assertion 换取 IAM Identity Center access token。
3. 没有邮箱地址的用户在导出时自动跳过。

目标账号必须完成：托管 JWKS 和 OIDC discovery 文档、创建 TTI、注册 IdC 应用并配置 `jwt-bearer` 授权和 IAM 认证方式、将所有用户分配到应用、授予 `sso-oauth:CreateTokenWithIAM`。配置不完整时返回 `TOKEN_EXPORT_NOT_CONFIGURED`，不会生成 token 为空的伪成功文件。

所需 `.env` 变量：`SSO_OIDC_CLIENT_ID`（应用 ARN）、`SSO_OIDC_PRIVATE_KEY_B64`（RSA 私钥 PEM base64）、`SSO_OIDC_ISSUER_URL`（TTI IssuerUrl）、`SSO_OIDC_AUDIENCE`（JWT aud，默认 `kiro-fleet`）、`SSO_OIDC_KEY_ID`（JWKS kid）。完整配置步骤见[部署手册](./deployment.md#aws-接入与导出配置)。

### 数据与部署

- 默认数据库为 Compose 内的本地 MySQL；SQLite 只用于隔离测试或轻量开发。
- schema 由 Alembic 管理；生产不依赖 ORM `create_all`。
- 批量任务写入 `batch_tasks`，订阅失败保留待重试状态，由 scheduler 处理。
- `/health` 表示进程存活，`/ready` 验证数据库，`/metrics` 输出进程级请求指标。

## 主要流程

### 登录

1. `/api/v1/auth/login` 校验密码和账号状态。
2. 未启用 MFA 时签发 access/refresh token；启用 MFA 时返回 pre-auth token。
3. `/login/mfa` 校验 TOTP 后签发正式 token。
4. `/refresh` 查验 JWT、数据库 token 和用户状态，吊销旧 token 后重新签发。

### 批量开通与同步

`ProvisioningService` 生成不冲突用户名，创建 Identity Center 用户，分配订阅并输出 SSE 进度。任务状态、成功/失败数量写入数据库；订阅失败由 scheduler 重试。调度器按配置同步用户、订阅和 Credit 用量，操作日志保留审计记录。

## 功能覆盖

| honcho 能力 | Fleet 状态 |
|---|---|
| 登录、MFA、refresh、系统用户管理 | 保留并加固 |
| AWS 账号 CRUD、验证、同步、仪表盘 | 保留 |
| Identity Center 用户、用户组、密码/邮箱操作 | 保留；修复 groups 路由遮蔽 |
| 订阅管理、批量改套餐、跨账号总览、取消查询 | 保留；启用原死代码能力 |
| 批量列表/CSV 创建用户、操作日志、定时同步 | 保留并任务化 |
| 按套餐数量一键开通、任务历史、Credit 统计、JSON 导出 | 新增 |

## 运维约束

- `.env`、导出文件、MySQL 备份均不可提交到 Git。
- 发布、备份、恢复、升级和故障排查见 [部署手册](./deployment.md)。
- 自动化测试、迁移检查和 AWS 验收见 [测试手册](./testing.md)。
- AWS 最小权限模板在 `infra/iam/kiro-fleet-policy.json`；实际权限应按目标账号进一步收紧。
