const state = {
  token: localStorage.getItem("autocut_platform_token") || "",
  plans: [],
  scriptStyles: [],
  editingScriptStyleId: "",
};

function $(id) {
  return document.getElementById(id);
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character]));
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
  if (state.token) finalHeaders.Authorization = `Bearer ${state.token}`;
  let payload = body;
  if (body && typeof body !== "string") {
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
  return response.json();
}

function showApp() {
  $("login-layer").hidden = true;
  $("platform-app").hidden = false;
  loadPlans()
    .then(loadScriptStyles)
    .then(loadOverview)
    .then(loadTenants)
    .then(loadCodes)
    .then(loadOrders)
    .catch((error) => toast(error.message, true));
}

function showLogin() {
  $("login-layer").hidden = false;
  $("platform-app").hidden = true;
}

async function login(event) {
  event.preventDefault();
  try {
    const data = await api("/api/v1/platform/auth/login", {
      method: "POST",
      body: {
        email: $("admin-email").value.trim(),
        password: $("admin-password").value,
      },
    });
    state.token = data.access_token;
    localStorage.setItem("autocut_platform_token", state.token);
    showApp();
  } catch (error) {
    toast(error.message, true);
  }
}

function logout() {
  state.token = "";
  localStorage.removeItem("autocut_platform_token");
  showLogin();
}

async function loadPlans() {
  const data = await api("/api/v1/platform/plans");
  state.plans = data.items || [];
  $("tenant-plan").innerHTML = state.plans
    .map((plan) => `<option value="${esc(plan.id)}">${esc(plan.name)}</option>`)
    .join("");
  $("code-plan").innerHTML = state.plans
    .map((plan) => `<option value="${esc(plan.id)}">${esc(plan.name)}</option>`)
    .join("");
}

async function loadOverview() {
  const data = await api("/api/v1/platform/overview");
  const feedback = data.feedback || {};
  $("platform-stats").innerHTML = [
    ["租户", data.tenants],
    ["活跃租户", data.active_tenants],
    ["用户", data.users],
    ["任务", data.jobs],
    ["平均评分", feedback.average ?? 0],
    ["负反馈", feedback.negative ?? 0],
  ].map(([label, value]) => `<div class="stat"><span class="muted">${label}</span><b>${esc(value)}</b></div>`).join("");
}

async function loadScriptStyles() {
  const data = await api("/api/v1/platform/script-styles");
  state.scriptStyles = data.items || [];
  $("script-style-empty").hidden = state.scriptStyles.length > 0;
  $("script-style-list").innerHTML = state.scriptStyles.map((style) => `
    <li class="list-item stacked">
      <div class="hit-meta">
        <span class="row">
          <input type="checkbox" class="bulk-check" data-platform-style-check="${esc(style.id)}" />
          <b>${esc(style.name)}</b>
        </span>
        <span class="pill ${style.enabled ? "ok" : "muted"}">${style.enabled ? "启用中" : "已停用"}</span>
      </div>
      <div class="hit-snippet">${esc(style.prompt || "未填写风格要求")}</div>
      <div class="row end">
        <button type="button" class="btn ghost small" data-edit-script-style="${esc(style.id)}">编辑</button>
        <button type="button" class="btn ghost small" data-toggle-script-style="${esc(style.id)}" data-enabled="${style.enabled ? "1" : "0"}">
          ${style.enabled ? "停用" : "启用"}
        </button>
        <button type="button" class="btn ghost small danger row-delete" data-delete-script-style="${esc(style.id)}">删除</button>
      </div>
    </li>`).join("");
  updatePlatformStyleSelection();
}

function updatePlatformStyleSelection() {
  const checks = [...document.querySelectorAll("[data-platform-style-check]")];
  const selected = checks.filter((item) => item.checked);
  const managing = $("script-style-list").classList.contains("managing");
  $("platform-script-style-bulk").hidden = checks.length === 0;
  $("platform-script-style-bulk").classList.toggle("idle", !managing);
  $("platform-script-style-tools").hidden = !managing;
  $("toggle-script-style-manage").textContent = managing ? "退出管理" : "批量管理";
  $("platform-script-style-count").textContent = `已选 ${selected.length} 项`;
  $("platform-script-style-all").checked = checks.length > 0 && selected.length === checks.length;
  $("platform-script-style-all").indeterminate = selected.length > 0 && selected.length < checks.length;
  $("delete-selected-script-styles").disabled = selected.length === 0;
}

function togglePlatformStyleManage() {
  const list = $("script-style-list");
  const managing = !list.classList.contains("managing");
  list.classList.toggle("managing", managing);
  if (!managing) {
    document.querySelectorAll("[data-platform-style-check]").forEach((item) => {
      item.checked = false;
    });
  }
  updatePlatformStyleSelection();
}

