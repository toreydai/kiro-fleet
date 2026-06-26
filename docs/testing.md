# Kiro Fleet 测试手册

本手册分三部分：自动化测试、手工功能验收用例、AWS 集成验收。

---

## 第一部分：自动化测试

### 范围

自动化测试不访问真实 AWS，当前覆盖：

- 认证登录、错误密码、token 校验、refresh token 轮换。
- MFA 设置、启用、禁用校验。
- 管理员权限边界与最后一个管理员保护。
- AWS 账号创建 payload 契约：前端应提交的完整 payload 可通过 `AccountCreate` 校验；旧版 `account_id` / `region` payload 必须被拒绝。
- 批量用户名生成的去重规则。
- 账户 JSON 导出格式及 Trusted Token Issuer 未配置时的失败行为。

### 准备 Python 环境

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r deploy/requirements.lock
```

### 执行后端测试

```bash
PYTHONPATH=. .venv/bin/pytest -q
```

预期结果：全部通过。测试使用内存 SQLite、临时导出目录和伪造密钥；不会读取 `.env`，也不会访问 AWS。

运行单一文件：

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/test_token_export.py
```

账号添加 payload 契约回归：

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/test_accounts_api.py
```

预期：完整账号 payload 可通过 `AccountCreate` 校验，缺少 `access_key_id`、`secret_access_key`、`sso_region`、`kiro_region` 的旧 payload 被 Pydantic 拒绝。该测试用于防止前端表单字段与后端 schema 再次漂移；真实 HTTP 创建/删除仍需在部署环境执行验收。

### 前端构建检查

```bash
cd frontend
npm ci
npm run build
```

预期生成 `frontend/dist/`。该命令同时进行 TypeScript/Vite 构建检查；不代表浏览器端真实 AWS 工作流已验收。账号添加这类表单到 API 的字段契约仍需配合后端契约测试或浏览器端 E2E 测试验证。

### 迁移验证

使用临时 SQLite，不要指向真实数据库：

```bash
SECRET_KEY=test-secret ENCRYPTION_KEY=test-encryption-key \
DB_TYPE=sqlite \
SQLITE_PATH=/tmp/kiro-fleet-migration.db \
.venv/bin/alembic upgrade head
```

预期创建 `aws_accounts`、`ic_users`、`kiro_subscriptions`、`batch_tasks` 等表及 `alembic_version`。

### 容器构建检查

```bash
docker build -f deploy/Dockerfile.backend -t kiro-fleet-backend:verify .
docker build -f deploy/Dockerfile.frontend -t kiro-fleet-frontend:verify .
```

---

## 第二部分：手工功能验收

**测试环境**：`http://<服务器地址>`，账号见 `.env` 中 `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD`。

没有真实 AWS 账号时，认证、系统用户、健康检查三块可独立验收；账号验证、IC 用户、订阅、开通、Credit 等模块需要有效的 AWS 凭证。

**推荐执行顺序**：

```
TC-AUTH-01 → TC-AUTH-10      认证基本流
TC-SYS-01  → TC-SYS-07      系统用户
TC-ACC-01  → TC-ACC-05      AWS 账号（需真实凭证）
TC-USER-03 → TC-SUB-06      用户 + 订阅（依赖 active 账号）
TC-PROV-01 → TC-PROV-08     批量开通 + 导出
TC-CREDIT-04 → TC-CREDIT-01 Credit 同步后查询
TC-LOG-01  → TC-LOG-05      日志（前序操作会产生记录）
TC-HEALTH-01 → TC-SEC-05    健康检查与安全边界
```

---

### 1. 认证

#### TC-AUTH-01 正常登录

1. 打开系统登录页，输入正确用户名和密码。

**预期**：跳转到仪表盘，右上角显示当前用户名。

---

#### TC-AUTH-02 错误密码拒绝登录

1. 输入正确用户名，密码填写任意错误值。

**预期**：提示"用户名或密码错误"，停留在登录页。

---

#### TC-AUTH-03 登录限流

1. 连续用错误密码登录 11 次（超过每分钟 10 次上限）。

**预期**：第 11 次返回 429。等待约一分钟后恢复。

---

#### TC-AUTH-04 MFA 设置与启用

1. 进入"个人设置 → 安全"，点击"设置 MFA"。
2. 用 Authenticator 扫描二维码。
3. 输入当前 TOTP 验证码，点击"启用 MFA"。

**预期**：提示"MFA 已启用"。

---

#### TC-AUTH-05 启用 MFA 后两步登录

**前置**：TC-AUTH-04 已完成，已登出。

1. 输入用户名和密码，出现 TOTP 输入框。
2. 输入 Authenticator 验证码提交。

**预期**：正常进入仪表盘。

---

#### TC-AUTH-06 TOTP 错误时 MFA 登录被拒绝

