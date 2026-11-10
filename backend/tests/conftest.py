from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

os.environ["AUTOCUT_TREND_AUTO_REFRESH"] = "false"
os.environ["AUTOCUT_TTS_PROVIDER"] = "placeholder"
for key in (
    "AUTOCUT_LLM_API_KEY",
    "AUTOCUT_DEEPSEEK_API_KEY",
    "AUTOCUT_QWEN_API_KEY",
    "AUTOCUT_DOUBAO_API_KEY",
    "AUTOCUT_ZHIPU_API_KEY",
    "AUTOCUT_MOONSHOT_API_KEY",
):
    os.environ[key] = ""


def pytest_configure(config) -> None:
    """Use a per-process temp root.

    A shared basetemp can be created by another Windows account or sandbox
    process with an ACL the current user cannot write to.
    """
    from app.config import get_settings

    get_settings.cache_clear()
    if config.option.basetemp:
        return
    base = Path(tempfile.gettempdir()) / f"autocut-pytest-{os.getpid()}"
    config.option.basetemp = str(base)


def pytest_sessionfinish(session, exitstatus) -> None:
    base = session.config.option.basetemp
    if exitstatus == 0 and base and "autocut-pytest-" in str(base):
        shutil.rmtree(str(base), ignore_errors=True)
