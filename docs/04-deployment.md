# 部署方案

## 1. 本地开发

```powershell
cd C:\path\to\auto_cut
docker compose up -d postgres redis
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.api.main:app --reload --port 8010
```

## 2. 容器化

```powershell
docker compose build
docker compose up -d
```

服务：

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| api | 8010（容器内 8000） | FastAPI |
| postgres | 5432 | 元数据 |
| redis | 6379 | 队列与事件 |
| caddy | 80/443 | 反向代理与 HTTPS |

## 3. 云服务器

第一版建议 2 核 4G、40G 系统盘、按量对象存储。视频文件不要放系统盘。

步骤：

1. 安装 Docker 与 Compose 插件
2. 拉代码，配置 `.env`
3. `docker compose up -d --build`
4. 配置域名解析到服务器
5. Caddy 自动申请 HTTPS 证书
6. 用 `docker compose logs -f api` 检查启动

## 4. 环境变量

```text
AUTOCUT_ENVIRONMENT=prod
AUTOCUT_WORK_ROOT=/data/work
AUTOCUT_MAX_CONCURRENCY=2
AUTOCUT_FFMPEG_BIN=ffmpeg
AUTOCUT_FFPROBE_BIN=ffprobe
AUTOCUT_LLM_BASE_URL=https://api.deepseek.com
AUTOCUT_LLM_API_KEY=***
AUTOCUT_LLM_MODEL=deepseek-chat
AUTOCUT_DATABASE_URL=postgresql+psycopg://autocut:***@postgres:5432/autocut
AUTOCUT_REDIS_URL=redis://redis:6379/0
AUTOCUT_S3_ENDPOINT=
AUTOCUT_S3_BUCKET=
AUTOCUT_S3_ACCESS_KEY=
AUTOCUT_S3_SECRET_KEY=
```

## 5. 数据与备份

- PostgreSQL 每天 `pg_dump`，保留 7 天
- 对象存储开启版本控制或跨区复制
- 本地工作目录只做临时缓存，任务成功后清理
- 迁移前先备份，再执行

## 6. 监控

第一版用最小组合：

- `/health` 健康检查
- Docker 日志轮转
- 每日任务统计脚本
- 磁盘使用率告警

第二阶段再上 Prometheus + Grafana。

## 7. 发布流程

```text
本地测试 -> 构建镜像 -> 推送镜像 -> 服务器拉取 -> 滚动重启 -> 健康检查
```

数据库迁移与应用启动分离，迁移失败不启动新版本。

## 8. 成本估算

| 项目 | 规格 | 月成本（估算） |
| --- | --- | --- |
| 云服务器 | 2C4G | 60 到 100 元 |
| 对象存储 | 100GB | 10 到 20 元 |
| 模型调用 | 按量 | 视用量 |
| 域名与证书 | 年付 | 10 元/月 |

第一版控制在 150 元/月以内，等有真实客户再扩。
