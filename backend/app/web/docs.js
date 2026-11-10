const container = document.getElementById("endpoints");

async function boot() {
  try {
    const response = await fetch("/openapi.json");
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    const spec = await response.json();
    const pathCount = Object.keys(spec.paths || {}).length;
    document.getElementById("spec-meta").textContent =
      `${spec.info?.title || "API"} · v${spec.info?.version || ""} · ${pathCount} 条路径`;
    render(spec);
  } catch (error) {
    container.innerHTML = `<div class="empty">接口定义加载失败：${escapeHtml(error.message)}</div>`;
  }
}

function render(spec) {
  const groups = new Map();
  for (const [path, methods] of Object.entries(spec.paths || {})) {
    for (const [method, operation] of Object.entries(methods)) {
      if (!["get", "post", "put", "patch", "delete"].includes(method)) continue;
      const tags = operation.tags?.length ? operation.tags : ["default"];
      for (const tag of tags) {
        if (!groups.has(tag)) groups.set(tag, []);
        groups.get(tag).push({ path, method: method.toUpperCase(), operation });
      }
    }
  }

  if (!groups.size) {
    container.innerHTML = `<div class="empty">没有可用接口</div>`;
    return;
  }

  container.innerHTML = [...groups.entries()].map(([tag, items]) => `
    <section class="docs-group">
      <h2>${escapeHtml(tag)}</h2>
      ${items.map(endpointHtml).join("")}
    </section>`).join("");
}

function endpointHtml({ path, method, operation }) {
  const parameters = (operation.parameters || []).filter((item) => item.in === "path");
  const hasJson = Boolean(operation.requestBody?.content?.["application/json"]);
  const isMultipart = Boolean(operation.requestBody?.content?.["multipart/form-data"]);

  return `
    <details class="endpoint" data-path="${escapeHtml(path)}" data-method="${method}">
      <summary>
        <span class="method ${method.toLowerCase()}">${method}</span>
        <span class="path">${escapeHtml(path)}</span>
        <span class="muted">${escapeHtml(operation.summary || "")}</span>
      </summary>
      <div class="endpoint-body">
        ${parameters.map((parameter) => `
          <label>${escapeHtml(parameter.name)}
            <input data-param="${escapeHtml(parameter.name)}"
                   placeholder="${escapeHtml(parameter.schema?.type || "string")}" />
          </label>`).join("")}
        ${hasJson ? `<label>请求体<textarea data-body>{}</textarea></label>` : ""}
        ${isMultipart ? `<p class="muted">文件上传接口，请在前端页面操作。</p>` : ""}
        ${isMultipart ? "" : `<div class="row end"><button type="button" class="btn primary small" data-send>发送</button></div>`}
        <pre class="response" data-response hidden></pre>
      </div>
    </details>`;
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-send]");
  if (!button) return;

  const details = button.closest(".endpoint");
  const path = details.dataset.path;
  const method = details.dataset.method;
  let url = path;

  details.querySelectorAll("[data-param]").forEach((input) => {
    url = url.replace(`{${input.dataset.param}}`, encodeURIComponent(input.value || ""));
  });

  const options = { method };
  const body = details.querySelector("[data-body]");
  if (body) {
    options.headers = { "Content-Type": "application/json" };
    options.body = body.value;
  }

  const responseNode = details.querySelector("[data-response]");
  responseNode.hidden = false;
  responseNode.textContent = "请求中...";
  try {
    const response = await fetch(url, options);
    const text = await response.text();
    let formatted = text;
    try {
      formatted = JSON.stringify(JSON.parse(text), null, 2);
    } catch {
      // keep the raw response
    }
    responseNode.textContent = `${response.status} ${response.statusText}\n${formatted}`;
  } catch (error) {
    responseNode.textContent = `请求失败：${error.message}`;
  }
});

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character]));
}

boot();