**前置**：TC-AUTH-04 已完成，已登出。

1. 完成密码登录，在 TOTP 框输入错误的 6 位码。

**预期**：提示验证码错误，不签发 token。

---

#### TC-AUTH-07 禁用 MFA

**前置**：TC-AUTH-04 已完成。

1. 进入 MFA 设置，点击"禁用 MFA"，输入当前 TOTP 确认。

**预期**：提示"MFA 已禁用"，之后登录只需密码。

---

#### TC-AUTH-08 修改密码

1. 进入"修改密码"，填写旧密码和新密码，提交。

**预期**：提示"密码已修改"。旧密码登录失败，新密码登录成功。

---

#### TC-AUTH-09 Token 自动刷新

1. 保持页面活动，等待 access token 到期（默认 30 分钟），或通过开发者工具观察自动刷新请求。

**预期**：页面不需要手动重新登录。

---

#### TC-AUTH-10 退出登录

1. 点击"退出登录"。

**预期**：跳转到登录页，旧 refresh token 吊销，直接访问内部页面被重定向回登录页。

---

### 2. 系统用户管理

#### TC-SYS-01 创建普通系统用户

1. 进入"系统用户 → 新增"，填写用户名（如 `operator1`）、邮箱、密码，角色选"普通用户"。

**预期**：列表出现新用户，角色为普通用户。

---

#### TC-SYS-02 创建管理员用户

1. 同 TC-SYS-01，角色选"管理员"。

**预期**：新用户 `is_admin` 为 true。

---

#### TC-SYS-03 普通用户无法访问管理员接口

**前置**：用 `operator1` 登录。

1. 尝试访问系统用户管理页面或调用 `GET /api/v1/auth/users`。

**预期**：返回 403。

---

#### TC-SYS-04 管理员重置其他用户密码

1. 找到 `operator1`，点击"重置密码"，填写新密码。

**预期**：提示"密码已重置"，旧密码失效，新密码可用。

---

#### TC-SYS-05 更新用户信息

1. 编辑 `operator1`，修改邮箱或启用/禁用状态，保存。

**预期**：列表中字段更新。

---

#### TC-SYS-06 删除系统用户

1. 找到 `operator1`，点击"删除"，确认。

**预期**：列表中消失，该账号无法登录。

---

#### TC-SYS-07 不能删除最后一个管理员

**前置**：系统中只有 `admin` 一个管理员。

1. 尝试删除 `admin`。

**预期**：返回错误，提示不能删除唯一管理员。

---

### 3. AWS 账号管理

#### TC-ACC-01 新增 AWS 账号

1. 进入"账号管理 → 添加账号"。
2. 确认弹窗包含名称、Access Key ID、Secret Access Key、SSO 区域、Kiro 区域、SSO Instance ARN、Identity Store ID、同步间隔字段。
3. 填写有效值并提交。

**预期**：账号出现在列表，状态为 `pending`。

---

#### TC-ACC-02 验证账号

**前置**：TC-ACC-01 已完成。

1. 点击"验证"。

**预期**：凭证有效时状态变为 `active`；无效时变为 `error` 并显示原因。

---

#### TC-ACC-03 账号名称重复被拒绝

1. 再次新增与已有账号同名的账号。

**预期**：提示名称已存在。

---

#### TC-ACC-04 编辑账号

1. 修改名称或 Kiro 区域，保存。

**预期**：列表中字段更新。

---

#### TC-ACC-05 同步账号

**前置**：账号状态为 `active`。

1. 点击"同步"。

**预期**：从 AWS Identity Center 拉取最新数据，提示同步成功及更新数量。

---

#### TC-ACC-06 仪表盘统计

1. 进入仪表盘。

**预期**：显示账号、用户、订阅的汇总数据。

---

#### TC-ACC-07 删除账号

1. 点击"删除"，确认。

**预期**：账号及本地关联数据清除。

---

### 4. IC 用户管理

#### TC-USER-01 列出用户

**前置**：账号已同步。

1. 进入"用户管理"，选择账号。

**预期**：显示用户列表和分页信息。

---

#### TC-USER-02 搜索用户

1. 输入用户名或邮箱片段搜索。

**预期**：只显示匹配结果。

---

#### TC-USER-03 创建单个用户

1. 填写用户名、邮箱、名、姓，提交。

**预期**：返回新用户详情，AWS Identity Center 中可查到，操作日志新增 `create_user`。

---

#### TC-USER-04 查看用户详情

1. 点击用户名。

**预期**：显示完整信息，包含订阅状态和所属用户组。

---

#### TC-USER-05 重置用户密码

1. 点击"重置密码"。

**预期**：提示"密码重置邮件已发送"；操作日志新增 `reset_password`。

---

#### TC-USER-06 发送邮箱验证

