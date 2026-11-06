# 模型网关与多模型接入

## 1. 目标

一个平台接入国内多家模型，但用户看到的不是「模型列表」，而是「能力」：

```text
生成视频 / 生成提示词 / 生成字幕 / 知识问答 / 图片生成 / 配音
```

每个能力背后可以挂多个模型，系统按质量、价格、可用性自动路由。高级用户才需要手动指定模型。

## 2. 能力分类

| 能力 | 说明 | 典型模型 |
| --- | --- | --- |
| `chat` | 对话、规划、选段 | DeepSeek、通义、豆包、GLM、Kimi |
| `vision` | 图片理解、画面分析 | 通义 VL、豆包 Vision、GLM-4V |
| `embedding` | 向量化 | BGE-M3、通义 Embedding、豆包 Embedding |
| `rerank` | 检索重排 | BGE-reranker、通义 GTE-Rerank |
| `asr` | 语音转写 | faster-whisper、通义 ASR、豆包 ASR |
| `tts` | 语音合成 | CosyVoice、MiniMax Speech、豆包 TTS |
| `image.generate` | 文生图、图生图 | 通义万相、Seedream、可图、混元 |
| `video.generate` | 文生视频、图生视频 | Seedance、可灵、海螺、Vidu、通义万相 |

## 3. 国内模型清单

### 3.1 文本

| 厂商 | 接入方式 | 备注 |
| --- | --- | --- |
| DeepSeek | OpenAI 兼容 | 便宜，适合意图识别和选段 |
| 通义千问 | DashScope 兼容模式 | 模型全，多模态强 |
| 豆包 | 火山方舟 OpenAI 兼容 | 与 Seedance 同一套账号体系 |
| 智谱 GLM | OpenAI 兼容 | 中文稳定 |
| Moonshot | OpenAI 兼容 | 长上下文 |
| MiniMax | OpenAI 兼容 | 对话 + 语音 + 视频 |
| 商汤 SenseNova | 自有协议 | 需要单独适配 |

### 3.2 向量与重排

| 模型 | 部署 | 备注 |
| --- | --- | --- |
| BGE-M3 | 自托管 | 中文效果好，无 API 成本 |
| 通义 text-embedding-v3 | API | 稳定，按量计费 |
| 豆包 Embedding | API | 与方舟账号打通 |
| BGE-reranker-v2-m3 | 自托管 | 首版够用 |
| 通义 GTE-Rerank | API | 免运维 |

### 3.3 语音

| 能力 | 模型 | 部署 |
| --- | --- | --- |
| ASR | faster-whisper | 自托管，首版默认 |
| ASR | 通义 ASR / 豆包 ASR | API，长音频更稳 |
| TTS | CosyVoice | 自托管 |
| TTS | MiniMax Speech / 豆包 TTS | API，音色多 |

### 3.4 图像与视频

| 模型 | 厂商 | 能力 | 接入方式 |
| --- | --- | --- | --- |
| Seedance | 字节 / 火山方舟 | 文生视频、图生视频 | 异步任务 API |
| 可灵 Kling | 快手 | 文生视频、图生视频 | 异步任务，AK/SK 签名 |
| 海螺 Hailuo | MiniMax | 文生视频 | 异步任务 |
| Vidu | 生数科技 | 文生视频、参考生视频 | 异步任务 |
| 通义万相 Wan | 阿里 | 文生视频、图生视频 | DashScope 异步任务 |
| 混元视频 | 腾讯 | 文生视频 | 异步任务 |
| SenseNova 视频 | 商汤 | 文生视频 | 自有协议 |
| Seedream | 字节 | 文生图 | 方舟 |
| 可图 Kolors | 快手 | 文生图 | API |
| 通义万相图片 | 阿里 | 文生图 | DashScope |

## 4. Seedance 接入

如果「sendence」指的是字节的 Seedance，走火山方舟：

```text
认证：ARK_API_KEY
提交：POST /api/v3/contents/generations/tasks
查询：GET  /api/v3/contents/generations/tasks/{task_id}
输入：prompt、可选首帧图片、时长、比例、分辨率、种子
输出：任务状态 + 临时视频 URL
```

要点：

- 它不是 OpenAI 聊天协议，必须写独立适配器
- 模型参数填方舟上的推理接入点 ID（`ep-...`）或模型 ID
- 生成是异步任务，提交后轮询，不能当同步接口用
- 返回的 URL 有时效，必须立刻下载到自己的对象存储
- 按生成次数或秒数计费，要在提交时预扣、完成时结算

