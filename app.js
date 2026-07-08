/* ============================================
   Smart Health – Dashboard Application Logic
   ============================================ */

const API = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost'
  ? 'http://127.0.0.1:8000/api'
  : `${window.location.origin}/api`;

let centresCache = [];
let riskCache = {};
let refreshTimer = null;
let map = null;
let markersGroup = null;
let routeGroup = null;

// ─── UTILITIES ────────────────────────────────
function $(id) { return document.getElementById(id); }

function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast toast--${type}`;
  el.textContent = msg;
  $('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

async function api(path, opts = {}) {
  try {
    const r = await fetch(`${API}${path}`, opts);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    console.error(`API ${path}:`, e);
    toast(`API error: ${e.message}`, 'error');
    return null;
  }
}

function scoreColor(score) {
  if (score >= 80) return 'green';
  if (score >= 50) return 'yellow';
  return 'red';
}

function urgencyClass(score) {
  if (score >= 7) return 'urgency-high';
  if (score >= 4) return 'urgency-med';
  return 'urgency-low';
}

function dayLabel(i) {
  const d = new Date();
  d.setDate(d.getDate() + i);
  return d.toLocaleDateString('en-US', { weekday: 'short' });
}

// ─── CLOCK ────────────────────────────────────
function updateClock() {
  const now = new Date();
  $('header-clock').textContent = now.toLocaleDateString('en-IN', {
    weekday: 'long', year: 'numeric', month: 'short', day: 'numeric'
  }) + '  •  ' + now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
setInterval(updateClock, 1000);
updateClock();

// ─── LEAFLET MAP ──────────────────────────────
function initMap() {
  if (map) return;
  // Center near Cuttack Sadar CHC, Odisha
  map = L.map('leaflet-map').setView([20.4625, 85.8792], 10);
  
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '© OpenStreetMap contributors'
  }).addTo(map);

  markersGroup = L.layerGroup().addTo(map);
  routeGroup = L.layerGroup().addTo(map);
}

function updateMapMarkers(centres) {
  if (!map) initMap();
  markersGroup.clearLayers();

  // Find the main hub: Cuttack Sadar CHC
  const mainHub = centres.find(c => c.name === "Cuttack Sadar CHC") || centres[0];

  centres.forEach(c => {
    const risk = riskCache[c.id] || {};
    const relScore = risk.data_reliability_score ?? 100;
    const adqScore = risk.resource_adequacy_score ?? 100;

    const isCHC = c.type === 'CHC';
    const markerColor = isCHC ? '#8b5cf6' : '#06b6d4'; // Purple for CHC, Cyan for PHC
    
    const icon = L.divIcon({
      className: 'custom-map-marker',
      html: `<div style="background-color:${markerColor}; width:16px; height:16px; border:2px solid #fff; border-radius:50%; box-shadow:0 0 10px rgba(0,0,0,0.5);"></div>`,
      iconSize: [16, 16],
      iconAnchor: [8, 8]
    });

    const marker = L.marker([c.lat, c.lng], { icon: icon });
    marker.bindPopup(`
      <div style="font-family:'Inter', sans-serif; font-size:0.8rem; color:#fff; min-width:140px;">
        <strong style="font-size:0.85rem;">${c.name}</strong><br/>
        <span style="color:var(--text-secondary)">Type: ${c.type} • Tier: ${c.tier_classification}</span>
        <hr style="border:none; border-top:1px solid var(--border-glass); margin:6px 0;" />
        <div style="display:flex; justify-content:space-between; margin-bottom:2px;"><span>Reliability:</span><strong style="color:var(--accent-${scoreColor(relScore)})">${relScore.toFixed(0)}</strong></div>
        <div style="display:flex; justify-content:space-between;"><span>Adequacy:</span><strong style="color:var(--accent-${scoreColor(adqScore)})">${adqScore.toFixed(0)}</strong></div>
        <a href="#" onclick="event.preventDefault(); DetailPanel.open(${c.id});" style="display:block; margin-top:8px; text-align:center; color:var(--accent-blue); text-decoration:none; font-weight:700;">Open Details</a>
      </div>
    `);
    markersGroup.addLayer(marker);

    // Draw static red network line to main hub if this is not the main hub itself
    if (mainHub && c.id !== mainHub.id) {
      L.polyline([[c.lat, c.lng], [mainHub.lat, mainHub.lng]], {
        color: '#ef4444',
        weight: 1.5,
        opacity: 0.45,
        dashArray: '3, 6'
      }).addTo(markersGroup);
    }
  });
}

function drawRoute(fromLat, fromLng, toLat, toLng, fromName, toName, drugName, qty, unit) {
  if (!map) return;
  routeGroup.clearLayers();

  const startPoint = [fromLat, fromLng];
  const endPoint = [toLat, toLng];

  // Draw dashed polyline
  const polyline = L.polyline([startPoint, endPoint], {
    color: '#8b5cf6',
    weight: 4,
    opacity: 0.95,
    className: 'map-route-line'
  }).addTo(routeGroup);

  // Add source/target highlight circles
  const startCircle = L.circleMarker(startPoint, {
    color: '#ef4444',
    radius: 7,
    fillColor: '#ef4444',
    fillOpacity: 1
  }).addTo(routeGroup);
  startCircle.bindPopup(`<strong>Source: ${fromName}</strong>`);

  const endCircle = L.circleMarker(endPoint, {
    color: '#10b981',
    radius: 7,
    fillColor: '#10b981',
    fillOpacity: 1
  }).addTo(routeGroup);
  endCircle.bindPopup(`
    <div style="font-family:'Inter'; font-size:0.78rem;">
      <strong>Destination: ${toName}</strong><br/>
      <span>Receiving: ${qty} ${unit} of ${drugName}</span>
    </div>
  `);

  const bounds = L.latLngBounds([startPoint, endPoint]);
  map.fitBounds(bounds, { padding: [40, 40] });
  endCircle.openPopup();
}

// ─── DATA LOADING ─────────────────────────────
async function loadAll() {
  const [centres, flags, transfers, bedsStatus, hospitals, activities] = await Promise.all([
    api('/centres'),
    api('/flags?resolved=false'),
    api('/transfers/recommend'),
    api('/beds/current'),
    api('/beds/hospitals'),
    api('/activities?limit=15')
  ]);

  if (centres) {
    centresCache = centres;
    const riskResults = await Promise.all(
      centres.map(c => api(`/centres/${c.id}/risk-state`))
    );
    riskCache = {};
    centres.forEach((c, i) => { if (riskResults[i]) riskCache[c.id] = riskResults[i]; });
    renderOverview(centres, flags, transfers);
    renderCentresGrid(centres);
    updateMapMarkers(centres);
  }

  if (flags) renderAlerts(flags);
  if (transfers) renderTransfers(transfers);
  if (bedsStatus) renderBedsTracker(bedsStatus);
  if (hospitals) renderReferralHospitals(hospitals);
  if (activities) renderActivities(activities);
}

function renderActivities(activities) {
  const feed = $('activity-feed');
  feed.innerHTML = '';

  if (!activities || !activities.length) {
    feed.innerHTML = '<div class="empty-state">No activities recorded yet.</div>';
    return;
  }

  activities.forEach(act => {
    const item = document.createElement('div');
    item.className = 'activity-item';
    
    let colorClass = 'blue';
    let icon = '✏️';
    if (act.action === 'approve_transfer') { colorClass = 'purple'; icon = '🚚'; }
    else if (act.action === 'refer_patient') { colorClass = 'green'; icon = '🏥'; }
    else if (act.action === 'submit_report') { colorClass = 'cyan'; icon = '💬'; }
    else if (act.action === 'scan_anomalies') { colorClass = 'red'; icon = '🔍'; }
    else if (act.action === 'analyze_adequacy') { colorClass = 'yellow'; icon = '⚙️'; }
    else if (act.action === 'resolve_flag') { colorClass = 'green'; icon = '✅'; }
    else if (act.action === 'retrain_models') { colorClass = 'purple'; icon = '🤖'; }

    const timeStr = new Date(act.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const details = act.details.details || act.details.message || JSON.stringify(act.details);

    item.innerHTML = `
      <div style="display: flex; align-items: start; gap: 8px; font-size: 0.78rem; padding: 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border-glass);">
        <span style="font-size: 1.1rem;">${icon}</span>
        <div style="flex: 1;">
          <div style="display: flex; justify-content: space-between; font-weight: 600; margin-bottom: 2px;">
            <span style="color: var(--accent-${colorClass});">${act.action.replace(/_/g, ' ').toUpperCase()}</span>
            <span style="font-size: 0.65rem; color: var(--text-secondary);">${timeStr}</span>
          </div>
          <div style="color: var(--text-secondary); font-size: 0.74rem;">${details}</div>
        </div>
      </div>
    `;
    feed.appendChild(item);
  });
}


function renderBedsTracker(beds) {
  const grid = $('beds-grid');
  grid.innerHTML = '';
  
  let totalOccupied = 0;
  let totalCapacity = 0;

  beds.forEach(b => {
    totalOccupied += b.occupied_beds;
    totalCapacity += b.total_beds;

    const available = b.total_beds - b.occupied_beds;
    const pct = (b.occupied_beds / b.total_beds) * 100;
    
    let barColor = 'green';
    let statusLabel = 'Available';
    let statusClass = 'bed-card__available--ok';

    if (pct >= 85) {
      barColor = 'red';
      statusLabel = 'Full';
      statusClass = 'bed-card__available--full';
    } else if (pct >= 60) {
      barColor = 'yellow';
      statusLabel = 'Low Beds';
      statusClass = 'bed-card__available--low';
    }

    const card = document.createElement('div');
    card.className = 'bed-card';
    card.innerHTML = `
      <div class="bed-card__name">${b.centre_name}</div>
      <div class="bed-card__stats">
        <div class="bed-card__count">${b.occupied_beds}<span>/${b.total_beds} beds</span></div>
        <div class="bed-card__available ${statusClass}">${statusLabel} (${available} empty)</div>
      </div>
      <div class="bed-card__bar-track">
        <div class="bed-card__bar-fill bed-card__bar-fill--${barColor}" style="width: ${pct}%"></div>
      </div>
    `;
    grid.appendChild(card);
  });

  $('beds-total-badge').textContent = `${totalOccupied} / ${totalCapacity} Beds Occupied`;
}

function renderReferralHospitals(hospitals) {
  const grid = $('hospital-grid');
  grid.innerHTML = '';

  hospitals.forEach(h => {
    const card = document.createElement('div');
    card.className = 'hospital-card';
    
    let bedRowsHtml = '';
    for (const [type, info] of Object.entries(h.beds)) {
      const available = info.total - info.occupied;
      const pct = info.total > 0 ? (info.occupied / info.total) * 100 : 0;
      
      bedRowsHtml += `
        <div class="hospital-bed-row">
          <div class="hospital-bed-info">
            <span class="hospital-bed-name">
              ${type === 'icu' ? '🚨 ICU Bed' : type === 'ventilator' ? '💨 Ventilator' : type === 'oxygen' ? '🧪 Oxygen Supported' : '🛏️ General Bed'}
            </span>
            <span class="hospital-bed-count">${available} <span>/ ${info.total} free</span></span>
          </div>
          <div class="bed-card__bar-track" style="margin-top: 2px;">
            <div class="bed-card__bar-fill bed-card__bar-fill--${pct >= 85 ? 'red' : pct >= 60 ? 'yellow' : 'green'}" style="width: ${pct}%"></div>
          </div>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="hospital-card__header">
        <div>
          <div class="hospital-card__title">${h.name}</div>
          <div class="hospital-card__type">${h.type}</div>
        </div>
      </div>
      <div class="hospital-card__meta">
        <span class="hospital-card__distance">🚙 ${h.distance} km away</span>
        <span>📞 ${h.contact}</span>
      </div>
      <div class="hospital-card__beds">
        ${bedRowsHtml}
      </div>
      <div class="hospital-card__action">
        <select class="hospital-select" id="refer-select-${h.id}">
          <option value="general">General Bed</option>
          <option value="icu">ICU Bed</option>
          <option value="oxygen">Oxygen Supported</option>
          <option value="ventilator">Ventilator Bed</option>
        </select>
        <button class="btn btn--sm btn--accent" onclick="Actions.referPatient(${h.id}, 'refer-select-${h.id}')">Refer Patient</button>
      </div>
    `;
    grid.appendChild(card);
  });
}


// ─── OVERVIEW CARDS ───────────────────────────
function renderOverview(centres, flags, transfers) {
  $('ov-centres-val').textContent = centres.length;
  $('ov-centres-val').classList.remove('skeleton-text');

  const reliabilities = Object.values(riskCache).map(r => r.data_reliability_score || 0);
  const adequacies = Object.values(riskCache).map(r => r.resource_adequacy_score || 0);

  const avgRel = reliabilities.length ? (reliabilities.reduce((a, b) => a + b, 0) / reliabilities.length) : 0;
  const avgAdq = adequacies.length ? (adequacies.reduce((a, b) => a + b, 0) / adequacies.length) : 0;

  $('ov-reliability-val').textContent = avgRel.toFixed(1);
  $('ov-reliability-val').classList.remove('skeleton-text');
  $('ov-reliability-val').style.color = `var(--accent-${scoreColor(avgRel)})`;

  $('ov-adequacy-val').textContent = avgAdq.toFixed(1);
  $('ov-adequacy-val').classList.remove('skeleton-text');
  $('ov-adequacy-val').style.color = `var(--accent-${scoreColor(avgAdq)})`;

  const alertCount = flags ? flags.length : 0;
  $('ov-alerts-val').textContent = alertCount;
  $('ov-alerts-val').classList.remove('skeleton-text');
  if (alertCount > 0) $('ov-alerts-val').style.color = 'var(--accent-red)';

  const transferCount = transfers ? transfers.filter(t => t.status === 'recommended').length : 0;
  $('ov-transfers-val').textContent = transferCount;
  $('ov-transfers-val').classList.remove('skeleton-text');
}

// ─── CENTRES GRID ─────────────────────────────
function renderCentresGrid(centres) {
  const grid = $('centres-grid');
  grid.innerHTML = '';
  $('centre-count-badge').textContent = `${centres.length} centres`;

  centres.forEach(c => {
    const risk = riskCache[c.id] || {};
    const relScore = risk.data_reliability_score ?? 0;
    const adqScore = risk.resource_adequacy_score ?? 0;

    const card = document.createElement('div');
    card.className = 'centre-card';
    card.onclick = () => DetailPanel.open(c.id);
    card.innerHTML = `
      <div class="centre-card__info">
        <span class="centre-card__name">${c.name}</span>
        <div class="centre-card__meta">
          <span class="badge badge--${c.type === 'PHC' ? 'phc' : 'chc'}">${c.type}</span>
          <span>${c.tier_classification}</span>
          <span>Pop: ${(c.population_served || 0).toLocaleString()}</span>
        </div>
      </div>
      <div class="score-bar">
        <div class="score-bar__label"><span>Reliability</span><span>${relScore.toFixed(0)}</span></div>
        <div class="score-bar__track"><div class="score-bar__fill score-bar__fill--${scoreColor(relScore)}" style="width:${relScore}%"></div></div>
      </div>
      <div class="score-bar">
        <div class="score-bar__label"><span>Adequacy</span><span>${adqScore.toFixed(0)}</span></div>
        <div class="score-bar__track"><div class="score-bar__fill score-bar__fill--${scoreColor(adqScore)}" style="width:${adqScore}%"></div></div>
      </div>
    `;
    grid.appendChild(card);
  });
}

// ─── ALERTS FEED ──────────────────────────────
function renderAlerts(flags) {
  const feed = $('alerts-feed');
  feed.innerHTML = '';
  $('alert-count-badge').textContent = flags.length;

  if (!flags.length) {
    feed.innerHTML = '<div class="empty-state">✅ No active alerts — all centres reporting normally.</div>';
    return;
  }

  flags.forEach(f => {
    const centre = centresCache.find(c => c.id === f.centre_id);
    const item = document.createElement('div');
    item.className = 'alert-item';
    item.innerHTML = `
      <div class="alert-item__header">
        <span class="alert-item__metric">${f.triggering_metric.replace(/_/g, ' ')}</span>
        <span class="badge badge--${f.flag_type === 'reliability' ? 'danger' : 'warning'}">${f.flag_type}</span>
      </div>
      <div class="alert-item__details">
        <span>${centre ? centre.name : `Centre #${f.centre_id}`}</span> — 
        Value: <span>${f.value}</span> (threshold: ${f.threshold})
      </div>
      <button class="btn btn--sm btn--green" style="margin-top:8px" onclick="Actions.resolveFlag(${f.id}, this)">Resolve</button>
    `;
    feed.appendChild(item);
  });
}

// ─── TRANSFERS TABLE ──────────────────────────
function renderTransfers(transfers) {
  const tbody = $('transfers-tbody');
  tbody.innerHTML = '';
  const pending = transfers.filter(t => t.status === 'recommended');
  $('transfer-count-badge').textContent = pending.length;

  if (!pending.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No pending transfer recommendations.</td></tr>';
    return;
  }

  pending.forEach(t => {
    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';
    
    // Calculate transportation details
    const distance = t.distance || 0;
    const time = Math.round(distance * 2); // approx 2 mins per km
    const mode = distance < 10 ? 'Emergency Courier' : 'Medical Van';
    const cost = Math.round(distance * 15); // ₹15 per km

    tr.onclick = () => {
      // Draw route on the map
      drawRoute(t.from_lat, t.from_lng, t.to_lat, t.to_lng, t.from_centre_name, t.to_centre_name, t.drug_name, t.quantity, t.drug_unit);
      toast(`Showing route: ${t.from_centre_name} ➔ ${t.to_centre_name}`, 'info');
    };

    tr.innerHTML = `
      <td>
        <strong style="color:var(--text-primary)">${t.from_centre_name || '—'}</strong>
        <div style="font-size:0.68rem; color:var(--text-secondary); margin-top:2px;">📤 Main Dispensing Wing</div>
      </td>
      <td>
        <strong style="color:var(--accent-green)">${t.to_centre_name || '—'}</strong>
        <div style="font-size:0.68rem; color:var(--text-secondary); margin-top:2px;">📥 Deliver to: Pharmacy Cold-Chain</div>
      </td>
      <td>${t.drug_name || '—'}</td>
      <td><strong>${t.quantity} ${t.drug_unit || ''}</strong></td>
      <td><span class="${urgencyClass(t.urgency_score)} urgency-bar">${t.urgency_score.toFixed(1)}</span></td>
      <td>
        <div style="font-size:0.75rem; font-weight:600;">🚙 ${mode}</div>
        <div style="font-size:0.68rem; color:var(--text-secondary); margin-top:2px;">
          ${distance.toFixed(1)} km • ~${time} mins • ₹${cost}
        </div>
      </td>
      <td style="max-width:240px;font-size:0.74rem;color:var(--text-secondary)">${t.reasoning || ''}</td>
      <td><button class="btn btn--sm btn--accent" onclick="event.stopPropagation(); Actions.approveTransfer(${t.id}, this)">Approve</button></td>
    `;
    tbody.appendChild(tr);
  });
}

// ─── DETAIL PANEL ─────────────────────────────
const DetailPanel = {
  open: async function(centreId) {
    const overlay = $('detail-overlay');
    const body = $('detail-body');
    body.innerHTML = '<div class="skeleton-card" style="height:200px"></div>';
    overlay.classList.add('active');

    const risk = riskCache[centreId] || await api(`/centres/${centreId}/risk-state`);
    if (!risk) { body.innerHTML = '<p>Failed to load centre data.</p>'; return; }

    const centre = centresCache.find(c => c.id === centreId) || {};
    const relScore = risk.data_reliability_score || 0;
    const adqScore = risk.resource_adequacy_score || 0;
    const forecasts = risk.stock_forecasts || [];
    const footfall = risk.predicted_footfall_next_7_days || [];
    const beds = risk.predicted_bed_demand_next_7_days || [];

    body.innerHTML = `
      <div class="detail-header">
        <div>
          <div class="detail-header__name">${risk.centre_name || centre.name}</div>
          <div class="detail-header__meta">
            <span class="badge badge--${(risk.centre_type || centre.type) === 'PHC' ? 'phc' : 'chc'}">${risk.centre_type || centre.type}</span>
            &nbsp;•&nbsp; ${centre.tier_classification || ''} &nbsp;•&nbsp; Pop: ${(centre.population_served || 0).toLocaleString()}
          </div>
        </div>
      </div>

      <div class="gauges">
        <div class="gauge-card">
          ${renderGauge(relScore, 'Data Reliability', scoreColor(relScore))}
          <ul class="gauge-card__reasons">${(risk.reliability_reasons || []).map(r => `<li>${r}</li>`).join('')}</ul>
        </div>
        <div class="gauge-card">
          ${renderGauge(adqScore, 'Resource Adequacy', scoreColor(adqScore))}
          <ul class="gauge-card__reasons">${(risk.adequacy_reasons || []).map(r => `<li>${r}</li>`).join('')}</ul>
        </div>
      </div>

      <div class="mini-charts">
        <div class="mini-chart">
          <div class="mini-chart__title">📊 7-Day Footfall Forecast</div>
          <div class="mini-chart__bars" id="detail-footfall-bars"></div>
        </div>
        <div class="mini-chart">
          <div class="mini-chart__title">🛏️ 7-Day Bed Demand Forecast</div>
          <div class="mini-chart__bars" id="detail-bed-bars"></div>
        </div>
      </div>

      ${forecasts.length ? `
      <div>
        <div class="detail-section__title">💊 Stock Forecasts</div>
        <div class="table-wrap">
          <table class="table">
            <thead><tr><th>Drug</th><th>Stock</th><th>Days to Stockout</th><th>Range</th><th>Reasoning</th></tr></thead>
            <tbody>
              ${forecasts.map(f => `
                <tr>
                  <td><strong>${f.drug_name}</strong></td>
                  <td>${f.current_stock} ${f.unit || ''}</td>
                  <td><span class="${urgencyClass(10 - Math.min(f.expected_days, 10))} urgency-bar">${f.expected_days}d</span></td>
                  <td style="font-size:0.74rem">${f.lower_days}d – ${f.upper_days}d</td>
                  <td style="max-width:240px;font-size:0.72rem;color:var(--text-secondary)">${f.reasoning}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>` : ''}
    `;

    // Render bar charts
    setTimeout(() => {
      renderBarChart('detail-footfall-bars', footfall, 'footfall');
      renderBarChart('detail-bed-bars', beds, 'bed');
    }, 50);
  },

  close: function() {
    $('detail-overlay').classList.remove('active');
  }
};

