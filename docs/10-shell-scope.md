# 空壳范围与填充顺序

## 1. 现在能用的

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| 健康检查 | 可用 | `GET /health` |
| 能力清单 | 可用 | `GET /api/v1/meta`，标注每个模块是 shell 还是 ready |
| 工作流列表 | 可用 | 读取现有 `subtitle`、`clip` 两个 YAML |
| 任务上传 | 可用 | `POST /api/v1/jobs`，multipart 上传 |
| 任务查询 | 可用 | 列表、详情、事件、取消、重试 |
| 产物下载 | 可用 | 带路径穿越保护 |
| 意图路由 | 可用 | 关键词规则，不依赖模型 |
| 提示词技能 | 可用 | 无模型时返回模板，有模型时调网关 |
| 模型目录 | 可用 | 只读，列出国内厂商和能力 |
| 登录 | 演示 | demo 模式任意账号可登录 |
| 计费 | 演示 | 返回固定的试用套餐和用量 |
| 知识库 | 演示 | 内存列表，检索返回空 |
| 视频/字幕技能 | 空壳 | 返回 501 |
| 工作流画布 | 未开始 | 前端第二期 |

## 2. API 一览

```text
GET  /health
GET  /api/v1/meta
GET  /api/v1/workflows
GET  /api/v1/workflows/{name}

POST /api/v1/jobs
GET  /api/v1/jobs
GET  /api/v1/jobs/{id}
POST /api/v1/jobs/{id}/cancel
POST /api/v1/jobs/{id}/retry
GET  /api/v1/jobs/{id}/artifacts
GET  /api/v1/jobs/{id}/files/{path}

POST /api/v1/auth/login
POST /api/v1/auth/register
POST /api/v1/auth/logout
GET  /api/v1/auth/me

POST /api/v1/chat
GET  /api/v1/conversations
POST /api/v1/skills/prompt
POST /api/v1/skills/video
POST /api/v1/skills/subtitle

GET  /api/v1/knowledge-bases
POST /api/v1/knowledge-bases
POST /api/v1/knowledge-bases/{id}/search

GET  /api/v1/billing/plan
GET  /api/v1/billing/usage
POST /api/v1/billing/redeem

GET  /api/v1/settings/models
PUT  /api/v1/settings/models
```

## 3. 代码位置

```text
backend/app/
  api/routers/        HTTP 路由，按模块拆分
  agents/             意图识别、计划生成
  gateway/            能力协议、模型适配器、模型目录
  rag/                检索协议与空实现
  skills/             提示词、视频技能
  domain.py           任务模型
  storage.py          SQLite 任务存储
  service.py          任务服务
  worker.py           后台 worker
  core/workflow/      执行引擎与 DSL
```

## 4. 填充顺序

| 顺序 | 模块 | 工作 |
| --- | --- | --- |
| 1 | 运行环境 | 装 Python 3.12、FFmpeg，跑通 pytest |
| 2 | 任务闭环 | worker 真正消费任务，跑通 subtitle 工作流 |
| 3 | 提示词技能 | 接 DeepSeek，替换模板回退 |
| 4 | 登录 | JWT、密码哈希、用户表 |
| 5 | 知识库 | 上传、切分、Embedding、pgvector、检索 |
| 6 | 主控 Agent | 用模型做意图识别和槽位抽取 |
| 7 | 视频技能 | 接 clip 工作流和 Seedance |
| 8 | 订阅 | 套餐、配额、兑换码、用量扣减 |
| 9 | 前端 | 登录、工作台、任务、知识库、设置 |
| 10 | 画布 | React Flow 编排 |

## 5. 空壳的边界

空壳只保证：

- 接口存在、返回结构稳定
- 页面能点、能看

空壳不保证：

- 真实鉴权
- 真实计费
- 真实检索
- 真实视频生成

这些都要在对应阶段替换实现，接口保持不变。
