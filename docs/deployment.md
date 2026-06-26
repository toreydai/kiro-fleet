# Kiro Fleet 部署手册

本文分为两部分：先完成部署，再按需查阅运维操作。

## 第一部分：部署

最短部署路径：复制 `.env.example` 为 `.env` 并替换密钥和 MySQL 密码；执行 `docker compose --env-file .env -f deploy/docker-compose.yml up --build -d`；确认 `/ready` 返回成功后登录。

### 部署边界

本手册覆盖单机 Docker Compose 部署：Nginx 前端、FastAPI 后端和同机 MySQL 8.4。系统默认监听宿主机 80 端口，**本期不配置 HTTPS/TLS**；若部署在公网，请在受控网络或上游网关后使用，并自行完成 TLS 终止。

### 前置条件

- Linux 主机，建议至少 2 vCPU、4 GB 内存、20 GB 可用磁盘。
- Docker Engine 25+ 和 Docker Compose v2。
- 宿主机 80 端口可用。
- 可从主机访问 Docker Hub 拉取 `mysql:8.4`、`python:3.12-slim`、`node:20-alpine`、`nginx:alpine`。
- 用于管理 AWS Identity Center 的访问密钥，以及所需 IAM 权限。权限模板见 `infra/iam/kiro-fleet-policy.json`。

检查运行环境：

```bash
docker --version
docker compose version
```

### 首次配置

在仓库根目录执行：

```bash
cp .env.example .env
chmod 600 .env
```

编辑 `.env`，至少替换以下值：

| 配置 | 要求 |
|---|---|
| `SECRET_KEY` | 随机高熵字符串；用于 JWT 签名 |
| `ENCRYPTION_KEY` | 随机高熵字符串；用于加密 AWS 凭证 |
| `MYSQL_PASSWORD` | 本地 MySQL 应用用户密码 |
| `MYSQL_ROOT_PASSWORD` | 本地 MySQL root 密码 |
| `INITIAL_ADMIN_PASSWORD` | 首次管理员密码，不能保留默认值 |
| `CORS_ORIGINS` | 实际前端访问来源，逗号分隔 |

可用以下命令生成两项应用密钥：

```bash
openssl rand -hex 32
```

不要将 `.env` 提交、复制到聊天工具或上传至不受控位置。

### 启动与验收

```bash
docker compose --env-file .env -f deploy/docker-compose.yml up --build -d
```

首次启动会完成以下动作：

1. 创建 MySQL 数据卷 `mysql_data`。
2. 启动 MySQL 并等待健康检查通过。
3. 构建 backend，执行 `alembic upgrade head`。
4. 创建初始管理员（仅在数据库中不存在该用户名时）。
5. 启动调度器、backend 和 frontend。

检查状态：

```bash
docker compose --env-file .env -f deploy/docker-compose.yml ps
curl http://127.0.0.1/health
curl http://127.0.0.1/ready
curl http://127.0.0.1/metrics
```

`/health` 应返回 `ok`；`/ready` 会验证数据库连接。浏览器访问 `http://<server-host>`，使用 `.env` 的初始管理员账号登录。

### 方式二：CloudFormation 一键基础设施（AWS 私有 EC2 + ALB）

上面的方式一假设你已有一台可登录的主机。如果直接在 AWS 上从零拉起，可用 `infra/kiro-fleet.yaml` 一次性创建并部署，无需手工建网络或登录主机：

- **私有子网** EC2（`t3.medium` / 2 vCPU 4 GB，60 GB gp3，Amazon Linux 2023），无公网 IP；
- 经 **NAT Gateway** 出网（从 GitHub 拉代码、从 Docker Hub 拉镜像）；
- 仅通过 **SSM Session Manager** 登录，不开放 SSH；
- 前面挂 **公网 Application Load Balancer**，转发到实例 80 端口；
- 实例 UserData 自动安装 Docker、`git clone` 本仓库并 `docker compose up`。

部署（在已配置好凭证的本地执行）：

```bash
aws cloudformation deploy \
  --stack-name kiro-fleet \
  --template-file infra/kiro-fleet.yaml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    VpcId=<vpc-id> \
    AvailabilityZone=<az，如 us-east-1a> \
    PublicSubnetA=<该 AZ 的公有子网，放 NAT 和一个 ALB 节点> \
    PublicSubnetB=<另一 AZ 的公有子网，ALB 第二可用区>
```