function renderGauge(value, label, color) {
  const circumference = 2 * Math.PI * 46;
  const offset = circumference - (value / 100) * circumference;
  const colorMap = { green: '#10b981', yellow: '#f59e0b', red: '#ef4444' };
  return `
    <div class="gauge-ring">
      <svg viewBox="0 0 100 100">
        <circle class="track" cx="50" cy="50" r="46" />
        <circle class="fill" cx="50" cy="50" r="46" stroke="${colorMap[color]}"
          stroke-dasharray="${circumference}" stroke-dashoffset="${offset}" />
      </svg>
      <div class="gauge-ring__value" style="color:${colorMap[color]}">${value.toFixed(0)}</div>
    </div>
    <div class="gauge-card__label">${label}</div>
  `;
}

function renderBarChart(containerId, values, type) {
  const container = document.getElementById(containerId);
  if (!container || !values.length) return;
  container.innerHTML = '';
  const maxVal = Math.max(...values, 1);

  values.forEach((v, i) => {
    const pct = (v / maxVal) * 100;
    const bar = document.createElement('div');
    bar.className = `mini-chart__bar mini-chart__bar--${type}`;
    bar.style.height = '0%';
    bar.innerHTML = `<span class="mini-chart__bar-value">${Math.round(v)}</span><span class="mini-chart__bar-label">${dayLabel(i)}</span>`;
    container.appendChild(bar);
    setTimeout(() => { bar.style.height = `${Math.max(pct, 4)}%`; }, 80 + i * 60);
  });
}

