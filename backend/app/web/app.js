const state = {
  token: localStorage.getItem("autocut_token") || "",
  meta: null,
  view: "workspace",
  selectedKb: "",
  projectId: "",
  projectName: "",
  projects: [],
  assets: [],
  scripts: [],
  scriptTopics: [],
  lastScript: null,
  moduleJobs: [],
  storyboardData: null,
  module: "image",
  modules: [],
  templates: [],
  pipelineSteps: [],
  modelCatalog: [],
  modelDefaults: {},
  autoModels: {},
  preferences: null,
  styles: [],
  selectedStyleId: "",
  scriptStyles: [],
  scriptStyleId: "",
  trends: [],
  trendSources: [],
  trendSource: "weibo",
  trendRelated: null,
  trendSuggestions: [],
  trendTimer: null,
  calendarItems: [],
  complianceReports: [],
  publishAccounts: [],
  publishJobs: [],
  artifactJobId: "",
  artifactItems: [],
  chatConversationId: "",
  qualityAssetId: "",
  qualityRating: 0,
  qualityTags: new Set(),
  previewUrl: "",
  editJobs: [],
  timelineJobId: "",
  timelineJob: null,
  clipSegments: [],
  timelineSelectedId: "",
  timelineBatchMode: false,
  timelineCheckedIds: new Set(),
  timelineHasAdjustments: false,
  timelineOnlyHighlight: false,
  timelinePlayback: null,
  timelineDrag: null,
  timelineDragging: false,
  editJobSearchTimer: null,
  jobSearchTimer: null,
  storageBrowsePath: "",
  storageBrowseParent: "",
  brandKit: null,
  styleBaseline: null,
  workerOnline: null,
  workerTimer: null,
};

const VIEW_META = {
  workspace: ["工作台", "描述需求，系统选择技能并执行。"],
  runs: ["任务", "上传素材、查看进度、下载产物。"],
  knowledge: ["知识库", "品牌规范、产品卖点、历史脚本。"],
  billing: ["套餐", "订阅与用量。"],
  settings: ["设置", "模型、账号与运行开关。"],
  projects: ["项目", "画幅、素材与脚本归属。"],
  scripts: ["文案", "生成脚本、标题与标签。"],
  trends: ["热点", "抓取自媒体平台热榜并快速转成文案。"],
  calendar: ["选题日历", "按内容方向生成周计划、月计划和发布节奏。"],
  assets: ["素材", "图片、视频、音频与文档。"],
  brand: ["品牌", "统一品牌语气、颜色、水印与片头片尾。"],
  style: ["风格", "风格模板与 LoRA 微调。"],
  edit: ["一键成片", "自动分析、切片、导出成片。"],
  compliance: ["合规质检", "检查广告法、品牌规范、重复内容和视频规格。"],
  publish: ["发布矩阵", "管理平台账号、发布排期和发布状态。"],
  structure: ["结构剪辑", "按模块组合流水线。"],
  module: ["模块", "提交任务并查看队列。"],
  admin: ["团队管理", "用量、任务状态与审计日志。"],
};

const NAV_GROUPS = [
  {
    id: "workspace",
    label: "工作台",
    tabs: [{ label: "工作台", view: "workspace" }],
  },
  {
    id: "projects",
    label: "项目",
    tabs: [
      { label: "项目", view: "projects" },
      { label: "素材", view: "assets" },
    ],
  },
  {
    id: "brand",
    label: "品牌",
    tabs: [
      { label: "品牌资产", view: "brand" },
      { label: "风格与 LoRA", view: "style" },
    ],
  },
  {
    id: "create",
    label: "创作",
    tabs: [
      { label: "热点", view: "trends" },
      { label: "选题日历", view: "calendar" },
      { label: "文案脚本", view: "scripts" },
      { label: "分镜", view: "module", module: "storyboard" },
      { label: "生图", view: "module", module: "image" },
      { label: "音频字幕", view: "module", module: "audio" },
    ],
  },
  {
    id: "produce",
    label: "成片",
    tabs: [
      { label: "一键成片", view: "edit" },
      { label: "结构剪辑", view: "structure" },
      { label: "渲染", view: "module", module: "render" },
      { label: "矩阵批量", view: "module", module: "batch" },
      { label: "合规质检", view: "compliance" },
      { label: "发布矩阵", view: "publish" },
    ],
  },
  {
    id: "knowledge",
    label: "知识库",
    tabs: [{ label: "知识库", view: "knowledge" }],
  },
  {
    id: "runs",
    label: "任务",
    tabs: [{ label: "任务", view: "runs" }],
  },
  {
    id: "account",
    label: "账号",
    tabs: [
      { label: "套餐", view: "billing" },
      { label: "团队管理", view: "admin" },
      { label: "设置", view: "settings" },
    ],
  },
];

const STATUS_TEXT = {
  queued: "排队",
  running: "运行中",
  succeeded: "成功",
  failed: "失败",
  canceled: "已取消",
  needs_config: "待配置",
};

const USAGE_TEXT = {
  credits: "积分",
  projects: "项目",
  assets: "素材",
  scripts: "文案",
  jobs: "任务",
  jobs_total: "任务",
  storage_bytes: "存储空间",
  grant: "套餐赠送",
  reserve: "任务预扣",
  settle: "任务结算",
  refund: "额度退回",
};

const CALENDAR_STATUS_TEXT = {
  planned: "待创作",
  in_progress: "制作中",
  done: "已完成",
  skipped: "已跳过",
};

const COMPLIANCE_LEVEL_TEXT = {
  pass: "通过",
  warn: "需优化",
  fail: "高风险",
};

const PUBLISH_STATUS_TEXT = {
  scheduled: "已排期",
  due: "待发布",
  manual_required: "需手动发布",
  published: "已发布",
  canceled: "已取消",
  failed: "发布失败",
};

const PROVIDER_TEXT = {
  deepseek: "DeepSeek",
  qwen: "通义千问",
  doubao: "豆包",
  zhipu: "智谱 GLM",
  moonshot: "Kimi",
  sensenova: "商汤 SenseNova",
};

const MODEL_LIST_KEYS = {
  chat: "chat_models",
  "image.generate": "image_models",
  asr: "asr_models",
  tts: "tts_models",
  "video.generate": "video_models",
  embedding: "embedding_models",
};

const CAPABILITY_TEXT = {
  chat: "文本模型",
  "image.generate": "生图模型",
  asr: "语音识别",
  tts: "语音合成",
  "video.generate": "视频模型",
  embedding: "向量模型",
};

const MODE_LABELS = {
  script: "脚本",
  titles: "标题",
  tags: "标签",
  text2img: "文生图",
  img2img: "图生图",
  controlnet: "ControlNet",
  inpaint: "局部重绘",
  outpaint: "扩图",
  cover: "封面生成",
  auto: "自动分镜",
  manual: "手动分镜",
  asr: "语音识别",
  tts: "语音合成",
  bgm: "背景音乐",
  denoise: "降噪",
  train: "模型训练",
  style: "风格训练",
  render: "渲染",
  export: "导出",
  batch: "批量创作",
};

const MODULE_STATUS_TEXT = {
  ready: "就绪",
  shell: "待接入",
  planned: "规划中",
};

const QUALITY_LABELS = {
  draft: "草稿",
  standard: "标准",
  high: "高质量",
};

function modeLabel(mode) {
  return MODE_LABELS[String(mode || "")] || String(mode || "");
}

function qualityLabel(quality) {
  return QUALITY_LABELS[String(quality || "")] || String(quality || "");
}

function $(id) {
  return document.getElementById(id);
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function modelRefLabel(ref) {
  const value = String(ref || "");
  const separator = value.indexOf(":");
  if (separator <= 0) return value;
  const provider = value.slice(0, separator);
  const model = value.slice(separator + 1);
  return `${PROVIDER_TEXT[provider] || provider} · ${model}`;
}

function mediaUrl(path) {
  const value = String(path || "");
  if (!value) return value;
  const separator = value.includes("?") ? "&" : "?";
  return `${value}${separator}token=${encodeURIComponent(state.token)}`;
}

function toast(message, bad = false) {
  const node = $("toast");
  node.textContent = message;
  node.classList.toggle("bad", bad);
  node.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => {
    node.hidden = true;
  }, 2600);
}

async function copyText(text, successMessage = "已复制") {
  const value = String(text || "");
  if (!value) {
    toast("没有可复制的内容");
    return;
  }
  try {
    await navigator.clipboard.writeText(value);
    toast(successMessage);
    return;
  } catch {
    const area = document.createElement("textarea");
    area.value = value;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
    toast(successMessage);
  }
}

function showScriptModal(title, body) {
  $("script-modal-title").textContent = title || "脚本全文";
  $("script-modal-body").textContent = body || "";
  $("script-modal").hidden = false;
}

function closeScriptModal() {
  $("script-modal").hidden = true;
}

function renderStoryboardHtml(payload) {
  const scenes = Array.isArray(payload?.scenes) ? payload.scenes : [];
  if (!scenes.length) {
    return `<pre class="output">${esc(JSON.stringify(payload, null, 2))}</pre>`;
  }
  const total = scenes.reduce((sum, scene) => sum + (Number(scene.duration) || 0), 0);
  const cards = scenes.map((scene, index) => {
    const visual = scene.visual_prompt || scene.description || "";
    return `
      <article class="storyboard-card">
        <div class="storyboard-card-head">
          <span class="pill">镜头 ${esc(scene.index || index + 1)}</span>
          <span class="muted">${esc(scene.duration || 3)} 秒</span>
        </div>
        <div class="storyboard-shot">${esc(scene.shot || "中景")}${scene.camera ? ` · ${esc(scene.camera)}` : ""}</div>
        ${visual ? `<div class="storyboard-line"><b>画面</b><span>${esc(visual)}</span></div>` : ""}
        ${scene.voiceover ? `<div class="storyboard-line"><b>配音</b><span>${esc(scene.voiceover)}</span></div>` : ""}
        ${scene.transition ? `<div class="storyboard-line"><b>转场</b><span>${esc(scene.transition)}</span></div>` : ""}
      </article>`;
  }).join("");
  return `
    <div class="storyboard-summary">共 ${scenes.length} 个镜头，约 ${total.toFixed(1)} 秒</div>
    <div class="storyboard-grid">${cards}</div>
    <details class="json-details">
      <summary>查看原始 JSON 数据</summary>
      <pre class="output">${esc(JSON.stringify(payload, null, 2))}</pre>
    </details>`;
}

function showStoryboardModal(title, payload) {
  state.storyboardData = payload;
  $("storyboard-modal-title").textContent = title || "分镜预览";
  $("storyboard-modal-body").innerHTML = renderStoryboardHtml(payload);
  $("storyboard-modal").hidden = false;
}

function closeStoryboardModal() {
  $("storyboard-modal").hidden = true;
}