具体路径和参数以方舟当前文档为准，适配器里做一层隔离，文档变了只改一个文件。

## 5. 统一接口

按能力拆协议，不做一个万能接口：

```python
class ChatModel(Protocol):
    async def chat(self, messages: list[Message], **options) -> ChatResult: ...

class EmbeddingModel(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

class RerankModel(Protocol):
    async def rerank(self, query: str, documents: list[str], top_k: int) -> list[RerankHit]: ...

class ASRModel(Protocol):
    async def transcribe(self, audio: str, language: str | None) -> Transcript: ...

class ImageModel(Protocol):
    async def generate(self, prompt: str, **options) -> ImageResult: ...

class VideoModel(Protocol):
    async def submit(self, prompt: str, **options) -> str: ...
    async def poll(self, task_id: str) -> VideoTask: ...
```

适配器只实现自己支持的能力，注册表按能力查找。

## 6. 模型目录

```text
model_endpoints(
    id, tenant_id, provider, capability, base_url, model,
    api_key_encrypted, price_in, price_out, currency,
    timeout_s, max_concurrency, enabled, priority, meta_json
)
```

规则：

- 平台预置一套默认端点，租户可以覆盖自己的 Key
- 每个能力有一个默认模型和一个降级链
- 停用模型不影响历史任务，历史任务记录当时用的端点

## 7. 路由与降级

```yaml
capability: video.generate
policy: balanced
candidates:
  - model: seedance-pro
    weight: 60
  - model: kling-2
    weight: 30
  - model: hailuo
    weight: 10
fallback: true
```

路由考虑：

- 质量优先、均衡、便宜三档
- 当前并发和限流
- 租户预算
- 模型可用性（熔断）
- 区域和合规要求

熔断规则：连续失败 N 次，暂停该端点 5 分钟，自动切下一个。

## 8. 异步媒体任务

视频和图片生成大多是「提交任务 + 轮询」：

```text
提交 -> task_id -> 轮询 -> 成功 -> 下载 -> 入库 -> 返回 asset_id
                  -> 失败 -> 记录错误 -> 可重试
```

工作流里的 `video.generate` 节点必须：

- 支持超时（例如 10 分钟）
- 轮询间隔带退避
- 支持取消
- 记录供应商任务 ID，便于排查
- 产物下载后立刻转存，不依赖供应商临时 URL

## 9. 统一资产层

所有生成结果都落成资产：

```text
assets(id, tenant_id, kind, storage_key, sha256, size_bytes,
       provider, model, prompt, seed, cost_cents, status, meta_json)
```

好处：

- 前端只认 `asset_id`，不认供应商 URL
- 换模型不影响历史数据
- 成本可以按资产追溯
- 删除、归档、审计都有统一入口

## 10. 前端怎么暴露

不要让用户面对三十个模型。默认这样：

```text
生成视频
  质量优先 / 均衡 / 最快
  预计消耗：12 点
  [高级] 指定模型
```

高级模式再列出 Seedance、可灵、海螺等，显示价格和预计时长。大部分用户只需要点「生成」。

## 11. 分期

| 阶段 | 接入 |
| --- | --- |
| P0 | DeepSeek + 通义（chat）、BGE-M3（embedding）、faster-whisper（ASR） |
| P1 | 豆包、GLM、Kimi（chat）、Rerank |
| P2 | Seedance、可灵（video）、Seedream / 万相（image） |
| P3 | TTS、Vidu、海螺、混元 |

先接文本和检索，再接图像和视频。视频接入最重，放后面。

## 12. 风险

| 风险 | 应对 |
| --- | --- |
| 供应商接口变更 | 每个厂商一个适配器，加契约测试 |
| 临时 URL 过期 | 生成后立即转存对象存储 |
| 计费口径不一致 | 统一换算成「点数」，记录原始用量 |
| 限流和并发 | 按端点做令牌桶，队列削峰 |
| 内容合规 | 生成前敏感词、生成后审核、加隐式水印 |
| 模型下线 | 保留降级链，历史任务固定端点 |

## 13. 结论

「集能力于一身」的正确做法不是把每个模型都写死，而是：

```text
能力协议 + 适配器 + 模型目录 + 路由策略 + 统一资产 + 统一计费
```

新增一个模型，只加一个适配器和一条目录记录，不改业务代码。
