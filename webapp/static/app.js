"use strict";

/* ---------- 状态 ---------- */
const STAGES = ["P1", "P2", "P3", "P4", "P5", "P6"];
const STAGE_NAMES = { P1: "读题分析", P2: "建模", P3: "编程求解", P4: "出图", P5: "论文写作", P6: "验收" };

let currentTask = null;
let pollTimer = null;
let pendingFiles = [];
let loadedPaperStage = "";

const $ = (id) => document.getElementById(id);

/* ---------- 工具 ---------- */
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}
function badge(status) {
  const map = { new: "未开始", idle: "空闲", running: "运行中", done: "完成", failed: "失败" };
  return `<span class="badge ${esc(status)}">${esc(map[status] || status)}</span>`;
}
async function api(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try { const j = await r.json(); msg = j.detail || msg; } catch (_) { /* ignore */ }
    throw new Error(msg);
  }
  return r.json();
}

/* ---------- 任务列表 ---------- */
async function refreshTasks() {
  const tasks = await api("/api/tasks");
  const box = $("taskList");
  box.innerHTML = tasks.map(t => `
    <div class="task-card ${currentTask === t.id ? "active" : ""}" data-id="${esc(t.id)}">
      <div class="t-name">${esc(t.id)}</div>
      <div class="t-meta">${badge(t.status)}
        ${t.stage ? " · 阶段 " + esc(t.stage) : ""}
        ${t.paper ? " · 📄 有论文" : ""}${t.updated ? " · " + esc(t.updated.slice(5, 16)) : ""}
      </div>
    </div>`).join("") || `<div class="t-meta">暂无任务</div>`;
  box.querySelectorAll(".task-card").forEach(el => {
    el.onclick = () => selectTask(el.dataset.id);
  });
}

/* ---------- 新建任务 ---------- */
function setupUpload() {
  const drop = $("drop"), input = $("fileInput");
  drop.onclick = (e) => { if (e.target.tagName !== "INPUT") input.click(); };
  input.onchange = () => { pendingFiles = [...input.files]; renderFiles(); };
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("dragover"); };
  drop.ondragleave = () => drop.classList.remove("dragover");
  drop.ondrop = (e) => {
    e.preventDefault(); drop.classList.remove("dragover");
    pendingFiles = [...e.dataTransfer.files]; renderFiles();
  };
}
function renderFiles() {
  $("fileList").innerHTML = pendingFiles.map(f => `<div>📎 ${esc(f.name)}</div>`).join("");
}
$("btnCreate").onclick = async () => {
  if (!pendingFiles.length) { alert("请先添加题面/数据文件"); return; }
  const fd = new FormData();
  fd.append("task_id", $("taskName").value.trim());
  pendingFiles.forEach(f => fd.append("files", f));
  $("btnCreate").disabled = true;
  try {
    const r = await api("/api/tasks", { method: "POST", body: fd });
    pendingFiles = []; $("taskName").value = ""; renderFiles();
    await refreshTasks();
    selectTask(r.task_id);
  } catch (e) { alert("创建失败：" + e.message); }
  $("btnCreate").disabled = false;
};

/* ---------- 任务详情 ---------- */
async function selectTask(id) {
  currentTask = id;
  await refreshTasks();
  $("emptyState").classList.add("hidden");
  $("taskDetail").classList.remove("hidden");
  $("detailTitle").textContent = "任务：" + id;
  loadedPaperStage = "";
  stopPoll();
  await loadStatus();
  startPoll();
}

function renderTimeline(stage, status, error) {
  const box = $("stageTimeline");
  const idx = STAGES.indexOf(stage);
  box.innerHTML = STAGES.map((s, i) => {
    let cls = "", icon = "⬜";
    if (status === "done") { cls = "done"; icon = "✅"; }
    else if (status === "failed" && s === stage) { cls = "failed"; icon = "❌"; }
    else if (status === "running") {
      if (i < idx) { cls = "done"; icon = "✅"; }
      else if (i === idx) { cls = "running"; icon = "⏳"; }
    }
    return `<div class="stage-node ${cls}" title="${esc(error || "")}">
      <div class="s-icon">${icon}</div><div class="s-name">${s} ${esc(STAGE_NAMES[s])}</div></div>`;
  }).join("");
}