1. 点击"发送邮箱验证"。

**预期**：提示发送成功；操作日志新增对应记录。

---

#### TC-USER-07 列出用户组

1. 进入用户组入口。

**预期**：返回账号下所有 Identity Center 用户组。

---

#### TC-USER-08 将用户添加到用户组

1. 在用户详情点击"添加到用户组"，选择目标组。

**预期**：提示成功；AWS 侧用户组成员中可查到该用户；操作日志新增记录。

---

#### TC-USER-09 删除用户

1. 点击"删除用户"，确认。

**预期**：本地记录和 AWS Identity Center 中均删除；操作日志新增 `delete_user`。

---

### 5. 订阅管理

#### TC-SUB-01 查看账号订阅列表

1. 进入"订阅管理"，选择账号。

**预期**：显示订阅列表，含用户、套餐类型、状态和时间。

---

#### TC-SUB-02 按状态过滤订阅

1. 在状态筛选器选择 `active` 或 `canceled`。

**预期**：只显示对应状态的记录。

---

#### TC-SUB-03 为用户分配订阅

1. 点击"分配订阅"，选择用户和套餐，提交。

**预期**：新订阅出现在列表；AWS 侧生效；操作日志新增 `assign_subscription`。

---

#### TC-SUB-04 变更单个订阅套餐

1. 找到目标订阅，点击"变更套餐"，选新套餐，确认。

**预期**：套餐类型更新；操作日志新增 `change_plan`。

---

#### TC-SUB-05 批量变更套餐

1. 多选若干订阅，点击"批量变更套餐"，选目标套餐。

**预期**：所选订阅全部更新；返回成功/失败数量。

---

#### TC-SUB-06 取消订阅

1. 点击"取消订阅"，确认。

**预期**：状态变为 `canceled`；AWS 侧取消；操作日志新增 `cancel_subscription`。

---

#### TC-SUB-07 跨账号订阅总览

1. 进入全局订阅页面。

**预期**：显示所有账号的订阅汇总，支持分页。

---

#### TC-SUB-08 已取消订阅查询

1. 进入"已取消订阅"，可按账号筛选。

**预期**：只显示 `canceled` 状态记录，支持分页。

---

### 6. 批量开通

#### TC-PROV-01 按套餐数量一键开通

1. 进入"一键开通"，填写账号、邮箱域名（如 `example.com`）、用户名前缀（如 `kiro`）。
2. 在 4 档套餐（Power $200/月、Pro Max $100/月、Pro+ $40/月、Pro $20/月）中填写各档人数，至少一档大于 0。
3. 点击"开始"。

**预期**：SSE 流实时显示每个用户的创建/订阅进度；全部完成后显示成功/失败数；任务历史新增记录。

---

#### TC-PROV-02 用户名冲突自动顺延

**前置**：TC-PROV-01 已创建过 `kiro001`。

1. 再次以同域名同前缀开通。

**预期**：系统自动跳过已存在的编号，从下一个可用编号继续创建。

---

#### TC-PROV-03 列表批量导入

1. 选择"列表方式"，填写若干用户数据（user_name、email、given_name、family_name、subscription_type），提交。

**预期**：SSE 流显示逐条进度；任务历史新增记录。

---

#### TC-PROV-04 CSV 文件批量导入

1. 准备 CSV（列名：`user_name,email,given_name,family_name,subscription_type`，至少 3 行），上传并提交。

**预期**：SSE 流显示逐行进度；完成后显示统计。

---

#### TC-PROV-05 CSV 格式错误处理

1. 上传列名缺失或编码异常的 CSV。

**预期**：返回明确错误提示，不生成任务记录。

---

#### TC-PROV-06 查看任务历史

1. 进入"任务历史"，选择账号。

**预期**：列出历史任务，每条含时间、操作人、成功数、失败数和状态。

---

#### TC-PROV-07 查看单条任务详情

1. 点击任意任务。

**预期**：显示每个用户的处理结果和错误信息。

---

#### TC-PROV-08 导出任务结果 JSON

1. 在任务历史找到目标任务，点击"导出 JSON"。

**预期**：浏览器下载 JSON 文件，内容符合 kiro-account-manager 格式。

---

#### TC-PROV-09 导出账号 JSON（未配置 Trusted Token Issuer）

**前置**：`.env` 未配置 `SSO_OIDC_CLIENT_ID`。

1. 在账号管理页面找到目标账号，点击操作列的"导出"按钮。

**预期**：返回 `TOKEN_EXPORT_NOT_CONFIGURED`，不下载文件。

---

#### TC-PROV-10 导出账号 JSON（已配置 Trusted Token Issuer）