async function generateStoryboardFromScript(scriptId, button) {
  const script = state.scripts.find((item) => item.id === scriptId);
  if (!script) return;
  const label = button.textContent;
  button.disabled = true;
  button.textContent = "生成中...";
  try {
    const data = await api(`/api/v1/scripts/${scriptId}/storyboard`, {
      method: "POST",
    });
    showStoryboardModal(`分镜 · ${script.title}`, data);
    toast(`已生成 ${data.scenes?.length || 0} 个镜头`);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}

function downloadTextFile(filename, content) {
  const blob = new Blob([content || ""], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function api(path, options = {}) {
  const { method = "GET", body, headers = {} } = options;
  const finalHeaders = { ...headers };
  if (state.token) {
    finalHeaders.Authorization = `Bearer ${state.token}`;
  }

  let payload = body;
  if (body && !(body instanceof FormData) && typeof body !== "string") {
    finalHeaders["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const response = await fetch(path, { method, body: payload, headers: finalHeaders });
  if (response.status === 401 && !path.startsWith("/api/v1/auth/")) {
    state.token = "";
    localStorage.removeItem("autocut_token");
    showLogin();
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch {
      // keep status text
    }
    throw new Error(`${response.status} ${detail}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}

function statusPill(status) {
  const map = {
    succeeded: "ok",
    failed: "bad",
    running: "warn",
    queued: "muted",
    canceled: "muted",
    needs_config: "warn",
  };
  return `<span class="pill ${map[status] || "muted"}">${esc(STATUS_TEXT[status] || status)}</span>`;
}

function formatDuration(ms) {
  if (ms === null || ms === undefined) return "-";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function showApp() {
  $("login-layer").hidden = true;
  $("app").hidden = false;
  loadMeta();
  loadProjects();
  loadScriptStyleOptions();
  loadWorkspacePreferences();
  loadModelDefaults();
  loadWorkerStatus();
  if (!state.workerTimer) {
    state.workerTimer = setInterval(loadWorkerStatus, 8000);
  }
  if (!state.trendTimer) {
    state.trendTimer = setInterval(() => {
      if (state.view === "trends" && !state.trendRelated) loadTrends(false, true);
    }, 5 * 60 * 1000);
  }
  const hash = location.hash.replace(/^#/, "");
  if (hash.startsWith("module/")) {
    const moduleId = hash.split("/")[1];
    if (moduleId === "lora") {
      switchView("style");
    } else if (moduleId === "copywriting") {
      switchView("scripts");
    } else {
      switchView("module", moduleId);
    }
  } else if (hash && VIEW_META[hash]) {
    switchView(hash);
  } else {
    switchView(state.view);
  }
}

function showLogin() {
  if (state.workerTimer) {
    clearInterval(state.workerTimer);
    state.workerTimer = null;
  }
  $("app").hidden = true;
  $("login-layer").hidden = false;
}

async function login(event) {
  event.preventDefault();
  const email = $("login-email").value.trim();
  const password = $("login-password").value;
  try {
    const data = await api("/api/v1/auth/login", {
      method: "POST",
      body: { email, password },
    });
    state.token = data.access_token;
    localStorage.setItem("autocut_token", state.token);
    $("user-name").textContent = data.user?.name || email;
    showApp();
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadAuthMethods() {
  try {
    const data = await api("/api/v1/auth/methods");
    const methods = Object.fromEntries((data.items || []).map((item) => [item.id, item]));
    const smsTab = document.querySelector('.login-tab[data-method="sms"]');
    const wechatTab = document.querySelector('.login-tab[data-method="wechat"]');
    if (smsTab) {
      smsTab.disabled = !methods.sms?.enabled;
      smsTab.title = methods.sms?.reason || "";
    }
    if (wechatTab) {
      wechatTab.disabled = !methods.wechat?.enabled;
      wechatTab.title = methods.wechat?.reason || "";
    }
    $("sms-hint").textContent = methods.sms?.enabled ? "" : (methods.sms?.reason || "");
    $("wechat-hint").textContent = methods.wechat?.enabled ? "" : (methods.wechat?.reason || "");
  } catch {
    // login methods are best-effort; password login still works
  }
}

async function loadWorkerStatus() {
  const node = $("worker-status");
  if (!node) return;
  try {
    const data = await api("/api/v1/system/workers");
    const online = Number(data.online || 0);
    state.workerOnline = online > 0;
    node.textContent = online > 0 ? `Worker 在线 ${online}` : "Worker 未运行";
    node.className = `pill ${online > 0 ? "ok" : "bad"}`;
    const items = data.items || [];
    node.title = items.length
      ? items
        .map((item) => `${item.host}:${item.pid} · ${item.status} · ${item.age_seconds}s 前`)
        .join("\n")
      : "没有检测到 Worker 心跳";
  } catch {
    state.workerOnline = false;
    node.textContent = "Worker 状态未知";
    node.className = "pill bad";
    node.title = "无法读取 Worker 状态";
  }
}

async function loadLoginMeta() {
  try {
    const meta = await api("/api/v1/meta");
    state.meta = meta;
    $("login-mode-hint").innerHTML = meta.demo_mode
      ? 'Demo 模式，任意账号可登录 · <a href="/signup">企业开通</a>'
      : '企业账号登录 · 需要管理员开通账号 · <a href="/signup">企业开通</a>';
  } catch {
    $("login-mode-hint").textContent = "企业账号登录";
  }
}

function switchLoginMethod(method) {
  const target = document.querySelector(`.login-tab[data-method="${method}"]`);
  if (target?.disabled) return;
  const panels = {
    password: "password-form",
    sms: "sms-form",
    wechat: "wechat-panel",
  };
  document.querySelectorAll(".login-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.method === method);
  });
  Object.entries(panels).forEach(([key, id]) => {
    $(id).hidden = key !== method;
  });
}

async function sendSmsCode() {
  const phone = $("sms-phone").value.trim();
  const button = $("sms-send");
  button.disabled = true;
  try {
    const data = await api("/api/v1/auth/sms/send", {
      method: "POST",
      body: { phone },
    });
    $("sms-hint").textContent = data.demo_code
      ? `演示验证码：${data.demo_code}`
      : "验证码已发送";
    if (data.demo_code) {
      $("sms-code").value = data.demo_code;
    }
    let left = 60;
    button.textContent = `${left}s`;
    const timer = setInterval(() => {
      left -= 1;
      if (left <= 0) {
        clearInterval(timer);
        button.disabled = false;
        button.textContent = "发送";
      } else {
        button.textContent = `${left}s`;
      }
    }, 1000);
  } catch (error) {
    button.disabled = false;
    $("sms-hint").textContent = error.message;
    toast(error.message, true);
  }
}

async function loginSms(event) {
  event.preventDefault();
  const phone = $("sms-phone").value.trim();
  const code = $("sms-code").value.trim();
  try {
    const data = await api("/api/v1/auth/sms/verify", {
      method: "POST",
      body: { phone, code },
    });
    state.token = data.access_token;
    localStorage.setItem("autocut_token", state.token);
    $("user-name").textContent = data.user?.name || "Demo Owner";
    showApp();
  } catch (error) {
    $("sms-hint").textContent = error.message;
    toast(error.message, true);
  }
}

async function wechatLogin() {
  try {
    const data = await api("/api/v1/auth/wechat/url");
    window.open(data.url, "_blank", "width=520,height=640");
  } catch (error) {
    $("wechat-hint").textContent = error.message;
    toast(error.message, true);
  }
}

function logout() {
  state.token = "";
  localStorage.removeItem("autocut_token");
  showLogin();
}

function hardRefresh() {
  const url = new URL(location.href);
  url.searchParams.set("v", Date.now().toString());
  location.replace(url.toString());
}

async function loadMeta() {
  try {
    state.meta = await api("/api/v1/meta");
    $("env-badge").textContent = state.meta.demo_mode ? "demo" : "live";
    $("env-badge").classList.toggle("warn", Boolean(state.meta.demo_mode));
    $("demo-badge").hidden = !state.meta.demo_mode;
  } catch (error) {
    toast(error.message, true);
  }
}

function findNavGroup(view, moduleId = "") {
  return NAV_GROUPS.find((group) =>
    group.tabs.some((tab) =>
      tab.view === view && (tab.view !== "module" || tab.module === moduleId)
    )
  );
}

function renderGroupTabs(group, view, moduleId) {
  const node = $("group-tabs");
  if (!group || group.tabs.length <= 1) {
    node.hidden = true;
    node.innerHTML = "";
    return;
  }
  node.hidden = false;
  node.innerHTML = group.tabs.map((tab) => {
    const active = tab.view === view
      && (tab.view !== "module" || tab.module === moduleId);
    return `<button type="button" class="group-tab ${active ? "active" : ""}"
      data-tab-view="${esc(tab.view)}"
      ${tab.module ? `data-tab-module="${esc(tab.module)}"` : ""}>${esc(tab.label)}</button>`;
  }).join("");
}

function switchGroup(groupId) {
  const group = NAV_GROUPS.find((item) => item.id === groupId);
  if (!group) return;
  const current = group.tabs.find((tab) =>
    tab.view === state.view
    && (tab.view !== "module" || tab.module === state.module)
  );
  const tab = current || group.tabs[0];
  switchView(tab.view, tab.module);
}

function switchView(view, moduleId) {
  state.view = view;
  if (view === "module" && moduleId) {
    state.module = moduleId;
  }
  const activeModule = view === "module" ? state.module : "";
  const group = findNavGroup(view, activeModule);
  const hash = view === "module" ? `#module/${state.module}` : `#${view}`;
  if (location.hash !== hash) {
    history.replaceState(null, "", hash);
  }
  document.querySelectorAll(".nav-item").forEach((node) => {
    node.classList.toggle("active", node.dataset.group === group?.id);
  });
  document.querySelectorAll(".view").forEach((node) => {
    node.hidden = node.id !== `view-${view}`;
  });
  const [title, subtitle] = VIEW_META[view] || VIEW_META.workspace;
  $("view-title").textContent = title;
  $("view-subtitle").textContent = subtitle;
  $("artifact-panel").hidden = true;
  renderGroupTabs(group, view, activeModule);

  if (view === "projects") loadProjects();
  if (view === "workspace") loadChatOptions();
  if (view === "scripts") {
    loadProjects();
    loadKbOptions();
    loadScriptStyleOptions();
    loadScripts();
  }
  if (view === "trends") {
    loadTrendSources();
    toggleCustomTrendLimit();
    if (!state.trends.length) loadTrends();
  }
  if (view === "calendar") {
    loadProjects();
    loadCalendar();
  }
  if (view === "assets") {
    loadProjects();
    loadAssets();
  }
  if (view === "brand") loadBrandKit();
  if (view === "style") loadStyles();
  if (view === "edit") loadEdit();
  if (view === "compliance") loadCompliance();
  if (view === "publish") loadPublishing();
  if (view === "structure") loadStructure();
  if (view === "module") openModule(state.module);
  if (view === "runs") loadJobs();
  if (view === "knowledge") loadKnowledge();
  if (view === "billing") loadBilling();
  if (view === "settings") loadSettingsPage();
  if (view === "admin") loadAdmin();
}

async function sendChat() {
  const input = $("chat-input");
  const message = input.value.trim();
  if (!message) {
    toast("先输入需求");
    return;
  }

  appendChatMessage("user", message);
  input.value = "";
  const button = $("send-chat");
  button.disabled = true;
  try {
    const data = await api("/api/v1/chat", {
      method: "POST",
      body: {
        message,
        conversation_id: state.chatConversationId || null,
        project_id: state.projectId || null,
        knowledge_base_id: $("chat-kb").value || null,
        model: $("chat-model").value || null,
      },
    });
    state.chatConversationId = data.conversation_id;
    $("plan-empty").hidden = true;
    $("plan-result").hidden = false;
    $("plan-intent").textContent = data.tool || data.intent?.name || "-";
    $("plan-confidence").textContent = data.intent?.confidence ?? "-";
    $("plan-skill").textContent = data.tool || data.plan?.skill || "-";
    $("plan-workflow").textContent = data.plan?.workflow || "无";
    $("plan-reply").textContent = data.reply || "";
    appendChatMessage("assistant", data.reply || "", {
      tool: data.tool,
      files: data.files,
    });
  } catch (error) {
    appendChatMessage("assistant", `请求失败：${error.message}`, { tool: "error" });
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

function appendChatMessage(role, text, meta = {}) {
  const node = document.createElement("div");
  node.className = `msg ${role}`;
  const tool = meta.tool ? `<span class="pill muted">${esc(meta.tool)}</span>` : "";
  const files = (meta.files || [])
    .map((file) => `<a href="${file.url}" target="_blank" rel="noreferrer">${esc(file.name)}</a>`)
    .join("");
  node.innerHTML = `
    <div class="msg-meta">${role === "user" ? "你" : "云流影"} ${tool}</div>
    <div class="msg-body">${esc(text)}</div>
    ${files ? `<div class="file-links">${files}</div>` : ""}`;
  $("chat-thread").appendChild(node);
  $("chat-thread").scrollTop = $("chat-thread").scrollHeight;
}

async function loadChatOptions() {
  $("chat-project").textContent = state.projectName || "未选择项目";
  try {
    if (!Object.keys(state.modelDefaults).length) await loadModelDefaults();
    const catalog = await ensureCatalog();
    const defaultRef = state.modelDefaults.chat || "";
    const autoRef = state.autoModels.chat || "";
    const options = [];
    for (const provider of catalog) {
      if (!(provider.capabilities || []).includes("chat")) continue;
      if (provider.status !== "ready") continue;
      if (!(provider.wired_capabilities || []).includes("chat")) continue;
      for (const model of provider.chat_models || []) {
        const value = `${provider.provider}:${model}`;
        const providerName = PROVIDER_TEXT[provider.provider] || provider.provider;
        options.push({
          value,
          label: `${value === defaultRef ? "✓ 默认 · " : ""}${providerName} · ${model}`,
        });
      }
    }
    $("chat-model").innerHTML = `<option value="">自动（最便宜可用）</option>`
      + options
        .map((option) => `<option value="${esc(option.value)}">${esc(option.label)}</option>`)
        .join("");
    if (defaultRef && options.some((option) => option.value === defaultRef)) {
      $("chat-model").value = defaultRef;
    }
    $("chat-model-hint").textContent = defaultRef
      ? `当前默认：${modelRefLabel(defaultRef)}`
      : autoRef
        ? `自动使用：${modelRefLabel(autoRef)}（最便宜可用）`
        : "当前没有可用模型，请先配置 API Key";
    const kbs = await api("/api/v1/knowledge-bases");
    $("chat-kb").innerHTML = `<option value="">不使用</option>`
      + (kbs.items || [])
        .map((item) => `<option value="${esc(item.id)}">${esc(item.name)}</option>`)
        .join("");
  } catch {
    // chat options are optional
  }
}

async function runPrompt() {
  const button = $("run-prompt");
  button.disabled = true;
  try {
    const data = await api("/api/v1/skills/prompt", {
      method: "POST",
      body: {
        product: $("prompt-product").value.trim(),
        platform: $("prompt-platform").value,
        style: $("prompt-style").value.trim(),
      },
    });
    const output = $("prompt-output");
    output.hidden = false;
    output.textContent = data.prompt || "";
    $("view-prompt-output").hidden = false;
    $("copy-prompt-output").hidden = false;
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function loadProjects() {
  try {
    const [data, styles] = await Promise.all([
      api("/api/v1/projects"),
      api("/api/v1/styles"),
    ]);
    const items = data.items || [];
    state.projects = items;
    state.styles = styles.items || [];
    const styleOptions = `<option value="">企业默认风格</option><option value="__custom__">自定义风格</option>`
      + state.styles
        .map((style) => `<option value="${esc(style.id)}">${esc(style.name)}</option>`)
        .join("");
    $("project-style").innerHTML = styleOptions;
    $("project-style-current").innerHTML = styleOptions;
    $("project-empty").hidden = items.length > 0;
    $("project-list").innerHTML = items.map((item) => `
      <li class="list-item selectable ${item.id === state.projectId ? "selected" : ""}"
          data-project="${esc(item.id)}" data-name="${esc(item.name)}">
        ${bulkCheckbox("projects", item.id, item.name)}
        <span class="list-main">
          <span>${esc(item.name)}</span>
          <span class="list-meta">${esc(item.aspect_ratio)} · ${esc(item.custom_style ? "自定义风格" : (item.style_name || "企业默认风格"))} · ${esc(item.asset_count)} 素材 · ${esc(item.script_count)} 脚本</span>
        </span>
        <span class="row">
          <span class="pill ${item.status === "active" ? "" : "muted"}">${esc(item.status)}</span>
          <button type="button" class="btn ghost small danger row-delete" data-delete-project="${esc(item.id)}">删除</button>
        </span>
      </li>`).join("");

    if (!items.some((item) => item.id === state.projectId)) {
      state.projectId = "";
      $("script-project").textContent = "未选择项目";
      $("asset-project").textContent = "未选择项目";
      $("calendar-project").textContent = "未选择项目";
      state.scripts = [];
      state.assets = [];
      $("asset-list").innerHTML = "";
      $("asset-empty").hidden = false;
      $("asset-empty").textContent = "先在项目页选择或创建项目";
      $("script-list").innerHTML = "";
      $("script-empty").hidden = false;
      $("script-empty").textContent = "还没有脚本";
      updateBulkBar("assets");
      updateBulkBar("scripts");
    }
    if (!state.projectId && items.length) {
      selectProject(items[0].id, items[0].name);
    } else if (state.projectId) {
      const current = items.find((item) => item.id === state.projectId);
      if (current) {
        $("project-current-label").textContent = `当前项目：${current.name}`;
        $("project-style-current").value = current.custom_style ? "__custom__" : (current.style_id || "");
        $("project-custom-style-current").value = current.custom_style || "";
      }
    }
    toggleProjectCustom("project-style", "project-custom-wrap");
    toggleProjectCustom("project-style-current", "project-custom-current-wrap");
    updateBulkBar("projects");
  } catch (error) {
    toast(error.message, true);
  }
}

function selectProject(id, name) {
  state.projectId = id;
  state.projectName = name || id;
  const project = state.projects.find((item) => item.id === id);
  $("chat-project").textContent = name || id;
  $("script-project").textContent = name || id;
  $("asset-project").textContent = name || id;
  $("calendar-project").textContent = name || id;
  $("project-current-label").textContent = `当前项目：${name || id}`;
  $("project-style-current").value = project?.custom_style ? "__custom__" : (project?.style_id || "");
  $("project-custom-style-current").value = project?.custom_style || "";
  toggleProjectCustom("project-style-current", "project-custom-current-wrap");
  document.querySelectorAll("#project-list [data-project]").forEach((node) => {
    node.classList.toggle("selected", node.dataset.project === id);
  });
  if (state.view === "scripts") loadScripts();
  if (state.view === "assets") loadAssets();
  if (state.view === "edit") loadEdit();
  if (state.view === "structure") loadStructure();
}

async function createProject() {
  const name = $("project-name").value.trim();
  if (!name) {
    toast("先输入项目名称");
    return;
  }
  const isCustom = $("project-style").value === "__custom__";
  const customStyle = isCustom ? $("project-custom-style").value.trim() : "";
  if (isCustom && !customStyle) {
    toast("请输入自定义风格描述");
    return;
  }
  try {
    const project = await api("/api/v1/projects", {
      method: "POST",
      body: {
        name,
        aspect_ratio: $("project-aspect").value,
        style_id: isCustom ? "" : $("project-style").value,
        custom_style: customStyle,
      },
    });
    $("project-name").value = "";
    state.projectId = "";
    toast("项目已创建");
    await loadProjects();
    selectProject(project.id, project.name);
  } catch (error) {
    toast(error.message, true);
  }
}

async function saveProjectStyle() {
  if (!state.projectId) {
    toast("先选择一个项目");
    return;
  }
  const isCustom = $("project-style-current").value === "__custom__";
  const customStyle = isCustom ? $("project-custom-style-current").value.trim() : "";
  if (isCustom && !customStyle) {
    toast("请输入自定义风格描述");
    return;
  }
  const button = $("save-project-style");
  button.disabled = true;
  try {
    await api(`/api/v1/projects/${state.projectId}`, {
      method: "PATCH",
      body: {
        style_id: isCustom ? "" : $("project-style-current").value,
        custom_style: customStyle,
      },
    });
    await loadProjects();
    selectProject(state.projectId, state.projectName);
    toast("项目风格已更新");
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

function toggleProjectCustom(selectId, wrapId) {
  $(wrapId).hidden = $(selectId).value !== "__custom__";
}

async function loadKbOptions() {
  try {
    const data = await api("/api/v1/knowledge-bases");
    const items = data.items || [];
    $("script-kb").innerHTML = `<option value="">不使用</option>`
      + items.map((item) => `<option value="${esc(item.id)}">${esc(item.name)}</option>`).join("");
  } catch {
    // knowledge base selection is optional
  }
}

async function loadScripts() {
  try {
    const suffix = state.projectId
      ? `?project_id=${encodeURIComponent(state.projectId)}`
      : "";
    const data = await api(`/api/v1/scripts${suffix}`);
    const items = data.items || [];
    state.scripts = items;
    renderScriptList();
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadScriptStyleOptions() {
  const select = $("script-style");
  if (!select) return;
  try {
    const data = await api("/api/v1/script-styles");
    state.scriptStyles = data.items || [];
    const current = state.scriptStyleId || select.value;
    select.innerHTML = state.scriptStyles
      .map((style) => `<option value="${esc(style.id)}">${esc(style.name)}</option>`)
      .join("") + `<option value="__custom__">自定义风格...</option>`;
    if (state.scriptStyles.some((style) => style.id === current)) {
      select.value = current;
    } else if (state.scriptStyles.length) {
      select.value = state.scriptStyles[0].id;
    }
    state.scriptStyleId = select.value;
    toggleScriptCustomStyle();
  } catch (error) {
    toast(error.message, true);
  }
}

function toggleScriptCustomStyle() {
  const select = $("script-style");
  const wrap = $("script-custom-style-wrap");
  if (!select || !wrap) return;
  wrap.hidden = select.value !== "__custom__";
  if (!wrap.hidden) $("script-custom-style").focus();
}

function selectedScriptStyle() {
  const select = $("script-style");
  if (select.value === "__custom__") {
    return $("script-custom-style").value.trim();
  }
  const style = state.scriptStyles.find((item) => item.id === select.value);
  if (style) return `${style.name}：${style.prompt}`;
  return select.selectedOptions[0]?.textContent?.trim() || "";
}

function toggleScriptCustomPlatform() {
  const custom = $("script-platform").value === "__custom__";
  $("script-custom-platform-wrap").hidden = !custom;
  if (custom) $("script-custom-platform").focus();
}

function selectedScriptPlatform() {
  const select = $("script-platform");
  if (select.value === "__custom__") {
    return $("script-custom-platform").value.trim();
  }
  return select.value;
}

function renderScriptList() {
  const query = $("script-search").value.trim().toLowerCase();
  const items = state.scripts.filter((item) =>
    !query
    || String(item.title || "").toLowerCase().includes(query)
    || String(item.body || "").toLowerCase().includes(query)
  );
  $("script-empty").hidden = items.length > 0;
  $("script-empty").textContent = state.scripts.length
    ? "没有匹配的脚本"
    : "还没有脚本";
  $("script-list").innerHTML = items.map((item) => `
      <li class="list-item stacked script-item" data-script-id="${esc(item.id)}">
        <div class="hit-meta">
          <span class="row">${bulkCheckbox("scripts", item.id, item.title)}<span>${esc(item.title)}</span></span>
          <span class="muted">${esc(formatTime(item.created_at))}</span>
        </div>
        <div class="hit-snippet">${esc(snippet(item.body, 140))}</div>
        <div class="script-actions">
          <button type="button" class="btn ghost small" data-storyboard-script="${esc(item.id)}">生成分镜</button>
          <button type="button" class="btn ghost small" data-copy-script="${esc(item.id)}">复制</button>
          <button type="button" class="btn ghost small" data-download-script="${esc(item.id)}">下载</button>
          <button type="button" class="btn small" data-open-script="${esc(item.id)}">查看全文</button>
          <button type="button" class="btn ghost small danger row-delete" data-delete-script="${esc(item.id)}">删除</button>
        </div>
      </li>`).join("");
  updateBulkBar("scripts");
}

async function generateScript() {
  const button = $("generate-script");
  const platform = selectedScriptPlatform();
  if (!platform) {
    toast("请选择平台或填写自定义平台");
    return;
  }
  const style = selectedScriptStyle();
  if (!style) {
    toast("请先选择风格或填写自定义风格");
    return;
  }
  button.disabled = true;
  try {
    const data = await api("/api/v1/scripts/generate", {
      method: "POST",
      body: {
        product: $("script-product").value.trim(),
        platform,
        style,
        brief: $("script-brief").value.trim(),
        project_id: state.projectId || null,
        knowledge_base_id: $("script-kb").value || null,
      },
    });
    state.lastScript = data.script || null;
    $("script-output-wrap").hidden = false;
    $("script-output").textContent = data.script?.body || "";
    toast(data.shell ? "已用模板生成" : "模型生成完成");
    loadScripts();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function expandScriptTopics() {
  const product = $("script-product").value.trim();
  if (!product) {
    toast("先填写产品或主题");
    return;
  }
  const button = $("expand-script-topics");
  button.disabled = true;
  button.textContent = "拓展中...";
  try {
    const data = await api("/api/v1/scripts/topics", {
      method: "POST",
      body: {
        product,
        platform: selectedScriptPlatform(),
        style: selectedScriptStyle(),
        brief: $("script-brief").value.trim(),
      },
    });
    state.scriptTopics = data.items || [];
    renderScriptTopics();
    toast(data.shell ? "已生成基础选题" : "AI 选题已生成");
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "AI 拓展选题";
  }
}

function renderScriptTopics() {
  const items = state.scriptTopics || [];
  $("script-topic-panel").hidden = items.length === 0;
  $("script-topic-list").innerHTML = items.map((item, index) => `
    <li class="list-item stacked">
      <div class="hit-meta">
        <b>${esc(item.title)}</b>
        ${item.format ? `<span class="pill">${esc(item.format)}</span>` : ""}
      </div>
      ${item.angle ? `<div class="hit-snippet">角度：${esc(item.angle)}</div>` : ""}
      ${item.hook ? `<div class="hit-snippet">钩子：${esc(item.hook)}</div>` : ""}
      <div class="row end">
        <button type="button" class="btn ghost small" data-use-script-topic="${index}">用这个选题</button>
      </div>
    </li>`).join("");
}

function useScriptTopic(index) {
  const item = state.scriptTopics[index];
  if (!item) return;
  $("script-brief").value = [
    `选题：${item.title}`,
    item.angle ? `切入角度：${item.angle}` : "",
    item.hook ? `开头钩子：${item.hook}` : "",
  ].filter(Boolean).join("；");
  $("script-brief").focus();
  toast("选题已带入任务描述");
}

async function loadTrendSources(preferredId = "") {
  try {
    const data = await api("/api/v1/trends/sources");
    const items = data.items || [];
    state.trendSources = items;
    const select = $("trend-source");
    const current = preferredId || select.value || state.trendSource;
    select.innerHTML = items
      .map((item) => `<option value="${esc(item.id)}">${esc(item.name)}${item.custom ? "（自定义）" : ""}</option>`)
      .join("");
    if (items.some((item) => item.id === current)) {
      select.value = current;
    } else if (items.length) {
      select.value = items[0].id;
    }
    state.trendSource = select.value;
    updateTrendCustomActions();
  } catch {
    // static fallback options remain available
  }
}

function updateTrendCustomActions() {
  const source = state.trendSources.find((item) => item.id === $("trend-source").value);
  $("delete-custom-trend-source").hidden = !source?.custom;
}

function toggleCustomTrendLimit() {
  const custom = $("trend-limit").value === "__custom__";
  $("trend-custom-limit-wrap").hidden = !custom;
  if (custom) $("trend-custom-limit").focus();
}

function selectedTrendLimit() {
  const limitMode = $("trend-limit").value;
  const limit = limitMode === "__custom__"
    ? Number($("trend-custom-limit").value)
    : Number(limitMode);
  if (!Number.isInteger(limit) || limit < 1 || limit > 200) {
    toast("热点数量需要是 1–200 的整数", true);
    return null;
  }
  return limit;
}

function toggleCustomTrendForm(show) {
  const form = $("trend-custom-form");
  form.hidden = show === undefined ? !form.hidden : !show;
  if (!form.hidden) {
    $("trend-custom-name").focus();
  } else {
    $("trend-custom-name").value = "";
    $("trend-custom-url").value = "";
    $("trend-custom-hint").textContent = "系统会自动识别 RSS、JSON 或普通网页中的热点标题。";
  }
}

async function saveCustomTrendSource() {
  const name = $("trend-custom-name").value.trim();
  const url = $("trend-custom-url").value.trim();
  if (!name || !url) {
    toast("请填写平台名称和热点链接", true);
    return;
  }
  const button = $("save-custom-trend-source");
  button.disabled = true;
  $("trend-custom-hint").textContent = "正在校验并添加...";
  try {
    const created = await api("/api/v1/trends/custom-sources", {
      method: "POST",
      body: { name, url },
    });
    toggleCustomTrendForm(false);
    await loadTrendSources(created.id);
    state.trendSource = created.id;
    state.trends = [];
    await loadTrends(false);
    toast("自定义热点平台已添加");
  } catch (error) {
    $("trend-custom-hint").textContent = error.message;
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function deleteCustomTrendSource() {
  const sourceId = $("trend-source").value;
  const source = state.trendSources.find((item) => item.id === sourceId);
  if (!source?.custom) return;
  if (!window.confirm(`确定删除自定义平台“${source.name}”吗？`)) return;
  try {
    await api(`/api/v1/trends/custom-sources/${sourceId}`, { method: "DELETE" });
    state.trends = [];
    await loadTrendSources();
    state.trendSource = $("trend-source").value;
    await loadTrends(false);
    toast("自定义热点平台已删除");
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadTrends(force = false, silent = false) {
  const button = $("load-trends");
  const source = $("trend-source").value;
  const limit = selectedTrendLimit();
  if (limit === null) return;
  state.trendRelated = null;
  state.trendSuggestions = [];
  $("clear-trend-related").hidden = true;
  state.trendSource = source;
  if (!silent) {
    button.disabled = true;
    $("trend-status").textContent = "正在获取热点...";
  }
  try {
    const query = new URLSearchParams({
      source,
      limit: String(limit),
      refresh: force ? "true" : "false",
    });
    const data = await api(`/api/v1/trends?${query.toString()}`);
    state.trends = data.items || [];
    state.trendSuggestions = [];
    renderTrends();
    renderTrendSuggestions();
    const cacheLabel = data.stale ? "最近成功快照" : (data.cached ? "缓存" : "实时");
    $("trend-status").textContent = `${data.source_name} · 共 ${data.items.length} 条 · ${cacheLabel} · 更新于 ${formatTime(data.updated_at)} · 系统每日自动刷新`;
  } catch (error) {
    if (!silent) {
      state.trends = [];
      renderTrends();
      $("trend-status").textContent = error.message;
      toast(error.message, true);
    }
  } finally {
    if (!silent) button.disabled = false;
  }
}

async function loadRelatedTrends(silent = false) {
  const direction = $("trend-direction").value.trim();
  if (!direction) {
    toast("先输入内容方向", true);
    $("trend-direction").focus();
    return;
  }
  const limit = selectedTrendLimit();
  if (limit === null) return;
  const button = $("search-related-trends");
  if (!silent) {
    button.disabled = true;
    $("trend-status").textContent = `正在查询与“${direction}”相关的热点...`;
  }
  try {
    const query = new URLSearchParams({
      direction,
      limit: String(limit),
      use_ai: $("trend-ai-expand").checked ? "true" : "false",
    });
    const data = await api(`/api/v1/trends/related?${query.toString()}`);
    state.trendRelated = data;
    const items = data.items || [];
    state.trends = items;
    state.trendSuggestions = data.ai_suggestions || [];
    $("clear-trend-related").hidden = false;
    renderTrends();
    renderTrendSuggestions();
    const keywordList = data.ai_keywords?.length ? data.ai_keywords : (data.keywords || []);
    const keywords = keywordList.slice(0, 6).join("、");
    const expandLabel = data.ai_expanded ? `AI 扩展 ${data.ai_keywords.length} 个词` : "本地关键词匹配";
    $("trend-status").textContent = items.length || state.trendSuggestions.length
      ? `方向“${data.direction}” · 热榜匹配 ${items.length} 条 · AI 选题 ${state.trendSuggestions.length} 个 · 覆盖 ${data.source_count} 个平台 · ${expandLabel} · 关联词：${keywords}`
      : `方向“${data.direction}”暂时没有匹配到的热点或选题，可以换个说法再试`;
  } catch (error) {
    if (!silent) {
      $("trend-status").textContent = error.message;
      toast(error.message, true);
    }
  } finally {
    if (!silent) button.disabled = false;
  }
}

function clearTrendRelated() {
  state.trendRelated = null;
  state.trendSuggestions = [];
  $("clear-trend-related").hidden = true;
  state.trends = [];
  renderTrendSuggestions();
  loadTrends(false);
}

function refreshTrends() {
  if (state.trendRelated) loadRelatedTrends();
  else loadTrends(true);
}

function renderTrends() {
  const items = state.trends || [];
  $("trend-empty").hidden = items.length > 0;
  if (!items.length) {
    $("trend-empty").textContent = state.trendRelated && state.trendSuggestions.length
      ? "今天热榜没有直接匹配的热点，下面是根据方向生成的选题参考。"
      : "暂无热点数据";
  }
  $("trend-list").innerHTML = items.map((item, index) => {
    const hot = Number(item.hot) > 0 ? Number(item.hot).toLocaleString() : "-";
    const hotText = hot === "-" ? "" : ` · ${hot} 热度`;
    const matched = Array.isArray(item.matched_keywords) && item.matched_keywords.length
      ? ` · 命中 ${item.matched_keywords.slice(0, 3).join("/")}`
      : "";
    const alsoOn = Array.isArray(item.also_on) && item.also_on.length
      ? ` · 另见 ${item.also_on.slice(0, 2).join("/")}`
      : "";
    return `
      <li class="list-item">
        <span class="list-main">
          <span class="trend-title-row">
            <span class="trend-rank" title="实时热榜第 ${esc(item.rank)} 名">🔥${esc(item.rank)}</span>
            <span class="trend-title">${esc(item.title)}</span>
          </span>
          <span class="list-meta">${esc(item.source_name)}${esc(hotText)}${esc(matched)}${esc(alsoOn)}</span>
        </span>
        <span class="row">
          <a href="${esc(item.url)}" target="_blank" rel="noreferrer">查看</a>
          <button type="button" class="btn ghost small" data-copy-trend="${index}">复制</button>
          <button type="button" class="btn small" data-use-trend="${index}">写脚本</button>
        </span>
      </li>`;
  }).join("");
}

function renderTrendSuggestions() {
  const items = state.trendSuggestions || [];
  $("trend-suggestions").hidden = items.length === 0;
  $("trend-suggestion-list").innerHTML = items.map((item, index) => `
    <li class="list-item stacked">
      <div class="hit-meta">
        <b>${esc(item.title)}</b>
        ${item.format ? `<span class="pill">${esc(item.format)}</span>` : ""}
      </div>
      ${item.angle ? `<div class="hit-snippet">切入角度：${esc(item.angle)}</div>` : ""}
      ${item.hook ? `<div class="hit-snippet">开头钩子：${esc(item.hook)}</div>` : ""}
      <div class="row end">
        <button type="button" class="btn ghost small" data-copy-suggestion="${index}">复制选题</button>
        <button type="button" class="btn small" data-use-suggestion="${index}">用这个选题写脚本</button>
      </div>
    </li>`).join("");
}

function useTrendForScript(index) {
  const item = state.trends[index];
  if (!item) return;
  switchView("scripts");
  $("script-product").value = item.title;
  const platformMap = {
    weibo: "微博",
    zhihu: "知乎",
    bilibili: "B站",
    baidu: "百度",
    douyin: "抖音",
    toutiao: "今日头条",
  };
  const target = platformMap[item.source] || "抖音";
  const platformSelect = $("script-platform");
  const exists = [...platformSelect.options].some((option) => option.value === target);
  if (exists) {
    platformSelect.value = target;
  } else {
    platformSelect.value = "__custom__";
    $("script-custom-platform").value = target;
  }
  toggleScriptCustomPlatform();
  $("script-product").focus();
  toast("热点已带入文案生成");
}

function useTrendSuggestion(index) {
  const item = state.trendSuggestions[index];
  if (!item) return;
  switchView("scripts");
  $("script-product").value = item.title;
  const source = state.trendSources.find((entry) => entry.id === $("trend-source").value);
  const platform = source?.custom ? source.name : ({
    weibo: "微博",
    zhihu: "知乎",
    bilibili: "B站",
    baidu: "百度",
    douyin: "抖音",
    toutiao: "今日头条",
  }[$("trend-source").value] || "抖音");
  const platformSelect = $("script-platform");
  const exists = [...platformSelect.options].some((option) => option.value === platform);
  if (exists) {
    platformSelect.value = platform;
  } else {
    platformSelect.value = "__custom__";
    $("script-custom-platform").value = platform;
  }
  toggleScriptCustomPlatform();
  $("script-product").focus();
  toast("关联选题已带入文案生成");
}

function calendarStatusPill(status) {
  const text = CALENDAR_STATUS_TEXT[status] || status;
  const kind = status === "done" ? "ok" : (status === "in_progress" ? "warn" : "muted");
  return `<span class="pill ${kind}">${esc(text)}</span>`;
}

async function loadCalendar() {
  try {
    const data = await api("/api/v1/content-calendar");
    state.calendarItems = data.items || [];
    $("calendar-empty").hidden = state.calendarItems.length > 0;
    $("calendar-list").innerHTML = state.calendarItems.map((item) => `
      <li class="list-item stacked">
        <div class="hit-meta">
          <span class="row">
            ${bulkCheckbox("calendar", item.id, item.title)}
            <b>${esc(item.plan_date)}</b>
            <span>${esc(item.title)}</span>
          </span>
          ${calendarStatusPill(item.status)}
        </div>
        ${item.angle ? `<div class="hit-snippet">角度：${esc(item.angle)}</div>` : ""}
        ${item.hook ? `<div class="hit-snippet">钩子：${esc(item.hook)}</div>` : ""}
        <div class="hit-meta">
          <span class="muted">${esc(item.platform)} · ${esc(item.format || "口播")}</span>
          <span class="row">
            <select data-calendar-status="${esc(item.id)}">
              ${Object.entries(CALENDAR_STATUS_TEXT).map(([value, label]) =>
                `<option value="${esc(value)}" ${value === item.status ? "selected" : ""}>${esc(label)}</option>`
              ).join("")}
            </select>
            <button type="button" class="btn ghost small" data-calendar-script="${esc(item.id)}">写脚本</button>
            <button type="button" class="btn ghost small danger row-delete" data-delete-calendar="${esc(item.id)}">删除</button>
          </span>
        </div>
      </li>`).join("");
    updateBulkBar("calendar");
  } catch (error) {
    toast(error.message, true);
  }
}

async function generateCalendar() {
  const direction = $("calendar-direction").value.trim();
  if (!direction) {
    toast("先填写内容方向");
    $("calendar-direction").focus();
    return;
  }
  const startDate = $("calendar-start").value || new Date().toISOString().slice(0, 10);
  const platforms = $("calendar-platforms").value
    .split(/[,，、]/)
    .map((item) => item.trim())
    .filter(Boolean);
  const button = $("generate-calendar");
  button.disabled = true;
  $("calendar-status").textContent = "正在生成内容计划...";
  try {
    const data = await api("/api/v1/content-calendar/generate", {
      method: "POST",
      body: {
        direction,
        start_date: startDate,
        days: Number($("calendar-days").value),
        per_day: Number($("calendar-per-day").value),
        platforms,
        project_id: state.projectId || null,
      },
    });
    $("calendar-status").textContent = `已生成 ${data.count} 条内容计划`;
    toast("内容日历已生成");
    await loadCalendar();
  } catch (error) {
    $("calendar-status").textContent = error.message;
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function updateCalendarStatus(itemId, status) {
  try {
    await api(`/api/v1/content-calendar/${itemId}`, {
      method: "PATCH",
      body: { status },
    });
    toast("日历状态已更新");
    await loadCalendar();
  } catch (error) {
    toast(error.message, true);
  }
}

async function deleteCalendarItem(itemId) {
  if (!window.confirm("确定删除这条内容计划吗？")) return;
  try {
    await api(`/api/v1/content-calendar/${itemId}`, { method: "DELETE" });
    toast("内容计划已删除");
    await loadCalendar();
  } catch (error) {
    toast(error.message, true);
  }
}

function useCalendarItemForScript(itemId) {
  const item = state.calendarItems.find((entry) => entry.id === itemId);
  if (!item) return;
  switchView("scripts");
  $("script-product").value = item.title;
  const platformSelect = $("script-platform");
  const exists = [...platformSelect.options].some((option) => option.value === item.platform);
  if (exists) {
    platformSelect.value = item.platform;
  } else {
    platformSelect.value = "__custom__";
    $("script-custom-platform").value = item.platform;
  }
  toggleScriptCustomPlatform();
  $("script-product").focus();
  toast("选题已带入文案生成");
}

async function loadCompliance() {
  await loadComplianceOptions();
  await loadComplianceReports();
}

async function loadComplianceOptions() {
  try {
    const projects = await api("/api/v1/projects");
    const items = projects.items || [];
    $("compliance-project").innerHTML = `<option value="">不绑定项目</option>`
      + items.map((item) => `<option value="${esc(item.id)}">${esc(item.name)}</option>`).join("");
    if (state.projectId) $("compliance-project").value = state.projectId;
    await loadComplianceAssets($("compliance-project").value);
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadComplianceAssets(projectId) {
  const select = $("compliance-asset");
  if (!projectId) {
    select.innerHTML = `<option value="">只检查文案</option>`;
    return;
  }
  try {
    const data = await api(`/api/v1/projects/${projectId}/assets`);
    const videos = (data.items || []).filter((item) => item.kind === "video");
    select.innerHTML = `<option value="">只检查文案</option>`
      + videos.map((item) => `<option value="${esc(item.id)}">${esc(item.filename)}</option>`).join("");
  } catch (error) {
    toast(error.message, true);
  }
}

async function runComplianceCheck() {
  const text = $("compliance-text").value.trim();
  const assetId = $("compliance-asset").value;
  if (!text && !assetId) {
    toast("请填写文案或选择视频素材");
    return;
  }
  const button = $("run-compliance");
  button.disabled = true;
  $("compliance-status").textContent = "正在检查...";
  try {
    const report = await api("/api/v1/compliance/check", {
      method: "POST",
      body: {
        project_id: $("compliance-project").value || null,
        asset_id: assetId || null,
        platform: $("compliance-platform").value,
        text,
      },
    });
    renderComplianceResult(report);
    $("compliance-status").textContent = "质检完成";
    toast("质检完成");
    await loadComplianceReports();
  } catch (error) {
    $("compliance-status").textContent = error.message;
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

function renderComplianceResult(report) {
  const level = report.level || "warn";
  const levelNode = $("compliance-level");
  levelNode.textContent = `${COMPLIANCE_LEVEL_TEXT[level] || level} · ${report.score ?? 0} 分`;
  levelNode.className = `pill ${level === "pass" ? "ok" : (level === "fail" ? "bad" : "warn")}`;
  const issues = report.issues || [];
  const media = report.media
    ? `<div class="list-meta">视频：${esc(report.media.width)}x${esc(report.media.height)} · ${Number(report.media.duration || 0).toFixed(1)}s · ${report.media.has_audio ? "有音轨" : "无音轨"}</div>`
    : "";
  $("compliance-result").className = "";
  $("compliance-result").innerHTML = `
    <div class="hit-snippet">${esc(report.summary || "")}</div>
    ${media}
    ${issues.length ? issues.map((item) => `
      <div class="compliance-issue severity-${esc(item.severity)}">
        <div class="hit-meta">
          <b>${esc(item.category)}</b>
          <span class="pill ${item.severity === "critical" ? "bad" : (item.severity === "high" ? "warn" : "muted")}">${esc(item.severity)}</span>
        </div>
        <div>${esc(item.message)}</div>
        ${item.evidence ? `<div class="list-meta">命中：${esc(item.evidence)}</div>` : ""}
        <div class="hit-snippet">建议：${esc(item.suggestion)}</div>
      </div>`).join("") : `<div class="empty">未发现明显风险</div>`}`;
}

async function loadComplianceReports() {
  try {
    const data = await api("/api/v1/compliance/reports");
    state.complianceReports = data.items || [];
    $("compliance-report-empty").hidden = state.complianceReports.length > 0;
    $("compliance-report-list").innerHTML = state.complianceReports.map((item) => `
      <li class="list-item stacked" data-compliance-report="${esc(item.id)}">
        <div class="hit-meta">
          <span class="row">
            ${bulkCheckbox("complianceReports", item.id, item.summary || item.id)}
            <b>${esc(item.platform)} · ${esc(item.score)} 分</b>
            <span class="pill ${item.level === "pass" ? "ok" : (item.level === "fail" ? "bad" : "warn")}">${esc(COMPLIANCE_LEVEL_TEXT[item.level] || item.level)}</span>
          </span>
          <span class="muted">${esc(formatTime(item.created_at))}</span>
        </div>
        <div class="hit-snippet">${esc(item.summary || "")} · ${esc((item.issues || []).length)} 个问题</div>
        <div class="row end">
          <button type="button" class="btn ghost small" data-view-compliance="${esc(item.id)}">查看</button>
          <button type="button" class="btn ghost small danger row-delete" data-delete-compliance="${esc(item.id)}">删除</button>
        </div>
      </li>`).join("");
    updateBulkBar("complianceReports");
  } catch (error) {
    toast(error.message, true);
  }
}

async function deleteComplianceReport(reportId) {
  if (!window.confirm("确定删除这份质检报告吗？")) return;
  try {
    await api(`/api/v1/compliance/reports/${reportId}`, { method: "DELETE" });
    toast("质检报告已删除");
    await loadComplianceReports();
  } catch (error) {
    toast(error.message, true);
  }
}

function defaultPublishTime() {
  const value = new Date(Date.now() + 60 * 60 * 1000);
  const pad = (number) => String(number).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`;
}

async function loadPublishing() {
  if (!$("publish-scheduled-at").value) {
    $("publish-scheduled-at").value = defaultPublishTime();
  }
  await Promise.all([
    loadPublishAccounts(),
    loadPublishJobs(),
    loadPublishOptions(),
  ]);
}

async function loadPublishOptions() {
  try {
    const data = await api("/api/v1/projects");
    const items = data.items || [];
    $("publish-project").innerHTML = `<option value="">不绑定项目</option>`
      + items.map((item) => `<option value="${esc(item.id)}">${esc(item.name)}</option>`).join("");
    if (state.projectId) $("publish-project").value = state.projectId;
    await loadPublishAssets($("publish-project").value);
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadPublishAssets(projectId) {
  const select = $("publish-asset");
  if (!projectId) {
    select.innerHTML = `<option value="">不绑定素材</option>`;
    return;
  }
  try {
    const data = await api(`/api/v1/projects/${projectId}/assets`);
    select.innerHTML = `<option value="">不绑定素材</option>`
      + (data.items || []).map((item) => `<option value="${esc(item.id)}">${esc(item.filename)}</option>`).join("");
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadPublishAccounts() {
  try {
    const data = await api("/api/v1/publish/accounts");
    state.publishAccounts = data.items || [];
    $("publish-account-empty").hidden = state.publishAccounts.length > 0;
    $("publish-account").innerHTML = state.publishAccounts.length
      ? state.publishAccounts.map((item) => `<option value="${esc(item.id)}">${esc(item.platform)} · ${esc(item.name)}</option>`).join("")
      : `<option value="">先添加账号</option>`;
    $("publish-account-list").innerHTML = state.publishAccounts.map((item) => `
      <li class="list-item">
        ${bulkCheckbox("publishAccounts", item.id, item.name)}
        <span class="list-main">
          <span>${esc(item.platform)} · ${esc(item.name)}</span>
          <span class="list-meta">${esc(item.handle || "未填写账号标识")} · ${esc(item.followers)} 粉丝</span>
        </span>
        <span class="row">
          <span class="pill ${item.status === "active" ? "ok" : "muted"}">${esc(item.status)}</span>
          <button type="button" class="btn ghost small danger row-delete" data-delete-publish-account="${esc(item.id)}">删除</button>
        </span>
      </li>`).join("");
    updateBulkBar("publishAccounts");
  } catch (error) {
    toast(error.message, true);
  }
}

async function createPublishAccount() {
  const name = $("publish-account-name").value.trim();
  if (!name) {
    toast("先填写账号名称");
    return;
  }
  const button = $("create-publish-account");
  button.disabled = true;
  try {
    await api("/api/v1/publish/accounts", {
      method: "POST",
      body: {
        platform: $("publish-account-platform").value,
        name,
        handle: $("publish-account-handle").value.trim(),
        followers: Number($("publish-account-followers").value) || 0,
      },
    });
    $("publish-account-name").value = "";
    $("publish-account-handle").value = "";
    toast("发布账号已添加");
    await loadPublishAccounts();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function loadPublishJobs() {
  try {
    const data = await api("/api/v1/publish/jobs");
    state.publishJobs = data.items || [];
    $("publish-job-empty").hidden = state.publishJobs.length > 0;
    $("publish-job-list").innerHTML = state.publishJobs.map((item) => `
      <li class="list-item stacked">
        <div class="hit-meta">
          <span class="row">
            ${bulkCheckbox("publishJobs", item.id, item.title)}
            <b>${esc(item.title)}</b>
            <span class="pill ${item.status === "published" ? "ok" : (item.status === "manual_required" ? "warn" : "muted")}">${esc(PUBLISH_STATUS_TEXT[item.status] || item.status)}</span>
          </span>
          <span class="muted">${esc(formatTime(item.scheduled_at))}</span>
        </div>
        <div class="list-meta">${esc(item.platform)} · ${esc(item.account_name || "未绑定账号")}${item.result_url ? ` · <a href="${esc(item.result_url)}" target="_blank" rel="noreferrer">发布链接</a>` : ""}</div>
        ${item.error ? `<div class="hit-snippet">${esc(item.error)}</div>` : ""}
        <div class="row end">
          <button type="button" class="btn ghost small" data-run-publish="${esc(item.id)}">执行发布</button>
          <button type="button" class="btn ghost small" data-mark-published="${esc(item.id)}">标记已发布</button>
          <button type="button" class="btn ghost small" data-cancel-publish="${esc(item.id)}">取消</button>
          <button type="button" class="btn ghost small danger row-delete" data-delete-publish-job="${esc(item.id)}">删除</button>
        </div>
      </li>`).join("");
    updateBulkBar("publishJobs");
  } catch (error) {
    toast(error.message, true);
  }
}

async function createPublishJob() {
  const title = $("publish-title").value.trim();
  const accountId = $("publish-account").value;
  const scheduledAt = $("publish-scheduled-at").value;
  if (!title || !accountId || !scheduledAt) {
    toast("请填写标题、账号和发布时间", true);
    return;
  }
  const button = $("create-publish-job");
  button.disabled = true;
  try {
    await api("/api/v1/publish/jobs", {
      method: "POST",
      body: {
        title,
        scheduled_at: scheduledAt,
        account_id: accountId,
        project_id: $("publish-project").value || null,
        asset_id: $("publish-asset").value || null,
        notes: $("publish-notes").value.trim(),
      },
    });
    $("publish-title").value = "";
    $("publish-notes").value = "";
    toast("已加入发布队列");
    await loadPublishJobs();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function runPublishJob(jobId) {
  try {
    const job = await api(`/api/v1/publish/jobs/${jobId}/run`, { method: "POST" });
    toast(job.error || "已更新发布状态");
    await loadPublishJobs();
  } catch (error) {
    toast(error.message, true);
  }
}

async function markPublishJobPublished(jobId) {
  const url = window.prompt("填写发布后的链接，可留空：", "") ?? "";
  try {
    await api(`/api/v1/publish/jobs/${jobId}/published`, {
      method: "POST",
      body: { result_url: url.trim() },
    });
    toast("已标记为已发布");
    await loadPublishJobs();
  } catch (error) {
    toast(error.message, true);
  }
}

async function cancelPublishJob(jobId) {
  try {
    await api(`/api/v1/publish/jobs/${jobId}/cancel`, { method: "POST" });
    toast("发布计划已取消");
    await loadPublishJobs();
  } catch (error) {
    toast(error.message, true);
  }
}

async function deletePublishJob(jobId) {
  if (!window.confirm("确定删除这条发布计划吗？")) return;
  try {
    await api(`/api/v1/publish/jobs/${jobId}`, { method: "DELETE" });
    toast("发布计划已删除");
    await loadPublishJobs();
  } catch (error) {
    toast(error.message, true);
  }
}

async function deletePublishAccount(accountId) {
  if (!window.confirm("确定删除这个发布账号吗？")) return;
  try {
    await api(`/api/v1/publish/accounts/${accountId}`, { method: "DELETE" });
    toast("发布账号已删除");
    await loadPublishAccounts();
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadAssets() {
  if (!state.projectId) {
    state.assets = [];
    $("asset-list").innerHTML = "";
    $("asset-empty").hidden = false;
    $("asset-empty").textContent = "先在项目页选择或创建项目";
    updateBulkBar("assets");
    return;
  }
  try {
    const data = await api(`/api/v1/projects/${state.projectId}/assets`);
    const items = data.items || [];
    state.assets = items;
    $("asset-empty").hidden = items.length > 0;
    $("asset-empty").textContent = "还没有素材";
    $("asset-list").innerHTML = items.map((item) => {
      let meta = {};
      try {
        meta = JSON.parse(item.meta_json || "{}");
      } catch {
        meta = {};
      }
      const source = meta.url
        ? `<span class="list-meta">来源：${esc(meta.url)}</span>`
        : "";
      return `
        <li class="list-item">
          ${bulkCheckbox("assets", item.id, item.filename)}
          <span class="list-main">
            <span>${esc(item.filename)}</span>
            <span class="list-meta">${esc(item.kind)} · ${Math.max(1, Math.round(item.size_bytes / 1024))} KB</span>
            ${source}
          </span>
          <span class="row">
            <button type="button" class="btn ghost small" data-preview-asset="${esc(item.id)}">预览</button>
            <button type="button" class="btn ghost small" data-quality="${esc(item.id)}">质检</button>
            <a href="${mediaUrl(`/api/v1/projects/${state.projectId}/assets/${item.id}/file`)}" target="_blank" rel="noreferrer">下载</a>
            <button type="button" class="btn ghost small danger row-delete" data-delete-asset="${esc(item.id)}">删除</button>
          </span>
        </li>`;
    }).join("");
    updateBulkBar("assets");
  } catch (error) {
    toast(error.message, true);
  }
}

async function previewAssetFile(assetId) {
  const asset = state.assets.find((item) => item.id === assetId);
  if (!asset || !state.projectId) return;
  const url = mediaUrl(`/api/v1/projects/${state.projectId}/assets/${assetId}/file`);
  const filename = String(asset.filename || "素材");
  const lower = filename.toLowerCase();
  const body = $("asset-preview-body");
  $("asset-preview-title").textContent = filename;
  $("asset-preview-meta").textContent = `${asset.kind} · ${Math.max(1, Math.round(asset.size_bytes / 1024))} KB`;
  $("asset-preview-open").href = url;
  $("asset-preview-download").href = url;
  $("asset-preview-download").setAttribute("download", filename);
  body.innerHTML = `<p class="muted">加载中...</p>`;
  $("asset-preview-modal").hidden = false;

  try {
    if (asset.kind === "image" || /\.(png|jpe?g|webp|gif|svg|bmp)$/.test(lower)) {
      body.innerHTML = `<img class="preview-media" src="${url}" alt="${esc(filename)}" />`;
      return;
    }
    if (asset.kind === "video" || /\.(mp4|webm|mov|mkv|avi)$/.test(lower)) {
      body.innerHTML = `<p class="muted">正在检查视频编码，首次预览 H.265 视频可能需要转码...</p>`;
      await loadBrowserVideoPreview(assetId, body);
      return;
    }
    if (asset.kind === "audio" || /\.(mp3|wav|m4a|aac|flac|ogg)$/.test(lower)) {
      body.innerHTML = `<audio class="preview-media audio" controls preload="metadata" src="${url}"></audio>`;
      return;
    }
    if (/\.(txt|md|markdown|json|csv|srt|vtt|yaml|yml)$/.test(lower)) {
      const response = await fetch(url);
      if (!response.ok) throw new Error("素材内容读取失败");
      const text = await response.text();
      const limited = text.length > 1_000_000 ? `${text.slice(0, 1_000_000)}\n\n...内容过长，已截断` : text;
      body.innerHTML = `<pre class="output modal-output">${esc(limited)}</pre>`;
      return;
    }
    body.innerHTML = `<p class="muted">这个文件类型暂不支持内嵌预览，可以下载后用本地软件打开。</p>`;
  } catch (error) {
    body.innerHTML = `<p class="muted">${esc(error.message)}</p>`;
  }
}

async function loadBrowserVideoPreview(assetId, body) {
  if (!state.projectId) return;
  const statusUrl = `/api/v1/projects/${state.projectId}/assets/${assetId}/preview-status`;
  for (let attempt = 0; attempt < 150; attempt += 1) {
    if ($("asset-preview-modal").hidden) return;
    const data = await api(statusUrl);
    if (data.status === "ready") {
      body.innerHTML = `<video class="preview-media" controls autoplay preload="metadata" src="${data.url}"></video>`;
      return;
    }
    body.innerHTML = `<p class="muted">${esc(data.message || "正在生成兼容预览...")}</p>`;
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error("视频预览转码超时，请先下载原文件查看");
}

function closeAssetPreview() {
  $("asset-preview-body").innerHTML = "";
  $("asset-preview-modal").hidden = true;
}

async function uploadAsset() {
  if (!state.projectId) {
    toast("先选择项目");
    return;
  }
  const file = $("asset-file").files?.[0];
  if (!file) {
    toast("先选择文件");
    return;
  }
  const button = $("upload-asset");
  button.disabled = true;
  try {
    const form = new FormData();
    form.append("file", file);
    await api(`/api/v1/projects/${state.projectId}/assets`, {
      method: "POST",
      body: form,
    });
    $("asset-file").value = "";
    toast("素材已上传");
    loadAssets();
    loadProjects();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function previewAsset() {
  if (!state.projectId) {
    toast("先选择项目");
    return;
  }
  const url = $("asset-url").value.trim();
  if (!url) {
    toast("先粘贴链接");
    return;
  }

  const button = $("preview-asset");
  button.disabled = true;
  button.textContent = "解析中...";
  try {
    const data = await api(`/api/v1/projects/${state.projectId}/assets/import/preview`, {
      method: "POST",
      body: { url },
    });
    state.previewUrl = url;
    $("import-preview").hidden = false;
    $("preview-title").textContent = data.title || "素材预览";
    $("preview-kind").textContent = data.kind || "file";
    const size = data.size_bytes
      ? `${Math.max(1, Math.round(data.size_bytes / 1024))} KB`
      : "未知大小";
    const duration = data.duration
      ? `${Math.round(data.duration)} 秒`
      : "未知时长";
    $("preview-meta").textContent = `${size} · ${duration} · ${data.provider || ""}`;
    const thumb = $("preview-thumb");
    if (data.thumbnail) {
      thumb.src = data.thumbnail;
      thumb.hidden = false;
    } else {
      thumb.hidden = true;
      thumb.removeAttribute("src");
    }
  } catch (error) {
    $("import-hint").textContent = error.message;
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "解析链接";
  }
}

async function confirmImport() {
  if (!state.previewUrl) {
    toast("先解析链接");
    return;
  }
  const button = $("confirm-import");
  button.disabled = true;
  button.textContent = "下载中...";
  try {
    await api(`/api/v1/projects/${state.projectId}/assets/import`, {
      method: "POST",
      body: { url: state.previewUrl },
    });
    $("asset-url").value = "";
    $("import-preview").hidden = true;
    state.previewUrl = "";
    $("import-hint").textContent = "导入完成，素材已进入项目库。";
    toast("素材已导入");
    loadAssets();
    loadProjects();
  } catch (error) {
    $("import-hint").textContent = error.message;
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "下载到项目";
  }
}

function cancelImport() {
  state.previewUrl = "";
  $("import-preview").hidden = true;
}

async function checkAssetQuality(assetId) {
  if (!state.projectId) {
    toast("先选择项目");
    return;
  }
  try {
    const data = await api("/api/v1/quality/check", {
      method: "POST",
      body: { project_id: state.projectId, asset_id: assetId },
    });
    state.qualityAssetId = assetId;
    state.qualityRating = 0;
    state.qualityTags = new Set();
    $("quality-report").hidden = false;
    $("quality-score").textContent = `${data.score} 分`;
    $("quality-score").className = `pill ${data.passed ? "" : "bad"}`;
    $("quality-checks").innerHTML = (data.checks || []).map((check) => `
      <div class="list-item">
        <span>${esc(check.name)}</span>
        <span class="pill ${check.ok ? "" : "bad"}">${check.ok ? "通过" : "未通过"}</span>
        <span class="muted">${esc(check.detail || "")}</span>
      </div>`).join("") || `<div class="empty">没有检查项</div>`;
    $("quality-rating").querySelectorAll("button").forEach((button) => {
      button.classList.remove("selected");
    });
    $("quality-tags").querySelectorAll(".chip").forEach((chip) => {
      chip.classList.remove("selected");
    });
    $("quality-comment").value = "";
  } catch (error) {
    toast(error.message, true);
  }
}

async function submitQualityFeedback() {
  if (!state.qualityAssetId) {
    toast("先做一次质检");
    return;
  }
  if (!state.qualityRating) {
    toast("先选择评分");
    return;
  }
  try {
    await api("/api/v1/quality/feedback", {
      method: "POST",
      body: {
        project_id: state.projectId,
        asset_id: state.qualityAssetId,
        rating: state.qualityRating,
        tags: [...state.qualityTags],
        comment: $("quality-comment").value.trim(),
      },
    });
    toast("反馈已提交，会用于后续质量优化");
    $("quality-report").hidden = true;
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadEditModelOptions() {
  if (!$("edit-model")) return;
  try {
    if (!Object.keys(state.modelDefaults).length) await loadModelDefaults();
    const catalog = await ensureCatalog();
    const defaultRef = state.modelDefaults.chat || "";
    const autoRef = state.autoModels.chat || "";
    const saved = localStorage.getItem("autocut_edit_model") || defaultRef;
    const options = [`<option value="">自动（最便宜可用）</option>`];
    for (const provider of catalog) {
      const models = provider.chat_models || [];
      const wired = (provider.wired_capabilities || []).includes("chat");
      if (!wired || !models.length) continue;
      const providerName = PROVIDER_TEXT[provider.provider] || provider.provider;
      for (const model of models) {
        const value = `${provider.provider}:${model}`;
        options.push(
          `<option value="${esc(value)}" ${provider.configured ? "" : "disabled"} ${value === saved ? "selected" : ""}>`
          + `${value === defaultRef ? "✓ 默认 · " : ""}${esc(providerName)} · ${esc(model)}${provider.configured ? "" : "（未配置 Key）"}`
          + `</option>`,
        );
      }
    }
    $("edit-model").innerHTML = options.join("");
    $("edit-model-hint").textContent = defaultRef
      ? `当前默认：${modelRefLabel(defaultRef)}`
      : autoRef
        ? `自动使用：${modelRefLabel(autoRef)}（最便宜可用）`
        : "当前没有可用模型，请先配置 API Key";
  } catch {
    // keep the default option
  }
}

function loadEditAsrOptions(caps) {
  const select = $("edit-asr-model");
  if (!select) return;
  const saved = localStorage.getItem("autocut_edit_asr") || "cloud:";
  let selectedLabel = "";
  const options = (caps.asr_options || []).map((item) => {
    const value = `${item.provider}:${item.model || ""}`;
    if (value === saved) selectedLabel = item.label;
    return `<option value="${esc(value)}" ${item.ready ? "" : "disabled"} ${value === saved ? "selected" : ""}>`
      + `${value === saved ? "✓ 默认 · " : ""}${esc(item.label)}${item.ready ? "" : "（未安装）"}`
      + `</option>`;
  });
  select.innerHTML = options.join("") || `<option value="cloud:">云端 GLM-ASR</option>`;
  const hint = $("edit-asr-hint");
  if (hint) {
    hint.textContent = selectedLabel ? `当前默认：${selectedLabel}` : "使用云端默认识别模型";
  }
}

async function loadEdit() {
  try {
    const caps = await api("/api/v1/edit/capabilities");
    $("edit-mode").textContent = caps.ai_ready ? "AI 自动" : "规则切片";
    $("edit-mode").title = caps.reason || "";
    $("edit-mode").classList.toggle("warn", !caps.ffmpeg);
    $("edit-mode").classList.toggle("ok", Boolean(caps.ai_ready));
    if (caps.ai_ready) {
      $("edit-hint").textContent = "AI 自动剪辑已接通：按字幕句段和画面切点选段，单段时长不设固定上限";
    } else if (!caps.ffmpeg) {
      $("edit-hint").textContent = "FFmpeg 未安装，任务会失败；先安装 FFmpeg 再启动 worker";
    } else {
      $("edit-hint").textContent = caps.reason || "当前使用规则切片";
    }
    loadEditAsrOptions(caps);
    await loadEditModelOptions();
  } catch {
    // capability badge is best-effort
  }

  if (!state.projectId) {
    $("edit-project").textContent = "先在项目页创建项目";
    $("edit-asset").innerHTML = `<option value="">没有可用项目</option>`;
    $("edit-job-list").innerHTML = "";
    $("edit-job-empty").hidden = false;
    $("edit-job-empty").textContent = "还没有剪辑任务";
    return;
  }

  $("edit-project").textContent = state.projectName || state.projectId;
  try {
    const data = await api(`/api/v1/projects/${state.projectId}/assets`);
    state.assets = data.items || [];
    const videos = state.assets.filter((item) => item.kind === "video");
    $("edit-asset").innerHTML = videos.length
      ? videos.map((item) => `<option value="${esc(item.id)}">${esc(item.filename)}</option>`).join("")
      : `<option value="">先在素材页上传视频</option>`;
    await loadEditJobs();
  } catch (error) {
    toast(error.message, true);
  }
}

function editJobCount(job) {
  return job.segment_count
    || job.result?.select?.segments?.length
    || job.result?.cut?.clips?.length
    || job.params?.count
    || job.params?.max_clips
    || 0;
}

function editJobSourceStem(job) {
  const asset = state.assets.find((item) => item.id === job.params?.asset_id);
  const raw = job.source_name
    || job.params?.source_name
    || asset?.filename
    || String(job.input_path || "").split(/[\\/]/).pop()
    || "未命名素材";
  return String(raw).replace(/\.[^.]+$/, "") || "未命名素材";
}

function compactJobTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (number) => String(number).padStart(2, "0");
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function editJobSearchText(job) {
  return [
    editJobSourceStem(job),
    job.id,
    job.params?.brief || "",
    job.params?.model_ref || "",
    compactJobTime(job.created_at),
    `${editJobCount(job)}段`,
  ].join(" ").toLowerCase();
}

function workflowLabel(job) {
  if (job.workflow === "clip") {
    return job.params?.mode === "ai" ? "AI 成片" : "智能切片";
  }
  if (job.workflow === "quick_cut") return "规则切片";
  const labels = {
    subtitle: "字幕生成",
    render: "渲染导出",
    batch: "批量创作",
  };
  return labels[job.workflow] || job.workflow;
}

function jobSearchText(job) {
  return [
    editJobSearchText(job),
    workflowLabel(job),
    job.status,
    job.params?.brief || "",
  ].join(" ").toLowerCase();
}

async function loadEditJobs() {
  if (!state.projectId) return;
  try {
    const data = await api("/api/v1/jobs");
    const projectJobs = (data.items || []).filter(
      (job) => ["quick_cut", "clip"].includes(job.workflow)
        && job.params?.project_id === state.projectId,
    );
    state.editJobs = projectJobs;
    const keyword = $("edit-job-search").value.trim().toLowerCase();
    const items = keyword
      ? projectJobs.filter((job) => editJobSearchText(job).includes(keyword))
      : projectJobs;
    $("edit-job-empty").hidden = items.length > 0;
    $("edit-job-empty").textContent = keyword
      ? "没有匹配的剪辑任务"
      : "还没有剪辑任务";
    $("edit-job-list").innerHTML = items.map((job) => {
      const actualSegments = editJobCount(job);
      const source = editJobSourceStem(job);
      const model = job.params?.model_ref
        ? modelRefLabel(job.params.model_ref)
        : "自动模型";
      return `
      <li class="list-item stacked">
        <div class="hit-meta">
          <span><b>${esc(source)}</b> · ${esc(actualSegments)} 段 · ${esc(compactJobTime(job.created_at))}</span>
          <span>${statusPill(job.status)}</span>
        </div>
        <div class="hit-meta">
          <span class="muted">${job.params?.mode === "ai" ? "AI" : "规则"} · ${esc(model)} · ${esc(formatDuration(job.duration_ms))}</span>
          <code class="muted">${esc(job.id)}</code>
        </div>
        ${job.error ? `<div class="hit-snippet">${esc(snippet(job.error, 120))}</div>` : ""}
        ${job.params?.brief ? `<div class="hit-snippet">要求：${esc(snippet(job.params.brief, 100))}</div>` : ""}
        ${job.result?.select?.warning ? `<div class="hit-snippet">${esc(job.result.select.warning)}</div>` : ""}
        <div class="row end">
          ${job.status === "succeeded"
            ? `<button type="button" class="btn ghost small" data-timeline-job="${esc(job.id)}">时间轴</button>`
            : ""}
          ${(job.status === "failed" || job.status === "canceled")
            ? `<button type="button" class="btn ghost small" data-retry-edit="${esc(job.id)}">重试</button>`
            : ""}
        </div>
      </li>`;
    }).join("");
  } catch (error) {
    toast(error.message, true);
  }
}

async function retryEditJob(id) {
  try {
    await api(`/api/v1/jobs/${id}/retry`, { method: "POST" });
    toast("AI 成片已重新排队");
    await loadEditJobs();
  } catch (error) {
    toast(error.message, true);
  }
}

function timelineSeconds(value) {
  return `${Number(value || 0).toFixed(1).replace(/\.0$/, "")}s`;
}

function timelineVideoSrc() {
  const job = state.timelineJob;
  const projectId = job?.params?.project_id || "";
  const assetId = job?.params?.asset_id || "";
  if (!projectId || !assetId) return "";
  return mediaUrl(`/api/v1/projects/${projectId}/assets/${assetId}/file`);
}

function timelineVisibleSegments() {
  return state.timelineOnlyHighlight
    ? state.clipSegments.filter((item) => item.kind === "highlight")
    : state.clipSegments;
}

function timelineSelected() {
  return state.clipSegments.find((item) => item.id === state.timelineSelectedId) || null;
}

function timelineIndexOf(segmentId) {
  return state.clipSegments.findIndex((item) => item.id === segmentId);
}

async function loadTimelineSegments() {
  if (!state.timelineJobId) return;
  const data = await api(`/api/v1/jobs/${state.timelineJobId}/segments`);
  state.clipSegments = (data.items || []).sort(
    (left, right) => Number(left.seq) - Number(right.seq),
  );
  state.timelineHasAdjustments = Boolean(data.has_adjustments);
  if (!state.clipSegments.some((item) => item.id === state.timelineSelectedId)) {
    state.timelineSelectedId = state.clipSegments[0]?.id || "";
  }
  renderTimeline();
}

async function openTimeline(jobId) {
  const job = state.editJobs.find((item) => item.id === jobId) || null;
  state.timelineJobId = jobId;
  state.timelineJob = job;
  state.timelineSelectedId = "";
  state.timelineOnlyHighlight = false;
  state.timelineBatchMode = false;
  state.timelineCheckedIds = new Set();
  $("timeline-only-highlight").checked = false;
  $("timeline-batch-mode").checked = false;
  $("timeline-panel").hidden = false;

  const video = $("timeline-video");
  const source = timelineVideoSrc();
  if (source) {
    video.src = source;
    video.hidden = false;
    video.load();
  } else {
    video.removeAttribute("src");
    video.hidden = true;
  }
  $("timeline-subtitle").textContent = job
    ? `${job.params?.source_name || "当前素材"} · ${job.id}`
    : jobId;
  $("timeline-full-subtitles").href = mediaUrl(
    `/api/v1/jobs/${state.timelineJobId}/subtitles.txt`,
  );
  $("timeline-full-subtitles").download = timelineFullSubtitleName();
  try {
    await loadTimelineSegments();
    $("timeline-panel").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    toast(error.message, true);
  }
}

function closeTimeline() {
  $("timeline-panel").hidden = true;
  state.timelineJobId = "";
  state.timelineJob = null;
  state.clipSegments = [];
  state.timelineSelectedId = "";
  state.timelineCheckedIds = new Set();
  state.timelinePlayback = null;
  $("timeline-video").pause();
}

function renderTimeline() {
  const visible = timelineVisibleSegments();
  const selected = timelineSelected();
  const activeIds = new Set(state.clipSegments.map((item) => item.id));
  state.timelineCheckedIds = new Set(
    [...state.timelineCheckedIds].filter((id) => activeIds.has(id)),
  );
  if (selected && !visible.some((item) => item.id === selected.id)) {
    state.timelineSelectedId = visible[0]?.id || "";
  }
  const total = visible.reduce((sum, item) => sum + Number(item.duration || 0), 0);
  $("timeline-track").innerHTML = visible.map((segment) => {
    const index = state.clipSegments.findIndex((item) => item.id === segment.id) + 1;
    const isSelected = segment.id === state.timelineSelectedId;
    const isChecked = state.timelineCheckedIds.has(segment.id);
    const classes = [
      "timeline-segment",
      segment.kind === "highlight" ? "highlight" : "normal",
      segment.locked ? "locked" : "",
      isSelected ? "selected" : "",
      state.timelineBatchMode ? "has-check" : "",
      isChecked ? "checked" : "",
    ].filter(Boolean).join(" ");
    const duration = Math.max(0.01, Number(segment.duration || 0));
    return `
      <article class="${classes}" data-segment-id="${esc(segment.id)}"
        style="flex: ${duration} 1 0" title="${esc(segment.title || "")}">
        ${state.timelineBatchMode
          ? `<label class="timeline-block-check"><input type="checkbox" data-timeline-check="${esc(segment.id)}" ${isChecked ? "checked" : ""} /></label>`
          : ""}
        ${segment.locked ? "" : `<span class="timeline-handle" data-trim="start" data-segment-id="${esc(segment.id)}"></span>`}
        <div class="timeline-segment-body">
          <b>切片${String(index).padStart(2, "0")}</b>
          <span>${timelineSeconds(duration)}</span>
          <small>${esc(segment.title || "未命名片段")}</small>
        </div>
        ${segment.locked ? "" : `<span class="timeline-handle" data-trim="end" data-segment-id="${esc(segment.id)}"></span>`}
      </article>`;
  }).join("");

  $("timeline-empty").hidden = visible.length > 0;
  const highlights = state.clipSegments.filter((item) => item.kind === "highlight").length;
  const locked = state.clipSegments.filter((item) => item.locked).length;
  $("timeline-meta").innerHTML = `
    <div class="timeline-meta-line"><b>${esc(state.timelineJob?.params?.source_name || "素材")}</b><span>· ${state.clipSegments.length} 个片段</span></div>
    <div class="timeline-meta-line"><span>总时长 ${timelineSeconds(total)}</span><span>· 高光 ${highlights}</span><span>· 已锁定 ${locked}</span></div>
    <div class="timeline-meta-line">拖动色块两侧边缘可调整起止点；锁定后自动精简不会删除该片段。导出的字幕会保存到任务的 字幕/ 并出现在任务产物。</div>`;
  renderTimelineBatchBar();
  renderTimelineEditor();
  $("timeline-reset").hidden = !state.timelineHasAdjustments;
}

function timelineCheckedSegments() {
  return state.clipSegments.filter((item) => state.timelineCheckedIds.has(item.id));
}

function renderTimelineBatchBar() {
  const bar = $("timeline-batch-bar");
  bar.hidden = !state.timelineBatchMode;
  if (!state.timelineBatchMode) return;
  const selected = timelineCheckedSegments();
  $("timeline-batch-count").textContent = `已选 ${selected.length} 段`;
  $("timeline-batch-render").disabled = selected.length === 0;
  $("timeline-batch-subtitles").disabled = selected.length === 0;
}

function renderTimelineEditor() {
  const segment = timelineSelected();
  $("timeline-editor").hidden = !segment;
  if (!segment) return;
  $("timeline-export-result").innerHTML = "";
  const index = timelineIndexOf(segment.id);
  $("timeline-editor-title").textContent = `切片${String(index + 1).padStart(2, "0")}`;
  $("timeline-editor-badge").textContent = segment.kind === "highlight" ? "高光片段" : "普通片段";
  $("timeline-editor-badge").className = `pill ${segment.kind === "highlight" ? "warn" : "muted"}`;
  $("timeline-start").value = Number(segment.start).toFixed(1);
  $("timeline-end").value = Number(segment.end).toFixed(1);
  $("timeline-title").value = segment.title || "";
  $("timeline-subtitle-export").href = mediaUrl(
    `/api/v1/jobs/${state.timelineJobId}/segments/${segment.id}/subtitles.txt`,
  );
  $("timeline-subtitle-export").download = segmentSubtitleName(segment);
  updateTimelineDirtyState();
  $("timeline-start").disabled = Boolean(segment.locked);
  $("timeline-end").disabled = Boolean(segment.locked);
  $("timeline-lock").textContent = segment.locked ? "解锁" : "锁定";
  $("timeline-merge-next").disabled = index < 0 || index >= state.clipSegments.length - 1;
  $("timeline-unmerge").hidden = !(
    (segment.merged_from || []).length || segment.reason === "手动合并"
  );
  $("timeline-move-left").disabled = index <= 0;
  $("timeline-move-right").disabled = index < 0 || index >= state.clipSegments.length - 1;
  $("timeline-delete").disabled = Boolean(segment.locked);
  $("timeline-editor-hint").textContent = [
    segment.reason ? `切分原因：${segment.reason}` : "",
    segment.transcript ? `字幕：${snippet(segment.transcript, 160)}` : "",
  ].filter(Boolean).join("  ") || "没有额外说明";
}

function updateTimelineDirtyState() {
  const segment = timelineSelected();
  if (!segment) {
    $("timeline-save").hidden = true;
    $("timeline-cancel-edits").hidden = true;
    return;
  }
  const start = Number($("timeline-start").value);
  const end = Number($("timeline-end").value);
  const title = $("timeline-title").value.trim();
  const dirty = (
    !Number.isFinite(start)
    || !Number.isFinite(end)
    || Math.abs(start - Number(segment.start)) > 0.05
    || Math.abs(end - Number(segment.end)) > 0.05
    || title !== String(segment.title || "").trim()
  );
  $("timeline-save").hidden = !dirty;
  $("timeline-cancel-edits").hidden = !dirty;
}

function cancelTimelineSegmentEdits() {
  renderTimelineEditor();
  toast("未保存的修改已取消");
}

async function resetTimelineSegments() {
  if (!state.timelineJobId) return;
  if (!window.confirm("取消所有调整，恢复到 AI 原始切分结果？已生成的重剪文件不会删除。")) {
    return;
  }
  try {
    await api(`/api/v1/jobs/${state.timelineJobId}/segments/reset`, {
      method: "POST",
    });
    state.timelineSelectedId = "";
    state.timelineCheckedIds = new Set();
    state.timelineHasAdjustments = false;
    toast("已恢复到 AI 原始切分");
    await loadTimelineSegments();
  } catch (error) {
    toast(error.message, true);
  }
}

function playTimelineSegment() {
  const segment = timelineSelected();
  const video = $("timeline-video");
  if (!segment || video.hidden) {
    toast("当前任务没有可预览的原始视频");
    return;
  }
  video.currentTime = Number(segment.start || 0);
  state.timelinePlayback = { end: Number(segment.end || 0) };
  video.play().catch(() => {});
}

async function saveTimelineSegment() {
  const segment = timelineSelected();
  if (!segment) return;
  const start = Number($("timeline-start").value);
  const end = Number($("timeline-end").value);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
    toast("结束时间必须大于开始时间", true);
    return;
  }
  try {
    await api(`/api/v1/segments/${segment.id}`, {
      method: "PATCH",
      body: { start, end, title: $("timeline-title").value.trim() },
    });
    toast("片段已更新");
    await loadTimelineSegments();
  } catch (error) {
    toast(error.message, true);
  }
}

async function renderTimelineSegment() {
  const segment = timelineSelected();
  if (!segment) return;
  const button = $("timeline-render");
  button.disabled = true;
  button.textContent = "导出中...";
  try {
    const aspects = state.timelineJob?.params?.aspects?.length
      ? state.timelineJob.params.aspects
      : ["9:16"];
    const data = await api(
      `/api/v1/jobs/${state.timelineJobId}/segments/render`,
      {
        method: "POST",
        body: { ids: [segment.id], aspects },
      },
    );
    const links = (data.outputs || []).map((output) => {
      const encoded = String(output.relative_path || "")
        .split("/")
        .map(encodeURIComponent)
        .join("/");
      const url = mediaUrl(
        `/api/v1/jobs/${encodeURIComponent(state.timelineJobId)}/files/${encoded}`,
      );
      return `<a href="${url}" download="${esc(output.name)}">${esc(output.name)}</a>`;
    }).join(" ");
    $("timeline-export-result").innerHTML = links
      ? `已导出：${links}`
      : "没有生成文件";
    toast("片段已重新导出");
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "导出此段";
  }
}

async function renderTimelineBatch() {
  const selected = timelineCheckedSegments();
  if (!selected.length) {
    toast("先勾选要导出的片段");
    return;
  }
  const button = $("timeline-batch-render");
  button.disabled = true;
  button.textContent = "导出中...";
  try {
    const aspects = state.timelineJob?.params?.aspects?.length
      ? state.timelineJob.params.aspects
      : ["9:16"];
    const data = await api(
      `/api/v1/jobs/${state.timelineJobId}/segments/render`,
      {
        method: "POST",
        body: { ids: selected.map((item) => item.id), aspects },
      },
    );
    const outputs = data.outputs || [];
    const links = outputs.map((output) => {
      const encoded = String(output.relative_path || "")
        .split("/")
        .map(encodeURIComponent)
        .join("/");
      const url = mediaUrl(
        `/api/v1/jobs/${encodeURIComponent(state.timelineJobId)}/files/${encoded}`,
      );
      return `<a href="${url}" download="${esc(output.name)}">${esc(output.name)}</a>`;
    }).join(" ");
    $("timeline-export-result").innerHTML = links
      ? `已导出 ${outputs.length} 个文件：${links}`
      : "没有生成文件";
    toast(`已批量导出 ${outputs.length} 个片段`);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "批量重剪导出";
    renderTimelineBatchBar();
  }
}

function segmentSubtitleName(segment) {
  const sequence = Number(segment.seq ?? timelineIndexOf(segment.id)) + 1;
  return `切片${String(sequence).padStart(2, "0")}_字幕.txt`;
}

function timelineFullSubtitleName() {
  const raw = String(state.timelineJob?.params?.source_name || "字幕");
  const stem = raw.replace(/\.[^.]+$/, "") || "字幕";
  return `${stem}_完整字幕.txt`;
}

async function saveTimelineSubtitlesBatch() {
  const selected = timelineCheckedSegments();
  if (!selected.length) {
    toast("先勾选要保存字幕的片段");
    return;
  }
  if (typeof window.showDirectoryPicker !== "function") {
    toast("当前浏览器不支持直接写入文件夹", true);
    return;
  }
  const button = $("timeline-batch-subtitles");
  button.disabled = true;
  button.textContent = "保存中...";
  try {
    const directory = await window.showDirectoryPicker({
      id: "autocut-subtitle-directory",
      mode: "readwrite",
      startIn: "downloads",
    });
    let saved = 0;
    for (const segment of selected) {
      const response = await fetch(
        mediaUrl(
          `/api/v1/jobs/${encodeURIComponent(state.timelineJobId)}/segments/${encodeURIComponent(segment.id)}/subtitles.txt`,
        ),
      );
      if (!response.ok) {
        throw new Error(`导出字幕失败：HTTP ${response.status}`);
      }
      const content = await response.text();
      const handle = await uniqueDirectoryHandle(
        directory,
        segmentSubtitleName(segment),
      );
      const writable = await handle.createWritable();
      await writable.write(
        new Blob([content], { type: "text/plain;charset=utf-8" }),
      );
      await writable.close();
      saved += 1;
    }
    toast(`已保存 ${saved} 个字幕到文件夹「${directory.name}」`);
  } catch (error) {
    if (error?.name !== "AbortError") {
      toast(error.message || "保存字幕失败", true);
    }
  } finally {
    button.disabled = false;
    button.textContent = "批量保存字幕";
    renderTimelineBatchBar();
  }
}

async function toggleTimelineLock() {
  const segment = timelineSelected();
  if (!segment) return;
  try {
    await api(`/api/v1/segments/${segment.id}`, {
      method: "PATCH",
      body: { locked: !segment.locked },
    });
    toast(segment.locked ? "片段已解锁" : "片段已锁定，自动精简不会删除");
    await loadTimelineSegments();
  } catch (error) {
    toast(error.message, true);
  }
}

async function deleteTimelineSegment() {
  const segment = timelineSelected();
  if (!segment || !window.confirm("删除这个片段？")) return;
  try {
    await api(`/api/v1/segments/${segment.id}`, { method: "DELETE" });
    state.timelineSelectedId = "";
    toast("片段已删除");
    await loadTimelineSegments();
  } catch (error) {
    toast(error.message, true);
  }
}

async function mergeTimelineNext() {
  const segment = timelineSelected();
  const index = segment ? timelineIndexOf(segment.id) : -1;
  const next = index >= 0 ? state.clipSegments[index + 1] : null;
  if (!segment || !next) return;
  if (segment.locked || next.locked) {
    toast("锁定片段不能合并，请先解锁", true);
    return;
  }
  try {
    await api(`/api/v1/jobs/${state.timelineJobId}/segments/merge`, {
      method: "POST",
      body: { ids: [segment.id, next.id] },
    });
    state.timelineSelectedId = "";
    toast("相邻片段已合并");
    await loadTimelineSegments();
  } catch (error) {
    toast(error.message, true);
  }
}

async function unmergeTimelineSegment() {
  const segment = timelineSelected();
  if (!segment) return;
  try {
    await api(
      `/api/v1/jobs/${state.timelineJobId}/segments/${segment.id}/unmerge`,
      { method: "POST" },
    );
    state.timelineSelectedId = "";
    toast("已取消合并，原片段已恢复");
    await loadTimelineSegments();
  } catch (error) {
    toast(error.message, true);
  }
}

async function moveTimelineSegment(direction) {
  const segment = timelineSelected();
  const index = segment ? timelineIndexOf(segment.id) : -1;
  const target = index + direction;
  if (index < 0 || target < 0 || target >= state.clipSegments.length) return;
  const ordered = [...state.clipSegments];
  [ordered[index], ordered[target]] = [ordered[target], ordered[index]];
  try {
    await api(`/api/v1/jobs/${state.timelineJobId}/segments/reorder`, {
      method: "POST",
      body: { ids: ordered.map((item) => item.id) },
    });
    toast(direction < 0 ? "片段已前移" : "片段已后移");
    await loadTimelineSegments();
  } catch (error) {
    toast(error.message, true);
  }
}

function startTimelineTrim(event) {
  const handle = event.target.closest("[data-trim]");
  if (!handle) return;
  const segment = state.clipSegments.find((item) => item.id === handle.dataset.segmentId);
  if (!segment) return;
  if (segment.locked) {
    toast("锁定片段不能调整，请先解锁", true);
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  const total = timelineVisibleSegments().reduce(
    (sum, item) => sum + Number(item.duration || 0),
    0,
  );
  const trackWidth = Math.max(240, $("timeline-track").clientWidth);
  state.timelineDrag = {
    id: segment.id,
    side: handle.dataset.trim,
    startX: event.clientX,
    start: Number(segment.start),
    end: Number(segment.end),
    sourceDuration: Number(segment.source_duration || 0),
    pxPerSecond: trackWidth / Math.max(1, total),
    block: handle.closest(".timeline-segment"),
  };
  state.timelineDragging = true;
}

function moveTimelineTrim(event) {
  const drag = state.timelineDrag;
  if (!drag) return;
  const segment = state.clipSegments.find((item) => item.id === drag.id);
  if (!segment) return;
  const delta = (event.clientX - drag.startX) / drag.pxPerSecond;
  let start = drag.start;
  let end = drag.end;
  if (drag.side === "start") {
    start = Math.max(0, Math.min(drag.end - 0.5, drag.start + delta));
  } else {
    const maximum = drag.sourceDuration > 0 ? drag.sourceDuration : Number.MAX_SAFE_INTEGER;
    end = Math.min(maximum, Math.max(drag.start + 0.5, drag.end + delta));
  }
  segment.start = Math.round(start * 10) / 10;
  segment.end = Math.round(end * 10) / 10;
  segment.duration = Math.round((end - start) * 10) / 10;
  if (drag.block) {
    drag.block.style.flex = `${Math.max(0.01, segment.duration)} 1 0`;
    const durationLabel = drag.block.querySelector(".timeline-segment-body span");
    if (durationLabel) durationLabel.textContent = timelineSeconds(segment.duration);
  }
}

async function endTimelineTrim() {
  const drag = state.timelineDrag;
  state.timelineDrag = null;
  if (!drag) return;
  const segment = state.clipSegments.find((item) => item.id === drag.id);
  if (!segment) return;
  try {
    await api(`/api/v1/segments/${segment.id}`, {
      method: "PATCH",
      body: { start: segment.start, end: segment.end },
    });
    toast("片段起止点已更新");
    await loadTimelineSegments();
  } catch (error) {
    toast(error.message, true);
    await loadTimelineSegments();
  } finally {
    setTimeout(() => {
      state.timelineDragging = false;
    }, 80);
  }
}

async function createEditJob() {
  if (!state.projectId) {
    toast("先在项目页创建项目");
    return;
  }
  const assetId = $("edit-asset").value;
  if (!assetId) {
    toast("先在素材页上传视频");
    return;
  }
  const aspects = [...document.querySelectorAll("#edit-aspects input:checked")]
    .map((node) => node.value);
  if (!aspects.length) {
    toast("至少选择一个输出画幅");
    return;
  }

  const button = $("create-edit-job");
  const asrValue = $("edit-asr-model").value || "cloud:";
  const asrSeparator = asrValue.indexOf(":");
  const asrProvider = asrSeparator >= 0 ? asrValue.slice(0, asrSeparator) : "cloud";
  const asrModel = asrSeparator >= 0 ? asrValue.slice(asrSeparator + 1) : "";
  button.disabled = true;
  try {
    await api(`/api/v1/projects/${state.projectId}/auto-edit`, {
      method: "POST",
      body: {
        asset_id: assetId,
        count: Number($("edit-count").value) || 3,
        min_seconds: $("edit-min-seconds").value ? Number($("edit-min-seconds").value) : null,
        max_seconds: $("edit-max-seconds").value ? Number($("edit-max-seconds").value) : null,
        aspects,
        model_ref: $("edit-model").value || "",
        asr_provider: asrProvider,
        asr_model: asrModel,
        brief: $("edit-brief").value.trim(),
      },
    });
    if (state.workerOnline === false) {
      toast("任务已提交，但 Worker 未运行，会一直排队", true);
    } else {
      toast("成片任务已提交");
    }
    loadEditJobs();
    loadWorkerStatus();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function loadStructure() {
  $("structure-project").textContent = state.projectId
    ? (state.projectName || state.projectId)
    : "先在项目页创建项目";
  try {
    await ensureModules();
    if (!state.templates.length) {
      const data = await api("/api/v1/pipeline-templates");
      state.templates = data.items || [];
    }
    const select = $("structure-template");
    if (!select.options.length) {
      select.innerHTML = state.templates
        .map((item) => `<option value="${esc(item.id)}">${esc(item.name)}</option>`)
        .join("");
    }
    $("structure-add-module").innerHTML = state.modules
      .map((item) => `<option value="${esc(item.id)}">${esc(item.name)}</option>`)
      .join("");
    resetPipelineSteps();
    await loadPipelines();
  } catch (error) {
    toast(error.message, true);
  }
}

function resetPipelineSteps() {
  const templateId = $("structure-template").value;
  const template = state.templates.find((item) => item.id === templateId);
  state.pipelineSteps = (template?.steps || []).map((step) => ({ ...step }));
  $("structure-template-desc").textContent = template?.description || "";
  renderPipelineSteps();
}

function renderPipelineSteps() {
  $("structure-steps").innerHTML = state.pipelineSteps.map((step, index) => {
    const module = state.modules.find((item) => item.id === step.module);
    return `
      <div class="step-row" data-step="${index}">
        <span class="step-index">${index + 1}</span>
        <span class="step-module">${esc(module?.name || step.module)}</span>
        <span class="step-mode">${esc(modeLabel(step.mode))}</span>
        <span class="step-prompt">${esc(step.prompt)}</span>
        <span class="row">
          <button type="button" class="btn ghost small" data-move="up">上移</button>
          <button type="button" class="btn ghost small" data-move="down">下移</button>
          <button type="button" class="btn ghost small" data-remove-step>删除</button>
        </span>
      </div>`;
  }).join("") || `<div class="empty">还没有步骤</div>`;
}

function pipelineOutput(pipeline) {
  if (!pipeline.project_id) return "";
  const step = (pipeline.steps || []).find(
    (item) => item.module === "render" && item.result?.asset_id,
  );
  if (!step) return "";
  const result = step.result || {};
  const url = mediaUrl(`/api/v1/projects/${encodeURIComponent(pipeline.project_id)}/assets/${encodeURIComponent(result.asset_id)}/file`);
  const filename = result.filename || "render.mp4";
  return `
    <div class="pipeline-output">
      <div class="hit-meta">
        <span class="row"><span class="pill">成片</span><span>${esc(filename)}</span></span>
        <span class="muted">${esc(result.width || "")}×${esc(result.height || "")} · ${esc(result.duration || "")} 秒</span>
      </div>
      <video class="artifact-preview" controls preload="metadata" src="${url}"></video>
      <div class="row end">
        <a class="btn ghost small" href="${url}" target="_blank" rel="noreferrer">打开原片</a>
        <a class="btn primary small" href="${url}" download="${esc(filename)}">下载成片</a>
      </div>
    </div>`;
}

function addPipelineStep() {
  const moduleId = $("structure-add-module").value;
  const module = state.modules.find((item) => item.id === moduleId);
  if (!module) {
    toast("先选择模块");
    return;
  }
  state.pipelineSteps.push({
    module: moduleId,
    mode: (module.modes || [""])[0],
    prompt: $("structure-add-prompt").value.trim(),
  });
  $("structure-add-prompt").value = "";
  renderPipelineSteps();
}

function applyPipelineBrief(steps, brief) {
  if (!brief) return steps;
  return steps.map((step) => {
    if (step.module === "copywriting") {
      return { ...step, prompt: brief };
    }
    if (["image", "storyboard", "render"].includes(step.module)) {
      return { ...step, prompt: `${step.prompt}：${brief}` };
    }
    return step;
  });
}

async function createPipeline() {
  const template = $("structure-template").value;
  if (!state.projectId) {
    toast("先在项目页创建并选择项目");
    return;
  }
  if (!state.pipelineSteps.length) {
    toast("至少添加一个步骤");
    return;
  }
  const templateName = state.templates.find((item) => item.id === template)?.name || "";
  const brief = $("structure-brief").value.trim();
  const button = $("create-pipeline");
  button.disabled = true;
  try {
    await api("/api/v1/pipelines", {
      method: "POST",
      body: {
        name: $("structure-name").value.trim() || templateName,
        project_id: state.projectId || null,
        steps: applyPipelineBrief(state.pipelineSteps, brief),
      },
    });
    $("structure-name").value = "";
    $("structure-brief").value = "";
    toast("流水线已创建");
    loadPipelines();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function loadPipelines() {
  try {
    const data = await api("/api/v1/pipelines");
    const items = data.items || [];
    $("pipeline-empty").hidden = items.length > 0;
    $("pipeline-list").innerHTML = items.map((pipeline) => `
      <li class="list-item stacked">
        <div class="hit-meta">
          <span class="row">${bulkCheckbox("pipelines", pipeline.id, pipeline.name)}<span>${esc(pipeline.name)}</span></span>
          <span>${statusPill(pipeline.status)}</span>
        </div>
        <div class="hit-meta">
          <span class="muted">${esc(pipeline.template || "custom")} · ${esc(formatTime(pipeline.created_at))}</span>
          <span class="row">
            ${pipeline.status === "queued" ? `<button class="btn ghost small" data-pipeline="${esc(pipeline.id)}">取消</button>` : ""}
            <button class="btn ghost small row-delete" data-delete-pipeline="${esc(pipeline.id)}">删除</button>
          </span>
        </div>
        <div class="steps">
          ${(pipeline.steps || []).map((step, index) => `
            <div class="step-row">
              <span class="step-index">${index + 1}</span>
              <span class="step-module">${esc((state.modules.find((item) => item.id === step.module) || {}).name || step.module)}</span>
              <span class="step-mode">${esc(modeLabel(step.mode))}</span>
              <span>${statusPill(step.status)}</span>
            </div>`).join("")}
        </div>
        ${pipeline.status === "failed"
          ? `<div class="hit-snippet">${esc((pipeline.steps || []).find((step) => step.error)?.error || "流水线执行失败")}</div>`
          : ""}
        ${pipelineOutput(pipeline)}
      </li>`).join("");
    updateBulkBar("pipelines");
  } catch (error) {
    toast(error.message, true);
  }
}

async function cancelPipeline(pipelineId) {
  try {
    await api(`/api/v1/pipelines/${pipelineId}/cancel`, { method: "POST" });
    toast("已取消");
    loadPipelines();
  } catch (error) {
    toast(error.message, true);
  }
}

async function deletePipeline(pipelineId) {
  if (!window.confirm("删除这条流水线记录？")) return;
  try {
    await api(`/api/v1/pipelines/${pipelineId}`, { method: "DELETE" });
    toast("已删除");
    loadPipelines();
  } catch (error) {
    toast(error.message, true);
  }
}

async function ensureModules() {
  if (state.modules.length) return state.modules;
  const data = await api("/api/v1/modules");
  state.modules = data.items || [];
  return state.modules;
}

async function ensureCatalog() {
  if (state.modelCatalog.length) return state.modelCatalog;
  const data = await api("/api/v1/settings/models");
  state.modelCatalog = data.items || [];
  state.autoModels = data.auto || state.autoModels;
  return state.modelCatalog;
}

function moduleCapabilities(moduleId) {
  if (["image", "lora"].includes(moduleId)) return ["image.generate"];
  if (moduleId === "audio") return ["asr", "tts"];
  if (["copywriting", "storyboard"].includes(moduleId)) return ["chat"];
  return [];
}

async function populateModuleModels(moduleId) {
  if (!Object.keys(state.modelDefaults).length) await loadModelDefaults();
  const catalog = await ensureCatalog();
  const wanted = moduleCapabilities(moduleId);
  const preferred = wanted.map((capability) => state.modelDefaults[capability]).find(Boolean);
  const options = new Map();
  for (const provider of catalog) {
    if (provider.status !== "ready") continue;
    for (const capability of wanted) {
      if (!(provider.capabilities || []).includes(capability)) continue;
      if (!(provider.wired_capabilities || []).includes(capability)) continue;
      const listKey = MODEL_LIST_KEYS[capability];
      for (const model of provider[listKey] || []) {
        const value = `${provider.provider}:${model}`;
        const providerName = PROVIDER_TEXT[provider.provider] || provider.provider;
        options.set(
          value,
          `${value === preferred ? "✓ 默认 · " : ""}${providerName} · ${model}`,
        );
      }
    }
  }
  $("module-model").innerHTML = `<option value="">自动（最便宜可用）</option>`
    + [...options.entries()]
      .map(([value, label]) => `<option value="${esc(value)}">${esc(label)}</option>`)
      .join("");
  if (preferred && options.has(preferred)) {
    $("module-model").value = preferred;
  }
  const autoRef = wanted.map((capability) => state.autoModels[capability]).find(Boolean) || "";
  $("module-model-hint").textContent = preferred
    ? `当前默认：${modelRefLabel(preferred)}`
    : autoRef
      ? `自动使用：${modelRefLabel(autoRef)}（最便宜可用）`
      : "当前没有可用模型，请先配置 API Key";
}

async function openModule(moduleId) {
  try {
    const modules = await ensureModules();
    const module = modules.find((item) => item.id === moduleId) || modules[0];
    if (!module) return;
    state.module = module.id;
    $("module-title").textContent = module.name;
    $("module-desc").textContent = module.description;
    $("module-status").textContent = MODULE_STATUS_TEXT[module.status] || module.status || "待接入";
    $("module-mode").innerHTML = (module.modes || [])
      .map((mode) => `<option value="${esc(mode)}">${esc(modeLabel(mode))}</option>`)
      .join("");
    if (state.preferences?.default_quality) {
      $("module-quality").value = state.preferences.default_quality;
    }
    await populateModuleModels(module.id);
    const modelCapabilities = moduleCapabilities(module.id);
    $("module-model-fields").hidden = modelCapabilities.length === 0;
    $("module-engine-note").hidden = modelCapabilities.length > 0;
    if (!modelCapabilities.length) {
      $("module-engine-note").textContent = module.id === "render"
        ? "渲染由本机 FFmpeg 执行，不需要选择 AI 模型。"
        : "该模块没有独立模型，使用各步骤自己的配置。";
    }
    $("view-title").textContent = module.name;
    $("view-subtitle").textContent = module.description;
    await loadModuleJobs(module.id);
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadModuleJobs(moduleId) {
  try {
    const data = await api(`/api/v1/modules/${moduleId}/jobs`);
    const items = data.items || [];
    state.moduleJobs = items;
    $("module-job-empty").hidden = items.length > 0;
    $("module-job-list").innerHTML = items.map((job) => {
      const result = job.result || {};
      const note = result.note
        ? `<div class="hit-snippet">${esc(result.note)}</div>`
        : "";
      const candidates = job.module === "image" && Array.isArray(result.candidates)
        ? result.candidates
        : (result.asset_id ? [{ asset_id: result.asset_id, variant: 1 }] : []);
      const assetLinks = candidates
        .filter((candidate) => candidate.asset_id)
        .map((candidate) => {
          const url = mediaUrl(`/api/v1/projects/${job.project_id}/assets/${candidate.asset_id}/file`);
          const label = job.module === "image"
            ? `下载原图${candidate.variant ? ` ${candidate.variant}` : ""}`
            : "下载产物";
          return `<a href="${url}" download="${esc(candidate.filename || `image-${candidate.variant || 1}`)}" target="_blank" rel="noreferrer">${esc(label)}</a>`;
        }).join("");
      const scriptInfo = result.script_id
        ? `<span class="muted">脚本 ${esc(result.script_id)}</span>`
        : "";
      const previewAction = job.status === "succeeded" && (result.asset_id || result.script_id)
        ? `<button class="btn ghost small" data-preview-module-job="${esc(job.id)}">预览</button>`
        : "";
      const checkbox = job.status === "running"
        ? ""
        : bulkCheckbox("moduleJobs", job.id, job.prompt || job.id);
      return `
        <li class="list-item stacked" data-module-job-row="${esc(job.id)}">
          <div class="hit-meta">
            <span class="row">${checkbox}<span>${esc(modeLabel(job.mode))} · ${esc(qualityLabel(job.params?.quality || "standard"))} · <code>${esc(job.id)}</code>${job.result?.score ? ` · ${esc(job.result.score)} 分` : ""}</span></span>
            <span>${statusPill(job.status)}</span>
          </div>
          <div class="hit-snippet">${esc(snippet(job.prompt || "无描述", 100))}</div>
          ${note}
          ${job.error ? `<div class="hit-snippet">${esc(snippet(job.error, 140))}</div>` : ""}
          <div class="hit-meta">
            <span class="muted">${esc(formatTime(job.created_at))}</span>
            <span class="row">${assetLinks}${scriptInfo}${previewAction}</span>
            ${job.status === "queued" ? `<button class="btn ghost small" data-module-job="${esc(job.id)}">取消</button>` : ""}
            ${job.status !== "running" ? `<button class="btn ghost small danger row-delete" data-delete-module-job="${esc(job.id)}">删除</button>` : ""}
          </div>
      </li>`;
    }).join("");
    updateBulkBar("moduleJobs");
    const latest = items.find((job) => job.status === "succeeded" && job.result);
    if (latest) previewModuleJob(latest.id);
  } catch (error) {
    toast(error.message, true);
  }
}

async function previewModuleJob(jobId) {
  const job = state.moduleJobs.find((item) => item.id === jobId);
  if (!job) return;
  $("module-preview-title").textContent = `${modeLabel(job.mode) || "任务"} · ${job.id}`;
  const result = job.result || {};
  if (result.script_id) {
    try {
      const script = await api(`/api/v1/scripts/${result.script_id}`);
      $("module-preview").innerHTML = `
        <pre class="output">${esc(script.body || "")}</pre>
        <div class="preview-actions">
          <button type="button" class="btn small" data-copy-preview="${esc(script.body || "")}">复制</button>
          <button type="button" class="btn primary small" data-view-preview="${esc(script.body || "")}">查看全文</button>
        </div>`;
      return;
    } catch (error) {
      toast(error.message, true);
    }
  }
  if (
    job.module === "image"
    && job.project_id
    && Array.isArray(result.candidates)
    && result.candidates.length
  ) {
    $("module-preview").innerHTML = `
      <div class="preview-gallery">
        ${result.candidates.map((candidate) => {
          if (!candidate.asset_id) return "";
          const url = mediaUrl(`/api/v1/projects/${job.project_id}/assets/${candidate.asset_id}/file`);
          const selected = candidate.asset_id === result.asset_id;
          return `
            <figure class="preview-gallery-item ${selected ? "selected" : ""}">
              <img src="${url}" alt="${esc(candidate.filename || `候选 ${candidate.variant}`)}" />
              <figcaption>
                <span>候选 ${esc(candidate.variant || "")}${selected ? " · 默认" : ""}</span>
                <span class="row">
                  <a href="${url}" target="_blank" rel="noreferrer">打开原图</a>
                  <a href="${url}" download="${esc(candidate.filename || "image.jpg")}">下载</a>
                </span>
              </figcaption>
            </figure>`;
        }).join("")}
      </div>`;
    return;
  }
  if (result.asset_id && job.project_id) {
    try {
      const data = await api(`/api/v1/projects/${job.project_id}/assets`);
      const asset = (data.items || []).find((item) => item.id === result.asset_id);
      if (asset) {
        const url = mediaUrl(`/api/v1/projects/${job.project_id}/assets/${asset.id}/file`);
        const suffix = String(asset.filename || "").toLowerCase();
        if (asset.kind === "image") {
          $("module-preview").innerHTML = `
            <img class="preview-media" src="${url}" alt="${esc(asset.filename)}" />
            <div class="preview-actions">
              <a class="btn small" href="${url}" target="_blank" rel="noreferrer">打开原图</a>
              <a class="btn primary small" href="${url}" download="${esc(asset.filename)}">下载原图</a>
            </div>`;
          return;
        }
        if (asset.kind === "audio") {
          $("module-preview").innerHTML = `<audio class="preview-media" controls src="${url}"></audio>`;
          return;
        }
        if (asset.kind === "video") {
          $("module-preview").innerHTML = `<video class="preview-media" controls src="${url}"></video>`;
          return;
        }
        if ([".json", ".txt", ".md", ".srt", ".csv"].some((ext) => suffix.endsWith(ext))) {
          const response = await fetch(url);
          const text = await response.text();
          $("module-preview").innerHTML = `<pre class="output">${esc(text)}</pre>`;
          return;
        }
      }
    } catch (error) {
      toast(error.message, true);
    }
  }
  $("module-preview").innerHTML = `<pre class="output">${esc(JSON.stringify(result, null, 2))}</pre>`;
}

async function createModuleJob() {
  let params = {};
  try {
    params = $("module-params").value.trim()
      ? JSON.parse($("module-params").value)
      : {};
  } catch {
    toast("参数不是合法 JSON", true);
    return;
  }
  const customModel = $("module-model-custom").value.trim();
  const model = customModel || $("module-model").value;
  if (model) params.model = model;
  params.quality = $("module-quality").value;

  const button = $("create-module-job");
  button.disabled = true;
  try {
    await api(`/api/v1/modules/${state.module}/jobs`, {
      method: "POST",
      body: {
        mode: $("module-mode").value,
        prompt: $("module-prompt").value.trim(),
        params,
        project_id: state.projectId || null,
      },
    });
    toast("任务已提交");
    loadModuleJobs(state.module);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function cancelModuleJob(jobId) {
  try {
    await api(`/api/v1/module-jobs/${jobId}/cancel`, { method: "POST" });
    toast("已取消");
    loadModuleJobs(state.module);
  } catch (error) {
    toast(error.message, true);
  }
}

async function deleteModuleJob(jobId) {
  if (!window.confirm("确定删除这条任务记录吗？已完成的产物仍会保留。")) return;
  try {
    await api(`/api/v1/module-jobs/${jobId}`, { method: "DELETE" });
    toast("任务记录已删除");
    await loadModuleJobs(state.module);
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadAdmin() {
  try {
    const data = await api("/api/v1/admin/overview");
    const usage = data.usage || {};
    $("admin-usage").innerHTML = Object.entries(usage)
      .map(([key, value]) => `<span class="pill">${esc(key)} ${esc(value)}</span>`)
      .join("");
    const status = data.job_status || {};
    $("admin-jobs").innerHTML = Object.entries(status).length
      ? Object.entries(status)
        .map(([key, value]) => `<span class="pill">${esc(key)} ${esc(value)}</span>`)
        .join("")
      : `<span class="muted">暂无任务</span>`;
    $("admin-log-body").innerHTML = (data.recent_logs || []).map((log) => `
      <tr>
        <td class="muted">${esc(formatTime(log.created_at))}</td>
        <td>${esc(log.action)}</td>
        <td class="muted">${esc(log.target)}</td>
      </tr>`).join("");
    const feedback = data.feedback || {};
    const tags = (feedback.top_tags || [])
      .map((item) => `<span class="pill muted">${esc(item.tag)} ${esc(item.count)}</span>`)
      .join(" ");
    $("admin-feedback").innerHTML = `
      <span class="pill">平均 ${esc(feedback.average ?? 0)} 分</span>
      <span class="pill warn">负反馈 ${esc(feedback.negative ?? 0)}</span>
      <span class="pill muted">总数 ${esc(feedback.total ?? 0)}</span>
      ${tags}`;
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadJobs() {
  try {
    const data = await api("/api/v1/jobs");
    const allItems = data.items || [];
    const keyword = $("job-search").value.trim().toLowerCase();
    const items = keyword
      ? allItems.filter((job) => jobSearchText(job).includes(keyword))
      : allItems;
    $("jobs-empty").textContent = keyword ? "没有匹配的任务" : "还没有任务";
    $("jobs-empty").hidden = items.length > 0;
    $("jobs-table").hidden = items.length === 0;
    $("jobs-body").innerHTML = items.map((job) => {
      const actions = [];
      if (job.status === "queued") {
        actions.push(`<button class="btn ghost small" data-cancel="${esc(job.id)}">取消</button>`);
      }
      if (job.status === "failed" || job.status === "canceled") {
        actions.push(`<button class="btn ghost small" data-retry="${esc(job.id)}">重试</button>`);
      }
      if (job.status === "succeeded") {
        actions.push(`<button class="btn ghost small" data-artifacts="${esc(job.id)}">产物</button>`);
      }
      if (job.status !== "running") {
        actions.push(`<button class="btn ghost small danger" data-delete-job="${esc(job.id)}">删除</button>`);
      }
      const source = editJobSourceStem(job);
      const checkbox = job.status === "running"
        ? ""
        : bulkCheckbox("jobs", job.id, source);
      const model = job.params?.model_ref
        ? modelRefLabel(job.params.model_ref)
        : "自动模型";
      return `
        <tr>
          <td>
            <div class="row">
              ${checkbox}
              <span class="list-main">
                <b>${esc(source)} · ${esc(editJobCount(job))} 段 · ${esc(compactJobTime(job.created_at))}</b>
                <span class="list-meta">${esc(workflowLabel(job))} · ${esc(model)} · <code>${esc(job.id)}</code></span>
                ${job.params?.brief ? `<span class="list-meta">要求：${esc(snippet(job.params.brief, 100))}</span>` : ""}
              </span>
            </div>
          </td>
          <td>${esc(workflowLabel(job))}</td>
          <td>${statusPill(job.status)}</td>
          <td>${esc(formatTime(job.created_at))}</td>
          <td>${esc(formatDuration(job.duration_ms))}</td>
          <td>${actions.join(" ")}</td>
        </tr>`;
    }).join("");
    updateBulkBar("jobs");
  } catch (error) {
    toast(error.message, true);
  }
}

async function cancelJob(id) {
  try {
    await api(`/api/v1/jobs/${id}/cancel`, { method: "POST" });
    toast("已取消");
    loadJobs();
  } catch (error) {
    toast(error.message, true);
  }
}

async function retryJob(id) {
  try {
    await api(`/api/v1/jobs/${id}/retry`, { method: "POST" });
    toast("已重新排队");
    loadJobs();
  } catch (error) {
    toast(error.message, true);
  }
}

async function deleteJob(id) {
  if (!window.confirm("确定删除这个任务吗？任务记录和已生成的产物都会被删除。")) return;
  try {
    await api(`/api/v1/jobs/${id}`, { method: "DELETE" });
    if ($("artifact-job").textContent === id) {
      $("artifact-panel").hidden = true;
      $("artifact-list").innerHTML = "";
      $("artifact-job").textContent = "-";
    }
    toast("任务已删除");
    await loadJobs();
  } catch (error) {
    toast(error.message, true);
  }
}

function artifactClipNumber(item) {
  const match = String(item.name || "").match(/切片(\d+)/);
  return match ? Number(match[1]) : 9999;
}

function artifactTypeRank(item) {
  const name = String(item.name || "").toLowerCase();
  if (/\.(mp4|webm|mov|mkv)$/.test(name)) return 0;
  if (name.endsWith(".srt")) return 1;
  if (name.endsWith(".txt")) return 2;
  return 3;
}

function sortArtifacts(items) {
  return [...items].sort((left, right) =>
    artifactClipNumber(left) - artifactClipNumber(right)
    || artifactTypeRank(left) - artifactTypeRank(right)
    || String(left.name || "").localeCompare(String(right.name || "")));
}

function renderArtifactItem(id, item, options = {}) {
  const isFinal = String(item.path || "").startsWith("成片/");
  const isEdited = String(item.name || "").includes("_重剪");
  const nameLower = String(item.name || "").toLowerCase();
  const itemPath = String(item.path || "");
  const isSubtitle = nameLower.endsWith(".srt");
  const isSubtitleText = nameLower.endsWith(".txt") && itemPath.startsWith("字幕/");
  const isVideo = /\.(mp4|webm|mov|mkv)$/.test(nameLower);
  const isSystem = itemPath.startsWith("系统文件/");
  const isAudio = itemPath.startsWith("音频/");
  const clipMatch = String(item.name || "").match(/切片(\d+)/);
  const clipLabel = clipMatch ? `切片 ${clipMatch[1]}` : "";
  const clipKey = clipMatch ? String(Number(clipMatch[1])).padStart(2, "0") : "";
  const subtitleItem = clipKey
    ? options.subtitleByClip?.get(clipKey)
    : null;
  const subtitleUrl = subtitleItem
    ? mediaUrl(
      `/api/v1/jobs/${encodeURIComponent(id)}/files/${String(subtitleItem.path || "")
        .split("/")
        .map(encodeURIComponent)
        .join("/")}`,
    )
    : "";
  const encodedPath = String(item.path || "")
    .split("/")
    .map(encodeURIComponent)
    .join("/");
  const url = mediaUrl(`/api/v1/jobs/${encodeURIComponent(id)}/files/${encodedPath}`);
  return `
  <div class="list-item stacked">
    <div class="hit-meta">
      <span class="row">
        ${isSystem ? "" : bulkCheckbox("artifacts", item.path, item.name)}
        <a href="${url}" target="_blank" rel="noreferrer">${esc(item.name)}</a>
        ${clipLabel ? `<span class="pill muted">${clipLabel}</span>` : ""}
        ${isFinal ? `<span class="pill">成片</span>` : ""}
        ${isEdited ? `<span class="pill warn">重剪</span>` : ""}
        ${isSubtitle ? `<span class="pill">SRT 字幕</span>` : ""}
        ${isSubtitleText ? `<span class="pill">带时间戳字幕</span>` : ""}
        ${isAudio ? `<span class="pill muted">音频</span>` : ""}
        ${isSystem ? `<span class="pill muted">系统文件</span>` : ""}
      </span>
      <span class="row">
        <span class="muted">${Math.max(1, Math.round(item.size_bytes / 1024))} KB</span>
        <a class="btn ghost small" href="${url}" download="${esc(item.name)}">下载</a>
        ${isSystem ? "" : `<button type="button" class="btn ghost small danger row-delete" data-delete-artifact="${esc(item.path)}">删除</button>`}
      </span>
    </div>
    <div class="artifact-path">${esc(item.path)}</div>
    ${isVideo && subtitleItem ? `<a class="artifact-subtitle-link" href="${subtitleUrl}" target="_blank" rel="noreferrer">对应字幕：${esc(subtitleItem.name)}</a>` : ""}
    ${artifactPreview(id, item)}
  </div>`;
}

function renderArtifactSection(id, title, note, items, options = {}) {
  if (!items.length) return "";
  const body = `<div class="artifact-section-grid">
    ${items.map((item) => renderArtifactItem(id, item, options)).join("")}
  </div>`;
  if (options.collapsed) {
    return `<details class="artifact-section">
      <summary><b>${esc(title)}</b><span class="muted">${esc(note)}</span></summary>
      ${body}
    </details>`;
  }
  return `<section class="artifact-section">
    <div class="artifact-section-head">
      <h4>${esc(title)}</h4>
      <span class="muted">${esc(note)}</span>
    </div>
    ${body}
  </section>`;
}

async function showArtifacts(id) {
  try {
    const data = await api(`/api/v1/jobs/${id}/artifacts`);
    const items = data.items || [];
    state.artifactJobId = id;
    state.artifactItems = items;

    const finals = sortArtifacts(
      items.filter((item) => String(item.path || "").startsWith("成片/")),
    );
    const rawClips = sortArtifacts(
      items.filter((item) => String(item.path || "").startsWith("切片/")),
    );
    const subtitles = sortArtifacts(
      items.filter((item) => String(item.path || "").startsWith("字幕/")),
    );
    const support = items
      .filter((item) => {
        const itemPath = String(item.path || "");
        return itemPath.startsWith("音频/") || itemPath.startsWith("系统文件/");
      })
      .sort((left, right) => {
        const rank = (item) => String(item.path || "").startsWith("音频/") ? 0 : 1;
        return rank(left) - rank(right)
          || String(left.name || "").localeCompare(String(right.name || ""));
      });
    const known = new Set(
      [...finals, ...rawClips, ...subtitles, ...support].map((item) => item.path),
    );
    const others = items.filter((item) => !known.has(item.path));
    const subtitleByClip = new Map();
    for (const item of subtitles) {
      const match = String(item.name || "").match(/^切片(\d+)_字幕\.txt$/);
      if (match) subtitleByClip.set(match[1], item);
    }
    const finalVideos = finals.filter(
      (item) => /\.(mp4|webm|mov|mkv)$/i.test(String(item.name || "")),
    ).length;

    $("artifact-panel").hidden = false;
    $("artifact-job").textContent = `${id} · ${items.length} 个文件 · ${finalVideos} 个成片 · 按切片编号排序`;
    const sections = [
      renderArtifactSection(
        id,
        "成片",
        `${finals.length} 个文件`,
        finals,
        { subtitleByClip },
      ),
      renderArtifactSection(
        id,
        "原始切片",
        `${rawClips.length} 个片段`,
        rawClips,
        { subtitleByClip },
      ),
      renderArtifactSection(id, "字幕", `${subtitles.length} 个文件`, subtitles),
      renderArtifactSection(
        id,
        "音频与系统文件",
        `${support.length} 个文件`,
        support,
        { collapsed: true },
      ),
      renderArtifactSection(
        id,
        "其他文件",
        `${others.length} 个文件`,
        others,
        { collapsed: true },
      ),
    ].filter(Boolean);
    $("artifact-list").innerHTML = sections.length
      ? sections.join("")
      : `<div class="empty">还没有产物</div>`;
    hydrateArtifactTextPreviews();
    updateBulkBar("artifacts");
    $("artifact-panel").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    toast(error.message, true);
  }
}

function exportArtifacts(selectedOnly = false) {
  if (!state.artifactJobId) {
    toast("先打开一个任务的产物");
    return;
  }
  const paths = selectedOnly
    ? [...document.querySelectorAll('[data-bulk-check="artifacts"]')]
      .filter((item) => item.checked)
      .map((item) => item.value)
    : [];
  if (selectedOnly && !paths.length) {
    toast("先勾选要导出的产物");
    return;
  }
  const params = new URLSearchParams();
  paths.forEach((path) => params.append("path", path));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  window.location.href = mediaUrl(
    `/api/v1/jobs/${state.artifactJobId}/artifacts/export${suffix}`,
  );
}

function safeSaveName(name) {
  const value = String(name || "成片")
    .replace(/[<>:"/\\|?*\x00-\x1f]/g, "_")
    .trim();
  return value || "成片";
}

async function uniqueDirectoryHandle(directory, filename) {
  const safe = safeSaveName(filename);
  const suffixIndex = safe.lastIndexOf(".");
  const stem = suffixIndex > 0 ? safe.slice(0, suffixIndex) : safe;
  const suffix = suffixIndex > 0 ? safe.slice(suffixIndex) : "";
  let candidate = safe;
  let index = 2;
  while (true) {
    try {
      await directory.getFileHandle(candidate);
      candidate = `${stem}-${index}${suffix}`;
      index += 1;
    } catch {
      return directory.getFileHandle(candidate, { create: true });
    }
  }
}

async function saveArtifactsToFolder(selectedOnly = false) {
  if (!state.artifactJobId || !state.artifactItems.length) {
    toast("先打开一个任务的产物");
    return;
  }
  if (typeof window.showDirectoryPicker !== "function") {
    toast("当前浏览器不支持直接写入文件夹，已改用 ZIP 下载", true);
    exportArtifacts(selectedOnly);
    return;
  }

  const selectedPaths = selectedOnly
    ? new Set(
      [...document.querySelectorAll('[data-bulk-check="artifacts"]')]
        .filter((item) => item.checked)
        .map((item) => item.value),
    )
    : null;
  if (selectedOnly && !selectedPaths.size) {
    toast("先勾选要保存的产物");
    return;
  }
    const finals = state.artifactItems.filter(
      (item) => String(item.path || "").startsWith("成片/"),
  );
  const items = selectedOnly
    ? state.artifactItems.filter((item) => selectedPaths.has(item.path))
    : (finals.length ? finals : state.artifactItems);
  if (!items.length) {
    toast("没有可保存的成片");
    return;
  }

  try {
    const directory = await window.showDirectoryPicker({
      id: "autocut-export-directory",
      mode: "readwrite",
      startIn: "downloads",
    });
    let saved = 0;
    for (const [index, item] of items.entries()) {
      toast(`正在保存 ${index + 1}/${items.length}：${item.name}`);
      const encodedPath = String(item.path || "")
        .split("/")
        .map(encodeURIComponent)
        .join("/");
      const response = await fetch(
        mediaUrl(`/api/v1/jobs/${encodeURIComponent(state.artifactJobId)}/files/${encodedPath}`),
      );
      if (!response.ok) {
        throw new Error(`下载 ${item.name} 失败：HTTP ${response.status}`);
      }
      const blob = await response.blob();
      const handle = await uniqueDirectoryHandle(directory, item.name);
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      saved += 1;
    }
    toast(`已保存 ${saved} 个文件到文件夹「${directory.name}」`);
  } catch (error) {
    if (error?.name !== "AbortError") {
      toast(error.message || "保存到文件夹失败", true);
    }
  }
}

async function deleteArtifact(path) {
  if (!state.artifactJobId) return;
  if (!window.confirm(`确定删除产物“${path}”吗？`)) return;
  const encoded = path.split("/").map(encodeURIComponent).join("/");
  try {
    await api(`/api/v1/jobs/${state.artifactJobId}/files/${encoded}`, {
      method: "DELETE",
    });
    toast("产物已删除");
    await showArtifacts(state.artifactJobId);
  } catch (error) {
    toast(error.message, true);
  }
}

function artifactPreview(jobId, item) {
  const encodedPath = String(item.path || "")
    .split("/")
    .map(encodeURIComponent)
    .join("/");
  const url = mediaUrl(`/api/v1/jobs/${encodeURIComponent(jobId)}/files/${encodedPath}`);
  const name = String(item.name || "").toLowerCase();
  if (/\.(png|jpe?g|webp|gif|svg)$/.test(name)) {
    return `<img class="artifact-preview" src="${url}" alt="${esc(item.name)}" />`;
  }
  if (/\.(mp4|webm|mov|mkv)$/.test(name)) {
    const poster = mediaUrl(
      `/api/v1/jobs/${encodeURIComponent(jobId)}/thumbnail?path=${encodeURIComponent(item.path)}`,
    );
    return `<video class="artifact-preview" controls preload="none" poster="${poster}" src="${url}"></video>`;
  }
  if (/\.(mp3|wav|m4a|aac|flac)$/.test(name)) {
    return `<audio class="artifact-preview audio" controls src="${url}"></audio>`;
  }
  if (/\.(txt|srt)$/.test(name)) {
    return `<pre class="artifact-preview text" data-text-preview="${url}">正在载入 ${esc(item.name)}...</pre>`;
  }
  return "";
}

async function hydrateArtifactTextPreviews() {
  const nodes = [...document.querySelectorAll("[data-text-preview]")];
  await Promise.all(nodes.map(async (node) => {
    try {
      const response = await fetch(node.dataset.textPreview, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const text = (await response.text()).replace(/^\uFEFF/, "").trim();
      node.textContent = text || "（空文件）";
    } catch (error) {
      node.textContent = `载入失败：${error.message}`;
    }
  }));
}

function snippet(text, max = 180) {
  const clean = String(text ?? "").replace(/\s+/g, " ").trim();
  return clean.length > max ? `${clean.slice(0, max)}...` : clean;
}

const BULK_DEFS = {
  projects: {
    label: "项目",
    remove: (id) => api(`/api/v1/projects/${id}`, { method: "DELETE" }),
    reload: async () => loadProjects(),
  },
  assets: {
    label: "素材",
    remove: (id) => api(`/api/v1/projects/${state.projectId}/assets/${id}`, {
      method: "DELETE",
    }),
    reload: async () => {
      await loadAssets();
      await loadProjects();
    },
  },
  scripts: {
    label: "脚本",
    remove: (id) => api(`/api/v1/scripts/${id}`, { method: "DELETE" }),
    reload: async (ids) => {
      await loadScripts();
      if (state.lastScript && ids.includes(state.lastScript.id)) {
        state.lastScript = null;
        $("script-output-wrap").hidden = true;
        $("script-output").textContent = "";
      }
    },
  },
  moduleJobs: {
    label: "任务",
    remove: (id) => api(`/api/v1/module-jobs/${id}`, { method: "DELETE" }),
    reload: async () => loadModuleJobs(state.module),
  },
  jobs: {
    label: "任务",
    remove: (id) => api(`/api/v1/jobs/${id}`, { method: "DELETE" }),
    reload: async (ids) => {
      await loadJobs();
      if (state.artifactJobId && ids.includes(state.artifactJobId)) {
        $("artifact-panel").hidden = true;
        $("artifact-list").innerHTML = "";
        state.artifactJobId = "";
      }
    },
  },
  artifacts: {
    label: "产物",
    remove: (path) => api(
      `/api/v1/jobs/${state.artifactJobId}/files/${path.split("/").map(encodeURIComponent).join("/")}`,
      { method: "DELETE" },
    ),
    reload: async () => showArtifacts(state.artifactJobId),
  },
  pipelines: {
    label: "流水线",
    remove: (id) => api(`/api/v1/pipelines/${id}`, { method: "DELETE" }),
    reload: async () => loadPipelines(),
  },
  documents: {
    label: "文档",
    remove: (id) => api(
      `/api/v1/knowledge-bases/${state.selectedKb}/documents/${id}`,
      { method: "DELETE" },
    ),
    reload: async () => {
      await loadDocuments(state.selectedKb);
      await loadKnowledge();
    },
  },
  styles: {
    label: "风格",
    remove: (id) => api(`/api/v1/styles/${id}`, { method: "DELETE" }),
    reload: async () => loadStyles(),
  },
  calendar: {
    label: "日历条目",
    remove: (id) => api(`/api/v1/content-calendar/${id}`, { method: "DELETE" }),
    reload: async () => loadCalendar(),
  },
  complianceReports: {
    label: "质检报告",
    remove: (id) => api(`/api/v1/compliance/reports/${id}`, { method: "DELETE" }),
    reload: async () => loadComplianceReports(),
  },
  publishAccounts: {
    label: "发布账号",
    remove: (id) => api(`/api/v1/publish/accounts/${id}`, { method: "DELETE" }),
    reload: async () => loadPublishing(),
  },
  publishJobs: {
    label: "发布计划",
    remove: (id) => api(`/api/v1/publish/jobs/${id}`, { method: "DELETE" }),
    reload: async () => loadPublishJobs(),
  },
};

const BULK_GROUPS = [
  { kind: "projects", listId: "project-list" },
  { kind: "assets", listId: "asset-list" },
  { kind: "scripts", listId: "script-list" },
  { kind: "moduleJobs", listId: "module-job-list" },
  { kind: "jobs", listId: "jobs-body", hostId: "jobs-bulk-host" },
  { kind: "artifacts", listId: "artifact-list" },
  { kind: "pipelines", listId: "pipeline-list" },
  { kind: "documents", listId: "doc-list" },
  { kind: "styles", listId: "style-list" },
  { kind: "calendar", listId: "calendar-list" },
  { kind: "complianceReports", listId: "compliance-report-list" },
  { kind: "publishAccounts", listId: "publish-account-list" },
  { kind: "publishJobs", listId: "publish-job-list" },
];

function bulkCheckbox(kind, id, label = "") {
  return `<input type="checkbox" class="bulk-check" data-bulk-check="${esc(kind)}"
    value="${esc(id)}" aria-label="选择${esc(label)}" />`;
}

function installBulkBars() {
  BULK_GROUPS.forEach(({ kind, listId, hostId }) => {
    const list = $(listId);
    if (!list || document.querySelector(`[data-bulk-bar="${kind}"]`)) return;
    const bar = document.createElement("div");
    bar.className = "bulk-bar";
    bar.dataset.bulkBar = kind;
    bar.hidden = true;
    bar.innerHTML = `
      <button type="button" class="btn ghost small" data-bulk-toggle="${esc(kind)}">批量管理</button>
      <div class="bulk-tools" data-bulk-tools="${esc(kind)}" hidden>
        <label class="bulk-all">
          <input type="checkbox" data-bulk-all="${esc(kind)}" />
          全选
        </label>
        <span class="muted" data-bulk-count="${esc(kind)}">已选 0 项</span>
        ${kind === "artifacts" ? `<button type="button" class="btn small" data-bulk-export="${esc(kind)}" disabled>保存到文件夹</button>` : ""}
        <button type="button" class="btn ghost small danger" data-bulk-delete="${esc(kind)}" disabled>
          批量删除
        </button>
      </div>`;
    const host = hostId ? $(hostId) : (list.tagName === "TBODY" ? list.closest("table") : list);
    host.parentNode.insertBefore(bar, host);
  });
}

function updateBulkBar(kind) {
  const bar = document.querySelector(`[data-bulk-bar="${kind}"]`);
  if (!bar) return;
  const group = BULK_GROUPS.find((item) => item.kind === kind);
  const list = group ? $(group.listId) : null;
  const managing = Boolean(list?.classList.contains("managing"));
  const checks = [...document.querySelectorAll(`[data-bulk-check="${kind}"]`)];
  const selected = checks.filter((item) => item.checked);
  bar.hidden = checks.length === 0;
  bar.classList.toggle("idle", !managing);
  bar.querySelector(`[data-bulk-tools="${kind}"]`).hidden = !managing;
  bar.querySelector(`[data-bulk-toggle="${kind}"]`).textContent = managing ? "退出管理" : "批量管理";
  bar.querySelector(`[data-bulk-count="${kind}"]`).textContent = `已选 ${selected.length} 项`;
  const all = bar.querySelector(`[data-bulk-all="${kind}"]`);
  all.checked = checks.length > 0 && selected.length === checks.length;
  all.indeterminate = selected.length > 0 && selected.length < checks.length;
  bar.querySelector(`[data-bulk-delete="${kind}"]`).disabled = selected.length === 0;
  const exportButton = bar.querySelector(`[data-bulk-export="${kind}"]`);
  if (exportButton) exportButton.disabled = selected.length === 0;
}

function toggleBulkManage(kind) {
  const group = BULK_GROUPS.find((item) => item.kind === kind);
  if (!group) return;
  const list = $(group.listId);
  if (!list) return;
  const managing = !list.classList.contains("managing");
  list.classList.toggle("managing", managing);
  if (!managing) {
    document.querySelectorAll(`[data-bulk-check="${kind}"]`).forEach((item) => {
      item.checked = false;
    });
  }
  updateBulkBar(kind);
}

function updateAllBulkBars() {
  BULK_GROUPS.forEach(({ kind }) => updateBulkBar(kind));
}

function setBulkAll(kind, checked) {
  document.querySelectorAll(`[data-bulk-check="${kind}"]`).forEach((item) => {
    item.checked = checked;
  });
  updateBulkBar(kind);
}

async function deleteSelectedBulk(kind) {
  const definition = BULK_DEFS[kind];
  if (!definition) return;
  if (kind === "assets" && !state.projectId) {
    toast("先选择项目");
    return;
  }
  if (kind === "documents" && !state.selectedKb) {
    toast("先选择知识库");
    return;
  }
  const ids = [...document.querySelectorAll(`[data-bulk-check="${kind}"]`)]
    .filter((item) => item.checked)
    .map((item) => item.value);
  if (!ids.length) return;
  if (!window.confirm(`确定删除选中的 ${ids.length} 个${definition.label}吗？此操作不可撤销。`)) {
    return;
  }

  const button = document.querySelector(`[data-bulk-delete="${kind}"]`);
  if (button) button.disabled = true;
  let deleted = 0;
  const failures = [];
  for (const id of ids) {
    try {
      await definition.remove(id);
      deleted += 1;
    } catch (error) {
      failures.push(error.message);
    }
  }
  await definition.reload(ids);
  updateAllBulkBars();
  if (failures.length) {
    toast(`已删除 ${deleted} 个，${failures.length} 个失败：${failures[0]}`, true);
  } else {
    toast(`已删除 ${deleted} 个${definition.label}`);
  }
}

async function loadKnowledge() {
  try {
    const data = await api("/api/v1/knowledge-bases");
    const items = data.items || [];
    $("kb-empty").hidden = items.length > 0;
    $("kb-list").innerHTML = items.map((item) => `
      <li class="list-item selectable ${item.id === state.selectedKb ? "selected" : ""}"
          data-kb="${esc(item.id)}" data-name="${esc(item.name)}">
        <span>${esc(item.name)}</span>
        <span class="muted">${esc(item.document_count)} 文档 · ${esc(item.chunk_count)} 段</span>
      </li>`).join("");

    if (!items.some((item) => item.id === state.selectedKb)) {
      state.selectedKb = "";
      $("kb-selected").textContent = "未选择";
      $("doc-list").innerHTML = "";
      $("doc-empty").hidden = true;
      updateBulkBar("documents");
    }
    if (!state.selectedKb && items.length) {
      selectKb(items[0].id, items[0].name);
    }
  } catch (error) {
    toast(error.message, true);
  }
}

function selectKb(id, name) {
  state.selectedKb = id;
  $("kb-selected").textContent = name || id;
  document.querySelectorAll("#kb-list [data-kb]").forEach((node) => {
    node.classList.toggle("selected", node.dataset.kb === id);
  });
  loadDocuments(id);
}

async function loadDocuments(kbId) {
  if (!kbId) return;
  try {
    const data = await api(`/api/v1/knowledge-bases/${kbId}/documents`);
    const items = data.items || [];
    $("doc-empty").hidden = items.length > 0;
    $("doc-list").innerHTML = items.map((item) => `
      <li class="list-item">
        ${bulkCheckbox("documents", item.id, item.filename)}
        <span>${esc(item.filename)}</span>
        <span class="muted">${esc(item.chunk_count)} 段</span>
        <button type="button" class="btn ghost small row-delete" data-doc="${esc(item.id)}">删除</button>
      </li>`).join("");
    updateBulkBar("documents");
  } catch (error) {
    toast(error.message, true);
  }
}

async function createKnowledge() {
  const name = $("kb-name").value.trim();
  if (!name) {
    toast("先输入名称");
    return;
  }
  try {
    const kb = await api("/api/v1/knowledge-bases", { method: "POST", body: { name } });
    $("kb-name").value = "";
    toast("已创建");
    state.selectedKb = "";
    await loadKnowledge();
    selectKb(kb.id, kb.name);
  } catch (error) {
    toast(error.message, true);
  }
}

async function uploadDocument() {
  if (!state.selectedKb) {
    toast("先选择一个知识库");
    return;
  }
  const file = $("kb-file").files?.[0];
  if (!file) {
    toast("先选择文件");
    return;
  }
  const button = $("upload-doc");
  button.disabled = true;
  try {
    const form = new FormData();
    form.append("file", file);
    await api(`/api/v1/knowledge-bases/${state.selectedKb}/documents`, {
      method: "POST",
      body: form,
    });
    $("kb-file").value = "";
    toast("已上传");
    await loadDocuments(state.selectedKb);
    loadKnowledge();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function deleteDocument(documentId) {
  if (!state.selectedKb) return;
  if (!window.confirm("确定删除这个文档吗？")) return;
  try {
    await api(`/api/v1/knowledge-bases/${state.selectedKb}/documents/${documentId}`, {
      method: "DELETE",
    });
    toast("已删除");
    await loadDocuments(state.selectedKb);
    loadKnowledge();
  } catch (error) {
    toast(error.message, true);
  }
}

async function searchKnowledge() {
  if (!state.selectedKb) {
    toast("先选择一个知识库");
    return;
  }
  const query = $("kb-query").value.trim();
  if (!query) return;
  try {
    const data = await api(`/api/v1/knowledge-bases/${state.selectedKb}/search`, {
      method: "POST",
      body: { query, top_k: 5 },
    });
    const hits = data.hits || [];
    $("kb-hits-empty").hidden = hits.length > 0;
    $("kb-hits").innerHTML = hits.map((hit) => `
      <li class="list-item stacked">
        <div class="hit-meta">
          <span>${esc(hit.filename)} · 第 ${esc(hit.ordinal + 1)} 段</span>
          <span class="muted">score ${esc(hit.score)}</span>
        </div>
        <div class="hit-snippet">${esc(snippet(hit.content))}</div>
      </li>`).join("");
  } catch (error) {
    toast(error.message, true);
  }
}

function formatPlanPrice(plan) {
  const cents = Number(plan.price_monthly_cents ?? plan.price_cents ?? 0);
  if (!cents) return "免费";
  return `¥${(cents / 100).toFixed(0)}<small> / 月</small>`;
}

function renderPlanCards(plans, currentCode, currentCredits) {
  const container = $("plan-cards");
  if (!plans.length) {
    container.innerHTML = '<div class="empty">暂时没有可用套餐</div>';
    return;
  }
  const canUpgrade = Boolean(state.meta?.demo_mode);
  const tierNames = {
    trial: "体验",
    basic: "入门",
    pro: "专业",
    enterprise: "旗舰",
  };
  container.innerHTML = plans.map((plan) => {
    const credits = Number(plan.credits) || 0;
    const isCurrent = plan.id === currentCode;
    const isDowngrade = credits < currentCredits;
    const isRecommended = plan.id === "pro";
    const disabled = isCurrent || isDowngrade || !canUpgrade;
    const action = isCurrent
      ? "当前套餐"
      : isDowngrade
        ? "暂不支持降级"
        : canUpgrade
          ? `升级到${plan.name}`
          : "联系管理员开通";
    const note = plan.id === "trial"
      ? "适合先体验完整工作流"
      : plan.id === "pro"
        ? "适合稳定批量生产短视频"
        : plan.id === "enterprise"
          ? "适合多团队和更高并发"
          : "适合小团队日常内容生产";
    const yearly = Number(plan.price_yearly_cents) || 0;
    const features = [
      `${credits.toLocaleString()} 积分 / 月`,
      `${Number(plan.render_minutes) || 0} 分钟渲染`,
      `${Number(plan.storage_gb) || 0} GB 存储`,
      `${Number(plan.seats) || 0} 个成员席位`,
      `${Number(plan.concurrency) || 0} 个并发任务`,
    ];
    const resourceLine = `项目 ${Number(plan.projects) || 0} · 素材 ${Number(plan.assets) || 0} · 文案 ${Number(plan.scripts) || 0} · 任务 ${Number(plan.jobs) || 0}`;
    return `
      <article class="plan-card ${isCurrent ? "current" : ""} ${isRecommended ? "recommended" : ""}">
        <div class="plan-card-head">
          <div>
            <div class="plan-tier">${esc(tierNames[plan.id] || "套餐")}</div>
            <h4>${esc(plan.name)}</h4>
          </div>
          ${isCurrent
            ? '<span class="plan-badge">当前</span>'
            : isRecommended
              ? '<span class="plan-badge recommended-badge">推荐</span>'
              : ""}
        </div>
        <div class="plan-card-price">
          <div class="plan-price">${formatPlanPrice(plan)}</div>
          ${yearly ? `<div class="plan-yearly">年付 ¥${(yearly / 100).toFixed(0)}</div>` : ""}
        </div>
        <p class="plan-card-note">${esc(note)}</p>
        <ul class="plan-features">
          ${features.map((feature) => `<li>${esc(feature)}</li>`).join("")}
        </ul>
        <div class="plan-card-quota">${esc(resourceLine)}</div>
        <button
          type="button"
          class="btn ${isCurrent || isDowngrade || !canUpgrade ? "" : "primary"}"
          ${disabled ? "disabled" : `data-upgrade-plan="${esc(plan.id)}"`}
        >${esc(action)}</button>
      </article>`;
  }).join("");
}

async function upgradePlan(planId, button) {
  if (!planId || button.disabled) return;
  const label = button.textContent;
  button.disabled = true;
  button.textContent = "开通中...";
  try {
    const data = await api("/api/v1/billing/upgrade", {
      method: "POST",
      body: { plan: planId },
    });
    toast(`套餐已升级，补充 ${data.granted || 0} 积分`);
    await loadBilling();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}

async function loadBilling() {
  try {
    if (!state.meta) {
      try {
        state.meta = await api("/api/v1/meta");
      } catch {
        state.meta = null;
      }
    }
    const [plan, quotas, credit, catalog] = await Promise.all([
      api("/api/v1/billing/plan"),
      api("/api/v1/quotas"),
      api("/api/v1/billing/credits"),
      api("/api/v1/public/plans"),
    ]);
    $("plan-name").textContent = plan.name || "-";
    $("plan-price").textContent = plan.price_cents === 0
      ? "免费"
      : `¥${(plan.price_cents / 100).toFixed(0)} / ${plan.period}`;
    const limitLabels = {
      credits: "积分额度",
      render_minutes: "渲染分钟",
      storage_gb: "存储 GB",
      concurrency: "并发任务",
      seats: "成员席位",
    };
    $("plan-limits").innerHTML = `
      <div class="plan-stat-grid">
        ${Object.entries(plan.limits || {}).map(([key, value]) => `
          <div class="plan-stat">
            <span>${esc(limitLabels[key] || key)}</span>
            <b>${esc(value)}</b>
          </div>`).join("")}
        <div class="plan-stat highlight">
          <span>积分余额</span>
          <b>${esc(credit.balance)}</b>
        </div>
      </div>`;
    renderPlanCards(catalog.items || [], plan.code, Number(plan.credits) || 0);

    $("usage-period").textContent = quotas.period === "current" ? "当前周期" : quotas.period || "";
    const totalCredits = Number(plan.credits) || 0;
    const creditPercent = totalCredits > 0
      ? Math.min(100, Math.round((Number(credit.balance) / totalCredits) * 100))
      : 0;
    const ledger = (credit.ledger || []).slice(0, 6).map((item) => `
      <div class="list-item">
        <span>${esc(USAGE_TEXT[item.kind] || item.kind)}</span>
        <span class="${item.amount >= 0 ? "" : "muted"}">${item.amount > 0 ? "+" : ""}${esc(item.amount)}</span>
        <span class="muted">${esc(formatTime(item.created_at))}</span>
      </div>`).join("");
    $("usage-list").innerHTML = `
      <div class="usage-legend">
        <span>资源用量：已用 / 上限</span>
        <span>积分：剩余 / 套餐总额</span>
      </div>
      <div class="usage-row">
        <div class="line"><span>积分余额</span><span class="muted">${esc(credit.balance)} / ${esc(plan.credits)}</span></div>
        <div class="bar"><div class="bar-fill" style="width:${creditPercent}%"></div></div>
      </div>
      <div class="usage-bars">` + (quotas.items || []).map((item) => {
      const limit = Number(item.limit) || 0;
      const used = Number(item.used) || 0;
      const percent = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
      const usedText = item.unit === "bytes" ? formatBytes(used) : used;
      const limitText = item.unit === "bytes" ? formatBytes(limit) : limit;
      if (limit <= 0) {
        return `
          <div class="usage-row count-only">
            <div class="line"><span>${esc(USAGE_TEXT[item.kind] || item.kind)}</span><span class="muted">${usedText} ${esc(item.unit || "个")}</span></div>
          </div>`;
      }
      return `
        <div class="usage-row">
          <div class="line"><span>${esc(USAGE_TEXT[item.kind] || item.kind)}</span><span class="muted">${usedText} / ${limitText}</span></div>
          <div class="bar"><div class="bar-fill" style="width:${percent}%"></div></div>
        </div>`;
    }).join("") + "</div>";
    $("credit-ledger").innerHTML = `
      <div class="ledger-list">${ledger || '<div class="empty">暂无积分变动</div>'}</div>`;
    const canUpgrade = Boolean(state.meta?.demo_mode);
    $("billing-mode-badge").textContent = canUpgrade
      ? "演示环境即时生效"
      : "请联系管理员开通";
    $("billing-mode-badge").classList.toggle("muted", !canUpgrade);
    $("billing-upgrade-note").textContent = canUpgrade
      ? "当前为演示环境，升级会立即生效并补充积分。"
      : "正式环境暂不支持在线升级；请联系管理员或使用激活码开通。";
  } catch (error) {
    toast(error.message, true);
  }
}

function renderBrandPreview(kit) {
  const primary = /^#[0-9a-fA-F]{6}$/.test(String(kit.primary_color || ""))
    ? kit.primary_color
    : "#0f766e";
  const secondary = /^#[0-9a-fA-F]{6}$/.test(String(kit.secondary_color || ""))
    ? kit.secondary_color
    : "#2563eb";
  const preview = $("brand-preview");
  preview.style.setProperty("--brand-primary", primary);
  preview.style.setProperty("--brand-secondary", secondary);
  $("brand-preview-name").textContent = kit.brand_name || "企业品牌";
  $("brand-preview-slogan").textContent = kit.slogan || "品牌口号会显示在这里";
  $("brand-color-label").textContent = `${primary} / ${secondary}`;
  $("brand-primary-dot").style.background = `linear-gradient(135deg, ${primary}, ${secondary})`;

  const logo = $("brand-logo-preview");
  if (kit.logo_storage_key) {
    logo.innerHTML = `<img src="${mediaUrl(`/api/v1/brand-kit/logo?v=${Date.now()}`)}" alt="${esc(kit.brand_name || "品牌 Logo")}" />`;
  } else {
    logo.textContent = "LOGO";
  }

  const configured = Boolean(kit.configured);
  $("brand-status").textContent = configured ? "已配置" : "未保存";
  $("brand-status").className = `pill ${configured ? "ok" : "muted"}`;
}

function populateBrandForm(kit) {
  $("brand-name").value = kit.brand_name || "";
  $("brand-slogan").value = kit.slogan || "";
  $("brand-voice").value = kit.voice_tone || "";
  $("brand-font").value = kit.font_family || "";
  $("brand-intro").value = kit.intro_text || "";
  $("brand-outro").value = kit.outro_text || "";
  $("brand-primary").value = kit.primary_color || "#0f766e";
  $("brand-secondary").value = kit.secondary_color || "#2563eb";
  $("brand-watermark").value = kit.watermark_text || "";
  updateBrandSettingsState();
}

function brandPayload() {
  return {
    brand_name: $("brand-name").value.trim(),
    slogan: $("brand-slogan").value.trim(),
    voice_tone: $("brand-voice").value.trim(),
    font_family: $("brand-font").value.trim(),
    intro_text: $("brand-intro").value.trim(),
    outro_text: $("brand-outro").value.trim(),
    primary_color: $("brand-primary").value,
    secondary_color: $("brand-secondary").value,
    watermark_text: $("brand-watermark").value.trim(),
  };
}

function updateBrandSettingsState() {
  const kit = state.brandKit || {};
  const current = brandPayload();
  const dirty = Object.entries(current).some(
    ([key, value]) => String(value || "") !== String(kit[key] || ""),
  );
  $("save-brand").hidden = !dirty;
  $("reset-brand").hidden = !dirty;
}

function resetBrandSettings() {
  if (!state.brandKit) return;
  populateBrandForm(state.brandKit);
  updateBrandSettingsState();
  toast("品牌资产修改已取消");
}

async function loadBrandKit() {
  try {
    const kit = await api("/api/v1/brand-kit");
    state.brandKit = kit;
    populateBrandForm(kit);
    renderBrandPreview(kit);
  } catch (error) {
    toast(error.message, true);
  }
}

async function saveBrandKit() {
  const button = $("save-brand");
  button.disabled = true;
  try {
    const kit = await api("/api/v1/brand-kit", {
      method: "PUT",
      body: brandPayload(),
    });
    state.brandKit = kit;
    populateBrandForm(kit);
    renderBrandPreview(kit);
    toast("品牌资产已保存");
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function uploadBrandLogo() {
  const input = $("brand-logo-file");
  const file = input.files?.[0];
  if (!file) {
    toast("先选择 Logo 文件");
    return;
  }
  const button = $("upload-brand-logo");
  button.disabled = true;
  try {
    const form = new FormData();
    form.append("file", file);
    const kit = await api("/api/v1/brand-kit/logo", {
      method: "POST",
      body: form,
    });
    input.value = "";
    state.brandKit = kit;
    renderBrandPreview(kit);
    updateBrandSettingsState();
    toast("Logo 已上传");
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

function styleLoraStatus(status) {
  const map = {
    none: ["未配置", "muted"],
    queued: ["训练已排队", "muted"],
    training: ["训练中", "warn"],
    needs_config: ["待接训练服务", "warn"],
    ready: ["LoRA 可用", "ok"],
    failed: ["训练失败", "bad"],
  };
  return map[status] || [status || "未配置", "muted"];
}

function styleSwatches(palette) {
  return (palette || [])
    .slice(0, 6)
    .map((color) => `<span class="style-swatch" style="background:${esc(color)}"></span>`)
    .join("");
}

function renderStyleLoraStatus(status) {
  const [label, kind] = styleLoraStatus(status);
  const node = $("style-lora-status");
  node.textContent = label;
  node.className = `pill ${kind}`;
}

function renderStyleList() {
  const list = $("style-list");
  const items = state.styles || [];
  $("style-empty").hidden = items.length > 0;
  list.innerHTML = items.map((style) => `
    <li class="list-item selectable stacked ${style.id === state.selectedStyleId ? "selected" : ""}" data-style="${esc(style.id)}">
      <div class="list-main">
        <div class="row" style="justify-content:space-between">
          <span class="row">${bulkCheckbox("styles", style.id, style.name)}<b>${esc(style.name)}</b></span>
          ${style.is_default ? '<span class="pill ok">默认</span>' : ""}
        </div>
        <div class="list-meta">${esc(style.description || "未填写风格说明")}</div>
        <div class="style-swatches">${styleSwatches(style.palette)}</div>
      </div>
    </li>`).join("");
  updateBulkBar("styles");
}

function resetStyleForm() {
  state.selectedStyleId = "";
  $("style-editor-title").textContent = "新建风格模板";
  $("style-default-badge").textContent = "未设为默认";
  $("style-default-badge").className = "pill muted";
  $("delete-style").disabled = true;
  $("set-default-style").disabled = true;
  $("style-name").value = "";
  $("style-description").value = "";
  $("style-prompt").value = "";
  $("style-negative").value = "";
  $("style-model").value = "";
  $("style-rhythm").value = "中速";
  $("style-subtitle").value = "白字黑边";
  $("style-primary").value = "#0f766e";
  $("style-secondary").value = "#2563eb";
  $("style-lora-name").value = "";
  $("style-lora-trigger").value = "";
  $("style-lora-base").value = "";
  renderStyleLoraStatus("none");
  state.styleBaseline = stylePayload();
  updateStyleSettingsState();
  renderStyleList();
}

function selectStyle(styleId) {
  const style = (state.styles || []).find((item) => item.id === styleId);
  if (!style) return;
  state.selectedStyleId = style.id;
  $("style-editor-title").textContent = style.name || "编辑风格模板";
  $("style-default-badge").textContent = style.is_default ? "当前默认风格" : "未设为默认";
  $("style-default-badge").className = `pill ${style.is_default ? "ok" : "muted"}`;
  $("delete-style").disabled = false;
  $("set-default-style").disabled = Boolean(style.is_default);
  $("style-name").value = style.name || "";
  $("style-description").value = style.description || "";
  $("style-prompt").value = style.prompt || "";
  $("style-negative").value = style.negative_prompt || "";
  $("style-model").value = style.model_ref || "";
  $("style-rhythm").value = style.shot_rhythm || "中速";
  $("style-subtitle").value = style.subtitle_style || "白字黑边";
  $("style-primary").value = style.palette?.[0] || "#0f766e";
  $("style-secondary").value = style.palette?.[1] || "#2563eb";
  $("style-lora-name").value = style.lora_name || "";
  $("style-lora-trigger").value = style.lora_trigger || "";
  $("style-lora-base").value = style.lora_base_model || "";
  renderStyleLoraStatus(style.lora_status || "none");
  state.styleBaseline = stylePayload();
  updateStyleSettingsState();
  renderStyleList();
}

function stylePayload() {
  return {
    name: $("style-name").value.trim(),
    description: $("style-description").value.trim(),
    prompt: $("style-prompt").value.trim(),
    negative_prompt: $("style-negative").value.trim(),
    model_ref: $("style-model").value.trim(),
    palette: [$("style-primary").value, $("style-secondary").value],
    shot_rhythm: $("style-rhythm").value,
    subtitle_style: $("style-subtitle").value.trim(),
    lora_name: $("style-lora-name").value.trim(),
    lora_trigger: $("style-lora-trigger").value.trim(),
    lora_base_model: $("style-lora-base").value.trim(),
  };
}

function updateStyleSettingsState() {
  const dirty = JSON.stringify(stylePayload()) !== JSON.stringify(state.styleBaseline || {});
  $("save-style").hidden = !dirty;
  $("reset-style").hidden = !dirty;
}

function resetStyleSettings() {
  if (state.selectedStyleId) {
    selectStyle(state.selectedStyleId);
  } else {
    resetStyleForm();
  }
  toast("风格模板修改已取消");
}

async function loadStyles() {
  try {
    const [styles, projects] = await Promise.all([
      api("/api/v1/styles"),
      api("/api/v1/projects"),
    ]);
    state.styles = styles.items || [];
    $("style-lora-project").innerHTML = `<option value="">先选择项目</option>`
      + (projects.items || [])
        .map((project) => `<option value="${esc(project.id)}">${esc(project.name)}</option>`)
        .join("");
    if (state.selectedStyleId && state.styles.some((item) => item.id === state.selectedStyleId)) {
      selectStyle(state.selectedStyleId);
    } else if (state.styles.length) {
      selectStyle(state.styles[0].id);
    } else {
      resetStyleForm();
    }
  } catch (error) {
    toast(error.message, true);
  }
}

async function saveStyle(silent = false) {
  const name = $("style-name").value.trim();
  if (!name) {
    if (!silent) toast("先填写风格名称");
    return null;
  }
  const body = stylePayload();
  const button = $("save-style");
  button.disabled = true;
  try {
    const saved = state.selectedStyleId
      ? await api(`/api/v1/styles/${state.selectedStyleId}`, { method: "PATCH", body })
      : await api("/api/v1/styles", { method: "POST", body });
    state.selectedStyleId = saved.id;
    await loadStyles();
    if (!silent) toast("风格模板已保存");
    return saved;
  } catch (error) {
    toast(error.message, true);
    return null;
  } finally {
    button.disabled = false;
  }
}

async function setDefaultStyle() {
  if (!state.selectedStyleId) return;
  try {
    await api(`/api/v1/styles/${state.selectedStyleId}/default`, { method: "POST" });
    await loadStyles();
    toast("已设为默认风格");
  } catch (error) {
    toast(error.message, true);
  }
}

async function deleteStyle() {
  if (!state.selectedStyleId) return;
  if (!window.confirm("确定删除这个风格模板吗？")) return;
  try {
    await api(`/api/v1/styles/${state.selectedStyleId}`, { method: "DELETE" });
    state.selectedStyleId = "";
    await loadStyles();
    toast("风格模板已删除");
  } catch (error) {
    toast(error.message, true);
  }
}

async function trainStyleLora() {
  const projectId = $("style-lora-project").value;
  if (!projectId) {
    toast("先选择包含图片素材的项目");
    return;
  }
  const saved = await saveStyle(true);
  if (!saved) return;
  const button = $("train-style-lora");
  button.disabled = true;
  try {
    const job = await api(`/api/v1/styles/${saved.id}/lora/train`, {
      method: "POST",
      body: { project_id: projectId },
    });
    toast(`LoRA 训练已排队，消耗 ${job.credits_cost} 积分`);
    await loadStyles();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function loadSettingsPage() {
  await Promise.all([
    loadModels(),
    loadWorkspacePreferences(),
    loadSettingsStatus(),
  ]);
}

async function loadModelDefaults() {
  try {
    const data = await api("/api/v1/settings/defaults");
    state.modelDefaults = data.models || {};
    state.autoModels = data.auto || state.autoModels;
  } catch {
    state.modelDefaults = {};
  }
}

function applyWorkspacePreferences() {
  const prefs = state.preferences;
  if (!prefs) return;
  if (prefs.default_aspect && $("project-aspect")) {
    $("project-aspect").value = prefs.default_aspect;
  }
  if (prefs.default_platform) {
    if ($("prompt-platform")) $("prompt-platform").value = prefs.default_platform;
    if ($("script-platform")) $("script-platform").value = prefs.default_platform;
  }
  if (prefs.default_quality && $("module-quality")) {
    $("module-quality").value = prefs.default_quality;
  }
}

function populateWorkspacePreferences(prefs) {
  if ($("pref-default-platform")) $("pref-default-platform").value = prefs.default_platform || "抖音";
  if ($("pref-default-aspect")) $("pref-default-aspect").value = prefs.default_aspect || "9:16";
  if ($("pref-default-quality")) $("pref-default-quality").value = prefs.default_quality || "standard";
  if ($("pref-subtitle-style")) $("pref-subtitle-style").value = prefs.default_subtitle_style || "";
  if ($("pref-default-voice")) $("pref-default-voice").value = prefs.default_voice || "";
  const checks = {
    "pref-auto-subtitle": "auto_subtitle",
    "pref-auto-cover": "auto_cover",
    "pref-auto-bgm": "auto_bgm",
    "pref-quality-gate": "quality_gate",
    "pref-keep-audio": "keep_original_audio",
    "pref-notify-success": "notify_success",
    "pref-notify-failure": "notify_failure",
    "pref-notify-low-credits": "notify_low_credits",
  };
  Object.entries(checks).forEach(([id, key]) => {
    if ($(id)) $(id).checked = prefs[key] !== false;
  });
  if ($("pref-storage-root") && prefs.storage_root) {
    $("pref-storage-root").value = prefs.storage_root;
  }
  updateStorageRootState();
  updateWorkspaceSettingsState();
}

async function loadWorkspacePreferences() {
  try {
    const prefs = await api("/api/v1/settings/preferences");
    state.preferences = prefs;
    populateWorkspacePreferences(prefs);
    applyWorkspacePreferences();
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadSettingsStatus() {
  try {
    const status = await api("/api/v1/settings/status");
    const items = [
      {
        label: "文本模型",
        value: status.llm.model || "未配置",
        ok: status.llm.configured,
        note: status.llm.configured ? "API Key 已配置" : "未配置 API Key",
      },
      {
        label: "视频渲染",
        value: status.ffmpeg.configured ? "FFmpeg 可用" : "FFmpeg 不可用",
        ok: status.ffmpeg.configured,
        note: status.ffmpeg.path || "",
      },
      {
        label: "图片能力",
        value: status.image.provider,
        ok: status.image.configured,
        note: status.image.configured
          ? `模型：${status.image.model || "默认"}`
          : "当前使用占位图",
      },
      {
        label: "语音识别",
        value: status.asr.provider,
        ok: status.asr.configured,
        note: status.asr.configured ? "已配置" : "待接入",
      },
      {
        label: "存储目录",
        value: status.storage.root,
        ok: true,
        note: status.storage.mode === "local" ? "本地磁盘" : status.storage.mode,
      },
    ];
    $("settings-status").innerHTML = items.map((item) => `
      <div class="status-card">
        <span class="status-label">${esc(item.label)}</span>
        <span class="status-value">${esc(item.value)}</span>
        <span class="pill ${item.ok ? "ok" : "muted"}">${esc(item.ok ? "就绪" : "待配置")}</span>
        <span class="muted">${esc(item.note)}</span>
      </div>`).join("");
    if ($("storage-mode")) {
      $("storage-mode").textContent = status.storage.mode === "local" ? "本地" : status.storage.mode;
    }
  } catch (error) {
    toast(error.message, true);
  }
}

async function saveWorkspaceSettings() {
  const body = workspacePreferencesBody();
  const button = $("save-workspace-settings");
  button.disabled = true;
  try {
    state.preferences = await api("/api/v1/settings/preferences", {
      method: "PUT",
      body,
    });
    populateWorkspacePreferences(state.preferences);
    applyWorkspacePreferences();
    toast("工作区设置已保存");
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    updateWorkspaceSettingsState();
  }
}

function workspacePreferencesBody() {
  return {
    default_platform: $("pref-default-platform").value,
    default_aspect: $("pref-default-aspect").value,
    default_quality: $("pref-default-quality").value,
    default_subtitle_style: $("pref-subtitle-style").value.trim(),
    default_voice: $("pref-default-voice").value.trim(),
    auto_subtitle: $("pref-auto-subtitle").checked,
    auto_cover: $("pref-auto-cover").checked,
    auto_bgm: $("pref-auto-bgm").checked,
    quality_gate: $("pref-quality-gate").checked,
    keep_original_audio: $("pref-keep-audio").checked,
    notify_success: $("pref-notify-success").checked,
    notify_failure: $("pref-notify-failure").checked,
    notify_low_credits: $("pref-notify-low-credits").checked,
  };
}

function workspacePreferencesDirty() {
  const saved = state.preferences;
  if (!saved) return false;
  const current = workspacePreferencesBody();
  return Object.entries(current).some(([key, value]) => {
    if (typeof value === "boolean") {
      return value !== (saved[key] !== false);
    }
    return String(value ?? "") !== String(saved[key] ?? "");
  });
}

function updateWorkspaceSettingsState() {
  const dirty = workspacePreferencesDirty();
  const badge = $("workspace-settings-state");
  badge.textContent = dirty ? "有未保存修改" : "未修改";
  badge.className = `pill ${dirty ? "warn" : "muted"}`;
  $("save-workspace-settings").hidden = !dirty;
  $("reset-workspace-settings").hidden = !dirty;
}

function resetWorkspaceSettings() {
  if (!state.preferences) return;
  populateWorkspacePreferences(state.preferences);
  updateWorkspaceSettingsState();
  toast("未保存的设置修改已取消");
}

const WORKSPACE_SETTING_IDS = [
  "pref-default-platform",
  "pref-default-aspect",
  "pref-default-quality",
  "pref-subtitle-style",
  "pref-default-voice",
  "pref-auto-subtitle",
  "pref-auto-cover",
  "pref-auto-bgm",
  "pref-quality-gate",
  "pref-keep-audio",
  "pref-notify-success",
  "pref-notify-failure",
  "pref-notify-low-credits",
];

function bindWorkspaceSettingEvents() {
  WORKSPACE_SETTING_IDS.forEach((id) => {
    if (!$(id)) return;
    $(id).addEventListener("input", updateWorkspaceSettingsState);
    $(id).addEventListener("change", updateWorkspaceSettingsState);
  });
}

async function applyStorageRoot() {
  const root = $("pref-storage-root").value.trim();
  if (!root) {
    toast("先填写存储目录");
    return;
  }
  const button = $("apply-storage-root");
  button.disabled = true;
  try {
    const data = await api("/api/v1/settings/storage", {
      method: "PUT",
      body: { root },
    });
    $("pref-storage-root").value = data.storage_root;
    await loadWorkspacePreferences();
    await loadSettingsStatus();
    updateStorageRootState();
    toast("存储位置已更新");
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

function updateStorageRootState() {
  const current = $("pref-storage-root").value.trim();
  const saved = String(state.preferences?.storage_root || "").trim();
  const dirty = Boolean(current) && current !== saved;
  $("apply-storage-root").hidden = !dirty;
  $("reset-storage-root").hidden = !dirty;
}

function resetStorageRoot() {
  $("pref-storage-root").value = String(state.preferences?.storage_root || "");
  updateStorageRootState();
  toast("存储位置修改已取消");
}

async function loadStorageBrowser(path = "") {
  const suffix = path ? `?path=${encodeURIComponent(path)}` : "";
  let data;
  try {
    data = await api(`/api/v1/settings/storage/browse${suffix}`);
  } catch (error) {
    if (!path) throw error;
    data = await api("/api/v1/settings/storage/browse");
  }
  state.storageBrowsePath = data.current || "";
  state.storageBrowseParent = data.parent || "";
  $("storage-browser-current").textContent = state.storageBrowsePath;
  $("storage-browser-roots").innerHTML = (data.roots || []).map((root) => `
    <button type="button" class="btn ghost small" data-storage-path="${esc(root.path)}">
      ${esc(root.name)}
    </button>`).join("");
  $("storage-browser-list").innerHTML = (data.items || []).length
    ? data.items.map((item) => `
      <li class="list-item" data-storage-path="${esc(item.path)}">
        <span>📁 ${esc(item.name)}</span>
        <span class="muted">打开</span>
      </li>`).join("")
    : `<li class="storage-browser-empty">当前目录没有子文件夹</li>`;
  $("storage-browser-up").disabled = !state.storageBrowseParent;
}

async function openStorageBrowser() {
  const initial = $("pref-storage-root").value.trim();
  toast("请在弹出的系统窗口中选择文件夹");
  try {
    const data = await api("/api/v1/settings/storage/pick", {
      method: "POST",
      body: { initial },
    });
    if (data.canceled) return;
    $("pref-storage-root").value = data.path;
    updateStorageRootState();
    toast("已选择存储目录，记得点击“应用存储位置”");
  } catch {
    toast("系统文件夹选择器不可用，改用内置浏览");
    await openBuiltinStorageBrowser();
  }
}

async function openBuiltinStorageBrowser() {
  const initial = $("pref-storage-root").value.trim();
  $("storage-browser-modal").hidden = false;
  $("storage-browser-current").textContent = "正在读取目录...";
  $("storage-browser-list").innerHTML = "";
  try {
    await loadStorageBrowser(initial);
  } catch (error) {
    toast(error.message, true);
  }
}

function selectStorageFolder() {
  if (!state.storageBrowsePath) return;
  $("pref-storage-root").value = state.storageBrowsePath;
  updateStorageRootState();
  $("storage-browser-modal").hidden = true;
  toast("已选择存储目录，记得点击“应用存储位置”");
}

function closeStorageBrowser() {
  $("storage-browser-modal").hidden = true;
}

async function loadModels() {
  try {
    const [catalog, defaults] = await Promise.all([
      api("/api/v1/settings/models"),
      api("/api/v1/settings/defaults"),
    ]);
    state.modelCatalog = catalog.items || [];
    state.modelDefaults = defaults.models || {};
    state.autoModels = catalog.auto || defaults.auto || {};
    $("model-body").innerHTML = state.modelCatalog.map((item) => `
      <tr>
        <td>${esc(item.provider)}</td>
        <td>${(item.capabilities || []).map((cap) => {
          const wired = (item.wired_capabilities || []).includes(cap);
          return `<span class="pill ${wired ? "" : "muted"}">${esc(cap)}${wired ? "" : " · 待接入"}</span>`;
        }).join(" ")}</td>
        <td class="muted">${(item.models || []).map(esc).join(", ")}</td>
        <td>${statusPill(item.status === "ready" && (item.wired_capabilities || []).length ? "succeeded" : "needs_config")}</td>
      </tr>`).join("");
    renderDefaultModels(state.modelCatalog, defaults.models || {}, state.autoModels);
  } catch (error) {
    toast(error.message, true);
  }
}

function renderDefaultModels(catalog, defaults, autoModels = {}) {
  const capabilities = new Map();
  for (const provider of catalog) {
    if (provider.status !== "ready") continue;
    for (const capability of provider.wired_capabilities || []) {
      if (!capabilities.has(capability)) capabilities.set(capability, []);
      const listKey = MODEL_LIST_KEYS[capability];
      for (const model of provider[listKey] || []) {
        capabilities.get(capability).push(`${provider.provider}:${model}`);
      }
    }
  }
  $("default-models").innerHTML = [...capabilities.entries()].map(([capability, options]) => `
      <label>${esc(CAPABILITY_TEXT[capability] || capability)}
        <select data-default-cap="${esc(capability)}">
        <option value="">自动（最便宜可用）</option>
        ${options.map((option) => `<option value="${esc(option)}" ${defaults[capability] === option ? "selected" : ""}>${esc(option)}</option>`).join("")}
      </select>
    </label>`).join("");
  const autoText = [...capabilities.keys()]
    .map((capability) => {
      const ref = autoModels[capability];
      return ref
        ? `${CAPABILITY_TEXT[capability] || capability} ${modelRefLabel(ref)}`
        : "";
    })
    .filter(Boolean)
    .join("；");
  $("defaults-hint").textContent = autoText
    ? `自动会使用当前已配置的最便宜可用模型：${autoText}。`
    : "自动会使用当前已配置的最便宜可用模型；配置 API Key 后会自动出现。";
  updateDefaultModelsState();
}

function currentDefaultModels() {
  const models = {};
  document.querySelectorAll("[data-default-cap]").forEach((select) => {
    if (select.value) models[select.dataset.defaultCap] = select.value;
  });
  return models;
}

function defaultModelsDirty() {
  const current = Object.entries(currentDefaultModels()).sort();
  const saved = Object.entries(state.modelDefaults || {}).sort();
  return JSON.stringify(current) !== JSON.stringify(saved);
}

function updateDefaultModelsState() {
  const dirty = defaultModelsDirty();
  $("save-defaults").hidden = !dirty;
  $("reset-defaults").hidden = !dirty;
}

function resetDefaultModels() {
  renderDefaultModels(
    state.modelCatalog,
    state.modelDefaults || {},
    state.autoModels || {},
  );
  updateDefaultModelsState();
  toast("默认模型修改已取消");
}

async function saveDefaults() {
  const models = currentDefaultModels();
  try {
    await api("/api/v1/settings/defaults", { method: "PUT", body: { models } });
    state.modelDefaults = models;
    toast("默认模型已保存");
    updateDefaultModelsState();
  } catch (error) {
    toast(error.message, true);
  }
}

function bind() {
  installBulkBars();
  if ($("calendar-start") && !$("calendar-start").value) {
    $("calendar-start").value = new Date().toISOString().slice(0, 10);
  }
  $("password-form").addEventListener("submit", login);
  $("sms-form").addEventListener("submit", loginSms);
  $("sms-send").addEventListener("click", sendSmsCode);
  $("wechat-login").addEventListener("click", wechatLogin);
  document.querySelectorAll(".login-tab").forEach((tab) => {
    tab.addEventListener("click", () => switchLoginMethod(tab.dataset.method));
  });
  loadAuthMethods();
  loadLoginMeta();
  $("hard-refresh").addEventListener("click", hardRefresh);
  $("logout").addEventListener("click", logout);
  $("send-chat").addEventListener("click", sendChat);
  $("run-prompt").addEventListener("click", runPrompt);
  $("copy-prompt-output").addEventListener("click", () => {
    copyText($("prompt-output").textContent, "提示词已复制");
  });
  $("view-prompt-output").addEventListener("click", () => {
    showScriptModal("提示词全文", $("prompt-output").textContent);
  });
  $("refresh-jobs").addEventListener("click", loadJobs);
  $("job-search").addEventListener("input", () => {
    clearTimeout(state.jobSearchTimer);
    state.jobSearchTimer = setTimeout(loadJobs, 180);
  });
  $("create-kb").addEventListener("click", createKnowledge);
  $("kb-search").addEventListener("click", searchKnowledge);
  $("upload-doc").addEventListener("click", uploadDocument);
  $("create-project").addEventListener("click", createProject);
  $("save-project-style").addEventListener("click", saveProjectStyle);
  $("project-style").addEventListener("change", () => {
    toggleProjectCustom("project-style", "project-custom-wrap");
  });
  $("project-style-current").addEventListener("change", () => {
    toggleProjectCustom("project-style-current", "project-custom-current-wrap");
  });
  $("refresh-scripts").addEventListener("click", loadScripts);
  $("script-search").addEventListener("input", renderScriptList);
  $("script-style").addEventListener("change", () => {
    state.scriptStyleId = $("script-style").value;
    toggleScriptCustomStyle();
  });
  $("script-platform").addEventListener("change", toggleScriptCustomPlatform);
  $("generate-script").addEventListener("click", generateScript);
  $("expand-script-topics").addEventListener("click", expandScriptTopics);
  $("script-topic-list").addEventListener("click", (event) => {
    const use = event.target.closest("[data-use-script-topic]");
    if (use) useScriptTopic(Number(use.dataset.useScriptTopic));
  });
  $("load-trends").addEventListener("click", () => loadTrends(false));
  $("refresh-trends").addEventListener("click", refreshTrends);
  $("search-related-trends").addEventListener("click", () => loadRelatedTrends());
  $("clear-trend-related").addEventListener("click", clearTrendRelated);
  $("trend-direction").addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadRelatedTrends();
  });
  $("trend-limit").addEventListener("change", toggleCustomTrendLimit);
  $("trend-source").addEventListener("change", () => {
    state.trendSource = $("trend-source").value;
    updateTrendCustomActions();
    state.trends = [];
    loadTrends(false);
  });
  $("toggle-custom-trend-source").addEventListener("click", () => toggleCustomTrendForm());
  $("cancel-custom-trend-source").addEventListener("click", () => toggleCustomTrendForm(false));
  $("save-custom-trend-source").addEventListener("click", saveCustomTrendSource);
  $("delete-custom-trend-source").addEventListener("click", deleteCustomTrendSource);
  $("trend-list").addEventListener("click", (event) => {
    const copy = event.target.closest("[data-copy-trend]");
    if (copy) {
      const item = state.trends[Number(copy.dataset.copyTrend)];
      if (item) copyText(item.title, "热点标题已复制");
      return;
    }
    const use = event.target.closest("[data-use-trend]");
    if (use) useTrendForScript(Number(use.dataset.useTrend));
  });
  $("trend-suggestion-list").addEventListener("click", (event) => {
    const copy = event.target.closest("[data-copy-suggestion]");
    if (copy) {
      const item = state.trendSuggestions[Number(copy.dataset.copySuggestion)];
      if (item) {
        copyText(
          `${item.title}\n切入角度：${item.angle || ""}\n开头钩子：${item.hook || ""}`,
          "关联选题已复制",
        );
      }
      return;
    }
    const use = event.target.closest("[data-use-suggestion]");
    if (use) useTrendSuggestion(Number(use.dataset.useSuggestion));
  });
  $("generate-calendar").addEventListener("click", generateCalendar);
  $("refresh-calendar").addEventListener("click", loadCalendar);
  $("calendar-list").addEventListener("change", (event) => {
    const select = event.target.closest("[data-calendar-status]");
    if (select) updateCalendarStatus(select.dataset.calendarStatus, select.value);
  });
  $("calendar-list").addEventListener("click", (event) => {
    if (event.target.closest("[data-bulk-check]")) return;
    const script = event.target.closest("[data-calendar-script]");
    if (script) {
      useCalendarItemForScript(script.dataset.calendarScript);
      return;
    }
    const remove = event.target.closest("[data-delete-calendar]");
    if (remove) deleteCalendarItem(remove.dataset.deleteCalendar);
  });
  $("run-compliance").addEventListener("click", runComplianceCheck);
  $("refresh-compliance-reports").addEventListener("click", loadComplianceReports);
  $("compliance-project").addEventListener("change", () => {
    loadComplianceAssets($("compliance-project").value);
  });
  $("compliance-report-list").addEventListener("click", (event) => {
    if (event.target.closest("[data-bulk-check]")) return;
    const remove = event.target.closest("[data-delete-compliance]");
    if (remove) {
      deleteComplianceReport(remove.dataset.deleteCompliance);
      return;
    }
    const view = event.target.closest("[data-view-compliance]");
    if (!view) return;
    const report = state.complianceReports.find(
      (item) => item.id === view.dataset.viewCompliance,
    );
    if (report) renderComplianceResult(report);
  });
  $("create-publish-account").addEventListener("click", createPublishAccount);
  $("create-publish-job").addEventListener("click", createPublishJob);
  $("refresh-publish-jobs").addEventListener("click", loadPublishJobs);
  $("publish-project").addEventListener("change", () => {
    loadPublishAssets($("publish-project").value);
  });
  $("publish-account-list").addEventListener("click", (event) => {
    if (event.target.closest("[data-bulk-check]")) return;
    const remove = event.target.closest("[data-delete-publish-account]");
    if (remove) deletePublishAccount(remove.dataset.deletePublishAccount);
  });
  $("publish-job-list").addEventListener("click", (event) => {
    if (event.target.closest("[data-bulk-check]")) return;
    const run = event.target.closest("[data-run-publish]");
    if (run) {
      runPublishJob(run.dataset.runPublish);
      return;
    }
    const published = event.target.closest("[data-mark-published]");
    if (published) {
      markPublishJobPublished(published.dataset.markPublished);
      return;
    }
    const cancel = event.target.closest("[data-cancel-publish]");
    if (cancel) {
      cancelPublishJob(cancel.dataset.cancelPublish);
      return;
    }
    const remove = event.target.closest("[data-delete-publish-job]");
    if (remove) deletePublishJob(remove.dataset.deletePublishJob);
  });
  $("copy-script-output").addEventListener("click", () => {
    copyText(state.lastScript?.body || $("script-output").textContent, "生成结果已复制");
  });
  $("view-script-output").addEventListener("click", () => {
    showScriptModal("生成结果", state.lastScript?.body || $("script-output").textContent);
  });
  $("script-list").addEventListener("click", (event) => {
    if (event.target.closest("[data-bulk-check]")) return;
    const storyboard = event.target.closest("[data-storyboard-script]");
    if (storyboard) {
      generateStoryboardFromScript(storyboard.dataset.storyboardScript, storyboard);
      return;
    }
    const copy = event.target.closest("[data-copy-script]");
    if (copy) {
      const script = state.scripts.find((item) => item.id === copy.dataset.copyScript);
      if (script) copyText(script.body, "脚本已复制");
      return;
    }
    const download = event.target.closest("[data-download-script]");
    if (download) {
      const script = state.scripts.find((item) => item.id === download.dataset.downloadScript);
      if (script) {
        const title = String(script.title || "script").replace(/[\\/:*?"<>|]/g, "_");
        downloadTextFile(`${title}.md`, `# ${script.title}\n\n${script.body}`);
        toast("脚本已下载");
      }
      return;
    }
    const remove = event.target.closest("[data-delete-script]");
    if (remove) {
      deleteScript(remove.dataset.deleteScript);
      return;
    }
    const item = event.target.closest("[data-script-id]");
    if (!item) return;
    const script = state.scripts.find((entry) => entry.id === item.dataset.scriptId);
    if (script) showScriptModal(script.title, script.body);
  });
  $("script-modal-close").addEventListener("click", closeScriptModal);
  $("script-modal-copy").addEventListener("click", () => {
    copyText($("script-modal-body").textContent, "全文已复制");
  });
  $("script-modal").addEventListener("click", (event) => {
    if (event.target === $("script-modal")) closeScriptModal();
  });
  $("storyboard-modal-close").addEventListener("click", closeStoryboardModal);
  $("storyboard-modal-copy").addEventListener("click", () => {
    copyText(JSON.stringify(state.storyboardData || {}, null, 2), "分镜 JSON 已复制");
  });
  $("storyboard-modal").addEventListener("click", (event) => {
    if (event.target === $("storyboard-modal")) closeStoryboardModal();
  });
  $("asset-preview-close").addEventListener("click", closeAssetPreview);
  $("asset-preview-modal").addEventListener("click", (event) => {
    if (event.target === $("asset-preview-modal")) closeAssetPreview();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("script-modal").hidden) closeScriptModal();
    if (event.key === "Escape" && !$("storyboard-modal").hidden) closeStoryboardModal();
    if (event.key === "Escape" && !$("asset-preview-modal").hidden) closeAssetPreview();
    if (event.key === "Escape" && !$("storage-browser-modal").hidden) closeStorageBrowser();
  });
  $("upload-asset").addEventListener("click", uploadAsset);
  $("preview-asset").addEventListener("click", previewAsset);
  $("confirm-import").addEventListener("click", confirmImport);
  $("cancel-import").addEventListener("click", cancelImport);
  $("asset-list").addEventListener("click", (event) => {
    if (event.target.closest("[data-bulk-check]")) return;
    const preview = event.target.closest("[data-preview-asset]");
    if (preview) {
      previewAssetFile(preview.dataset.previewAsset);
      return;
    }
    const remove = event.target.closest("[data-delete-asset]");
    if (remove) {
      deleteAsset(remove.dataset.deleteAsset);
      return;
    }
    const button = event.target.closest("[data-quality]");
    if (button) checkAssetQuality(button.dataset.quality);
  });
  $("quality-rating").addEventListener("click", (event) => {
    const button = event.target.closest("[data-rating]");
    if (!button) return;
    state.qualityRating = Number(button.dataset.rating);
    $("quality-rating").querySelectorAll("button").forEach((node) => {
      node.classList.toggle("selected", node === button);
    });
  });
  $("quality-tags").addEventListener("click", (event) => {
    const chip = event.target.closest("[data-tag]");
    if (!chip) return;
    const tag = chip.dataset.tag;
    if (state.qualityTags.has(tag)) {
      state.qualityTags.delete(tag);
    } else {
      state.qualityTags.add(tag);
    }
    chip.classList.toggle("selected", state.qualityTags.has(tag));
  });
  $("submit-quality-feedback").addEventListener("click", submitQualityFeedback);
  $("create-edit-job").addEventListener("click", createEditJob);
  $("edit-model").addEventListener("change", () => {
    localStorage.setItem("autocut_edit_model", $("edit-model").value);
  });
  $("edit-asr-model").addEventListener("change", () => {
    localStorage.setItem("autocut_edit_asr", $("edit-asr-model").value);
  });
  $("refresh-edit-jobs").addEventListener("click", loadEditJobs);
  $("edit-job-search").addEventListener("input", () => {
    clearTimeout(state.editJobSearchTimer);
    state.editJobSearchTimer = setTimeout(loadEditJobs, 180);
  });
  $("edit-job-list").addEventListener("click", (event) => {
    const timeline = event.target.closest("[data-timeline-job]");
    if (timeline) {
      openTimeline(timeline.dataset.timelineJob);
      return;
    }
    const retry = event.target.closest("[data-retry-edit]");
    if (retry) retryEditJob(retry.dataset.retryEdit);
  });
  $("timeline-close").addEventListener("click", closeTimeline);
  $("timeline-only-highlight").addEventListener("change", () => {
    state.timelineOnlyHighlight = $("timeline-only-highlight").checked;
    renderTimeline();
  });
  $("timeline-batch-mode").addEventListener("change", () => {
    state.timelineBatchMode = $("timeline-batch-mode").checked;
    if (!state.timelineBatchMode) state.timelineCheckedIds = new Set();
    renderTimeline();
  });
  $("timeline-track").addEventListener("click", (event) => {
    if (event.target.closest("[data-timeline-check]")) return;
    if (state.timelineDragging) return;
    const block = event.target.closest("[data-segment-id]");
    if (!block) return;
    state.timelineSelectedId = block.dataset.segmentId;
    const segment = timelineSelected();
    const video = $("timeline-video");
    if (segment && !video.hidden) {
      video.pause();
      video.currentTime = Number(segment.start || 0);
    }
    renderTimeline();
  });
  $("timeline-track").addEventListener("change", (event) => {
    const check = event.target.closest("[data-timeline-check]");
    if (!check) return;
    if (check.checked) {
      state.timelineCheckedIds.add(check.dataset.timelineCheck);
    } else {
      state.timelineCheckedIds.delete(check.dataset.timelineCheck);
    }
    const block = check.closest(".timeline-segment");
    if (block) block.classList.toggle("checked", check.checked);
    renderTimelineBatchBar();
  });
  $("timeline-track").addEventListener("pointerdown", startTimelineTrim);
  document.addEventListener("pointermove", moveTimelineTrim);
  document.addEventListener("pointerup", endTimelineTrim);
  $("timeline-play").addEventListener("click", playTimelineSegment);
  $("timeline-render").addEventListener("click", renderTimelineSegment);
  $("timeline-batch-render").addEventListener("click", renderTimelineBatch);
  $("timeline-batch-subtitles").addEventListener("click", saveTimelineSubtitlesBatch);
  $("timeline-save").addEventListener("click", saveTimelineSegment);
  $("timeline-cancel-edits").addEventListener("click", cancelTimelineSegmentEdits);
  $("timeline-reset").addEventListener("click", resetTimelineSegments);
  ["timeline-start", "timeline-end", "timeline-title"].forEach((id) => {
    $(id).addEventListener("input", updateTimelineDirtyState);
  });
  $("timeline-lock").addEventListener("click", toggleTimelineLock);
  $("timeline-merge-next").addEventListener("click", mergeTimelineNext);
  $("timeline-unmerge").addEventListener("click", unmergeTimelineSegment);
  $("timeline-move-left").addEventListener("click", () => moveTimelineSegment(-1));
  $("timeline-move-right").addEventListener("click", () => moveTimelineSegment(1));
  $("timeline-delete").addEventListener("click", deleteTimelineSegment);
  $("timeline-video").addEventListener("timeupdate", () => {
    const playback = state.timelinePlayback;
    if (!playback) return;
    if ($("timeline-video").currentTime >= playback.end) {
      $("timeline-video").pause();
      state.timelinePlayback = null;
    }
  });
  $("save-defaults").addEventListener("click", saveDefaults);
  $("reset-defaults").addEventListener("click", resetDefaultModels);
  $("default-models").addEventListener("change", updateDefaultModelsState);
  $("save-workspace-settings").addEventListener("click", saveWorkspaceSettings);
  $("reset-workspace-settings").addEventListener("click", resetWorkspaceSettings);
  bindWorkspaceSettingEvents();
  $("pref-storage-root").addEventListener("input", updateStorageRootState);
  $("apply-storage-root").addEventListener("click", applyStorageRoot);
  $("reset-storage-root").addEventListener("click", resetStorageRoot);
  $("browse-storage-root").addEventListener("click", openStorageBrowser);
  $("storage-browser-close").addEventListener("click", closeStorageBrowser);
  $("storage-browser-cancel").addEventListener("click", closeStorageBrowser);
  $("storage-browser-select").addEventListener("click", selectStorageFolder);
  $("storage-browser-modal").addEventListener("click", (event) => {
    if (event.target === $("storage-browser-modal")) closeStorageBrowser();
  });
  $("storage-browser-up").addEventListener("click", () => {
    if (state.storageBrowseParent) loadStorageBrowser(state.storageBrowseParent);
  });
  $("storage-browser-roots").addEventListener("click", (event) => {
    const target = event.target.closest("[data-storage-path]");
    if (target) loadStorageBrowser(target.dataset.storagePath);
  });
  $("storage-browser-list").addEventListener("click", (event) => {
    const target = event.target.closest("[data-storage-path]");
    if (target) loadStorageBrowser(target.dataset.storagePath);
  });
  $("save-brand").addEventListener("click", saveBrandKit);
  $("reset-brand").addEventListener("click", resetBrandSettings);
  [
    "brand-name",
    "brand-slogan",
    "brand-voice",
    "brand-font",
    "brand-intro",
    "brand-outro",
    "brand-primary",
    "brand-secondary",
    "brand-watermark",
  ].forEach((id) => {
    $(id).addEventListener("input", updateBrandSettingsState);
    $(id).addEventListener("change", updateBrandSettingsState);
  });
  $("upload-brand-logo").addEventListener("click", uploadBrandLogo);
  $("refresh-styles").addEventListener("click", loadStyles);
  $("new-style").addEventListener("click", resetStyleForm);
  $("save-style").addEventListener("click", () => saveStyle());
  $("reset-style").addEventListener("click", resetStyleSettings);
  [
    "style-name",
    "style-description",
    "style-prompt",
    "style-negative",
    "style-model",
    "style-rhythm",
    "style-subtitle",
    "style-primary",
    "style-secondary",
    "style-lora-name",
    "style-lora-trigger",
    "style-lora-base",
  ].forEach((id) => {
    $(id).addEventListener("input", updateStyleSettingsState);
    $(id).addEventListener("change", updateStyleSettingsState);
  });
  $("set-default-style").addEventListener("click", setDefaultStyle);
  $("delete-style").addEventListener("click", deleteStyle);
  $("train-style-lora").addEventListener("click", trainStyleLora);
  $("style-list").addEventListener("click", (event) => {
    if (event.target.closest("[data-bulk-check]")) return;
    const item = event.target.closest("[data-style]");
    if (item) selectStyle(item.dataset.style);
  });
  $("structure-template").addEventListener("change", resetPipelineSteps);
  $("add-step").addEventListener("click", addPipelineStep);
  $("create-pipeline").addEventListener("click", createPipeline);
  $("refresh-pipelines").addEventListener("click", loadPipelines);
  $("structure-steps").addEventListener("click", (event) => {
    const row = event.target.closest("[data-step]");
    if (!row) return;
    const index = Number(row.dataset.step);
    const move = event.target.dataset.move;
    if (move === "up" && index > 0) {
      [state.pipelineSteps[index - 1], state.pipelineSteps[index]] = [
        state.pipelineSteps[index],
        state.pipelineSteps[index - 1],
      ];
      renderPipelineSteps();
    } else if (move === "down" && index < state.pipelineSteps.length - 1) {
      [state.pipelineSteps[index + 1], state.pipelineSteps[index]] = [
        state.pipelineSteps[index],
        state.pipelineSteps[index + 1],
      ];
      renderPipelineSteps();
    } else if (event.target.hasAttribute("data-remove-step")) {
      state.pipelineSteps.splice(index, 1);
      renderPipelineSteps();
    }
  });
  $("refresh-module-jobs").addEventListener("click", () => loadModuleJobs(state.module));
  $("create-module-job").addEventListener("click", createModuleJob);
  $("refresh-admin").addEventListener("click", loadAdmin);
  $("jump-upgrade").addEventListener("click", () => {
    $("upgrade-plans").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  $("plan-cards").addEventListener("click", (event) => {
    const button = event.target.closest("[data-upgrade-plan]");
    if (button) upgradePlan(button.dataset.upgradePlan, button);
  });

  $("project-list").addEventListener("click", (event) => {
    if (event.target.closest("[data-bulk-check]")) return;
    const remove = event.target.closest("[data-delete-project]");
    if (remove) {
      deleteProject(remove.dataset.deleteProject);
      return;
    }
    const item = event.target.closest("[data-project]");
    if (item) selectProject(item.dataset.project, item.dataset.name);
  });

  $("module-job-list").addEventListener("click", (event) => {
    const preview = event.target.closest("[data-preview-module-job]");
    if (preview) {
      previewModuleJob(preview.dataset.previewModuleJob);
      return;
    }
    const copy = event.target.closest("[data-copy-preview]");
    if (copy) {
      copyText(copy.dataset.copyPreview, "预览内容已复制");
      return;
    }
    const view = event.target.closest("[data-view-preview]");
    if (view) {
      showScriptModal("结果预览", view.dataset.viewPreview);
      return;
    }
    const remove = event.target.closest("[data-delete-module-job]");
    if (remove) {
      deleteModuleJob(remove.dataset.deleteModuleJob);
      return;
    }
    const button = event.target.closest("[data-module-job]");
    if (button) cancelModuleJob(button.dataset.moduleJob);
  });

  $("pipeline-list").addEventListener("click", (event) => {
    const cancelButton = event.target.closest("[data-pipeline]");
    if (cancelButton) {
      cancelPipeline(cancelButton.dataset.pipeline);
      return;
    }
    const deleteButton = event.target.closest("[data-delete-pipeline]");
    if (deleteButton) deletePipeline(deleteButton.dataset.deletePipeline);
  });

  $("kb-list").addEventListener("click", (event) => {
    const item = event.target.closest("[data-kb]");
    if (item) selectKb(item.dataset.kb, item.dataset.name);
  });

  $("doc-list").addEventListener("click", (event) => {
    if (event.target.closest("[data-bulk-check]")) return;
    const button = event.target.closest("[data-doc]");
    if (button) deleteDocument(button.dataset.doc);
  });

  document.addEventListener("change", (event) => {
    const all = event.target.closest("[data-bulk-all]");
    if (all) {
      setBulkAll(all.dataset.bulkAll, all.checked);
      return;
    }
    const check = event.target.closest("[data-bulk-check]");
    if (check) updateBulkBar(check.dataset.bulkCheck);
  });

  document.addEventListener("click", (event) => {
    const toggle = event.target.closest("[data-bulk-toggle]");
    if (toggle) {
      toggleBulkManage(toggle.dataset.bulkToggle);
      return;
    }
    const button = event.target.closest("[data-bulk-delete]");
    if (button) deleteSelectedBulk(button.dataset.bulkDelete);
    const exportButton = event.target.closest("[data-bulk-export]");
    if (exportButton) saveArtifactsToFolder(true);
  });

  document.querySelectorAll(".nav-item[data-group]").forEach((node) => {
    node.addEventListener("click", () => switchGroup(node.dataset.group));
  });

  $("group-tabs").addEventListener("click", (event) => {
    const tab = event.target.closest("[data-tab-view]");
    if (tab) switchView(tab.dataset.tabView, tab.dataset.tabModule);
  });

  document.querySelectorAll(".chip").forEach((node) => {
    node.addEventListener("click", () => {
      $("chat-input").value = node.dataset.prompt;
      sendChat();
    });
  });

  $("jobs-body").addEventListener("click", (event) => {
    const target = event.target.closest("button");
    if (!target) return;
    if (target.dataset.cancel) cancelJob(target.dataset.cancel);
    if (target.dataset.retry) retryJob(target.dataset.retry);
    if (target.dataset.artifacts) showArtifacts(target.dataset.artifacts);
    if (target.dataset.deleteJob) deleteJob(target.dataset.deleteJob);
  });

  $("artifact-list").addEventListener("click", (event) => {
    if (event.target.closest("[data-bulk-check]")) return;
    const remove = event.target.closest("[data-delete-artifact]");
    if (remove) deleteArtifact(remove.dataset.deleteArtifact);
  });
  $("export-final-artifacts").addEventListener("click", () => saveArtifactsToFolder(false));
}

async function deleteScript(scriptId) {
  const script = state.scripts.find((item) => item.id === scriptId);
  if (!script) return;
  if (!window.confirm(`确定删除脚本“${script.title}”吗？`)) return;
  try {
    await api(`/api/v1/scripts/${scriptId}`, { method: "DELETE" });
    if (state.lastScript?.id === scriptId) {
      state.lastScript = null;
      $("script-output-wrap").hidden = true;
      $("script-output").textContent = "";
    }
    toast("脚本已删除");
    await loadScripts();
  } catch (error) {
    toast(error.message, true);
  }
}

async function deleteProject(projectId) {
  const project = state.projects.find((item) => item.id === projectId);
  if (!project) return;
  if (!window.confirm(`确定删除项目“${project.name}”吗？项目下的素材也会被删除。`)) {
    return;
  }
  try {
    await api(`/api/v1/projects/${projectId}`, { method: "DELETE" });
    toast("项目已删除");
    await loadProjects();
    updateAllBulkBars();
  } catch (error) {
    toast(error.message, true);
  }
}

async function deleteAsset(assetId) {
  if (!state.projectId) return;
  if (!window.confirm("确定删除这个素材吗？文件会一并删除。")) return;
  try {
    await api(`/api/v1/projects/${state.projectId}/assets/${assetId}`, {
      method: "DELETE",
    });
    toast("素材已删除");
    await loadAssets();
    await loadProjects();
    updateAllBulkBars();
  } catch (error) {
    toast(error.message, true);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  bind();
  if (state.token) {
    showApp();
  } else {
    showLogin();
  }
});
