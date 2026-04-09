/**
 * AquaSense AI — Agricultural Dashboard
 */

const _BASE       = window.AQUASENSE_API_BASE || "";
const API_ANALYZE = `${_BASE}/api/analyze`;
const API_HEALTH  = `${_BASE}/api/inference/health`;
const API_HISTORY = `${_BASE}/api/analyses`;
const API_STATS   = `${_BASE}/api/stats`;
const API_TREND   = `${_BASE}/api/trend`;
const API_EXPORT  = `${_BASE}/api/analyses/export`;
const API_ZONES        = `${_BASE}/api/zones`;
const API_PUBLIC_STATS = `${_BASE}/api/stats/public`;
const API_AUTH_ME      = `${_BASE}/auth/me`;
const API_AUTH_LOGIN   = `${_BASE}/auth/login`;
const API_AUTH_LOGOUT  = `${_BASE}/auth/logout`;
const API_IMAGE   = id => `${_BASE}/api/analyses/${id}/image`;
const API_DELETE  = id => `${_BASE}/api/analyses/${id}`;

const CAT_CONFIG = {
  water_quality:     { cls:"cat-water",  label:"💧 Water Quality" },
  irrigation_system: { cls:"cat-system", label:"⚙️ Irrigation System" },
  field_soil:        { cls:"cat-field",  label:"🌱 Field & Soil" },
  crop_health:       { cls:"cat-crop",   label:"🌿 Crop Health" },
};

const ISSUE_LABELS = {
  turbid_water:"Turbid Water", algae_bloom:"Algae Bloom", contamination:"Contamination",
  salinity_stress:"Salinity Stress", pathogen_risk:"Pathogen Risk",
  clogged_emitter:"Clogged Emitter", pipe_leak:"Pipe Leak", broken_sprinkler:"Broken Sprinkler",
  pressure_problem:"Pressure Problem", pipe_damage:"Pipe Damage", filter_blockage:"Filter Blockage",
  dry_patch:"Dry Patch", waterlogging:"Waterlogging", runoff:"Runoff",
  soil_erosion:"Soil Erosion", uneven_distribution:"Uneven Distribution",
  wilting:"Wilting", overwatering_symptoms:"Overwatering",
  nutrient_deficiency:"Nutrient Deficiency", disease_pressure:"Disease Pressure",
};

// ── State ─────────────────────────────────────────────────────────────────────
let selectedFile       = null;
let _trendChartInstance= null;
let _historyOffset     = 0;
let _historyDateFrom   = undefined;
let _historyDateTo     = undefined;
let _historyIssueType  = undefined;
let _historyZoneFilter = undefined;
let _stageTimer        = null;
let _notificationsOn   = false;
let _batchFiles        = [];
let _batchRunning      = false;
const HISTORY_PAGE     = 20;

// ── DOM refs ──────────────────────────────────────────────────────────────────
let dropZone, dropInner, previewContainer, previewImg, fileInput, batchInput;
let analyzeBtn, changeBtn, loadingEl, loadingStageEl, errorEl, errorMsgEl, fieldZoneInput;
let resultsEl, statusBanner, statusIcon, statusLabel, urgencyPill;
let categoryRow, categoryBadge, issuesList;
let mConf, mArea, mWaste, faultyBar, faultyPct, normalBar, normalPct;
let aiMessage, cropImpact, cropImpactText, recBox, recIcon, recText;
let enginePill, datasetPill, fieldPill, engineBadge;
let historySection, historyList, loadMoreBtn, historyEmpty;
let statCritical, statWarning, statHealthy, statTotal;
let trendSection, filterFrom, filterTo, filterIssue;
let batchPanel, batchList, batchProgress, batchRunBtn, batchBarTrack, batchBarFill;
let zoneDashboard, zoneGrid;
let notifBtn, copyRecBtn, historyCount, filterActiveBadge, authArea;
let scanCounter, scTotal, scCritical, scHealthy, scZones;

