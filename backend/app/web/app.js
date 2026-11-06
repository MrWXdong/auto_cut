const state = {
  token: localStorage.getItem("autocut_token") || "",
  meta: null,
  view: "workspace",
};

const VIEW_META = {
  workspace: ["工作台", "描述需求，系统选择技能并执行。"],
  runs: ["任务", "上传素材、查看进度、下载产物。"],
  knowledge: ["知识库", "品牌规范、产品卖点、历史脚本。"],
  billing: ["套餐", "订阅与用量。"],
  settings: ["设置", "模型、账号与运行开关。"],
};

const STATUS_TEXT = {
  queued: "排队",
  running: "运行中",
  succeeded: "成功",
  failed: "失败",
  canceled: "已取消",
};

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
  };
  return `<span class="pill ${map[status] || "muted"}">${esc(STATUS_TEXT[status] || status)}</span>`;
}

function formatDuration(ms) {
  if (ms === null || ms === undefined) return "-";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
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
  switchView(state.view);
}

function showLogin() {
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

function logout() {
  state.token = "";
  localStorage.removeItem("autocut_token");
  showLogin();
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

function switchView(view) {
  state.view = view;
  document.querySelectorAll(".nav-item").forEach((node) => {
    node.classList.toggle("active", node.dataset.view === view);
  });
  document.querySelectorAll(".view").forEach((node) => {
    node.hidden = node.id !== `view-${view}`;
  });
  const [title, subtitle] = VIEW_META[view] || VIEW_META.workspace;
  $("view-title").textContent = title;
  $("view-subtitle").textContent = subtitle;
  $("artifact-panel").hidden = true;

  if (view === "runs") loadJobs();
  if (view === "knowledge") loadKnowledge();
  if (view === "billing") loadBilling();
  if (view === "settings") loadModels();
}

async function sendChat() {
  const input = $("chat-input");
  const message = input.value.trim();
  if (!message) {
    toast("先输入需求");
    return;
  }

  const button = $("send-chat");
  button.disabled = true;
  try {
    const data = await api("/api/v1/chat", { method: "POST", body: { message } });
    $("plan-empty").hidden = true;
    $("plan-result").hidden = false;
    $("plan-intent").textContent = data.intent?.name || "-";
    $("plan-confidence").textContent = data.intent?.confidence ?? "-";
    $("plan-skill").textContent = data.plan?.skill || "-";
    $("plan-workflow").textContent = data.plan?.workflow || "无";
    $("plan-reply").textContent = data.reply || "";
    $("intent-hint").textContent = data.intent?.name || "已识别";
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
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
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function loadJobs() {
  try {
    const data = await api("/api/v1/jobs");
    const items = data.items || [];
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
      return `
        <tr>
          <td><code>${esc(job.id)}</code></td>
          <td>${esc(job.workflow)}</td>
          <td>${statusPill(job.status)}</td>
          <td>${esc(formatTime(job.created_at))}</td>
          <td>${esc(formatDuration(job.duration_ms))}</td>
          <td>${actions.join(" ")}</td>
        </tr>`;
    }).join("");
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

async function showArtifacts(id) {
  try {
    const data = await api(`/api/v1/jobs/${id}/artifacts`);
    const items = data.items || [];
    $("artifact-panel").hidden = false;
    $("artifact-job").textContent = id;
    $("artifact-list").innerHTML = items.length
      ? items.map((item) => `
        <li class="list-item">
          <a href="/api/v1/jobs/${encodeURIComponent(id)}/files/${item.path}" target="_blank" rel="noreferrer">${esc(item.name)}</a>
          <span class="muted">${Math.max(1, Math.round(item.size_bytes / 1024))} KB</span>
        </li>`).join("")
      : `<li class="empty">还没有产物</li>`;
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadKnowledge() {
  try {
    const data = await api("/api/v1/knowledge-bases");
    const items = data.items || [];
    $("kb-empty").hidden = items.length > 0;
    $("kb-list").innerHTML = items.map((item) => `
      <li class="list-item">
        <span>${esc(item.name)}</span>
        <span class="pill muted">${esc(item.document_count)} 文档</span>
      </li>`).join("");
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
    await api("/api/v1/knowledge-bases", { method: "POST", body: { name } });
    $("kb-name").value = "";
    toast("已创建");
    loadKnowledge();
  } catch (error) {
    toast(error.message, true);
  }
}

async function searchKnowledge() {
  const query = $("kb-query").value.trim();
  if (!query) return;
  try {
    const data = await api("/api/v1/knowledge-bases/demo/search", {
      method: "POST",
      body: { query },
    });
    const output = $("kb-result");
    output.hidden = false;
    output.textContent = data.message || JSON.stringify(data, null, 2);
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadBilling() {
  try {
    const [plan, usage] = await Promise.all([
      api("/api/v1/billing/plan"),
      api("/api/v1/billing/usage"),
    ]);
    $("plan-name").textContent = plan.name || "-";
    $("plan-price").textContent = plan.price_cents === 0
      ? "免费"
      : `¥${(plan.price_cents / 100).toFixed(0)} / ${plan.period}`;
    $("plan-limits").innerHTML = Object.entries(plan.limits || {})
      .map(([key, value]) => `<span class="pill">${esc(key)} ${esc(value)}</span>`)
      .join("");

    $("usage-period").textContent = usage.period || "";
    $("usage-list").innerHTML = (usage.items || []).map((item) => {
      const limit = Number(item.limit) || 0;
      const used = Number(item.used) || 0;
      const percent = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
      return `
        <div class="usage-row">
          <div class="line"><span>${esc(item.kind)}</span><span class="muted">${used} / ${limit} ${esc(item.unit)}</span></div>
          <div class="bar"><div class="bar-fill" style="width:${percent}%"></div></div>
        </div>`;
    }).join("");
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadModels() {
  try {
    const data = await api("/api/v1/settings/models");
    $("model-body").innerHTML = (data.items || []).map((item) => `
      <tr>
        <td>${esc(item.provider)}</td>
        <td>${(item.capabilities || []).map((cap) => `<span class="pill muted">${esc(cap)}</span>`).join(" ")}</td>
        <td class="muted">${(item.models || []).map(esc).join(", ")}</td>
        <td>${statusPill(item.status === "ready" ? "succeeded" : "queued")}</td>
      </tr>`).join("");
  } catch (error) {
    toast(error.message, true);
  }
}

function bind() {
  $("login-form").addEventListener("submit", login);
  $("logout").addEventListener("click", logout);
  $("send-chat").addEventListener("click", sendChat);
  $("run-prompt").addEventListener("click", runPrompt);
  $("refresh-jobs").addEventListener("click", loadJobs);
  $("create-kb").addEventListener("click", createKnowledge);
  $("kb-search").addEventListener("click", searchKnowledge);

  document.querySelectorAll(".nav-item").forEach((node) => {
    node.addEventListener("click", () => switchView(node.dataset.view));
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
  });
}

document.addEventListener("DOMContentLoaded", () => {
  bind();
  if (state.token) {
    showApp();
  } else {
    showLogin();
  }
});