完成后取访问地址与自动生成的初始管理员密码：

```bash
aws cloudformation describe-stacks --stack-name kiro-fleet \
  --query "Stacks[0].Outputs" --output table
aws ssm get-parameter --name /kiro-fleet/initial-admin-password \
  --with-decryption --query Parameter.Value --output text
```

UserData 在实例上随机生成 `SECRET_KEY`、`ENCRYPTION_KEY`、MySQL 密码和初始管理员密码（管理员密码写入 SSM Parameter Store `/kiro-fleet/initial-admin-password`，SecureString）。两处与生产配置相关的已知约束已内置处理，重建时幂等生效：

- **buildx**：Amazon Linux 2023 自带的 buildx 过旧，Compose 构建会报 `requires buildx 0.17.0 or later`；UserData 显式安装 buildx v0.19.3 的 CLI 插件。
- **CORS**：生产模式（`APP_ENV=production`）拒绝通配符 `CORS_ORIGINS=*`；UserData 启动时通过 `DescribeLoadBalancers` 发现本栈 ALB 的 DNS，并将 `CORS_ORIGINS` 设为该地址。

> 当前未配置 HTTPS/TLS，ALB 仅监听 80 端口；公网暴露场景请自行在 ALB 上挂证书并改为 443 监听。

### AWS 接入与导出配置

登录后在“账号管理”新增 AWS 账号并执行验证。每个账号需要正确填写 SSO 区域、Kiro 区域、Identity Center Instance ARN、Identity Store ID 和 AWS 访问密钥。

如需导出含可用 access token 的账户 JSON，除 AWS 访问密钥外还必须完成以下一次性配置：

**步骤 1 — 生成 RSA 密钥并托管 JWKS**

```bash
# 生成私钥（保留在服务器，写入 .env）
openssl genrsa -out tti-private.pem 2048

# 提取公钥（发布到公网）
openssl rsa -in tti-private.pem -pubout -out tti-public.pem

# 将私钥 base64 编码，用于 SSO_OIDC_PRIVATE_KEY_B64
base64 -w 0 tti-private.pem
```

将以下两个文件上传到公网可访问的 HTTPS 路径（如 S3 公共存储桶）：

- `<bucket>/jwks.json` — 包含公钥的 JWKS 文档
- `<bucket>/.well-known/openid-configuration` — 内容：`{"jwks_uri": "<bucket-url>/jwks.json"}`

**步骤 2 — 创建 Trusted Token Issuer**

```bash
aws sso-admin create-trusted-token-issuer \
  --instance-arn <IdC-instance-arn> \
  --name kiro-fleet-tti \
  --trusted-token-issuer-type OIDC_JWT \
  --trusted-token-issuer-configuration \
    "OidcJwtConfiguration={IssuerUrl=<存储桶基础域名>,ClaimAttributePath=email,IdentityStoreAttributePath=emails.value,JwksRetrievalOption=OPEN_ID_DISCOVERY}" \
  --region <IdC-region>
```

**步骤 3 — 注册 IdC 应用并配置授权**

```bash
# 创建 IdC 应用
aws sso-admin create-application \
  --instance-arn <IdC-instance-arn> \
  --name kiro-fleet-app \
  --application-provider-arn arn:aws:sso::aws:applicationProvider/custom \
  --region <IdC-region>

# 配置 jwt-bearer 授权
aws sso-admin put-application-grant \
  --application-arn <app-arn> \
  --grant-type urn:ietf:params:oauth:grant-type:jwt-bearer \
  --grant '{"JwtBearer":{"AuthorizedTokenIssuers":[{"TrustedTokenIssuerArn":"<tti-arn>","AuthorizedAudiences":["kiro-fleet"]}]}}' \
  --region <IdC-region>

# 配置 IAM 认证方式（需使用 --cli-input-json 文件）
cat > /tmp/auth-method.json <<'EOF'
{
  "ApplicationArn": "<app-arn>",
  "AuthenticationMethodType": "IAM",
  "AuthenticationMethod": {"Iam": {"ActorPolicy": {"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"AWS":"<访问密钥所在 IAM 用户/角色 ARN>"},"Action":"sso-oauth:CreateTokenWithIAM","Resource":"*"}]}}}
}
EOF
aws sso-admin put-application-authentication-method \
  --cli-input-json file:///tmp/auth-method.json \
  --region <IdC-region>
```

