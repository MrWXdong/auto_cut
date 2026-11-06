# 工作流 DSL v2 设计（对标扣子核心能力）

## 1. 先划清边界

扣子的工作流由六部分组成：

| 能力 | 作用 | 交付客户是否必须 |
| --- | --- | --- |
| DSL | 描述节点、连线、变量 | 必须 |
| 执行引擎 | 调度、变量传递、分支、重试 | 必须 |
| 可视化画布 | 拖拽编排、连线、配置 | 看客户 |
| 调试运行 | 单节点测试、全流程试运行 | 必须 |
| 版本发布 | 草稿、发布、回滚 | 必须 |
| 插件市场 | 第三方节点 | 后期 |

全量对标是 3 到 6 个月的工程量。交付客户的第一版，建议做「核心子集」：执行引擎、变量、条件分支、调试、版本化，加上有限的 8 到 10 个节点。画布是否要做，取决于客户是不是要自己编排。

## 2. 和当前实现的差距

当前引擎是静态 DAG：

- 节点用 `needs` 声明依赖，只能顺序或分层并发
- 参数用 `${input_path}` 做字符串替换
- 没有端口类型，没有条件分支，没有循环
- 没有运行态变量池，节点之间靠合并字典传值

这套够跑固定流水线，但做不了扣子那种「任意编排」。要升级的是四件事：端口、变量、控制流、版本。

## 3. DSL v2

### 3.1 结构

```yaml
id: wf_clip
name: 长视频切片
version: 3
status: draft

inputs:
  - name: source
    type: video
    required: true
  - name: max_clips
    type: number
    default: 5

variables:
  - name: transcript
    type: json

nodes:
  - id: start
    type: start
    outputs:
      source: "{{inputs.source}}"
      max_clips: "{{inputs.max_clips}}"

  - id: probe
    type: media.probe
    inputs:
      path: "{{start.source}}"

  - id: audio
    type: audio.extract
    inputs:
      path: "{{start.source}}"

  - id: transcript
    type: ai.asr
    inputs:
      audio: "{{audio.path}}"
      language: zh

  - id: enough
    type: logic.condition
    inputs:
      left: "{{transcript.segment_count}}"
      op: ">="
      right: 3

  - id: select
    type: ai.select_segments
    inputs:
      segments: "{{transcript.segments}}"
      duration: "{{probe.duration}}"
      max_clips: "{{start.max_clips}}"

  - id: cut
    type: video.cut_many
    inputs:
      source: "{{start.source}}"
      segments: "{{select.segments}}"

  - id: export
    type: video.export
    inputs:
      clips: "{{cut.clips}}"
      aspects: ["9:16", "1:1"]

  - id: end
    type: end
    inputs:
      outputs: "{{export.outputs}}"

edges:
  - from: { node: start, port: out }
    to: { node: probe, port: in }
  - from: { node: start, port: out }
    to: { node: audio, port: in }
  - from: { node: audio, port: out }
    to: { node: transcript, port: in }
  - from: { node: transcript, port: out }
    to: { node: enough, port: in }
  - from: { node: enough, port: "true" }
    to: { node: select, port: in }
  - from: { node: select, port: out }
    to: { node: cut, port: in }
  - from: { node: cut, port: out }
    to: { node: export, port: in }
  - from: { node: export, port: out }
    to: { node: end, port: in }
  - from: { node: probe, port: out }
    to: { node: select, port: in }
```

### 3.2 变量引用

语法：`{{scope.name}}`，支持点路径访问嵌套字段。

| 作用域 | 示例 | 说明 |
| --- | --- | --- |
| inputs | `{{inputs.source}}` | 运行入参 |
| vars | `{{vars.transcript}}` | 流程变量 |
| 节点输出 | `{{transcript.segments}}` | 上游节点输出 |
| 环境 | `{{env.LLM_MODEL}}` | 服务端环境变量，只读 |

解析规则：

- 整个字符串就是一个引用时，返回原始类型（数组、对象、数字）
- 引用嵌在字符串里时，按字符串插值
- 引用不存在时直接失败，不做静默兜底
- 节点执行前统一解析，执行中不可变

### 3.3 端口类型

```text
string | number | boolean | json | video | audio | image | file | any
```

端口类型的价值：

- 画布连线时做类型校验
- 配置面板自动生成合适的控件
- 执行前静态检查，减少运行期错误

## 4. 执行语义

### 4.1 触发

- `start` 节点是唯一入口，持有流程入参
- 一个节点满足以下条件才执行：所有必需输入已就绪，且至少一条入边被激活
- 合流默认 `join: all`，可配置为 `any`

### 4.2 分支

`logic.condition` 输出 `true` / `false` 两个端口，只有命中的端口激活，另一个分支标记为 `skipped`。跳过不是失败，不计入错误率。

### 4.3 循环

`logic.loop` 持有一个子图，对数组逐项执行：

```yaml
- id: each_clip
  type: logic.loop
  inputs:
    items: "{{select.segments}}"
    item_name: segment
  subgraph: clip_body
```