// ─── ACTIONS ──────────────────────────────────
const Actions = {
  scanAnomalies: async function() {
    toast('Running anomaly scan…', 'info');
    const r = await api('/anomaly/analyze', { method: 'POST' });
    if (r) { toast('Anomaly scan complete!', 'success'); loadAll(); }
  },

  analyzeAdequacy: async function() {
    toast('Analyzing resource adequacy…', 'info');
    const r = await api('/flags/analyze', { method: 'POST' });
    if (r) { toast('Adequacy analysis complete!', 'success'); loadAll(); }
  },

  retrainModels: async function() {
    toast('Retraining ML models… this may take a moment.', 'info');
    const r = await api('/forecasting/retrain', { method: 'POST' });
    if (r) {
      const msg = r.footfall_model_cv_rmse
        ? `Models retrained! Footfall CV-RMSE: ${r.footfall_model_cv_rmse.toFixed(2)}`
        : 'Models retrained successfully!';
      toast(msg, 'success');
      loadAll();
    }
  },

  resolveFlag: async function(flagId, btn) {
    btn.disabled = true;
    const r = await api(`/flags/${flagId}/resolve`, { method: 'PATCH' });
    if (r) { toast('Flag resolved.', 'success'); loadAll(); }
  },

  approveTransfer: async function(transferId, btn) {
    btn.disabled = true;
    const r = await api(`/transfers/${transferId}?new_status=approved`, { method: 'PATCH' });
    if (r) { toast('Transfer approved!', 'success'); loadAll(); }
  },

  referPatient: async function(hospitalId, selectId) {
    const select = $(selectId);
    const bedType = select.value;
    toast(`Initiating patient referral…`, 'info');
    const r = await api(`/beds/hospitals/${hospitalId}/refer?bed_type=${bedType}`, { method: 'POST' });
    if (r && r.status === 'success') {
      toast(r.message, 'success');
      loadAll();
    } else {
      toast('Failed to refer patient or no beds available.', 'error');
    }
  }
};

