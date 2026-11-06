# 本地环境搭建（Windows）

## 1. 安装 Python 3.12

当前机器的 PATH 还指向 `C:\Users\user\AppData\Local\Programs\Python\Python312`，但这个目录已经不存在，所以 `python` 命令找不到。旧项目 `enterprise_rag_agent` 的虚拟环境也因此失效。

步骤：

1. 打开 https://www.python.org/downloads/windows/
2. 下载 Python 3.12.x 的 64-bit installer
3. 安装时勾选 **Add python.exe to PATH**
4. 重新打开终端，执行：

```powershell
python --version
python -m pip --version
```

如果仍然找不到，卸载后重装，或手动把下面两个目录加入用户 PATH：

```text
C:\Users\user\AppData\Local\Programs\Python\Python312\
C:\Users\user\AppData\Local\Programs\Python\Python312\Scripts\
```

## 2. 安装 FFmpeg

1. 打开 https://www.gyan.dev/ffmpeg/builds/
2. 下载 `ffmpeg-release-essentials.zip`
3. 解压到 `C:\ffmpeg`
4. 把 `C:\ffmpeg\bin` 加入用户 PATH
5. 重新打开终端验证：

```powershell
ffmpeg -version
ffprobe -version
```

## 3. 初始化项目

```powershell
cd C:\Users\user\Documents\auto_cut
.\scripts\setup.ps1
```

默认使用云端 ASR。只有切换到本地离线回退（`AUTOCUT_ASR_PROVIDER=local`）时，才需要安装本地语音依赖：

```powershell
.\scripts\setup.ps1 -WithAsr
```

## 4. 在 PyCharm 中打开

- 用 PyCharm Community 打开 `C:\Users\user\Documents\auto_cut\backend`
- Interpreter 选择 `backend\.venv\Scripts\python.exe`
- 测试目录标记为 `tests`
- 运行配置里新建 Python 配置，模块名填 `app.cli`，参数示例：

```text
run subtitle --input C:\path\to\video.mp4
```

## 5. 验证

```powershell
cd C:\Users\user\Documents\auto_cut\backend
python -m pytest
python -m app.cli run subtitle --input C:\path\to\video.mp4
```

第一次跑字幕流前，需要在 `backend\.env` 里填 `AUTOCUT_LLM_API_KEY`，否则选段节点会报错。只跑字幕流不需要 LLM，但需要安装 `asr` 依赖。

## 6. 常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `python` 不是命令 | PATH 未配置或安装被删除 | 重装并勾选 Add to PATH |
| `ffmpeg` 不是命令 | PATH 未包含 ffmpeg\bin | 加入 PATH 后重开终端 |
| `No module named faster_whisper` | 没装 asr 依赖 | `pip install -e ".[asr]"` |
| 401 / 403 | LLM Key 无效 | 检查 `backend\.env` |
| 子进程编码报错 | 终端编码不是 UTF-8 | `chcp 65001` 或改用 PyCharm 终端 |