子图内可用 `{{segment.start}}`、`{{loop.index}}`。循环上限必须配置，防止死循环。

### 4.4 暂停与人工审核

`human.review` 节点把任务置为 `awaiting_review`，保存当前变量快照；审核通过后从该节点继续，不重跑上游。这是企业交付的刚需。

### 4.5 取消

每个节点执行前后检查取消标记；FFmpeg 子进程收到终止信号后清理临时文件。取消不是直接杀进程，要保证检查点一致。

## 5. 节点协议

```python
class NodeHandler(Protocol):
    type: str
    inputs: dict[str, PortSpec]
    outputs: dict[str, PortSpec]

    async def run(self, ctx: NodeContext, inputs: dict[str, Any]) -> dict[str, Any]:
        ...
```

节点同时暴露一份 JSON Schema 给前端，配置面板据此渲染，不写死表单。

首批节点：

| 分类 | 节点 | 说明 |
| --- | --- | --- |
| 触发器 | `start` | 入参 |
| AI | `ai.asr` | 语音转写 |
| AI | `ai.llm` | 通用文本生成 |
| AI | `ai.select_segments` | 选段 |
| 媒体 | `media.probe` | 元数据 |
| 媒体 | `audio.extract` | 抽音频 |
| 媒体 | `video.cut_many` | 批量裁剪 |
| 媒体 | `video.export` | 多规格导出 |
| 逻辑 | `logic.condition` | 条件分支 |
| 逻辑 | `logic.loop` | 循环 |
| 集成 | `http.request` | 调外部接口 |
| 人工 | `human.review` | 审核 |
| 输出 | `end` | 结束并汇总 |

## 6. 版本与发布

```text
workflows(id, name, current_version)
workflow_versions(id, workflow_id, version, status, spec_json, created_by, created_at)
runs(id, workflow_version_id, status, inputs_json, outputs_json, error, started_at, finished_at)
run_nodes(id, run_id, node_id, status, inputs_json, outputs_json, error, duration_ms)
```

规则：

- 编辑只改草稿，发布生成不可变版本
- 任务绑定 `workflow_version_id`，发布新版本不影响在跑任务
- 回滚就是把 `current_version` 指回旧版本

## 7. 调试

扣子最好用的部分不是画布，是调试。必须做：

- 单节点测试：填输入，直接跑一个节点，看输出
- 全流程试运行：不落正式任务，事件流式返回
- 节点级输入输出快照
- 失败节点可单独重跑
- 变量面板实时显示当前值

接口：

```text
POST /api/v1/workflows/{id}/runs             创建试运行
GET  /api/v1/runs/{run_id}                   查询状态
GET  /api/v1/runs/{run_id}/events            SSE 事件流
POST /api/v1/runs/{run_id}/nodes/{node}/run  单节点调试
```

## 8. 画布

技术选型：`React Flow`（`@xyflow/react`），不自研画布。

页面结构：

- 左侧节点面板，按分类折叠
- 中间画布，连线做类型校验
- 右侧配置面板，按节点 JSON Schema 生成表单
- 底部运行面板，输入、时间线、节点输出

变量选择器：选中输入框时，列出所有上游节点的输出字段，点击插入 `{{node.field}}`。

## 9. 分阶段

| 阶段 | 内容 | 工期 |
| --- | --- | --- |
| P0 | DSL v2、变量解析、条件分支、8 个节点、CLI 试运行 | 2 周 |
| P1 | 运行 API、SSE、单节点调试、版本化 | 1.5 周 |
| P2 | React Flow 画布、配置面板、变量选择器 | 2.5 周 |
| P3 | 循环、子工作流、人工审核、模板 | 2 周 |
| P4 | 插件机制、权限、多人协作 | 按需 |

## 10. 关键取舍

- 不做通用低代码平台，节点控制在视频生产需要的范围内
- 画布不是第一优先级，先保证引擎和调试可用
- 版本化从第一天做，客户交付必须能回滚
- 任何节点都必须有超时、重试、取消和成本记录
- 客户的品牌模板、字体、logo、安全区属于交付内容，不是附加功能

## 11. 决策点

如果客户只是使用你配置好的流程，交付形态应该是「模板 + 参数 + 审核 + 下载」，画布可以砍掉，工期缩短一半以上。

如果客户要自己搭流程、自己接模型、自己加节点，才需要完整画布和插件体系。

## 12. 代码位置

已落地：

- DSL 模型与图校验：`backend/app/core/workflow/dsl.py`
- 变量引用解析：`backend/app/core/workflow/resolver.py`
- 对应测试：`backend/tests/test_dsl.py`、`backend/tests/test_resolver.py`
- 旧版静态 DAG 引擎：`backend/app/core/workflow/executor.py`（迁移前保留）

下一步：

1. `runtime.py`：基于边和端口的执行器，支持条件分支、跳过传播、节点事件
2. 节点适配：把现有媒体节点接到 v2 输入协议
3. 运行 API 与 SSE
4. React Flow 画布
