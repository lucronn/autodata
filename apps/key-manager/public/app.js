const form = document.querySelector("#create-form");
const rows = document.querySelector("#keys");
const errorBox = document.querySelector("#form-error");
const secretBox = document.querySelector("#new-secret");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

function status(key) {
  if (key.revoked_at) return "Revoked";
  if (key.expires_at && new Date(key.expires_at) <= new Date()) return "Expired";
  return "Active";
}

function displayDate(value) {
  if (!value) return "Never";
  return new Date(value).toLocaleString();
}

async function loadKeys() {
  rows.innerHTML = '<tr><td colspan="6">Loading keys…</td></tr>';
  try {
    const response = await fetch("/api/keys", { cache: "no-store" });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error?.message || "Unable to load keys.");
    rows.innerHTML = body.keys.length ? body.keys.map((key) => `<tr><td><span class="service">${escapeHtml(key.service)}</span><br>${escapeHtml(key.label)}</td><td><code>${escapeHtml(key.key_prefix)}…</code></td><td>${escapeHtml(displayDate(key.created_at))}</td><td>${escapeHtml(displayDate(key.expires_at))}</td><td><span class="badge ${status(key).toLowerCase()}">${status(key)}</span></td><td>${status(key) === "Active" ? `<button class="revoke" data-id="${escapeHtml(key.id)}">Revoke</button>` : ""}</td></tr>`).join("") : '<tr><td colspan="6">No keys yet. Create the first one above.</td></tr>';
  } catch (error) {
    rows.innerHTML = `<tr><td colspan="6" class="error">${escapeHtml(error.message)}</td></tr>`;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.textContent = "";
  secretBox.classList.add("hidden");
  const data = new FormData(form);
  const payload = Object.fromEntries(data.entries());
  if (!payload.expiresAt) delete payload.expiresAt;
  else payload.expiresAt = new Date(payload.expiresAt).toISOString();
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  button.textContent = "Creating…";
  try {
    const response = await fetch("/api/keys", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload), cache: "no-store" });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error?.message || "Unable to create key.");
    secretBox.replaceChildren();
    const message = document.createElement("p");
    message.textContent = "Copy this key now. It cannot be shown again.";
    const key = document.createElement("code");
    key.textContent = body.secret;
    const copy = document.createElement("button");
    copy.type = "button";
    copy.textContent = "Copy key";
    copy.addEventListener("click", async () => { await navigator.clipboard.writeText(body.secret); copy.textContent = "Copied"; });
    secretBox.append(message, key, copy);
    secretBox.classList.remove("hidden");
    form.reset();
    await loadKeys();
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    button.disabled = false;
    button.innerHTML = 'Create key <span aria-hidden="true">↗</span>';
  }
});

rows.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-id]");
  if (!button || !window.confirm("Revoke this key? New requests using it will be denied.")) return;
  button.disabled = true;
  try {
    const response = await fetch(`/api/keys/${encodeURIComponent(button.dataset.id)}`, { method: "DELETE", cache: "no-store" });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error?.message || "Unable to revoke key.");
    await loadKeys();
  } catch (error) {
    button.disabled = false;
    alert(error.message);
  }
});

document.querySelector("#refresh").addEventListener("click", loadKeys);
loadKeys();