/* ---------- 团队协作面板 ---------- */
const TEAM_AGENTS = [
  { key: "modeler", name: "建模手", icon: "📐", desc: "读题拆解 · 假设 · 建模" },
  { key: "coder", name: "代码手", icon: "💻", desc: "实现 · 运行验证 · 图表" },
  { key: "writer", name: "论文手", icon: "✍️", desc: "评审 · 撰写 · 编译 PDF" },
];
const TEAM_STATUS = {
  working: "进行中", reviewing: "评审中", revising: "修订中",
  waiting: "等待", done: "完成", idle: "就绪",
};
function renderTeam(team) {
  const box = $("teamGrid");
  box.innerHTML = TEAM_AGENTS.map(a => {
    const t = (team && team[a.key]) || {};
    const status = t.status || "idle";
    const notePath = `team/${a.key}_notes.md`;
    return `
      <div class="agent-card st-${esc(status)}">
        <div class="a-head">
          <span class="a-icon">${a.icon}</span>
          <span class="a-name">${a.name}</span>
          <span class="badge ${esc(status)}">${esc(TEAM_STATUS[status] || status)}</span>
        </div>
        <div class="a-desc">${esc(a.desc)}</div>
        <div class="a-activity">${esc(t.activity || "待命")}</div>
        <div class="a-foot">
          <span class="link" onclick="viewFile('${notePath}')">📝 协作笔记</span>
        </div>
      </div>`;
  }).join("");
}

function appendLogs(logs) {
  const box = $("logBox");
  box.innerHTML = logs.map(l => {
    const cls = l.level === "error" ? "l-error" : l.level === "warn" ? "l-warn" : "";
    return `<div class="${cls}">[${esc(l.ts)}] ${esc(l.msg)}</div>`;
  }).join("");
  box.scrollTop = box.scrollHeight;
}

async function loadStatus() {
  if (!currentTask) return;
  const st = await api(`/api/tasks/${currentTask}/status`);
  $("detailStatus").innerHTML = `状态：${badge(st.status)}
    ${st.stage ? "· 阶段 " + esc(st.stage) + "（" + esc(st.stage_name) + "）" : ""}
    ${st.error ? `<div class="error">⚠ ${esc(st.error)}</div>` : ""}`;
  renderTimeline(st.stage, st.status, st.error);
  renderTeam(st.team);
  appendLogs(st.logs);
  $("btnRun").disabled = st.status === "running";

  // PDF：done 时加载；running 时若已存在也加载（重跑场景保留）
  if (st.status === "done" || st.status === "failed") {
    loadPaper();
    await refreshArtifacts();
    await refreshTasks();
    if (st.status === "done") stopPoll();
  } else if (st.status === "running") {
    await refreshArtifacts();
  }
  return st;
}

function startPoll() {
  stopPoll();
  pollTimer = setInterval(async () => {
    try {
      const st = await loadStatus();
      if (st.status === "done" || st.status === "failed") stopPoll();
    } catch (e) {
      stopPoll(); console.error(e);
    }
  }, 2000);
}
function stopPoll() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

/* ---------- 产物浏览 ---------- */
async function refreshArtifacts() {
  const tree = await api(`/api/tasks/${currentTask}/artifacts`);
  const box = $("artifactTree");
  box.innerHTML = Object.entries(tree).map(([dir, files]) => `
    <div class="dir">${esc(dir)}/</div>
    ${files.map(f => `
      <div class="file" data-path="${esc(f.path)}">
        <span>${esc(fname(f.path))}</span>
        <span class="sz">${(f.size / 1024).toFixed(1)}KB</span>
      </div>`).join("")}
  `).join("");
  box.querySelectorAll(".file").forEach(el => {
    el.onclick = () => viewFile(el.dataset.path);
  });
}
function fname(path) { return path.split("/").pop(); }
function baseName(name) { return name.replace(/_q\d+$/, ""); }

async function viewFile(path) {
  const name = fname(path);
  const suffix = name.split(".").pop().toLowerCase();
  const viewer = $("fileViewer");
  viewer.classList.remove("hidden");
  if (suffix === "png") {
    viewer.innerHTML = `<div class="fv-head"><span>${esc(name)}</span>
      <span class="fv-close">✕</span></div>
      <div style="padding:10px"><img src="/api/tasks/${currentTask}/file?path=${encodeURIComponent(path)}"
      style="max-width:100%;border-radius:6px"></div>`;
  } else if (suffix === "pdf") {
    viewer.innerHTML = `<div class="fv-head"><span>${esc(name)}</span>
      <span class="fv-close">✕</span></div>
      <iframe src="/api/tasks/${currentTask}/file?path=${encodeURIComponent(path)}"
      style="width:100%;height:50vh;border:none"></iframe>`;
  } else {
    const r = await api(`/api/tasks/${currentTask}/file?path=${encodeURIComponent(path)}`);
    viewer.innerHTML = `<div class="fv-head"><span>${esc(name)}</span>
      <span class="fv-close">✕</span></div><pre>${esc(r.content)}</pre>`;
  }
  viewer.querySelector(".fv-close").onclick = () => viewer.classList.add("hidden");
}

