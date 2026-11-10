# 存储与对象存储

## 默认模式

默认 `AUTOCUT_OBJECT_STORAGE_BACKEND=local`：

- 素材和任务文件放在服务器 `work` 目录
- 浏览器不会自动下载
- 用户点击下载时才复制到用户电脑

## 任务目录结构

新任务统一使用客户可读的中文目录：

```text
jobs/<时间_素材名_任务ID>/
├─ 成片/                 最终成片、重剪成片、单段成片
├─ 切片/                 AI 切分出的原始片段
├─ 音频/原声.wav         从原素材提取的音频
├─ 字幕/
│  ├─ 完整字幕.txt       全片字幕，按切片片段聚合
│  ├─ 切片01_字幕.txt    每个切片自己的字幕和时间范围
│  ├─ 切片02_字幕.txt
│  └─ 切片03_字幕.txt
└─ 系统文件/
   ├─ 语音识别.json      ASR 原始识别结果，供程序内部使用
   └─ 任务断点.json      工作流断点，供失败重试使用
```

客户在任务产物区默认看到的是成片、切片和字幕；`系统文件/` 只用于系统恢复和排查，排在产物列表最后。
全片字幕默认生成一个 `完整字幕.txt`，按切出来的片段聚合，每个片段一行：
`[开始时间 --> 结束时间] 该片段字幕`，时间精确到秒，避免用户阅读时被过细的时间戳干扰。
每个切片同时生成独立的 `切片NN_字幕.txt`，任务产物区会把视频和对应字幕关联起来。
旧任务可通过 `scripts/organize-storage.ps1` 自动迁移为上述结构，并清理旧的 `完整字幕.srt`。

## S3 / MinIO / OSS

配置：

```text
AUTOCUT_OBJECT_STORAGE_BACKEND=s3
AUTOCUT_S3_ENDPOINT_URL=http://127.0.0.1:9000
AUTOCUT_S3_BUCKET=autocut
AUTOCUT_S3_ACCESS_KEY=autocut
AUTOCUT_S3_SECRET_KEY=autocut-secret
AUTOCUT_S3_REGION=auto
AUTOCUT_S3_PREFIX=autocut
AUTOCUT_S3_PATH_STYLE=true
AUTOCUT_S3_PRESIGN_SECONDS=3600
```

当前已完成：

- 工作流任务产物自动上传到 S3 兼容对象存储
- 上传成功后清理本地任务目录
- 任务产物列表读取云端元数据
- 下载接口返回短期签名 URL
- 删除单个产物同时删除云端对象
- 删除任务同时清理云端产物

当前未完成：

- 项目素材仍走本地存储
- 套餐 `storage_gb` 还没有做上传额度校验
- 大文件上传还未改成浏览器直传预签名 URL

## Docker MinIO

`docker-compose.yml` 已加入 `minio` 和 `minio-init`：

```powershell
docker compose up -d minio minio-init
```

MinIO 控制台：

```text
http://127.0.0.1:9001
```

默认账号密码来自：

```text
AUTOCUT_S3_ACCESS_KEY
AUTOCUT_S3_SECRET_KEY
```

## 生产策略

1. API 服务器不存长期媒体文件
2. 对象存储按租户前缀隔离
3. 素材直传使用预签名 URL
4. 下载和预览使用短期签名链接
5. 套餐存储额度按资产和产物实际大小校验
6. 免费版设置更短的产物生命周期
7. 删除素材或产物后释放额度
