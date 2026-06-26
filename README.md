# kiro-fleet

> 多 AWS 账号下 Kiro 账号批量开通与订阅管理平台。

## 主要功能

| 功能 | 说明 |
|------|------|
| **多账号管理** | 统一纳管多个 AWS 账号的 IAM Identity Center，加密存储访问凭证，支持连通性验证和用户/订阅定时同步 |
| **批量开通** | 按套餐数量（Power / Pro Max / Pro+ / Pro）、用户名列表或 CSV 三种方式批量创建 IC 用户并分配订阅，SSE 实时进度推送 |
| **订阅管理** | 分配、变更、取消 Kiro 订阅；支持跨账号总览和已取消订阅查询 |
| **Credit 统计** | 查看和同步各用户的 Kiro Credit 用量，支持按日期范围过滤 |
| **账户 JSON 导出** | 为每个用户动态签发 IAM Identity Center access token（通过 Trusted Token Issuer），导出 kiro-account-manager 标准 JSON，可直接用于多端登录 |
| **操作日志** | 完整记录所有 AWS 侧操作，支持按账号、操作类型、状态过滤 |
| **系统用户与 MFA** | 多管理员支持，MFA TOTP 两步登录，JWT + refresh token 轮换，登录限流 |

技术栈：Python + FastAPI + React + Ant Design，单机 docker-compose 部署，MySQL 持久化，Alembic 管理 schema 迁移。

## 与 kiro-honcho 的关系

`kiro-fleet` fork 自 [kiro-honcho](https://github.com/nwcd-samples/kiro-honcho) 并全面重构，在保留原有 Identity Center 和 Kiro 订阅核心逻辑的基础上新增了批量开通、任务历史、Credit 统计、账户 JSON 导出和完整的 Web UI，并将架构拆分为清晰的路由 / 业务 / 数据访问三层。

## 文档

| 文档 | 内容 |
|------|------|
| [docs/architecture.md](./docs/architecture.md) | 当前架构、关键决策、安全边界与功能迁移对照 |
| [docs/admin-guide.md](./docs/admin-guide.md) | 管理员部署、账号管理和日常运维手册 |
| [docs/deployment.md](./docs/deployment.md) | 部署手册：单机 Docker Compose 与 CloudFormation 一键基础设施（私有 EC2 + ALB + SSM）两种方式，含升级、备份和恢复 |
| [docs/testing.md](./docs/testing.md) | 自动化测试、构建、迁移与 AWS 验收手册 |

## 目录结构

```
app/
├── api/v1/        路由层（仅 HTTP）
├── services/      业务层（全部逻辑）
├── repositories/  数据访问层
├── aws/           唯一一份 AWS 客户端（异步）
├── workers/       后台任务
├── models/        ORM    schemas/  DTO
└── core/          config / security / db
tests/             pytest
deploy/            docker-compose / Dockerfile / nginx
infra/             CloudFormation 模板 / 应用 IAM 策略
frontend/          React + Vite
```

## 本地启动

1. 复制 `.env.example` 为 `.env`，设置随机的 `SECRET_KEY`、`ENCRYPTION_KEY` 和初始管理员密码。
2. 如需导出含可用 token 的账户 JSON，还需按[架构文档的 access token 决策](./docs/architecture.md#账户-json-与-access-token)在 IAM Identity Center 配置 Trusted Token Issuer，并在 `.env` 填入 `SSO_OIDC_CLIENT_ID`、`SSO_OIDC_PRIVATE_KEY_B64`、`SSO_OIDC_ISSUER_URL`、`SSO_OIDC_AUDIENCE`、`SSO_OIDC_KEY_ID`，详细配置步骤见[部署手册](./docs/deployment.md#aws-接入与导出配置)。
3. 运行 `docker compose --env-file .env -f deploy/docker-compose.yml up --build`，浏览器访问 `http://localhost`。

Compose 默认启动本地 MySQL；生产容器启动时会自动执行 `alembic upgrade head`。开发环境可显式设置 `DB_TYPE=sqlite` 使用轻量数据库。

## 免责声明

本项目仅供学习与技术参考，不构成生产部署方案。运行过程中会调用 AWS IAM Identity Center 和 Kiro 相关 API 并可能产生费用，请根据实际使用量评估成本。导出的账户 JSON 包含用户访问凭证，属于敏感数据，请妥善保管，切勿上传至不受控位置。作者不对因使用本项目产生的任何费用、数据泄露或其他损失承担责任。本项目与 Amazon Web Services 无官方关联，相关服务的可用性与定价以 AWS 官方文档为准。生产环境使用前请根据实际需求进行安全评估与调整。

## License

[MIT](./LICENSE)