// ─── INGESTION SIMULATOR ──────────────────────
const Simulator = {
  toggle: function() {
    $('simulator-panel').classList.toggle('active');
    if ($('simulator-panel').classList.contains('active')) {
      this.loadQueue();
    }
  },

  onTypeChange: function() {
    const selectedType = document.querySelector('input[name="sim-type"]:checked').value;
    if (selectedType === 'text') {
      $('sim-text-input-group').style.display = 'block';
      $('sim-voice-input-group').style.display = 'none';
    } else {
      $('sim-text-input-group').style.display = 'none';
      $('sim-voice-input-group').style.display = 'block';
      if (selectedType === 'voice-hindi-stock') {
        $('sim-voice-title').textContent = 'hindi_voice_stock.mp3';
        $('sim-voice-desc').textContent = 'Transcribes to: "पैरासिटामॉल ५००" (Hindi Stock Update)';
      } else if (selectedType === 'voice-hindi-footfall') {
        $('sim-voice-title').textContent = 'hindi_voice_footfall.mp3';
        $('sim-voice-desc').textContent = 'Transcribes to: "मरीज ३०" (Hindi Patient Footfall)';
      } else if (selectedType === 'voice-hindi-beds') {
        $('sim-voice-title').textContent = 'hindi_voice_beds.mp3';
        $('sim-voice-desc').textContent = 'Transcribes to: "बेड ७" (Hindi Occupied Beds)';
      } else if (selectedType === 'voice-hindi-attendance') {
        $('sim-voice-title').textContent = 'hindi_voice_attendance.mp3';
        $('sim-voice-desc').textContent = 'Transcribes to: "डॉक्टर उपस्थित" (Hindi Doctor Attendance)';
      }
    }
  },

  submit: async function() {
    const btn = $('sim-submit-btn');
    btn.disabled = true;
    const sender = $('sim-sender').value;
    const type = document.querySelector('input[name="sim-type"]:checked').value;
    
    let body = "";
    let mediaUrl = null;

    if (type === 'text') {
      body = $('sim-body').value;
    } else {
      body = "Voice report";
      if (type === 'voice-hindi-stock') {
        mediaUrl = "http://mock.com/hindi_voice_stock.mp3";
      } else if (type === 'voice-hindi-footfall') {
        mediaUrl = "http://mock.com/hindi_voice_footfall.mp3";
      } else if (type === 'voice-hindi-beds') {
        mediaUrl = "http://mock.com/hindi_voice_beds.mp3";
      } else if (type === 'voice-hindi-attendance') {
        mediaUrl = "http://mock.com/hindi_voice_attendance.mp3";
      }
    }

    toast('Sending simulated WhatsApp report...', 'info');

    // Twilio payload uses urlencoded Form Data
    const formData = new URLSearchParams();
    formData.append('From', sender);
    formData.append('Body', body);
    if (mediaUrl) {
      formData.append('MediaUrl0', mediaUrl);
    }

    const res = await api('/intake/whatsapp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData
    });

    btn.disabled = false;

    if (res) {
      $('sim-result').style.display = 'block';
      $('sim-result-data').textContent = JSON.stringify(res, null, 2);
      
      if (res.status === 'processed') {
        toast('Message processed successfully!', 'success');
      } else {
        toast(`Ingestion failed: ${res.error_message}`, 'error');
      }
      this.loadQueue();
      loadAll(); // Reload dashboard numbers
    }
  },

  loadQueue: async function() {
    const queue = await api('/intake/queue');
    const list = $('sim-queue-list');
    list.innerHTML = '';
    
    if (!queue || !queue.length) {
      list.innerHTML = '<div class="empty-state">No items in ingestion queue.</div>';
      return;
    }

    queue.forEach(item => {
      const el = document.createElement('div');
      el.className = 'sim-queue-item';
      const statusClass = `sim-queue-item__status--${item.status}`;
      
      const timeStr = new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const senderNum = item.sender.replace('whatsapp:', '');
      const bodyVal = item.media_url ? `🎙️ Voice Note (${item.media_url.split('/').pop()})` : `💬 ${item.message_body}`;

      el.innerHTML = `
        <div class="sim-queue-item__meta">
          <span>From: ${senderNum} (${timeStr})</span>
          <span class="sim-queue-item__status ${statusClass}">${item.status}</span>
        </div>
        <div class="sim-queue-item__body">${bodyVal}</div>
        ${item.error_message ? `<div style="font-size:0.64rem; color:var(--text-secondary); margin-top:2px;">${item.error_message}</div>` : ''}
        <div style="font-size:0.62rem; color:var(--text-secondary)">Retries: ${item.retry_count}</div>
      `;
      list.appendChild(el);
    });
  },

  triggerRetry: async function() {
    toast('Running background retry loop...', 'info');
    const res = await api('/intake/retry', { method: 'POST' });
    if (res) {
      toast(`Retry finished: ${res.successful} successful, ${res.retried} processed.`, 'success');
      this.loadQueue();
      loadAll();
    }
  }
};

// ─── INIT ─────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadAll();
  // Auto-refresh every 30 seconds
  refreshTimer = setInterval(loadAll, 30000);
});
