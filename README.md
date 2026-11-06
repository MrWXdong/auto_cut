# AutoCut

面向企业内容团队的 AI 视频生产平台。目标是把「一条长素材到多平台多规格成片」做成可配置的自动化工作流，而不是一堆写死的脚本。

当前阶段：Phase 0，需求、架构与工作流引擎骨架。

## 项目结构

```text
auto_cut/
  backend/
    app/
      core/workflow/     工作流引擎：节点、DAG、执行器、注册表
      nodes/             可复用节点：探测、抽音频、ASR、选段、裁剪、导出
      workflows/         工作流定义（YAML）
      api/               FastAPI 入口
      cli.py             本地运行工作流的命令行
    tests/               引擎单元测试
  docs/                  需求、架构、路线图、部署
  deploy/                Docker 与服务器配置
```

## 快速开始

前置条件：Python 3.12+、FFmpeg 6+。详细安装步骤见 [本地环境搭建](docs/05-local-setup.md)。

```powershell
cd C:\Users\user\Documents\auto_cut\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

默认走云端 ASR，不需要本地语音模型。只有启用 `AUTOCUT_ASR_PROVIDER=local` 的离线回退时，才需要加装：

```powershell
pip install -e ".[dev,asr]"
```

跑一条字幕工作流：

```powershell
python -m app.cli run subtitle --input C:\path\to\video.mp4
```

跑一条切片工作流：

```powershell
python -m app.cli run clip --input C:\path\to\video.mp4
```

## 设计原则

- 引擎与业务解耦：新增能力是注册节点、写 YAML，不改执行器。
- 每个节点输入输出都是可序列化的字典，便于落盘、重放和评测。
- 任务可断点续跑：节点成功即写检查点，失败重试不从头再来。
- 成本可归因：每个节点记录耗时、重试次数和模型用量。
- 先做单机闭环，再拆服务；不提前上 Kubernetes。

## 文档

- [需求文档](docs/01-product-requirements.md)
- [架构设计](docs/02-architecture.md)
- [开发路线图](docs/03-roadmap.md)
- [部署方案](docs/04-deployment.md)
- [工作流 DSL v2（对标扣子）](docs/07-workflow-dsl-v2.md)
- [平台总体架构（Agent + RAG + 订阅）](docs/08-platform-blueprint.md)
- [模型网关与多模型接入](docs/09-model-gateway.md)
- [空壳范围与填充顺序](docs/10-shell-scope.md)
- [Git 与 Gitee 仓库规范](docs/11-git-workflow.md)