function loadPaper() {
  const st = currentTask;
  if (loadedPaperStage === st) return;
  loadedPaperStage = st;
  $("paperFrame").src = `/api/tasks/${st}/paper?t=${Date.now()}`;
  $("btnWord").disabled = false;
}

/* ---------- Word 下载 ---------- */
$("btnWord").onclick = () => {
  if (!currentTask) return;
  const a = document.createElement("a");
  a.href = `/api/tasks/${currentTask}/word`;
  a.download = `${currentTask}_main.docx`;
  a.click();
};

/* ---------- 运行 ---------- */
$("btnRun").onclick = async () => {
  if (!currentTask) return;
  try { await api(`/api/tasks/${currentTask}/run`, { method: "POST", body: new URLSearchParams({ from_stage: "P1" }) }); }
  catch (e) { alert("启动失败：" + e.message); }
  await loadStatus(); startPoll();
};
$("btnRerunP1").onclick = async () => {
  if (!currentTask) return;
  try { await api(`/api/tasks/${currentTask}/run`, { method: "POST", body: new URLSearchParams({ from_stage: "P1" }) }); }
  catch (e) { alert("重跑失败：" + e.message); }
  await loadStatus(); startPoll();
};

/* ---------- LLM 配置 ---------- */
async function openConfig() {
  const cfg = await api("/api/config");
  $("cfgBaseUrl").value = cfg.base_url || "";
  $("cfgApiKey").value = "";
  $("cfgApiKey").placeholder = cfg.configured ? "已配置（留空不修改）" : "sk-...";
  $("cfgModel").value = cfg.model || "";
  $("cfgTemp").value = cfg.temperature ?? 0.3;
  const roles = cfg.roles || {};
  const roleInputs = [["modeler", "cfgRoleModeler"], ["coder", "cfgRoleCoder"], ["writer", "cfgRoleWriter"]];
  for (const [k, id] of roleInputs) {
    $(id).value = (roles[k] && roles[k].model) || "";
  }
  $("cfgTestMsg").textContent = "";
  $("configModal").classList.remove("hidden");
}
function closeConfig() { $("configModal").classList.add("hidden"); }
$("btnConfig").onclick = openConfig;
$("btnCloseCfg").onclick = closeConfig;
$("configModal").onclick = (e) => { if (e.target === $("configModal")) closeConfig(); };

function cfgPayload() {
  const p = {};
  const v = $("cfgBaseUrl").value.trim(); if (v) p.base_url = v;
  const k = $("cfgApiKey").value.trim(); if (k) p.api_key = k;
  const m = $("cfgModel").value.trim(); if (m) p.model = m;
  p.temperature = parseFloat($("cfgTemp").value) || 0.3;
  const roles = {};
  const roleInputs = [["modeler", "cfgRoleModeler"], ["coder", "cfgRoleCoder"], ["writer", "cfgRoleWriter"]];
  for (const [rk, id] of roleInputs) {
    const rm = $(id).value.trim();
    if (rm) roles[rk] = { model: rm };
  }
  if (Object.keys(roles).length) p.roles = roles;
  return p;
}
$("btnTestCfg").onclick = async () => {
  $("cfgTestMsg").textContent = "测试中…";
  try {
    const r = await api("/api/config/test", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cfgPayload()) });
    $("cfgTestMsg").textContent = r.ok ? "✅ " + r.msg : "❌ " + r.msg;
    $("cfgTestMsg").style.color = r.ok ? "var(--ok)" : "var(--err)";
  } catch (e) { $("cfgTestMsg").textContent = "❌ " + e.message; }
};
$("btnSaveCfg").onclick = async () => {
  try {
    await api("/api/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cfgPayload()) });
    closeConfig();
  } catch (e) { alert("保存失败：" + e.message); }
};

/* ---------- 初始化 ---------- */
setupUpload();
refreshTasks();
