# 一键扒素材

## 1. 能力

粘贴链接，把视频或图片直接下载到当前项目素材库：

```text
POST /api/v1/projects/{project_id}/assets/import
{"url": "https://example.com/video.mp4"}
```

入口：

- 素材页「一键扒素材」
- 聊天窗口直接粘贴链接，会调用 `import_material` 工具

## 2. 支持范围

- 直链：`.mp4`、`.mov`、`.webm`、`.jpg`、`.png`、`.webp`、`.mp3`、`.wav`
- 常见视频平台：通过 `yt-dlp` 解析
- 单文件上限 500MB，可配置 `AUTOCUT_ASSET_IMPORT_MAX_MB`

## 3. 安装 yt-dlp

项目依赖里已经包含 `yt-dlp`，重新安装依赖即可：

```powershell
cd C:\Users\user\Documents\auto_cut\backend
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

只装下载器：

```powershell
.\.venv\Scripts\python.exe -m pip install yt-dlp -i https://pypi.tuna.tsinghua.edu.cn/simple
```

没装 `yt-dlp` 时，直链仍可下载，平台链接会返回 501 并提示安装。

## 4. 安全限制

- 只允许 `http` / `https`
- 禁止内网地址、回环地址和保留地址，防止 SSRF
- 下载有大小上限
- 文件名和存储路径由服务端生成，不使用用户输入

## 5. 合规

只导入你拥有版权或已获得授权的素材。抓取第三方平台内容可能违反平台服务条款，交付给客户时要写进使用协议。

## 6. 代码位置

- 下载与校验：`backend/app/studio/importer.py`
- 接口：`backend/app/api/routers/projects.py`
- 聊天工具：`backend/app/agents/tools.py`
- 页面：`backend/app/web/index.html` 的素材页