**前置**：按[部署手册 TTI 配置节](./deployment.md#aws-接入与导出配置)完成以下一次性 AWS 侧配置：
- RSA 密钥对已生成，JWKS 和 OIDC discovery 文档已发布到公网（如 S3）
- TTI 已在 IAM Identity Center 创建，`IssuerUrl` 指向上述公网域名
- IdC 应用已注册，配置了 `jwt-bearer` 授权和 IAM 认证方式
- 所有 Identity Center 用户已分配到该应用
- `.env` 已填写 `SSO_OIDC_CLIENT_ID`、`SSO_OIDC_PRIVATE_KEY_B64`、`SSO_OIDC_ISSUER_URL`、`SSO_OIDC_AUDIENCE`、`SSO_OIDC_KEY_ID`

1. 在账号管理页面找到目标账号，点击操作列的"导出"按钮。

**预期**：浏览器下载 JSON 文件，每个用户条目包含有效的 IdC access token，可被 kiro-account-manager 直接使用。没有邮箱的用户自动跳过，不影响其他用户导出。

---

### 7. Credit 用量

#### TC-CREDIT-01 查看账号 Credit 列表

1. 进入"Credit 统计"，选择账号。

**预期**：显示按日期的用量记录，含 total_credits 和 feature_breakdown。

---

#### TC-CREDIT-02 按日期范围过滤

1. 填写开始/结束日期（`YYYY-MM-DD`），筛选。

**预期**：只显示该范围内的记录。

---

#### TC-CREDIT-03 查看单个用户 Credit

1. 进入用户详情，查看 Credit 标签。

**预期**：显示该用户历史用量，支持日期过滤。

---

#### TC-CREDIT-04 手动同步 Credit

1. 点击"同步"。

**预期**：从 AWS 拉取最新用量，显示更新条数。

---

### 8. 操作日志

#### TC-LOG-01 查看全部日志

1. 进入"操作日志"。

**预期**：按时间倒序显示所有记录，每条含账号、操作类型、目标、状态、操作人和时间。

---

#### TC-LOG-02 按账号过滤

1. 在账号筛选器选择特定账号。

**预期**：只显示该账号的操作记录。

---

#### TC-LOG-03 按操作类型过滤

1. 输入操作类型如 `create_user` 或 `sync`。

**预期**：只显示对应类型。

---

#### TC-LOG-04 按状态过滤

1. 选择 `success` 或 `failed`。

**预期**：只显示对应状态。

---

#### TC-LOG-05 查看单条日志详情

1. 点击任意一条日志。

**预期**：显示完整信息，包括 details 字段（操作参数或错误详情）。

---

### 9. 健康检查与安全边界

#### TC-HEALTH-01 /health

```bash
curl http://<服务器地址>/health
```

**预期**：`{"status":"ok","service":"kiro-fleet"}`，HTTP 200。

---

#### TC-HEALTH-02 /ready

```bash
curl http://<服务器地址>/ready
```

**预期**：`{"status":"ready","service":"kiro-fleet"}`，HTTP 200，表示数据库连接正常。

---

#### TC-HEALTH-03 /metrics

```bash
curl http://<服务器地址>/metrics
```

**预期**：返回进程级请求指标，HTTP 200。

---

#### TC-SEC-01 未登录访问受保护接口

1. 清除 Token，直接访问 `/api/v1/accounts`。

**预期**：返回 401，页面重定向到登录页。

---

#### TC-SEC-02 普通用户无法执行管理员操作

**前置**：用普通用户登录。

1. 尝试新增 AWS 账号、删除用户、执行批量开通。

**预期**：均返回 403。

---

#### TC-SEC-03 禁用账号无法登录

**前置**：某用户已被禁用。

1. 用该账号登录。

**预期**：提示账号已禁用。

---

#### TC-SEC-04 .env 未提交到 Git

```bash
git status
```

**预期**：`.env` 不出现在输出中。

---

#### TC-SEC-05 MySQL 不暴露端口

```bash
docker ps | grep mysql
```

**预期**：PORTS 列只显示内部端口（`3306/tcp`），没有 `0.0.0.0:3306`。

---

## 第三部分：AWS 集成验收清单

在专用测试 AWS 账号（非生产）中逐项确认：

1. 用权限最小化的测试凭证验证账号；验证失败时不保留 `active` 状态。
2. 创建一个测试 Identity Center 用户，检查本地记录和 AWS 控制台一致。
3. 分配、调整、取消一个测试订阅，检查操作日志和同步结果。
4. 执行一个小批量任务，确认 SSE 进度、任务历史和失败重试正常。
5. 按[部署手册 TTI 配置节](./deployment.md#aws-接入与导出配置)完成 TTI 一次性配置，在账号管理页面点击"导出"，检查 JSON 文件中 access token 不为空、过期时间合理，下游账户管理程序可读取。
6. 删除测试用户和订阅，确认日志保留、数据库无悬挂任务。
