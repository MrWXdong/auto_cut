# Git 与 Gitee 仓库规范

## 1. 仓库定位

`auto_cut` 是主仓库，包含后端、文档、脚本和后续的前端。媒体素材、模型文件、虚拟环境一律不进仓库。

## 2. 分支

| 分支 | 用途 |
| --- | --- |
| `main` | 可运行、可部署的稳定版本 |
| `dev` | 日常集成分支 |
| `feature/<name>` | 单个功能 |
| `fix/<name>` | 缺陷修复 |

个人开发阶段可以只保留 `main`，但进入交付期后必须留 `dev`，避免半成品直接上生产。

## 3. 提交信息

```text
feat: 新增 Seedance 视频节点
fix: 修复任务重试时检查点未清理
docs: 补充部署手册
refactor: 拆分模型网关适配器
chore: 更新依赖
test: 补充工作流引擎测试
```

一个提交只做一件事。不要把格式化、重命名、功能混在一个提交里。

## 4. 不要提交的东西

```text
.venv/
__pycache__/
.env
work/
backend/work/
node_modules/
.idea/
*.mp4 / *.mov / *.wav
模型权重
```

`.gitignore` 已经覆盖这些。密钥只放 `.env.example` 的空值，真实 Key 永远不进仓库。

## 5. 大文件

视频、素材、模型权重不进 Git。需要版本化的二进制走对象存储，仓库里只存引用和哈希。

## 6. 发布

交付前打标签：

```powershell
git tag -a v0.1.0 -m "内部可用版本"
git push origin v0.1.0
```

标签对应一个可部署的镜像版本，客户环境升级只认标签。

## 7. Gitee 远程仓库

1. 登录 https://gitee.com
2. 新建仓库，名称 `auto_cut`，选择私有
3. 不要勾选“使用 Readme 初始化”，本地已经有内容
4. 复制仓库地址，添加远程并推送：

```powershell
cd C:\Users\user\Documents\auto_cut
git remote add origin https://gitee.com/MrWXdong/auto_cut.git
git push -u origin main
```

HTTPS 推送需要 Gitee 账号密码或个人访问令牌。开启了两步验证的账号必须用令牌。

## 8. 日常流程

```powershell
git checkout -b feature/xxx
git add -A
git commit -m "feat: ..."
git push -u origin feature/xxx
```

合并回 `dev` 或 `main` 前先跑测试：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```
