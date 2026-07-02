// Attendance kiosk PWA. Front-camera capture -> POST /api/attendance/event.
// Config persists in localStorage; failed uploads queue in IndexedDB and retry.
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const CFG_KEY = "kiosk_config";
  const AUTO_INTERVAL_MS = 2500;   // sample cadence when idle
  const RESULT_HOLD_MS = 2600;     // show result before resetting
  const LOCAL_COOLDOWN_MS = 4000;  // client throttle after any submit

  let cfg = null;
  let stream = null;
  let state = "idle";              // idle | busy | result
  let lastSubmit = 0;
  let muted = localStorage.getItem("kiosk_muted") === "1";

  // ---------- config ----------
  function loadConfig() {
    const url = new URL(location.href);
    const qp = url.searchParams;
    if (qp.get("device_id") && qp.get("key")) {
      cfg = {
        apiBase: (qp.get("api") || "http://localhost:8901").replace(/\/$/, ""),
        deviceId: qp.get("device_id"),
        deviceKey: qp.get("key"),
        label: qp.get("label") || qp.get("device_id"),
      };
      localStorage.setItem(CFG_KEY, JSON.stringify(cfg));
      history.replaceState({}, "", url.pathname); // strip secrets from URL
      return;
    }
    try { cfg = JSON.parse(localStorage.getItem(CFG_KEY)); } catch { cfg = null; }
  }

  function showSetup() {
    $("setup").classList.remove("hidden");
    $("kiosk").classList.add("hidden");
    if (cfg) {
      $("cfg-api").value = cfg.apiBase; $("cfg-device").value = cfg.deviceId;
      $("cfg-key").value = cfg.deviceKey; $("cfg-label").value = cfg.label || "";
    } else {
      $("cfg-api").value = "http://localhost:8901";
    }
  }
  $("cfg-save").onclick = () => {
    const c = {
      apiBase: $("cfg-api").value.trim().replace(/\/$/, ""),
      deviceId: $("cfg-device").value.trim(),
      deviceKey: $("cfg-key").value.trim(),
      label: $("cfg-label").value.trim() || $("cfg-device").value.trim(),
    };
    if (!c.apiBase || !c.deviceId || !c.deviceKey) { $("cfg-err").textContent = "All fields except label are required."; return; }
    cfg = c; localStorage.setItem(CFG_KEY, JSON.stringify(c));
    location.reload();
  };

  // ---------- camera ----------
  async function startCamera() {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
    $("video").srcObject = stream;
    await $("video").play();
  }

  function grabFrame() {
    const v = $("video"), c = $("canvas");
    const w = v.videoWidth, h = v.videoHeight;
    if (!w || !h) return Promise.resolve(null);
    // Portrait-ish 3:4 crop centered (matches liveness model expectations).
    c.width = w; c.height = h;
    c.getContext("2d").drawImage(v, 0, 0, w, h);
    return new Promise((res) => c.toBlob((b) => res(b), "image/jpeg", 0.85));
  }

  // ---------- ui state ----------
  function setRing(cls) { $("ring").className = "ring" + (cls ? " " + cls : ""); }
  function beep(ok) {
    if (muted) return;
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      o.frequency.value = ok ? 880 : 220; g.gain.value = 0.08;
      o.start(); o.stop(ctx.currentTime + (ok ? 0.15 : 0.35));
    } catch {}
  }
  function showResult(r) {
    state = "result";
    $("prompt").classList.add("hidden");
    $("capture").classList.add("hidden");
    const box = $("result"); box.classList.remove("hidden");
    const ok = r.matched;
    setRing(ok ? "ok" : "bad");
    $("r-photo").src = ok && r.photo_url ? cfg.apiBase + r.photo_url : "";
    $("r-photo").style.display = ok && r.photo_url ? "" : "none";
    $("r-name").textContent = ok ? (r.employee_name || "") : "Not recognized";
    $("r-msg").textContent = r.message || "";
    $("r-time").textContent = r.timestamp ? new Date(r.timestamp).toLocaleTimeString() : "";
    beep(ok);
    setTimeout(resetIdle, RESULT_HOLD_MS);
  }
  function resetIdle() {
    state = "idle"; setRing("");
    $("result").classList.add("hidden");
    $("prompt").classList.remove("hidden");
    $("capture").classList.remove("hidden");
  }

  // ---------- submit + offline queue ----------
  async function postEvent(blob) {
    const fd = new FormData();
    fd.append("image", blob, "frame.jpg");
    const resp = await fetch(cfg.apiBase + "/api/attendance/event", {
      method: "POST",
      headers: { "X-Device-Id": cfg.deviceId, "X-Device-Key": cfg.deviceKey },
      body: fd,
    });
    if (!resp.ok) throw new Error("http " + resp.status);
    return resp.json();
  }

  async function capture(manual) {
    if (state !== "idle") return;
    if (Date.now() - lastSubmit < LOCAL_COOLDOWN_MS && !manual) return;
    const blob = await grabFrame();
    if (!blob) return;
    lastSubmit = Date.now();
    state = "busy"; setRing("busy"); $("prompt").textContent = "Verifying…";
    try {
      const r = await postEvent(blob);
      showResult(r);
    } catch (e) {
      await queuePut(blob);
      updateQueueBadge();
      $("prompt").textContent = "Look at the camera";
      state = "idle"; setRing("");
      setNet(false);
    }
  }

  // IndexedDB queue
  let db = null;
  function openDB() {
    return new Promise((res) => {
      const req = indexedDB.open("kiosk-queue", 1);
      req.onupgradeneeded = () => req.result.createObjectStore("q", { keyPath: "id", autoIncrement: true });
      req.onsuccess = () => res(req.result);
      req.onerror = () => res(null);
    });
  }
  async function queuePut(blob) { if (!db) return; const tx = db.transaction("q", "readwrite"); tx.objectStore("q").add({ blob, ts: Date.now() }); }
  async function queueAll() {
    if (!db) return [];
    return new Promise((res) => { const r = db.transaction("q").objectStore("q").getAll(); r.onsuccess = () => res(r.result || []); r.onerror = () => res([]); });
  }
  async function queueDel(id) { if (!db) return; db.transaction("q", "readwrite").objectStore("q").delete(id); }
  async function updateQueueBadge() { const n = (await queueAll()).length; $("q-count").textContent = String(n); }

  async function flushQueue() {
    const items = await queueAll();
    for (const it of items) {
      try { await postEvent(it.blob); await queueDel(it.id); setNet(true); }
      catch { setNet(false); break; }
    }
    updateQueueBadge();
  }

  function setNet(online) { $("dot-net").className = "dot" + (online ? "" : " off"); }

  // heartbeat so the dashboard shows this device online
  async function heartbeat() {
    try {
      await fetch(cfg.apiBase + "/api/devices/heartbeat", {
        method: "POST", headers: { "X-Device-Id": cfg.deviceId, "X-Device-Key": cfg.deviceKey },
      });
      setNet(true);
    } catch { setNet(false); }
  }

  // ---------- boot ----------
  async function boot() {
    loadConfig();
    if (!cfg) { showSetup(); return; }
    $("setup").classList.add("hidden");
    $("kiosk").classList.remove("hidden");
    $("k-label").textContent = cfg.label || cfg.deviceId;
    $("mute").textContent = muted ? "🔇" : "🔊";
    $("mute").onclick = () => { muted = !muted; localStorage.setItem("kiosk_muted", muted ? "1" : "0"); $("mute").textContent = muted ? "🔇" : "🔊"; };
    $("reconfig").onclick = () => { showSetup(); };
    $("capture").onclick = () => capture(true);
    db = await openDB();
    updateQueueBadge();
    try { await startCamera(); }
    catch (e) { $("prompt").textContent = "Camera unavailable — check permissions"; }
    setInterval(() => { if (state === "idle") capture(false); }, AUTO_INTERVAL_MS);
    setInterval(flushQueue, 5000);
    setInterval(heartbeat, 30000);
    heartbeat();
    window.addEventListener("online", () => { setNet(true); flushQueue(); });
    window.addEventListener("offline", () => setNet(false));
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
  }
  boot();
})();
