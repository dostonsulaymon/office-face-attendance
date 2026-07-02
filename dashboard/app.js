// Attendance ops dashboard (vanilla). Talks to the API on :8901.
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const API = localStorage.getItem("dash_api") || "http://localhost:8901";
  let token = localStorage.getItem("dash_token") || "";
  let ws = null;
  const enrollBlobs = []; // {blob, url}

  const authHeaders = () => ({ Authorization: "Bearer " + token });
  async function api(path, opts = {}) {
    const r = await fetch(API + path, { ...opts, headers: { ...(opts.headers || {}), ...authHeaders() } });
    if (r.status === 401) { logout(); throw new Error("unauthorized"); }
    return r;
  }
  const fmtTime = (t) => (t ? new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—");
  const fmtDur = (a, b) => {
    if (!a || !b) return "—";
    const m = Math.round((new Date(b) - new Date(a)) / 60000);
    return `${Math.floor(m / 60)}h ${m % 60}m`;
  };

  // ---------- auth ----------
  $("login-form").onsubmit = async (e) => {
    e.preventDefault();
    $("l-err").textContent = "";
    try {
      const r = await fetch(API + "/api/auth/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: $("l-email").value, password: $("l-pass").value }),
      });
      if (!r.ok) { $("l-err").textContent = "Invalid credentials"; return; }
      token = (await r.json()).access_token;
      localStorage.setItem("dash_token", token);
      startApp();
    } catch { $("l-err").textContent = "Cannot reach API at " + API; }
  };
  function logout() {
    token = ""; localStorage.removeItem("dash_token");
    if (ws) { ws.close(); ws = null; }
    $("app").classList.add("hidden"); $("login").classList.remove("hidden");
  }
  $("logout").onclick = logout;

  // ---------- routing ----------
  const loaders = {};
  document.querySelectorAll("#nav a").forEach((a) => {
    a.onclick = () => {
      document.querySelectorAll("#nav a").forEach((x) => x.classList.remove("active"));
      a.classList.add("active");
      const v = a.dataset.view;
      document.querySelectorAll(".view").forEach((el) => el.classList.add("hidden"));
      $("view-" + v).classList.remove("hidden");
      $("app").classList.remove("nav-open"); // close drawer after choosing
      loaders[v] && loaders[v]();
    };
  });
  // mobile drawer
  $("menu-toggle").onclick = () => $("app").classList.toggle("nav-open");
  $("nav-overlay").onclick = () => $("app").classList.remove("nav-open");

  // ---------- live ----------
  loaders.live = async () => { await loadHeadcountPresent(); await loadDevicesMini(); };
  async function loadHeadcountPresent() {
    const d = await (await api("/api/attendance/today")).json();
    $("headcount").textContent = d.currently_in;
    const present = d.rows.filter((r) => r.status === "open");
    $("present-grid").innerHTML = present.map((r) => personCard(r)).join("") ||
      '<p class="muted">Nobody checked in yet.</p>';
  }
  function personCard(r) {
    return `<div class="person">
      <img src="${photo(r)}" onerror="this.style.visibility='hidden'"/>
      <div class="nm">${esc(r.full_name)}</div>
      <div class="sub">${esc(r.department || "")}</div>
      <div class="sub">in ${fmtTime(r.check_in_at)}</div></div>`;
  }
  const photo = (r) => (r.photo_url ? API + r.photo_url : "");
  async function loadDevicesMini() {
    const devs = await (await api("/api/devices")).json();
    const now = Date.now();
    $("devices-mini").innerHTML = "<h3>Devices</h3>" + devs.map((d) => {
      const online = d.last_seen_at && now - new Date(d.last_seen_at) < 90000;
      return `<div class="dev-row"><span class="dot ${online ? "" : "off"}"></span>
        <b>${esc(d.label || d.device_id)}</b><span class="muted">${d.role}</span>
        <span class="muted" style="margin-left:auto">${d.last_seen_at ? fmtTime(d.last_seen_at) : "never"}</span></div>`;
    }).join("");
  }
  function connectWS() {
    if (ws) ws.close();
    ws = new WebSocket(API.replace(/^http/, "ws") + "/ws/dashboard?token=" + token);
    ws.onmessage = (ev) => {
      const e = JSON.parse(ev.data);
      addTick(e);
      loadHeadcountPresent();
    };
    ws.onclose = () => { setTimeout(() => { if (token) connectWS(); }, 3000); };
  }
  function addTick(e) {
    const cls = e.anomaly ? "t-anom" : e.type === "checkin" ? "t-in" : "t-out";
    const verb = e.anomaly ? "anomaly" : e.type === "checkin" ? "checked in" : "checked out";
    const div = document.createElement("div");
    div.className = "tick";
    div.innerHTML = `<img src="${e.photo_url ? API + e.photo_url : ""}" onerror="this.style.visibility='hidden'"/>
      <div><b>${esc(e.employee_name || "?")}</b> <span class="${cls}">${verb}</span>
      <div class="muted">${fmtTime(e.timestamp)}${e.department ? " · " + esc(e.department) : ""}</div></div>`;
    const t = $("ticker"); t.prepend(div);
    while (t.children.length > 40) t.lastChild.remove();
  }

  // ---------- today ----------
  let todayRows = [];
  loaders.today = async () => {
    todayRows = (await (await api("/api/attendance/today")).json()).rows;
    renderToday();
  };
  $("today-search").oninput = renderToday;
  function renderToday() {
    const q = $("today-search").value.toLowerCase();
    $("today-body").innerHTML = todayRows.filter((r) =>
      !q || (r.full_name + " " + (r.department || "")).toLowerCase().includes(q)
    ).map((r) => `<tr>
      <td>${esc(r.full_name)}</td><td>${esc(r.department || "")}</td>
      <td>${fmtTime(r.check_in_at)}</td><td>${fmtTime(r.check_out_at)}</td>
      <td>${fmtDur(r.check_in_at, r.check_out_at)}</td>
      <td><span class="badge ${r.status}">${r.status}</span></td></tr>`).join("");
  }

  // ---------- employees ----------
  loaders.employees = async () => renderEmployees();
  $("emp-search").oninput = () => renderEmployees($("emp-search").value);
  async function renderEmployees(q) {
    const list = await (await api("/api/employees" + (q ? "?q=" + encodeURIComponent(q) : ""))).json();
    $("emp-grid").innerHTML = list.map((e) => `<div class="person">
      <img src="${e.photo_url ? API + e.photo_url : ""}" onerror="this.style.visibility='hidden'"/>
      <div class="nm">${esc(e.full_name)}</div>
      <div class="sub">${esc(e.employee_code)} · ${esc(e.department || "")}</div>
      <div class="sub">${e.active ? "active" : "inactive"}</div>
      <div style="display:flex;gap:6px">
        <button class="btn ghost" onclick="DASH.toggle(${e.id},${!e.active})">${e.active ? "Deactivate" : "Activate"}</button>
        <button class="btn ghost" onclick="DASH.del(${e.id})">Delete</button></div></div>`).join("") ||
      '<p class="muted">No employees yet — enroll someone.</p>';
  }

  // ---------- enroll ----------
  let enrollStream = null;
  loaders.enroll = async () => {
    if (!enrollStream) {
      try { enrollStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } }); $("e-video").srcObject = enrollStream; }
      catch { $("e-msg").textContent = "Webcam unavailable — use Upload instead."; }
    }
  };
  $("e-shot").onclick = (ev) => {
    ev.preventDefault();
    const v = $("e-video"), c = $("e-canvas");
    if (!v.videoWidth) return;
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext("2d").drawImage(v, 0, 0);
    c.toBlob((b) => addEnrollBlob(b), "image/jpeg", 0.9);
  };
  $("e-file").onchange = (e) => { [...e.target.files].forEach((f) => addEnrollBlob(f)); };
  function addEnrollBlob(b) {
    if (enrollBlobs.length >= 3) { $("e-msg").textContent = "Max 3 photos."; return; }
    const url = URL.createObjectURL(b);
    enrollBlobs.push({ blob: b, url });
    $("e-thumbs").innerHTML = enrollBlobs.map((x) => `<img src="${x.url}"/>`).join("");
  }
  $("e-submit").onclick = async (ev) => {
    ev.preventDefault();
    $("e-msg").textContent = "";
    if (!$("e-code").value || !$("e-name").value) { $("e-msg").textContent = "Code and name required."; return; }
    if (!enrollBlobs.length) { $("e-msg").textContent = "Add 1–3 photos."; return; }
    const fd = new FormData();
    fd.append("employee_code", $("e-code").value);
    fd.append("full_name", $("e-name").value);
    fd.append("department", $("e-dept").value);
    fd.append("position", $("e-pos").value);
    enrollBlobs.forEach((x, i) => fd.append("photos", x.blob, `p${i}.jpg`));
    const r = await api("/api/employees", { method: "POST", body: fd });
    if (r.ok) {
      $("e-msg").style.color = "var(--ok)"; $("e-msg").textContent = "Enrolled ✓";
      enrollBlobs.length = 0; $("e-thumbs").innerHTML = "";
      ["e-code", "e-name", "e-dept", "e-pos"].forEach((id) => ($(id).value = ""));
    } else {
      $("e-msg").style.color = "var(--bad)";
      $("e-msg").textContent = "Failed: " + (await r.text());
    }
  };

  // ---------- review ----------
  loaders.review = async () => {
    const list = await (await api("/api/attendance/review")).json();
    const grid = $("review-grid");
    grid.innerHTML = list.map((e) => `<div class="person" id="rev-${e.id}">
      <img alt="loading"/>
      <div class="nm">${e.reject_reason || "rejected"}</div>
      <div class="sub">${esc(e.device_id)} · ${fmtTime(e.created_at)}</div>
      <div class="sub">live ${e.liveness_score ?? "—"} · conf ${e.confidence ?? "—"}</div></div>`).join("") ||
      '<p class="muted">No rejected attempts. Good.</p>';
    // capture images need auth headers -> fetch as blobs
    for (const e of list) {
      if (!e.image_ref) continue;
      try {
        const b = await (await api("/api/attendance/capture/" + e.id)).blob();
        const img = document.querySelector("#rev-" + e.id + " img");
        if (img) img.src = URL.createObjectURL(b);
      } catch {}
    }
  };

  // ---------- devices ----------
  loaders.devices = async () => {
    const devs = await (await api("/api/devices")).json();
    const now = Date.now();
    $("devices-body").innerHTML = devs.map((d) => {
      const online = d.last_seen_at && now - new Date(d.last_seen_at) < 90000;
      return `<tr><td><span class="dot ${online ? "" : "off"}"></span> ${esc(d.device_id)}</td>
        <td>${d.role}</td><td>${esc(d.label || "")}</td><td>${d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : "never"}</td>
        <td><button class="btn ghost" onclick="DASH.rotate('${d.device_id}')">Rotate key</button></td></tr>`;
    }).join("");
  };

  // exposed inline handlers
  window.DASH = {
    toggle: async (id, active) => { await api("/api/employees/" + id, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ active }) }); renderEmployees(); },
    del: async (id) => { if (confirm("Delete employee + all biometric data?")) { await api("/api/employees/" + id, { method: "DELETE" }); renderEmployees(); } },
    rotate: async (deviceId) => { const r = await api("/api/devices/" + deviceId + "/rotate-key", { method: "POST" }); const j = await r.json(); prompt("New key for " + deviceId + " (copy it now):", j.api_key); },
  };

  function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

  function startApp() {
    $("login").classList.add("hidden"); $("app").classList.remove("hidden");
    loaders.live();
    connectWS();
    setInterval(() => { if (!$("view-live").classList.contains("hidden")) loaders.live(); }, 15000);
  }
  if (token) startApp();
})();