document.addEventListener("DOMContentLoaded", () => {
  dropZone        = document.getElementById("dropZone");
  dropInner       = document.getElementById("dropInner");
  previewContainer= document.getElementById("previewContainer");
  previewImg      = document.getElementById("previewImg");
  fileInput       = document.getElementById("fileInput");
  batchInput      = document.getElementById("batchInput");
  analyzeBtn      = document.getElementById("analyzeBtn");
  changeBtn       = document.getElementById("changeBtn");
  loadingEl       = document.getElementById("loading");
  loadingStageEl  = document.getElementById("loadingStage");
  errorEl         = document.getElementById("error");
  errorMsgEl      = document.getElementById("errorMsg");
  fieldZoneInput  = document.getElementById("fieldZoneInput");
  resultsEl       = document.getElementById("results");
  statusBanner    = document.getElementById("statusBanner");
  statusIcon      = document.getElementById("statusIcon");
  statusLabel     = document.getElementById("statusLabel");
  urgencyPill     = document.getElementById("urgencyPill");
  categoryRow     = document.getElementById("categoryRow");
  categoryBadge   = document.getElementById("categoryBadge");
  issuesList      = document.getElementById("issuesList");
  mConf           = document.getElementById("mConf");
  mArea           = document.getElementById("mArea");
  mWaste          = document.getElementById("mWaste");
  faultyBar       = document.getElementById("faultyBar");
  faultyPct       = document.getElementById("faultyPct");
  normalBar       = document.getElementById("normalBar");
  normalPct       = document.getElementById("normalPct");
  aiMessage       = document.getElementById("aiMessage");
  cropImpact      = document.getElementById("cropImpact");
  cropImpactText  = document.getElementById("cropImpactText");
  recBox          = document.getElementById("recBox");
  recIcon         = document.getElementById("recIcon");
  recText         = document.getElementById("recText");
  enginePill      = document.getElementById("enginePill");
  datasetPill     = document.getElementById("datasetPill");
  fieldPill       = document.getElementById("fieldPill");
  engineBadge     = document.getElementById("engineBadge");
  historySection  = document.getElementById("historySection");
  historyList     = document.getElementById("historyList");
  loadMoreBtn     = document.getElementById("loadMoreBtn");
  historyEmpty    = document.getElementById("historyEmpty");
  statCritical    = document.getElementById("statCritical");
  statWarning     = document.getElementById("statWarning");
  statHealthy     = document.getElementById("statHealthy");
  statTotal       = document.getElementById("statTotal");
  trendSection    = document.getElementById("trendSection");
  filterFrom      = document.getElementById("filterFrom");
  filterTo        = document.getElementById("filterTo");
  filterIssue     = document.getElementById("filterIssue");
  batchPanel      = document.getElementById("batchPanel");
  batchList       = document.getElementById("batchList");
  batchProgress   = document.getElementById("batchProgress");
  batchRunBtn     = document.getElementById("batchRunBtn");
  batchBarTrack   = document.getElementById("batchBarTrack");
  batchBarFill    = document.getElementById("batchBarFill");
  zoneDashboard   = document.getElementById("zoneDashboard");
  zoneGrid        = document.getElementById("zoneGrid");
  notifBtn          = document.getElementById("notifBtn");
  copyRecBtn        = document.getElementById("copyRecBtn");
  historyCount      = document.getElementById("historyCount");
  filterActiveBadge = document.getElementById("filterActiveBadge");
  authArea          = document.getElementById("authArea");
  scanCounter       = document.getElementById("scanCounter");
  scTotal           = document.getElementById("scTotal");
  scCritical        = document.getElementById("scCritical");
  scHealthy         = document.getElementById("scHealthy");
  scZones           = document.getElementById("scZones");

  setupDragDrop();
  fileInput.addEventListener("change", e => { if (e.target.files[0]) setFile(e.target.files[0]); fileInput.value = ""; });
  batchInput.addEventListener("change", () => { if (batchInput.files.length) addToBatch(Array.from(batchInput.files)); batchInput.value = ""; });
  analyzeBtn.addEventListener("click", runAnalysis);
  changeBtn.addEventListener("click", resetUpload);

  // Keyboard shortcuts: Escape closes modal, Enter triggers analysis
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") { closeModal(); return; }
    if (e.key === "Enter" && selectedFile && !analyzeBtn.disabled && document.activeElement?.id !== "fieldZoneInput") {
      e.preventDefault();
      runAnalysis();
    }
  });

  // Register service worker for PWA
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }

  checkHealth();
  loadStats();
  loadZones();
  loadHistory();
  loadTrend();
  loadZoneAutocomplete();
  loadPublicStats();
  checkAuth();

  // Handle auth redirect result (?auth=success or ?auth_error=...)
  const _params = new URLSearchParams(location.search);
  if (_params.has("auth")) { history.replaceState({}, "", "/"); }
  if (_params.get("auth_error")) {
    showToast("Sign-in failed — please try again", true);
    history.replaceState({}, "", "/");
  }

  // Restore notification preference
  if (localStorage.getItem("aq_notif") === "on") {
    _notificationsOn = true;
    notifBtn.classList.add("active");
    notifBtn.textContent = "🔔 Alerts ON";
  }
});

// ── Drag & Drop ───────────────────────────────────────────────────────────────
function setupDragDrop() {
  const _dropTitle = () => dropInner.querySelector(".drop-title");
  const _origTitle = "Drag & drop or tap to upload";
  dropZone.addEventListener("dragover", e => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
    const count = e.dataTransfer?.items?.length || 0;
    const t = _dropTitle();
    if (t) t.textContent = count > 1 ? `Drop ${count} images for batch` : "Drop to analyze";
  });
  dropZone.addEventListener("dragleave", e => {
    if (!dropZone.contains(e.relatedTarget)) {
      dropZone.classList.remove("drag-over");
      const t = _dropTitle(); if (t) t.textContent = _origTitle;
    }
  });
  dropZone.addEventListener("drop", e => {
    e.preventDefault(); dropZone.classList.remove("drag-over");
    const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith("image/"));
    if (!files.length) { showError("Please drop image files."); return; }
    if (files.length > 1) { setupBatch(files); return; }
    setFile(files[0]);
  });
  dropZone.addEventListener("click",   e => { if (e.target !== changeBtn) fileInput.click(); });
  dropZone.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); } });
}

function setFile(file) {
  selectedFile = file;
  const r = new FileReader();
  r.onload = e => {
    previewImg.classList.remove("img-loaded");
    previewImg.src = e.target.result;
    previewImg.onload = () => previewImg.classList.add("img-loaded");
    dropInner.style.display    = "none";
    previewContainer.style.display = "flex";
    dropZone.classList.add("has-image");
  };
  r.readAsDataURL(file);
  analyzeBtn.disabled = false;
  analyzeBtn.classList.add("ready");
  errorEl.style.display = "none";
}

function resetUpload() {
  selectedFile = null;
  previewImg.src = "";
  dropInner.style.display        = "flex";
  previewContainer.style.display = "none";
  dropZone.classList.remove("has-image");
  analyzeBtn.disabled = true;
  analyzeBtn.classList.remove("ready");
}

// ── Loading stages ────────────────────────────────────────────────────────────
const _STAGES = [
  "Inspecting water quality & system components…",
  "Analyzing crop health indicators…",
  "Evaluating irrigation coverage…",
  "Checking for leaks & pressure issues…",
  "Generating AI assessment…",
];

