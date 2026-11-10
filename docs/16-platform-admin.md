# A 端平台管理与账号分离

## 1. 两套账号

| 账号类型 | 存储 | 登录入口 | Token scope |
| --- | --- | --- | --- |
| 平台管理员 | `platform_admins` | `/platform` | `platform` |
| 租户用户 | `tenant_users` | B 端 `/` | `tenant` |

平台管理员不属于任何租户，租户用户必须绑定 `tenant_id`。

## 2. 默认账号

开发环境首次启动会自动创建：

```text
平台管理员：admin@local / admin
Demo 租户：demo@local / demo
```

生产环境必须通过环境变量修改：

```text
AUTOCUT_AUTH_SECRET=
AUTOCUT_PLATFORM_ADMIN_EMAIL=
AUTOCUT_PLATFORM_ADMIN_PASSWORD=
AUTOCUT_SEED_DEMO_TENANT=false
```

## 3. A 端能力

页面：`/platform`

- 平台管理员登录
- 查看租户数、活跃租户、用户数、任务数、质量评分
- 开通租户，同时创建租户 owner 账号
- 修改套餐、状态
- 查看每个租户的席位、渲染分钟、存储、并发
- 查看每个租户的项目、素材、任务用量

套餐：

| 套餐 | 渲染分钟 | 存储 | 席位 | 并发 |
| --- | --- | --- | --- | --- |
| trial | 30 | 5GB | 3 | 1 |
| basic | 300 | 50GB | 10 | 2 |
| pro | 1200 | 200GB | 30 | 5 |

## 4. 接口

```text
POST  /api/v1/platform/auth/login
GET   /api/v1/platform/plans
GET   /api/v1/platform/overview
GET   /api/v1/platform/tenants
POST  /api/v1/platform/tenants
PATCH /api/v1/platform/tenants/{id}
GET   /api/v1/platform/tenants/{id}/users
```

平台接口必须携带 `scope=platform` 的 Token。租户 Token 访问会返回 403。

## 5. Token

当前使用 HMAC-SHA256 签名的轻量 Token，不依赖 JWT 库。

```json
{
  "scope": "tenant",
  "tenant_id": "demo",
  "sub": "user-id",
  "role": "owner",
  "exp": 1760000000
}
```

生产环境建议换成成熟 JWT 库，并加刷新令牌、撤销列表和密钥轮换。

## 6. 当前边界

账号分离、租户开通、套餐和额度配置已经可用。

**尚未完成**：B 端业务接口还没有把 Token 里的 `tenant_id` 注入到所有仓储查询，当前工作台仍以 `demo` 租户运行。下一步需要：

1. 在依赖层解析 Token，得到 `tenant_id`
2. 所有业务查询强制带 `tenant_id`
3. 增加跨租户越权测试
4. 迁移 PostgreSQL 后加 RLS 兜底

在这些完成之前，不要把系统放到公网多租户环境。