async function deleteSelectedPlatformStyles() {
  const ids = [...document.querySelectorAll("[data-platform-style-check]")]
    .filter((item) => item.checked)
    .map((item) => item.dataset.platformStyleCheck);
  if (!ids.length) return;
  if (!window.confirm(`确定删除选中的 ${ids.length} 个平台风格预设吗？`)) return;
  const button = $("delete-selected-script-styles");
  button.disabled = true;
  let deleted = 0;
  const failures = [];
  for (const styleId of ids) {
    try {
      await api(`/api/v1/platform/script-styles/${styleId}`, { method: "DELETE" });
      deleted += 1;
    } catch (error) {
      failures.push(error.message);
    }
  }
  await loadScriptStyles();
  if (failures.length) {
    toast(`已删除 ${deleted} 个，${failures.length} 个失败：${failures[0]}`, true);
  } else {
    toast(`已删除 ${deleted} 个平台风格预设`);
  }
}

function resetScriptStyleForm() {
  state.editingScriptStyleId = "";
  $("script-style-name").value = "";
  $("script-style-prompt").value = "";
  $("save-script-style").textContent = "新增风格";
  $("cancel-script-style").hidden = true;
}

function editScriptStyle(styleId) {
  const style = state.scriptStyles.find((item) => item.id === styleId);
  if (!style) return;
  state.editingScriptStyleId = styleId;
  $("script-style-name").value = style.name || "";
  $("script-style-prompt").value = style.prompt || "";
  $("save-script-style").textContent = "保存修改";
  $("cancel-script-style").hidden = false;
  $("script-style-name").focus();
}

