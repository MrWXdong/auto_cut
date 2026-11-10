# 模块清单与实现状态

## 0. 主流程

AutoCut 的主产品是一条全自动剪辑工作流：

```text
上传素材 -> 内容理解 -> 自动选段 -> 剪辑 -> 字幕/BGM/封面包装 -> 审核 -> 多平台导出
```

「一键成片」是唯一主入口。项目、文案、素材、生图、分镜、音频、渲染、矩阵都是这条流程上的能力组件，不是并列产品。

当前主入口会根据能力自动选择：

- AI 能力就绪：`clip` 工作流，ASR + LLM 选段 + 裁剪 + 导出
- AI 能力未就绪：`quick_cut` 工作流，按时长等分切片 + 裁剪 + 导出

## 1. 总览

| 模块 | 页面 | 后端 | 当前能力 | 外部依赖 |
| --- | --- | --- | --- | --- |
| 账号工作台 | 工作台 | 可用 | 登录、项目、画幅、额度 | 无 |
| AI 文案脚本 | 文案 | 可用 | 脚本 CRUD、模板/模型生成、知识库上下文 | LLM Key |
| 生图中台 | 生图 | 空壳 | 任务入口、6 种模式 | 云端图像 API |
| LoRA 训练 | LoRA | 空壳 | 训练任务入口、图集走素材库 | GPU 训练服务 |
| 素材资产 | 素材 | 可用 | 上传、列表、下载、删除 | 对象存储（后续） |
| 分镜编排 | 分镜 | 空壳 | 自动/手动任务入口 | LLM + 图像 API |
| 音频字幕 | 音频 | 空壳 | ASR/TTS/BGM/降噪任务入口 | 云端语音 API |
| 渲染导出 | 渲染 | 空壳 | 渲染任务入口 | FFmpeg |
| 矩阵批量 | 矩阵 | 空壳 | 批量任务入口 | 渲染 + 队列 |
| 能力网关 | 设置 | 部分 | 模型目录、OpenAI 兼容适配器 | 各家 API Key |
| 后台管控 | 后台 | 可用 | 用量、任务状态、审计日志、用户、模型 | 无 |
| 知识库 RAG | 知识库 | 可用 | 文档上传、切分、关键词检索 | 后续换向量检索 |
| 任务中心 | 任务 | 可用 | 工作流任务列表、取消、重试、产物 | FFmpeg / 模型 |

## 2. 已实现的真实能力

### 项目与额度

- 创建项目、画幅（9:16、16:9、1:1、4:5）、归档
- 项目下挂素材和脚本
- 额度统计：项目数、素材数、脚本数、任务数
- 后台展示任务状态和审计日志

### 素材资产

- 上传任意文件到项目
- 按扩展名分类：图片、视频、音频、文件
- 列表、下载、删除
- 单文件上限 500MB

### 文案脚本

- 手动创建、编辑、删除脚本
- 按项目筛选
- 生成脚本：产品、平台、风格
- 可选绑定知识库，检索结果拼进 Prompt
- 没配模型 Key 时走模板回退，接口不报错

### 模块任务

所有模块共用一张任务表，字段：

```text
id, project_id, module, mode, prompt, params, status, result, error, created_at
```

提交后状态是 `queued`，支持取消。执行器按 `module` 分发，后续逐个接入。

## 3. API

```text
POST   /api/v1/projects
GET    /api/v1/projects
GET    /api/v1/projects/{id}
PATCH  /api/v1/projects/{id}
DELETE /api/v1/projects/{id}

POST   /api/v1/projects/{id}/assets
GET    /api/v1/projects/{id}/assets
GET    /api/v1/projects/{id}/assets/{asset_id}/file
DELETE /api/v1/projects/{id}/assets/{asset_id}

GET    /api/v1/scripts
POST   /api/v1/scripts
POST   /api/v1/scripts/generate
GET    /api/v1/scripts/{id}
PATCH  /api/v1/scripts/{id}
DELETE /api/v1/scripts/{id}

GET    /api/v1/modules
POST   /api/v1/modules/{module_id}/jobs
GET    /api/v1/modules/{module_id}/jobs
GET    /api/v1/module-jobs
GET    /api/v1/module-jobs/{id}
POST   /api/v1/module-jobs/{id}/cancel
DELETE /api/v1/module-jobs/{id}

GET    /api/v1/admin/overview
GET    /api/v1/admin/logs
GET    /api/v1/admin/users
GET    /api/v1/admin/models
GET    /api/v1/quotas
```

## 4. 模块执行器怎么接

通用任务表已经统一，执行器按模块分发：

```python
EXECUTORS = {
    "image": ImageExecutor(),
    "storyboard": StoryboardExecutor(),
    "audio": AudioExecutor(),
    "lora": LoraExecutor(),
    "render": RenderExecutor(),
    "batch": BatchExecutor(),
}
```

每个执行器只需要：

1. 读取 `prompt` 和 `params`
2. 调用对应云端 API 或 FFmpeg
3. 把产物写入项目素材库
4. 更新任务状态和 `result_json`

## 5. 依赖与顺序

| 顺序 | 依赖 | 影响的模块 |
| --- | --- | --- |
| 1 | 安装 FFmpeg | 渲染、矩阵、视频任务 |
| 2 | 图像 API Key | 生图、分镜、封面 |
| 3 | 语音 API Key | ASR、TTS、BGM |
| 4 | GPU 训练服务 | LoRA |
| 5 | 对象存储 | 素材、产物、下载 |

## 6. 当前明确没做

- 生图、LoRA、分镜、音频、渲染、矩阵只建了任务入口，没有执行器
- 登录仍是 Demo，没有真实用户表和权限
- 额度是统计值，没有扣减和套餐限制
- 素材存本地磁盘，没有对象存储和 CDN
- 知识库是关键词检索，不是向量检索
- FFmpeg 未安装，视频任务无法执行
