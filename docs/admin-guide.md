# Kiro Fleet 管理员操作手册

## 启动前准备

1. 复制 `.env.example` 为 `.env`。
2. 设置随机的 `SECRET_KEY`、`ENCRYPTION_KEY` 和 `INITIAL_ADMIN_PASSWORD`。
3. 为每个受管 AWS 账号准备具备 IAM Identity Center 用户管理及 Kiro 订阅权限的访问密钥。
4. 启动服务：

   ```bash
   docker compose -f deploy/docker-compose.yml up --build -d
   ```

5. 打开 `http://<服务器地址>`，使用 `.env` 中 `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD` 登录。未修改 `.env` 时默认为 `admin` / `Admin@12345`。

Compose 会创建名为 `mysql_data` 的本地 Docker volume；数据库不对宿主机暴露端口。仅用于配置校验时，可执行 `ENV_FILE=../.env.example docker compose -f deploy/docker-compose.yml config`。

首次登录后应立即修改管理员密码，并在“系统用户”页面按职责创建其他管理员账号。

## 配置 AWS 账号

在“账号管理”中新增账号，填写：

- 名称：用于界面识别，必须唯一。
- Access Key ID / Secret Access Key：平台会加密存储。
- SSO 区域、Kiro 区域。
- IAM Identity Center Instance ARN 和 Identity Store ID（见下方说明）。
- 可选的 Kiro 登录 URL、同步间隔、默认账号标记。

**Instance ARN 与 Identity Store ID 的区别**

这两个值都在 AWS 控制台 → IAM Identity Center → 右侧"Settings summary"面板中，但格式和用途不同：

| 字段 | AWS 控制台标签 | 格式示例 |
|---|---|---|
| Instance ARN | ARN | `arn:aws:sso:::instance/ssoins-xxxxxxxxxxxxxxxxx` |
| Identity Store ID | Identity store ID | `d-xxxxxxxxxx` |

常见错误：将 ARN 中的 `ssoins-xxxxxxxxxxxxxxxxx` 片段复制到 Identity Store ID 字段。Identity Store ID 始终以 `d-` 开头，长度为 12 个字符（`d-` 加 10 位十六进制）。

保存后点击“验证”。仅状态为 active 的账号可创建用户、订阅和批量开通。首次接入建议先执行“同步”，确认用户与订阅数量符合 AWS 控制台。

## 管理用户和订阅

### 单个用户

1. 进入“用户管理”，选择 AWS 账号。
2. 创建用户或查询同步后的用户。
3. 按需重置密码、验证邮箱、加入 Identity Center 用户组。
4. 在“订阅管理”中为用户分配、调整或取消套餐。

密码重置和邮箱验证均会触发 AWS 侧操作；执行前确认目标账号与用户。

### 批量开通

“一键开通”支持三种方式：按套餐数量生成用户、粘贴用户列表、上传 CSV。

- 按数量开通需填写每档套餐人数（Power $200/月、Pro Max $100/月、Pro+ $40/月、Pro $20/月）、邮箱域名和用户名前缀；某档留 0 则不开通。
- CSV 列名为 `user_name,email,given_name,family_name,subscription_type`。
- 页面使用 SSE 显示进度；任务完成后可在任务历史查看成功/失败数量。

出现订阅分配失败时，先确认 AWS 权限和订阅类型；用户可能已创建，避免直接重复创建。平台会按待处理状态重试订阅分配。

## 导出账户 JSON

在批量任务完成后或账号范围内点击“导出”。导出文件仅供受信任的账户管理程序使用，包含用户 Identity Center token 时等同敏感凭证。

账号管理页面每行操作栏新增"导出"按钮，点击即下载该账号的 JSON 文件，无需进入任务历史。

导出可用 token 前，必须完成以下 AWS 侧配置（详见[部署手册 TTI 配置节](./deployment.md#aws-接入与导出配置)）：

1. 生成 RSA 2048 密钥对，将公钥发布为 JWKS 并托管到公网（如 S3 公共存储桶），同时创建 `/.well-known/openid-configuration` 指向 JWKS。
2. 在 IAM Identity Center 创建 Trusted Token Issuer，IssuerUrl 设为 JWKS 宿主域名（不含 `/.well-known`），AuthorizedAudiences 包含 `kiro-fleet`。
3. 注册 IdC 应用，配置 `jwt-bearer` 授权和 IAM 认证方式，并将所有用户分配到该应用。
4. 向访问密钥授予 `sso-oauth:CreateTokenWithIAM`。
5. 在 `.env` 填写：

   | 变量 | 说明 |
   |---|---|
   | `SSO_OIDC_CLIENT_ID` | IdC 应用 ARN |
   | `SSO_OIDC_PRIVATE_KEY_B64` | RSA 私钥 PEM 文件的 base64 编码 |
   | `SSO_OIDC_ISSUER_URL` | 与 TTI IssuerUrl 完全一致的字符串 |
   | `SSO_OIDC_AUDIENCE` | JWT aud 声明，默认 `kiro-fleet` |
   | `SSO_OIDC_KEY_ID` | JWKS 中对应公钥的 `kid` 字段 |

若页面返回 `TOKEN_EXPORT_NOT_CONFIGURED`，表示以上配置未完成；不要将其视作普通导出失败后继续重试。没有邮箱地址的用户会在导出时自动跳过。

## 日常运维

- “仪表盘”查看账号、用户、订阅概览。
- “Credit 统计”查看并同步用户用量。
- “操作日志”按账号、操作和时间排查问题。
- 健康检查：访问 `/health`，期望返回 `status: ok`。
- 查看容器日志：

  ```bash
  docker compose -f deploy/docker-compose.yml logs -f backend
  ```

## 备份与恢复

本地部署默认使用 Compose 的 MySQL volume。执行备份：

```bash
./scripts/backup-mysql.sh
```

脚本在 `backups/` 生成包含 schema、数据、存储过程和事件的压缩 SQL 文件。恢复时停止 backend，使用 MySQL 客户端将备份导入目标数据库，再启动服务；应用会执行未完成的 Alembic 迁移。

不要备份或共享 `.env` 到不受控的位置。