async function saveScriptStyle() {
  const name = $("script-style-name").value.trim();
  const prompt = $("script-style-prompt").value.trim();
  if (!name) {
    toast("先填写风格名称", true);
    return;
  }
  const button = $("save-script-style");
  button.disabled = true;
  try {
    if (state.editingScriptStyleId) {
      await api(`/api/v1/platform/script-styles/${state.editingScriptStyleId}`, {
        method: "PATCH",
        body: { name, prompt },
      });
    } else {
      await api("/api/v1/platform/script-styles", {
        method: "POST",
        body: { name, prompt },
      });
    }
    toast(state.editingScriptStyleId ? "风格已更新" : "风格已新增");
    resetScriptStyleForm();
    await loadScriptStyles();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function toggleScriptStyle(styleId, enabled) {
  try {
    await api(`/api/v1/platform/script-styles/${styleId}`, {
      method: "PATCH",
      body: { enabled },
    });
    toast(enabled ? "风格已启用" : "风格已停用");
    await loadScriptStyles();
  } catch (error) {
    toast(error.message, true);
  }
}

async function deleteScriptStyle(styleId) {
  if (!window.confirm("确定删除这个平台风格预设吗？租户端将不再显示。")) return;
  try {
    await api(`/api/v1/platform/script-styles/${styleId}`, { method: "DELETE" });
    if (state.editingScriptStyleId === styleId) resetScriptStyleForm();
    toast("风格已删除");
    await loadScriptStyles();
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadTenants() {
  const data = await api("/api/v1/platform/tenants");
  $("tenant-body").innerHTML = (data.items || []).map((tenant) => `
    <tr>
      <td>${esc(tenant.name)}<div class="muted">${esc(tenant.id)}</div></td>
      <td>
        <select data-plan="${esc(tenant.id)}">
          ${state.plans.map((plan) => `<option value="${esc(plan.id)}" ${plan.id === tenant.plan ? "selected" : ""}>${esc(plan.name)}</option>`).join("")}
        </select>
      </td>
      <td><span class="pill ${tenant.status === "active" ? "" : "bad"}">${esc(tenant.status)}</span></td>
      <td>${esc(tenant.user_count)}</td>
      <td class="muted">${esc(tenant.credits)} 积分 · ${esc(tenant.seats)} 席位 · ${esc(tenant.storage_gb)}GB · ${esc(tenant.concurrency)} 并发</td>
      <td class="muted">${esc(tenant.usage.projects)} 项目 · ${esc(tenant.usage.assets)} 素材 · ${esc(tenant.usage.jobs)} 任务</td>
      <td>
        <button type="button" class="btn ghost small" data-toggle="${esc(tenant.id)}" data-status="${esc(tenant.status)}">
          ${tenant.status === "active" ? "停用" : "启用"}
        </button>
      </td>
    </tr>`).join("");
}

async function createTenant() {
  const button = $("create-tenant");
  button.disabled = true;
  try {
    await api("/api/v1/platform/tenants", {
      method: "POST",
      body: {
        name: $("tenant-name").value.trim(),
        plan: $("tenant-plan").value,
        owner_email: $("owner-email").value.trim(),
        owner_password: $("owner-password").value,
        owner_name: $("owner-name").value.trim() || "Owner",
      },
    });
    $("tenant-hint").textContent = "租户已开通，管理员可以用邮箱登录 B 端。";
    $("tenant-name").value = "";
    $("owner-email").value = "";
    toast("租户已开通");
    loadOverview();
    loadTenants();
  } catch (error) {
    $("tenant-hint").textContent = error.message;
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function updateTenant(tenantId, values) {
  try {
    await api(`/api/v1/platform/tenants/${tenantId}`, { method: "PATCH", body: values });
    toast("已更新");
    loadOverview();
    loadTenants();
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadCodes() {
  const data = await api("/api/v1/platform/activation-codes");
  const items = data.items || [];
  $("code-empty").hidden = items.length > 0;
  $("code-list").innerHTML = items.map((item) => `
    <li class="list-item">
      <code>${esc(item.code)}</code>
      <span class="muted">${esc(item.plan)} · ${esc(item.duration_days)} 天</span>
      <span class="pill ${item.used_by ? "muted" : ""}">${item.used_by ? "已使用" : "未使用"}</span>
    </li>`).join("");
}

async function createCodes() {
  const button = $("create-codes");
  button.disabled = true;
  try {
    await api("/api/v1/platform/activation-codes", {
      method: "POST",
      body: {
        plan: $("code-plan").value,
        count: Number($("code-count").value) || 1,
        duration_days: Number($("code-days").value) || 30,
      },
    });
    toast("激活码已生成");
    loadCodes();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function loadOrders() {
  const data = await api("/api/v1/platform/orders");
  $("order-body").innerHTML = (data.items || []).map((order) => `
    <tr>
      <td><code>${esc(order.id)}</code></td>
      <td>${esc(order.company_name)}<div class="muted">${esc(order.owner_email)}</div></td>
      <td>${esc(order.plan)}</td>
      <td>¥${(Number(order.amount_cents) / 100).toFixed(0)}</td>
      <td><span class="pill ${order.status === "paid" ? "" : "warn"}">${esc(order.status)}</span></td>
      <td class="muted">${esc(order.tenant_id || "-")}</td>
    </tr>`).join("");
}

document.addEventListener("DOMContentLoaded", () => {
  $("platform-login").addEventListener("submit", login);
  $("platform-logout").addEventListener("click", logout);
  $("create-tenant").addEventListener("click", createTenant);
  $("refresh-tenants").addEventListener("click", loadTenants);
  $("create-codes").addEventListener("click", createCodes);
  $("refresh-orders").addEventListener("click", loadOrders);
  $("refresh-script-styles").addEventListener("click", loadScriptStyles);
  $("save-script-style").addEventListener("click", saveScriptStyle);
  $("cancel-script-style").addEventListener("click", resetScriptStyleForm);
  $("delete-selected-script-styles").addEventListener("click", deleteSelectedPlatformStyles);
  $("toggle-script-style-manage").addEventListener("click", togglePlatformStyleManage);
  $("platform-script-style-all").addEventListener("change", (event) => {
    document.querySelectorAll("[data-platform-style-check]").forEach((item) => {
      item.checked = event.target.checked;
    });
    updatePlatformStyleSelection();
  });

  $("script-style-list").addEventListener("click", (event) => {
    if (event.target.closest("[data-platform-style-check]")) return;
    const edit = event.target.closest("[data-edit-script-style]");
    if (edit) {
      editScriptStyle(edit.dataset.editScriptStyle);
      return;
    }
    const toggle = event.target.closest("[data-toggle-script-style]");
    if (toggle) {
      toggleScriptStyle(toggle.dataset.toggleScriptStyle, toggle.dataset.enabled !== "1");
      return;
    }
    const remove = event.target.closest("[data-delete-script-style]");
    if (remove) deleteScriptStyle(remove.dataset.deleteScriptStyle);
  });
  $("script-style-list").addEventListener("change", (event) => {
    if (event.target.closest("[data-platform-style-check]")) {
      updatePlatformStyleSelection();
    }
  });

  $("tenant-body").addEventListener("change", (event) => {
    const select = event.target.closest("[data-plan]");
    if (select) updateTenant(select.dataset.plan, { plan: select.value });
  });

  $("tenant-body").addEventListener("click", (event) => {
    const button = event.target.closest("[data-toggle]");
    if (!button) return;
    updateTenant(button.dataset.toggle, {
      status: button.dataset.status === "active" ? "suspended" : "active",
    });
  });

  if (state.token) {
    showApp();
  } else {
    showLogin();
  }
});