function _startLoadingStages() {
  if (!loadingStageEl) return;
  let i = 0;
  loadingStageEl.textContent = _STAGES[0];
  _stageTimer = setInterval(() => {
    i = (i + 1) % _STAGES.length;
    loadingStageEl.style.opacity = "0";
    setTimeout(() => { loadingStageEl.textContent = _STAGES[i]; loadingStageEl.style.opacity = "1"; }, 200);
  }, 2400);
}

function _stopLoadingStages() {
  if (_stageTimer) { clearInterval(_stageTimer); _stageTimer = null; }
}

// ── Analysis ──────────────────────────────────────────────────────────────────
async function runAnalysis() {
  if (!selectedFile) return;
  loadingEl.style.display  = "flex";
  errorEl.style.display    = "none";
  resultsEl.style.display  = "none";
  analyzeBtn.disabled      = true;
  _startLoadingStages();

  const fd   = new FormData();
  const file = await compressIfNeeded(selectedFile);
  fd.append("file", file, file.name || selectedFile.name);
  const zone = fieldZoneInput?.value.trim();
  if (zone) fd.append("field_zone", zone);

  try {
    const res = await apiFetch(API_ANALYZE, { method:"POST", body:fd });
    if (!res.ok) {
      let msg = `Server error ${res.status}`;
      try { const body = await res.text(); msg = JSON.parse(body).detail || body || msg; } catch {}
      throw new Error(msg);
    }
    const data = await res.json();
    _stopLoadingStages();
    loadingEl.style.display = "none";
    analyzeBtn.disabled = false;
    renderResults(data);
    loadStats(); loadZones(); loadHistory(); loadTrend();
    _maybeSendNotification(data);
  } catch (err) {
    _stopLoadingStages();
    loadingEl.style.display = "none";
    analyzeBtn.disabled = false;
    showError(err.message || "Unexpected error. Make sure the API server is running.");
  }
}

// ── Render Results ────────────────────────────────────────────────────────────
function renderResults(d) {
  const status = d.status || (d.issue_detected ? "warning" : "healthy");
  const bannerCls  = { critical:"status-critical", warning:"status-warning", healthy:"status-healthy" };
  const labelCls   = { critical:"lbl-critical",    warning:"lbl-warning",    healthy:"lbl-healthy" };
  const statusMeta = {
    critical:{ icon:"🔴", text:"Critical Issue" },
    warning: { icon:"⚠️", text:"Warning" },
    healthy: { icon:"✅", text:"Healthy" },
  }[status] || { icon:"❓", text:"Unknown" };

  statusBanner.className      = "status-banner " + (bannerCls[status] || "");
  statusIcon.textContent      = statusMeta.icon;
  statusLabel.textContent     = statusMeta.text;
  statusLabel.className       = "status-label " + (labelCls[status] || "");

  const urgMap = {
    immediate:{ cls:"urg-immediate", txt:"🚨 Act Immediately" },
    soon:     { cls:"urg-soon",      txt:"📅 Act Within Days" },
    monitor:  { cls:"urg-monitor",   txt:"👁 Monitor" },
    none:     { cls:"urg-none",      txt:"✓ No Action Needed" },
  };
  const urg = urgMap[d.urgency] || urgMap.none;
  urgencyPill.className   = "urgency-pill " + urg.cls;
  urgencyPill.textContent = urg.txt;

  const cat = d.issue_category && CAT_CONFIG[d.issue_category];
  if (cat && d.issue_detected) {
    categoryBadge.className   = "cat-badge " + cat.cls;
    categoryBadge.textContent = cat.label;
    issuesList.innerHTML = (Array.isArray(d.all_issues) ? d.all_issues : [])
      .map(k => `<span class="issue-tag active">${ISSUE_LABELS[k] || k}</span>`).join("");
    categoryRow.style.display = "flex";
  } else {
    categoryRow.style.display = "none";
  }

  mConf.textContent = Math.round((d.confidence || 0) * 100) + "%";
  mConf.style.color = status === "healthy" ? "var(--green)" : status === "critical" ? "var(--red)" : "var(--amber)";
  mArea.textContent = (d.affected_area_pct || 0) + "%";
  mArea.style.color = (d.affected_area_pct || 0) > 30 ? "var(--red)" : (d.affected_area_pct || 0) > 10 ? "var(--amber)" : "var(--green)";
  const wasteColors = { high:"var(--red)", medium:"var(--amber)", low:"var(--green)", none:"var(--grey)" };
  mWaste.textContent = capitalize(d.water_waste_risk || "none");
  mWaste.style.color = wasteColors[d.water_waste_risk] || "var(--grey)";

  const fp = Math.round((d.faulty_probability  || 0) * 100);
  const np = Math.round((d.normal_probability  || 0) * 100);
  faultyBar.style.width = fp + "%"; faultyPct.textContent = fp + "%";
  normalBar.style.width = np + "%"; normalPct.textContent = np + "%";

  aiMessage.textContent = d.message || "Analysis complete.";

  if (d.crop_impact && d.issue_detected) {
    cropImpact.className      = "impact-box impact-warning";
    cropImpactText.textContent = d.crop_impact;
    cropImpact.style.display  = "flex";
  } else if (!d.issue_detected) {
    cropImpact.className      = "impact-box impact-ok";
    cropImpactText.textContent = "No crop impact expected. System is operating normally.";
    cropImpact.style.display  = "flex";
  } else {
    cropImpact.style.display = "none";
  }

  if (d.recommendation) {
    const recCls = { critical:"rec-critical", warning:"rec-warning", healthy:"rec-healthy" };
    recBox.className      = "rec-box " + (recCls[status] || "rec-healthy");
    recIcon.textContent   = status === "critical" ? "🔧" : status === "warning" ? "⚠️" : "✓";
    recText.textContent   = d.recommendation;
    copyRecBtn.style.display = "inline-block";
    copyRecBtn.onclick = () => navigator.clipboard?.writeText(d.recommendation).then(() => showToast("Copied")).catch(() => {});
    recBox.style.display  = "flex";
  } else {
    recBox.style.display  = "none";
    copyRecBtn.style.display = "none";
  }

  if (d.model_type) { enginePill.textContent = "🤖 " + formatEngine(d.model_type); enginePill.style.display = "inline-block"; }
  datasetPill.style.display = d.dataset_saved ? "inline-block" : "none";
  if (d.field_zone) { fieldPill.textContent = "📍 " + d.field_zone; fieldPill.style.display = "inline-block"; }
  else fieldPill.style.display = "none";

  // Re-trigger flash animation on each new result
  resultsEl.classList.remove("result-flash");
  resultsEl.style.display = "block";
  void resultsEl.offsetWidth;
  resultsEl.classList.add("result-flash");
  resultsEl.scrollIntoView({ behavior:"smooth", block:"nearest" });
}

