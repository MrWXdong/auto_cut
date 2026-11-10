# 自媒体热点模块

## 1. 数据源

当前接入 6 个平台：

```text
微博、知乎、B站、百度、抖音、今日头条
```

每个平台都做了独立解析和错误隔离。单个平台失败不会影响其他平台。

另外支持租户添加自定义热点源：

- 支持 RSS / Atom
- 支持返回数组的 JSON 接口
- 支持普通 HTML 热点页面的链接标题提取
- 自定义源同样参与每日自动刷新
- 只允许公网 `http/https` 地址，拒绝本机和内网地址

## 2. 每日自动刷新

API 服务启动后会运行后台刷新任务：

1. 检查每个平台当天是否已有快照。
2. 缺失当天快照时抓取最新热榜，写入 `trend_snapshots`。
3. 每小时检查一次，跨天后自动刷新。
4. 单个平台抓取失败时，接口回退到最近一次成功快照，并标记 `stale=true`。
5. 默认保留 90 天历史快照。

相关配置：

```text
AUTOCUT_TREND_AUTO_REFRESH=true
AUTOCUT_TREND_REFRESH_INTERVAL_SECONDS=3600
AUTOCUT_TREND_TTL_SECONDS=300
AUTOCUT_TREND_RETENTION_DAYS=90
```

## 3. 接口

```text
GET /api/v1/trends/sources
POST   /api/v1/trends/custom-sources
DELETE /api/v1/trends/custom-sources/{id}
GET  /api/v1/trends/related?direction=美妆护肤&limit=50
GET /api/v1/trends?source=weibo&limit=30
GET /api/v1/trends?source=weibo&limit=30&refresh=true
```

`refresh=true` 会绕过当天快照，强制实时抓取。

`/related` 会跨全部平台和自定义源查询当天快照，按内容方向做关键词扩展、相关性排序和跨平台去重，返回命中的关键词与来源平台。

开启 `use_ai=true` 时还会调用聊天模型：

- 扩展与内容方向相关的同义词和品类词
- 生成 6-10 个 AI 关联选题
- 每个选题包含切入角度、开头钩子和建议内容形式
- 即使当天热榜没有直接匹配，也会返回创作参考

前端用 🔥 标记真实热榜条目，AI 关联选题不标记热点。

## 4. 前端

页面入口：`创作 → 热点`

支持：

- 切换平台和数量
- 查看热度、打开原文、复制标题
- 一键把热点带入文案生成
- 页面每 5 分钟自动同步一次当天快照

## 5. 存储

数据表：`trend_snapshots`

```text
source, source_name, snapshot_date, updated_at, items_json
```

主键是 `(source, snapshot_date)`，同一天重复刷新会覆盖当天快照。