将所有 Identity Center 用户分配到该应用（每个用户均需分配，否则 `CreateTokenWithIAM` 会失败）。

**步骤 4 — 配置 `.env`**

| 变量 | 说明 |
|---|---|
| `SSO_OIDC_CLIENT_ID` | IdC 应用 ARN |
| `SSO_OIDC_PRIVATE_KEY_B64` | RSA 私钥 PEM 的 base64（步骤 1 生成）|
| `SSO_OIDC_ISSUER_URL` | 与 TTI IssuerUrl 完全一致的存储桶基础域名 |
| `SSO_OIDC_AUDIENCE` | JWT aud 声明，默认 `kiro-fleet` |
| `SSO_OIDC_KEY_ID` | JWKS 中对应公钥的 `kid` 字段 |

未完成以上步骤时，导出会返回 `TOKEN_EXPORT_NOT_CONFIGURED`，这是安全保护，不应绕过。

## 第二部分：运维

### 日常操作

查看日志：

```bash
docker compose --env-file .env -f deploy/docker-compose.yml logs -f backend
docker compose --env-file .env -f deploy/docker-compose.yml logs -f mysql
```

停止服务：

```bash
docker compose --env-file .env -f deploy/docker-compose.yml down
```

该命令不会删除 MySQL 数据卷。只有明确要清空全部本地数据时才执行：

```bash
docker compose --env-file .env -f deploy/docker-compose.yml down -v
```

### 备份与恢复

创建逻辑备份：

```bash
./scripts/backup-mysql.sh
```

备份默认写入 `backups/kiro-fleet-<UTC 时间>.sql.gz`，目录被 Git 忽略。建议每天备份并将加密后的副本放到受控存储。

恢复流程：

1. 停止 frontend 和 backend，保留 mysql：

   ```bash
   docker compose --env-file .env -f deploy/docker-compose.yml stop frontend backend
   ```

2. 导入备份。命令会读取 MySQL 容器环境变量，不需要将密码写入命令历史：

   ```bash
   gzip -dc backups/kiro-fleet-<UTC 时间>.sql.gz | \
   docker compose --env-file .env -f deploy/docker-compose.yml exec -T mysql sh -c \
   'exec mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"'
   ```

3. 启动服务并检查 `/ready`：

   ```bash
   docker compose --env-file .env -f deploy/docker-compose.yml up -d
   ```

### 版本升级与回滚

升级前必须先备份数据库：

```bash
./scripts/backup-mysql.sh
git pull
docker compose --env-file .env -f deploy/docker-compose.yml up --build -d
docker compose --env-file .env -f deploy/docker-compose.yml ps
```

backend 会自动执行向前的 Alembic 迁移。生产升级前应先在隔离环境验证迁移与 AWS 集成。

发生应用回滚时，先切回已验证的代码/镜像版本，再重建容器。**不要自动执行数据库 downgrade**；只有确认目标版本支持当前 schema 且备份可恢复时才进行人工回滚。

### 故障排查

| 现象 | 检查方式 | 常见原因 |
|---|---|---|
| frontend 无法访问 | `docker compose ps`、检查 80 端口 | 端口占用或 frontend 未启动 |
| `/health` 正常但 `/ready` 失败 | backend 与 mysql 日志 | MySQL 未就绪、密码错误、迁移失败 |
| backend 循环重启 | `docker compose logs backend` | `.env` 密钥/数据库配置不合法 |
| 登录频繁返回 429 | 等待一分钟或检查来源 IP | 登录限流已触发 |
| 导出失败 | backend 日志与操作日志 | IdC 权限或 Trusted Token Issuer 未配置 |
| 批量任务停滞 | 任务历史、backend 日志、AWS 权限 | AWS API 失败或订阅分配被拒绝 |

### 发布验收

发布完成前确认：

- [ ] `docker compose ps` 中 mysql、backend、frontend 都为运行/健康状态。
- [ ] `/health`、`/ready`、`/metrics` 均可访问。
- [ ] 初始管理员已登录并修改密码。
- [ ] 至少一个测试 AWS 账号已验证、同步成功。
- [ ] 已执行一次数据库备份并验证可读取。
- [ ] `.env` 权限为 600，且不在 Git 状态中。
- [ ] 已明确当前部署未启用 HTTPS 的网络边界。