// ── Stats ─────────────────────────────────────────────────────────────────────
function _animateCount(el, target, duration = 600) {
  const start = parseInt(el.textContent) || 0;
  if (start === target) return;
  const diff = target - start;
  const t0 = performance.now();
  const step = now => {
    const p = Math.min((now - t0) / duration, 1);
    el.textContent = Math.round(start + diff * (1 - Math.pow(1 - p, 3)));
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

async function loadStats(zone) {
  try {
    const url = zone ? `${API_STATS}?field_zone=${encodeURIComponent(zone)}` : API_STATS;
    const data = await apiFetch(url).then(r => r.json());
    _animateCount(statCritical, data.critical ?? 0);
    _animateCount(statWarning,  data.warning  ?? 0);
    _animateCount(statHealthy,  data.healthy  ?? 0);
    _animateCount(statTotal,    data.total    ?? 0);
  } catch {}
}

// ── Zone dashboard ────────────────────────────────────────────────────────────
async function loadZones() {
  try {
    const rows = await apiFetch(API_ZONES).then(r => r.ok ? r.json() : []);
    if (!rows.length) { zoneDashboard.style.display = "none"; return; }
    zoneDashboard.style.display = "block";
    zoneGrid.innerHTML = rows.map(z => {
      const total = z.total || 1;
      const wC = Math.round((z.critical / total) * 100);
      const wW = Math.round((z.warning  / total) * 100);
      const wH = Math.round((z.healthy  / total) * 100);
      const cls = z.latest_status === "critical" ? "zc-critical" : z.latest_status === "warning" ? "zc-warning" : "zc-healthy";
      const lastScan = z.last_scan ? new Date(z.last_scan) : null;
      const daysAgo  = lastScan ? Math.floor((Date.now() - lastScan) / 86400000) : null;
      const stale    = daysAgo !== null && daysAgo >= 7;
      return `<div class="zone-card ${cls}" onclick="filterByZone(${esc(JSON.stringify(z.field_zone))})">
        ${stale ? `<div class="zone-stale">⏰ ${daysAgo}d ago</div>` : ""}
        <div class="zone-name" title="${esc(z.field_zone)}">${esc(z.field_zone)}</div>
        <div class="zone-bars">
          ${wC ? `<div class="zb-critical" style="flex:${wC}"></div>` : ""}
          ${wW ? `<div class="zb-warning"  style="flex:${wW}"></div>` : ""}
          ${wH ? `<div class="zb-healthy"  style="flex:${wH}"></div>` : ""}
        </div>
        <div class="zone-meta">
          <span class="zone-total">${z.total} scan${z.total !== 1 ? "s" : ""}</span>
          <span class="zone-last">${lastScan ? lastScan.toLocaleDateString() : "—"}</span>
        </div>
      </div>`;
    }).join("");
  } catch {}
}

function filterByZone(zone) {
  _historyZoneFilter = zone;
  if (filterActiveBadge) { filterActiveBadge.textContent = `Zone: ${zone}`; filterActiveBadge.style.display = "inline-block"; }
  loadHistory(undefined, undefined, undefined, zone);
  loadStats(zone);
  document.getElementById("historySection").scrollIntoView({ behavior:"smooth", block:"start" });
  showToast(`Filtered to: ${zone}`);
}

// ── Zone autocomplete ─────────────────────────────────────────────────────────
async function loadZoneAutocomplete() {
  try {
    const remote = await apiFetch(API_ZONES).then(r => r.ok ? r.json() : []);
    const remoteNames = remote.map(z => z.field_zone).filter(Boolean);
    // Merge with localStorage but drop any zones no longer on the server
    const stored = JSON.parse(localStorage.getItem("aq_zones") || "[]");
    const remoteSet = new Set(remoteNames);
    const merged = remoteNames.length
      ? [...new Set([...remoteNames, ...stored.filter(n => remoteSet.has(n))])]
      : [...new Set(stored)];
    localStorage.setItem("aq_zones", JSON.stringify(merged));
    const dl = document.getElementById("zoneList");
    dl.innerHTML = merged.map(n => `<option value="${esc(n)}">`).join("");
  } catch {}
}

// ── Trend chart ───────────────────────────────────────────────────────────────
async function loadTrend() {
  if (typeof Chart === "undefined" && !window._chartJsFailed) {
    await new Promise(resolve => {
      let waited = 0;
      const poll = setInterval(() => {
        waited += 100;
        if (typeof Chart !== "undefined" || window._chartJsFailed || waited >= 3000) {
          clearInterval(poll); resolve();
        }
      }, 100);
    });
  }
  if (window._chartJsFailed || typeof Chart === "undefined") {
    trendSection.style.display = "block";
    const canvas = document.getElementById("trendChart");
    if (canvas && !canvas.nextElementSibling?.classList?.contains("chart-fallback"))
      canvas.insertAdjacentHTML("afterend", '<p class="chart-fallback" style="color:#64748b;font-size:.85rem;text-align:center;padding:1rem">Trend chart unavailable (offline)</p>');
    return;
  }
  try {
    const rows = await apiFetch(API_TREND + "?days=14").then(r => r.ok ? r.json() : []);
    if (!rows.length) return;
    trendSection.style.display = "block";
    const labels   = rows.map(r => r.day.slice(5));
    const critical = rows.map(r => r.critical || 0);
    const warning  = rows.map(r => r.warning  || 0);
    const healthy  = rows.map(r => r.healthy  || 0);
    if (_trendChartInstance) _trendChartInstance.destroy();
    _trendChartInstance = new Chart(document.getElementById("trendChart"), {
      type:"bar",
      data:{ labels, datasets:[
        { label:"Critical", data:critical, backgroundColor:"#ef444466", borderColor:"#ef4444", borderWidth:1 },
        { label:"Warning",  data:warning,  backgroundColor:"#f59e0b66", borderColor:"#f59e0b", borderWidth:1 },
        { label:"Healthy",  data:healthy,  backgroundColor:"#22c55e66", borderColor:"#22c55e", borderWidth:1 },
      ]},
      options:{
        responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{ labels:{ color:"#94a3b8", font:{size:11} } } },
        scales:{
          x:{ stacked:true, ticks:{ color:"#94a3b8", font:{size:10} }, grid:{ color:"#1e3a5f" } },
          y:{ stacked:true, ticks:{ color:"#94a3b8", font:{size:10}, stepSize:1 }, grid:{ color:"#1e3a5f" }, beginAtZero:true },
        },
      },
    });
  } catch {}
}

// ── History ───────────────────────────────────────────────────────────────────
function _skeletonItems(n = 3) {
  return Array.from({ length:n }, () => `
    <div class="skeleton-item">
      <div class="sk-dot  skeleton"></div>
      <div class="sk-thumb skeleton"></div>
      <div class="sk-lines">
        <div class="sk-line w70 skeleton"></div>
        <div class="sk-line w45 skeleton"></div>
      </div>
    </div>`).join("");
}

async function loadHistory(dateFrom, dateTo, issueType, zone) {
  _historyOffset    = 0;
  _historyDateFrom  = dateFrom  !== undefined ? dateFrom  : _historyDateFrom;
  _historyDateTo    = dateTo    !== undefined ? dateTo    : _historyDateTo;
  _historyIssueType = issueType !== undefined ? issueType : _historyIssueType;
  _historyZoneFilter= zone      !== undefined ? zone      : _historyZoneFilter;

  historySection.style.display = "block";
  historyList.innerHTML        = _skeletonItems(3);
  historyList.style.display    = "flex";
  historyEmpty.style.display   = "none";
  loadMoreBtn.style.display    = "none";

  try {
    const rows = await _fetchHistory(0);
    renderHistory(rows, false);
  } catch { historyList.innerHTML = ""; }
}

async function loadMoreHistory() {
  _historyOffset += HISTORY_PAGE;
  loadMoreBtn.textContent = "Loading…";
  loadMoreBtn.disabled    = true;
  try {
    const rows = await _fetchHistory(_historyOffset);
    renderHistory(rows, true);
  } catch {} finally {
    loadMoreBtn.textContent = "Load more scans";
    loadMoreBtn.disabled    = false;
  }
}

async function _fetchHistory(offset) {
  let url = `${API_HISTORY}?limit=${HISTORY_PAGE}&offset=${offset}`;
  if (_historyDateFrom)  url += `&date_from=${_historyDateFrom}`;
  if (_historyDateTo)    url += `&date_to=${_historyDateTo}`;
  if (_historyIssueType) url += `&issue_type=${encodeURIComponent(_historyIssueType)}`;
  if (_historyZoneFilter)url += `&field_zone=${encodeURIComponent(_historyZoneFilter)}`;
  const res = await apiFetch(url);
  if (!res.ok) return [];
  return res.json();
}

function applyFilter() {
  _historyZoneFilter = null;
  const hasFilter = !!(filterFrom.value || filterTo.value || filterIssue.value);
  if (filterActiveBadge) filterActiveBadge.style.display = hasFilter ? "inline-block" : "none";
  loadHistory(
    filterFrom.value  || undefined,
    filterTo.value    || undefined,
    filterIssue.value || undefined,
    null,
  );
  loadStats();
}

function clearFilter() {
  filterFrom.value   = "";
  filterTo.value     = "";
  filterIssue.value  = "";
  _historyZoneFilter = null;
  if (filterActiveBadge) filterActiveBadge.style.display = "none";
  loadHistory(undefined, undefined, undefined, null);
  loadStats();
}

function exportCSV() {
  let url = API_EXPORT;
  const p = [];
  if (_historyDateFrom)   p.push(`date_from=${_historyDateFrom}`);
  if (_historyDateTo)     p.push(`date_to=${_historyDateTo}`);
  if (_historyZoneFilter) p.push(`field_zone=${encodeURIComponent(_historyZoneFilter)}`);
  if (p.length) url += "?" + p.join("&");
  window.location.href = url;
}

function _historyItemHTML(r) {
  const status = r.status || (r.issue_detected ? "warning" : "healthy");
  const dotCls = { critical:"dot-critical", warning:"dot-warning", healthy:"dot-healthy" }[status] || "dot-warning";
  const resCls = { critical:"h-crit", warning:"h-warn", healthy:"h-ok" }[status] || "h-warn";
  const barCls = { critical:"h-conf-crit", warning:"h-conf-warn", healthy:"h-conf-ok" }[status] || "h-conf-warn";
  const resLbl = { critical:"🔴 Critical", warning:"⚠️ Warning", healthy:"✅ Healthy" }[status] || "❓ Unknown";
  const pct    = Math.round((r.confidence || 0) * 100);
  const time   = r.created_at ? new Date(r.created_at).toLocaleString() : "";
  const detail = r.issue_type ? " · " + (ISSUE_LABELS[r.issue_type] || r.issue_type) : "";
  const imgSrc = r.id ? API_IMAGE(r.id) : "";
  return `<div class="history-item" data-id="${r.id || ""}" onclick="openModal(${r.id})">
    <div class="h-status-dot ${dotCls}"></div>
    ${imgSrc ? `<img class="h-thumb" src="${esc(imgSrc)}" alt="" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'h-thumb',style:'background:var(--bg);display:flex;align-items:center;justify-content:center;color:var(--dim);font-size:.6rem',textContent:'No img'}))" />` : ""}
    <div class="h-info">
      <div class="h-top">
        <span class="h-name" title="${esc(r.filename)}">${esc(r.filename)}</span>
        ${r.field_zone ? `<span class="h-zone">${esc(r.field_zone)}</span>` : ""}
      </div>
      <div class="h-res ${resCls}">${resLbl} · ${pct}%${detail}</div>
      <div class="h-conf-bar ${barCls}" style="width:${pct}%"></div>
      <div class="h-time">${time}</div>
    </div>
    ${r.id ? `<button class="btn-delete" title="Delete scan" onclick="event.stopPropagation();deleteScan(${r.id},this)">🗑</button>` : ""}
  </div>`;
}

function renderHistory(rows = [], append = false) {
  if (!append) {
    historyList.innerHTML      = rows.length ? rows.map(_historyItemHTML).join("") : "";
    historyList.style.display  = rows.length ? "flex" : "none";
    if (!rows.length) {
      historyEmpty.style.display = "block";
      if (!_currentUser) {
        historyEmpty.innerHTML = `<p>🔒 <a href="${API_AUTH_LOGIN}" style="color:var(--blue)">Sign in with Google</a> to see your scan history.</p>`;
      }
    } else {
      historyEmpty.style.display = "none";
    }
    const count = historyList.querySelectorAll(".history-item").length;
    if (historyCount) historyCount.textContent = count ? `(${count}${rows.length >= HISTORY_PAGE ? "+" : ""})` : "";
  } else {
    if (rows.length) rows.forEach(r => historyList.insertAdjacentHTML("beforeend", _historyItemHTML(r)));
    const count = historyList.querySelectorAll(".history-item").length;
    if (historyCount) historyCount.textContent = `(${count}${rows.length >= HISTORY_PAGE ? "+" : ""})`;
  }
  loadMoreBtn.style.display = rows.length >= HISTORY_PAGE ? "block" : "none";
}

async function deleteScan(id, btn) {
  if (!confirm("Delete this scan permanently?")) return;
  btn.disabled = true;
  try {
    const r = await apiFetch(API_DELETE(id), { method:"DELETE" });
    if (r.ok || r.status === 204) {
      btn.closest(".history-item").remove();
      loadStats(); loadTrend(); loadZones();
      if (!historyList.children.length) {
        historyList.style.display  = "none";
        historyEmpty.style.display = "block";
      }
      showToast("Scan deleted");
    } else {
      showToast("Delete failed — please try again", true);
      btn.disabled = false;
    }
  } catch {
    showToast("Delete failed — network error", true);
    btn.disabled = false;
  }
}

// ── Detail Modal ──────────────────────────────────────────────────────────────
async function openModal(id) {
  if (!id) return;
  const modal = document.getElementById("detailModal");
  const body  = document.getElementById("modalBody");
  modal.style.display = "flex";
  body.innerHTML = `<div style="text-align:center;padding:40px;color:var(--grey)">Loading…</div>`;

  try {
    const resp = await apiFetch(`${API_HISTORY}/${id}`);
    if (!resp.ok) { body.innerHTML = `<p style="color:var(--red);padding:20px">Record not found.</p>`; return; }
    const r = await resp.json();

    const status   = r.status || "unknown";
    const pct      = Math.round((r.confidence || 0) * 100);
    const imgSrc   = API_IMAGE(id);
    const time     = r.created_at ? new Date(r.created_at).toLocaleString() : "—";
    const bannerCls= { critical:"status-critical", warning:"status-warning", healthy:"status-healthy" }[status] || "";

    body.innerHTML = `
      <img class="modal-img" src="${esc(imgSrc)}" alt="Field scan" onerror="this.outerHTML='<div class=\\'modal-img-ph\\'>📷 Image unavailable</div>'" />
      <div class="status-banner ${bannerCls}" style="margin-bottom:16px">
        <div class="status-left">
          <span class="status-icon">${status==="critical"?"🔴":status==="warning"?"⚠️":"✅"}</span>
          <span class="status-label lbl-${status}">${capitalize(status)}</span>
        </div>
        <span class="urgency-pill urg-${r.urgency||"none"}">${{immediate:"🚨 Act Immediately",soon:"📅 Act Within Days",monitor:"👁 Monitor",none:"✓ No Action Needed"}[r.urgency]||"✓ No Action"}</span>
      </div>
      <div class="modal-row">
        <div class="modal-field"><div class="modal-field-label">File</div><div class="modal-field-value" style="word-break:break-all">${esc(r.filename)}</div></div>
        <div class="modal-field"><div class="modal-field-label">Scanned</div><div class="modal-field-value">${time}</div></div>
        <div class="modal-field"><div class="modal-field-label">Confidence</div><div class="modal-field-value">${pct}%</div></div>
        <div class="modal-field"><div class="modal-field-label">Area Affected</div><div class="modal-field-value">${r.affected_area_pct||0}%</div></div>
        <div class="modal-field"><div class="modal-field-label">Water Waste</div><div class="modal-field-value">${capitalize(r.water_waste_risk||"none")}</div></div>
        <div class="modal-field"><div class="modal-field-label">Field Zone</div><div class="modal-field-value">${r.field_zone ? esc(r.field_zone) : "—"}</div></div>
        <div class="modal-field"><div class="modal-field-label">Issue Type</div><div class="modal-field-value">${r.issue_type ? (ISSUE_LABELS[r.issue_type]||r.issue_type) : "—"}</div></div>
        <div class="modal-field"><div class="modal-field-label">AI Engine</div><div class="modal-field-value">${formatEngine(r.model_type||"")}</div></div>
      </div>
      ${r.message ? `<div class="msg-box"><span>🤖</span><span>${esc(r.message)}</span></div>` : ""}
      ${r.recommendation ? `<div class="rec-box rec-${status}"><span>🔧</span><span>${esc(r.recommendation)}</span></div>` : ""}
      ${r.crop_impact ? `<div class="impact-box impact-warning"><span>🌿</span><span>${esc(r.crop_impact)}</span></div>` : ""}
    `;
  } catch {
    body.innerHTML = `<p style="color:var(--red);padding:20px">Failed to load scan details.</p>`;
  }
}

function closeModal() {
  document.getElementById("detailModal").style.display = "none";
}

// ── Batch analysis ────────────────────────────────────────────────────────────
function batchDrop(e) {
  e.preventDefault();
  document.getElementById("batchDropZone").classList.remove("drag-over");
  const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith("image/"));
  if (files.length) addToBatch(files);
}

function addToBatch(newFiles) {
  if (_batchRunning) { showToast("Batch is running — wait for it to finish before adding files", true); return; }
  // Append to existing queue (de-duplicate by name+size)
  const existing = new Set(_batchFiles.map(f => f.name + f.size));
  const unique   = newFiles.filter(f => !existing.has(f.name + f.size));
  _batchFiles    = _batchFiles.concat(unique);
  renderBatchList();
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

/**
 * Compress an image file to stay under maxBytes using Canvas.
 * Needed for Vercel's 4.5 MB serverless request body limit.
 * Returns the original file unchanged if it's already small enough.
 */
async function compressIfNeeded(file, maxBytes = 4 * 1024 * 1024) {
  if (file.size <= maxBytes) return file;
  return new Promise(resolve => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      // Scale dimensions proportionally to hit the target size
      const scale  = Math.sqrt(maxBytes / file.size) * 0.88;
      const canvas = document.createElement("canvas");
      canvas.width  = Math.max(1, Math.round(img.naturalWidth  * scale));
      canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
      canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(
        blob => resolve(blob ? new File([blob], file.name, { type: "image/jpeg" }) : file),
        "image/jpeg", 0.85
      );
    };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(file); };
    img.src = url;
  });
}

function removeBatchItem(index) {
  if (_batchRunning) return;
  _batchFiles.splice(index, 1);
  if (!_batchFiles.length) { clearBatch(); return; }
  renderBatchList();
}

function renderBatchList() {
  batchPanel.style.display = "block";
  batchList.innerHTML = _batchFiles.map((f, i) =>
    `<div class="batch-item" id="bi-${i}">
      <span class="b-status b-pending">Pending</span>
      <span class="b-name" title="${esc(f.name)}">${esc(f.name)}</span>
      <span class="b-size">${formatBytes(f.size)}</span>
      <button class="b-remove" onclick="removeBatchItem(${i})" title="Remove">✕</button>
    </div>`
  ).join("");
  batchProgress.textContent = `0 / ${_batchFiles.length}`;
  if (batchBarTrack) { batchBarTrack.style.display = "none"; batchBarFill.style.width = "0%"; }
  batchRunBtn.disabled = false;
  batchPanel.scrollIntoView({ behavior:"smooth", block:"start" });
}

function setupBatch(files) {
  _batchFiles = [];
  addToBatch(Array.from(files));
}

async function runBatch() {
  if (_batchRunning || !_batchFiles.length) return;
  _batchRunning    = true;
  batchRunBtn.disabled = true;
  const zone = fieldZoneInput?.value.trim();
  let done = 0;
  const total = _batchFiles.length;

  if (batchBarTrack) { batchBarTrack.style.display = "block"; batchBarFill.style.width = "0%"; }

  try {
    for (let i = 0; i < total; i++) {
      const item  = document.getElementById(`bi-${i}`);
      const badge = item?.querySelector(".b-status");
      if (badge) { badge.className = "b-status b-running"; badge.textContent = "Running…"; }

      try {
        const fd         = new FormData();
        const compressed = await compressIfNeeded(_batchFiles[i]);
        fd.append("file", compressed, compressed.name || _batchFiles[i].name);
        if (zone) fd.append("field_zone", zone);
        const res  = await apiFetch(API_ANALYZE, { method:"POST", body:fd });
        if (!res.ok) throw new Error(`Server error ${res.status}`);
        const data = await res.json();
        const s    = data.status || "unknown";
        if (badge) {
          badge.className   = `b-status b-done-${s === "critical" ? "crit" : s === "warning" ? "warn" : "ok"}`;
          badge.textContent = s === "critical" ? "🔴 Critical" : s === "warning" ? "⚠️ Warning" : "✅ Healthy";
        }
        _maybeSendNotification(data);
      } catch {
        if (badge) { badge.className = "b-status b-error"; badge.textContent = "Error"; }
      }
      done++;
      batchProgress.textContent = `${done} / ${total}`;
      if (batchBarFill) batchBarFill.style.width = Math.round((done / total) * 100) + "%";
    }
  } finally {
    _batchRunning = false;
    batchRunBtn.disabled = false;
  }
  showToast(`Batch complete — ${done} images analyzed`);
  loadStats(); loadZones(); loadHistory(); loadTrend();
}

function clearBatch() {
  _batchFiles = [];
  batchPanel.style.display = "none";
}

// ── Push notifications ────────────────────────────────────────────────────────
async function toggleNotifications() {
  if (_notificationsOn) {
    _notificationsOn = false;
    localStorage.setItem("aq_notif", "off");
    notifBtn.classList.remove("active");
    notifBtn.textContent = "🔔 Alerts";
    showToast("Alerts disabled");
    return;
  }
  if (!("Notification" in window)) { showToast("Notifications not supported in this browser", true); return; }
  const perm = await Notification.requestPermission();
  if (perm === "granted") {
    _notificationsOn = true;
    localStorage.setItem("aq_notif", "on");
    notifBtn.classList.add("active");
    notifBtn.textContent = "🔔 Alerts ON";
    showToast("Alerts enabled — you'll be notified of critical detections");
    new Notification("AquaSense AI", { body:"Critical issue alerts are now active.", icon:"/icon-192.png" });
  } else {
    showToast("Permission denied — enable notifications in browser settings", true);
  }
}

function _maybeSendNotification(data) {
  if (!_notificationsOn || !("Notification" in window) || Notification.permission !== "granted") return;
  if (data.status !== "critical") return;
  const issue = ISSUE_LABELS[data.issue_type] || data.issue_type || "critical issue";
  const zone  = data.field_zone ? ` [${data.field_zone}]` : "";
  new Notification(`🔴 AquaSense Alert${zone}`, {
    body: `${issue} detected — ${data.recommendation || "Inspect immediately."}`,
    icon: "/icon-192.png",
    tag:  "aquasense-critical",
  });
}

// ── Health check ──────────────────────────────────────────────────────────────
function _fetchWithTimeout(url, options = {}, ms = 5000) {
  const ctrl  = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  return fetch(url, { credentials:"include", ...options, signal:ctrl.signal }).finally(() => clearTimeout(timer));
}

/** Wrapper that always sends the session cookie. */
function apiFetch(url, options = {}) {
  return fetch(url, { credentials:"include", ...options });
}

async function checkHealth() {
  try {
    const data   = await _fetchWithTimeout(API_HEALTH, {}, 5000).then(r => r.json());
    const labels = { openrouter:"🤖 Gemini 2.0 Flash", onnx:"⚙️ ONNX Model", heuristic:"⚡ Heuristic" };
    let label    = labels[data.active_engine] || data.message;
    if (data.db_connected) label += " · DB ✓";
    engineBadge.textContent = label;
    engineBadge.className   = "engine-badge " + (data.model_ready ? "ready" : "heuristic");
  } catch {
    engineBadge.textContent = "⚠️ API Offline";
    engineBadge.style.cssText = "border-color:var(--red);color:var(--red)";
  }
}

// ── Public scan counter ───────────────────────────────────────────────────────
async function loadPublicStats() {
  try {
    const d = await fetch(API_PUBLIC_STATS).then(r => r.ok ? r.json() : null);
    if (!d || !d.total_analyses) return;
    scanCounter.style.display = "flex";
    _animateCount(scTotal,    d.total_analyses  || 0);
    _animateCount(scCritical, d.critical        || 0);
    _animateCount(scHealthy,  d.healthy         || 0);
    _animateCount(scZones,    d.zones_monitored || 0);
  } catch {}
}

// ── Google Auth ───────────────────────────────────────────────────────────────
let _currentUser = null;

async function checkAuth() {
  try {
    const r = await fetch(API_AUTH_ME, { credentials:"include" });
    if (r.ok) {
      _currentUser = await r.json();
      _renderAuthArea(true);
    } else {
      _currentUser = null;
      _renderAuthArea(false);
    }
  } catch {
    _currentUser = null;
    _renderAuthArea(false);
  }
  // Reload data now that we know auth state
  loadHistory();
  loadStats();
  loadZones();
  loadTrend();
}

function _renderAuthArea(loggedIn) {
  if (!authArea) return;
  if (loggedIn && _currentUser) {
    const pic  = _currentUser.picture ? `<img class="user-avatar" src="${esc(_currentUser.picture)}" alt="" />` : "👤";
    const name = _currentUser.name ? esc(_currentUser.name.split(" ")[0]) : esc(_currentUser.email);
    authArea.innerHTML = `
      <span class="user-menu">
        ${pic}
        <span style="color:var(--white)">${name}</span>
        <a href="${API_AUTH_LOGOUT}" class="btn-signout">Sign out</a>
      </span>`;
  } else {
    authArea.innerHTML = `
      <a href="${API_AUTH_LOGIN}" class="btn-google">
        <svg width="14" height="14" viewBox="0 0 18 18" fill="none"><path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.703-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/><path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/><path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/><path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 6.29C4.672 4.163 6.656 3.58 9 3.58z" fill="#EA4335"/></svg>
        Sign in with Google
      </a>`;
  }
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, isError = false) {
  const t = document.createElement("div");
  t.className = "toast" + (isError ? " toast-error" : "");
  t.textContent = msg;
  document.body.appendChild(t);
  requestAnimationFrame(() => t.classList.add("toast-show"));
  setTimeout(() => { t.classList.remove("toast-show"); setTimeout(() => t.remove(), 300); }, 2800);
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function showError(msg) { errorMsgEl.textContent = msg; errorEl.style.display = "flex"; }
function capitalize(s)  { return s ? s[0].toUpperCase() + s.slice(1) : "—"; }
function formatEngine(mt) {
  return { openrouter_gemini:"Gemini 2.0 Flash", onnx_classification:"ONNX Model", heuristic:"Heuristic" }[mt] || mt;
}
function esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
