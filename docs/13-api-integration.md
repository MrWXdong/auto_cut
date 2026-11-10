# API 接入位置

模块执行器已经能本地跑，需要外部能力的地方集中在 `backend/app/studio/executors.py`。每个接入点都保留了相同的资产管理路径，替换实现时不需要改前端。

## 1. 生图

位置：`_image()`

当前行为：

- 已接入豆包 Seedream（火山方舟）和智谱 CogView。
- 豆包默认模型未开通时，会在 Seedream 5.0 / 4.5 / 4.0 候选模型间自动降级。
- 没有可用图像模型时仍会生成占位封面，但状态为 `needs_config`，不会再伪装成成功。

接入方式：

```python
# 调用通义万相 / Seedream / 可图
image_bytes = await image_provider.generate(prompt)
# 保存到 studio.work_root / projects/{project_id}/assets/...
# 调用 studio.add_asset()
```

需要配置：图像 API Key、模型名、尺寸、并发限制。

### 豆包 Seedream

```env
AUTOCUT_DOUBAO_API_KEY=方舟 API Key
AUTOCUT_DOUBAO_IMAGE_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
AUTOCUT_DOUBAO_IMAGE_MODEL=doubao-seedream-5-0-flash-260915
```

注意：

- 方舟 `/models` 能列出模型，不代表账号已经开通该模型。
- 报 `ModelNotOpen` 时，需要登录火山方舟控制台，在模型广场开通对应模型。
- 也可以创建推理接入点，把 `AUTOCUT_DOUBAO_IMAGE_MODEL` 填成 `ep-xxxxxxxx`。
- 当前生图请求使用 `response_format=url`、`watermark=false`，生成后会立即转存到项目素材库。

## 2. ASR

位置：`_audio()` 的 `asr` 分支

当前行为：返回 `needs_config`，提示接入云端语音 API。

接入方式：把音频/视频资产路径传给通义 ASR、豆包 ASR 或 SenseNova，返回带时间戳的 segments，写入字幕资产。

## 3. TTS

位置：`_audio()` 的 `tts` 分支

当前行为：生成 1 秒静音 WAV 占位，写入素材库。

接入方式：调用 MiniMax Speech、豆包 TTS 或 CosyVoice，保存返回的音频文件。

## 4. LoRA 训练

位置：`_lora()`

当前行为：生成训练配置 JSON，包含项目里的图片素材 ID，状态为 `needs_config`。

接入方式：把配置提交到 GPU 训练服务（如 RunPod、Replicate、自建队列），训练完成后把 LoRA 权重作为资产保存。

## 5. 渲染

位置：`_manifest()` 的 `render` 分支

当前行为：生成渲染配置 JSON，状态为 `needs_config`。

接入方式：安装 FFmpeg 后，读取配置里的素材和时间线，执行 `ffmpeg`，把成片写入项目素材库。

## 6. 批量

位置：`_manifest()` 的 `batch` 分支

当前行为：生成批量任务配置 JSON，状态为 `needs_config`。

接入方式：按 `params.items` 拆分模块任务，写入 `module_jobs`，由 worker 并发消费。

## 7. 模型网关

位置：`backend/app/gateway/`

- `openai_compatible.py`：文本模型已经可用
- `seedance.py`：视频任务适配器空壳
- `asr.py`：云端 ASR 适配器空壳

接入新厂商时只加适配器，不改业务代码。
