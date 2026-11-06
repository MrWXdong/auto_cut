from __future__ import annotations

MODEL_CATALOG: list[dict[str, object]] = [
    {
        "provider": "deepseek",
        "capabilities": ["chat"],
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "status": "ready",
    },
    {
        "provider": "qwen",
        "capabilities": ["chat", "embedding", "image.generate", "video.generate"],
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-max", "qwen-plus", "text-embedding-v3"],
        "status": "planned",
    },
    {
        "provider": "doubao",
        "capabilities": ["chat", "embedding", "image.generate", "video.generate"],
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "models": ["doubao-seed-1.6", "seedance", "seedream"],
        "status": "planned",
    },
    {
        "provider": "zhipu",
        "capabilities": ["chat", "embedding", "image.generate"],
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4-plus", "embedding-3"],
        "status": "planned",
    },
    {
        "provider": "moonshot",
        "capabilities": ["chat"],
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-128k"],
        "status": "planned",
    },
    {
        "provider": "kling",
        "capabilities": ["video.generate"],
        "base_url": "https://api.klingai.com",
        "models": ["kling-v2"],
        "status": "planned",
    },
    {
        "provider": "minimax",
        "capabilities": ["chat", "tts", "video.generate"],
        "base_url": "https://api.minimax.chat/v1",
        "models": ["speech-02", "hailuo-02"],
        "status": "planned",
    },
    {
        "provider": "sensenova",
        "capabilities": ["chat", "video.generate"],
        "base_url": "",
        "models": ["sensenova"],
        "status": "planned",
    },
]
