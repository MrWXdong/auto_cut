const state = { plans: [], selected: "trial" };

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

async function loadPlans() {
  const response = await fetch("/api/v1/public/plans");
  const data = await response.json();
  state.plans = data.items || [];
  state.selected = state.plans[0]?.id || "trial";
  $("plans").innerHTML = state.plans.map((plan) => `
    <article class="plan ${plan.id === state.selected ? "selected" : ""}" data-plan="${esc(plan.id)}">
      <h3>${esc(plan.name)}</h3>
      <div class="price">${(plan.price_monthly_cents ?? plan.price_cents) === 0 ? "免费" : `¥${((plan.price_monthly_cents ?? plan.price_cents) / 100).toFixed(0)}/月`}</div>
      <ul>
        <li>${esc(plan.credits)} 积分/月</li>
        <li>${esc(plan.storage_gb)}GB 存储</li>
        <li>${esc(plan.seats)} 个席位</li>
        <li>${esc(plan.concurrency)} 个并发任务</li>
        ${plan.price_yearly_cents ? `<li>年付 ¥${(plan.price_yearly_cents / 100).toFixed(0)}</li>` : ""}
      </ul>
    </article>`).join("");
  updateSelected();
}

function updateSelected() {
  document.querySelectorAll("[data-plan]").forEach((node) => {
    node.classList.toggle("selected", node.dataset.plan === state.selected);
  });
  const plan = state.plans.find((item) => item.id === state.selected);
  $("selected-plan").textContent = plan?.name || state.selected;
}

async function submitSignup() {
  const button = $("signup-submit");
  button.disabled = true;
  try {
    const response = await fetch("/api/v1/public/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan: state.selected,
        company_name: $("company-name").value.trim(),
        owner_email: $("owner-email").value.trim(),
        owner_password: $("owner-password").value,
        owner_name: $("owner-name").value.trim() || "Owner",
        activation_code: $("activation-code").value.trim(),
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || response.statusText);
    }
    localStorage.setItem("autocut_token", data.access_token);
    localStorage.setItem("autocut_tenant", data.tenant?.name || "");
    window.location.href = "/";
  } catch (error) {
    $("signup-hint").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadPlans().catch((error) => {
    $("signup-hint").textContent = error.message;
  });
  $("plans").addEventListener("click", (event) => {
    const plan = event.target.closest("[data-plan]");
    if (!plan) return;
    state.selected = plan.dataset.plan;
    updateSelected();
  });
  $("signup-submit").addEventListener("click", submitSignup);
});
