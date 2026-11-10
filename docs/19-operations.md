# 运营与治理模块

## 1. 选题日历

页面：`创作 → 选题日历`

能力：

- 输入内容方向、开始日期、天数、每天数量、发布平台
- 优先调用聊天模型生成结构化周计划/月计划
- 模型失败时使用本地模板生成兜底计划
- 生成结果写入 `content_calendar`
- 支持状态：`planned`、`in_progress`、`done`、`skipped`
- 可直接把日历选题带入文案生成

接口：

```text
GET    /api/v1/content-calendar
POST   /api/v1/content-calendar/generate
PATCH  /api/v1/content-calendar/{id}
DELETE /api/v1/content-calendar/{id}
```

## 2. 合规与成片质检

页面：`成片 → 合规质检`

文本规则：

- 广告法绝对化用语
- 医疗功效和疾病治疗承诺
- 金融收益保证
- 夸大宣传
- 平台站外引流
- 品牌名称露出
- 与已有脚本高度相似的重复内容

视频规则：

- 时长
- 分辨率和画幅
- 是否包含音轨
- 文件哈希

报告保存在 `compliance_reports`。

接口：

```text
POST   /api/v1/compliance/check
GET    /api/v1/compliance/reports
DELETE /api/v1/compliance/reports/{id}
```

## 3. 发布矩阵

页面：`成片 → 发布矩阵`

能力：

- 管理各平台账号
- 绑定项目和成片素材
- 创建发布排期
- 自动把到期计划标记为 `due`
- 支持取消、删除、标记已发布和填写发布链接

当前边界：

- 已支持账号矩阵、排期、状态流转和手动发布闭环
- 真正的自动发布仍需要平台开放接口授权
- 点击“执行发布”会返回 `manual_required`，提示用户手动发布后标记完成

接口：

```text
GET    /api/v1/publish/accounts
POST   /api/v1/publish/accounts
PATCH  /api/v1/publish/accounts/{id}
DELETE /api/v1/publish/accounts/{id}

GET    /api/v1/publish/jobs
POST   /api/v1/publish/jobs
POST   /api/v1/publish/jobs/{id}/run
POST   /api/v1/publish/jobs/{id}/published
POST   /api/v1/publish/jobs/{id}/cancel
DELETE /api/v1/publish/jobs/{id}
```
