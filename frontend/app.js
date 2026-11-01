'use strict';
/* Sudhaar web client - citizen app, department console, super admin and the Sudhaar AI monitor.
   Vanilla JS, no build step. */
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = d => d ? new Date(d).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
const fmtT = d => d ? new Date(d).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '';
const ago = d => { if (!d) return ''; const s = Math.max(0, (Date.now() - new Date(d)) / 1000); return s < 60 ? 'just now' : s < 3600 ? Math.floor(s / 60) + ' min ago' : s < 86400 ? Math.floor(s / 3600) + ' h ago' : Math.floor(s / 86400) + ' d ago'; };
const S = { token: localStorage.getItem('sdh_token'), role: localStorage.getItem('sdh_role'), name: localStorage.getItem('sdh_name'), meta: null };
/* ---------- site configuration: the operator fills these in; empty values are simply not shown ---------- */
const SITE = {
  name: 'Sudhaar', city: 'Varanasi, Uttar Pradesh', emergency: '112',
  operator: '',      // e.g. 'Varanasi Municipal Corporation'
  email: '',         // grievance / support e-mail
  phone: '',         // helpline number
  hours: '',         // e.g. 'Mon-Sat, 10:00-17:00'
  retention: ''      // e.g. 'Complaint media is kept for 2 years after closure.'
};
const VARANASI = [25.3176, 82.9739];
let timers = [];

/* ---------- icons (24px stroke set) ---------- */
const P = {
  home: '<path d="M3 11l9-8 9 8M5 10v10h14V10M10 20v-6h4v6"/>', camera: '<path d="M4 8h3l2-3h6l2 3h3v12H4z"/><circle cx="12" cy="13" r="3.5"/>',
  bell: '<path d="M6 17v-6a6 6 0 0 1 12 0v6l2 2H4zM10 21h4"/>', help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17v.01"/>',
  logout: '<path d="M9 4H5v16h4M16 8l4 4-4 4M20 12H9"/>', back: '<path d="M15 5l-7 7 7 7"/>', next: '<path d="M9 5l7 7-7 7"/>', check: '<path d="M5 12l5 5 9-10"/>', x: '<path d="M6 6l12 12M18 6L6 18"/>',
  pin: '<path d="M12 21s7-6.2 7-11a7 7 0 0 0-14 0c0 4.8 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/>', video: '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="M16 10l5-3v10l-5-3"/>',
  alert: '<path d="M12 3l10 18H2zM12 10v5M12 18v.01"/>', shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>', cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
  activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>', list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>', building: '<path d="M4 21V4h10v17M14 9h6v12M8 8h2M8 12h2M8 16h2M3 21h18"/>',
  map: '<path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2zM9 4v14M15 6v14"/>', log: '<path d="M6 3h9l4 4v14H6zM14 3v5h5M9 13h6M9 17h6"/>', chat: '<path d="M4 5h16v11H9l-5 4z"/>', send: '<path d="M4 12l16-8-6 16-3-7z"/>',
  eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>', globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18"/>',
  cloud: '<path d="M7 18a4 4 0 0 1-.5-8A6 6 0 0 1 18 9a4.5 4.5 0 0 1 0 9z"/>', inbox: '<path d="M3 13l3-8h12l3 8v6H3zM3 13h5l1 3h6l1-3h5"/>', users: '<circle cx="9" cy="8" r="3.5"/><path d="M2 20a7 7 0 0 1 14 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a7 7 0 0 1 4 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', search: '<circle cx="11" cy="11" r="6"/><path d="M16 16l5 5"/>', gauge: '<path d="M4 18a9 9 0 1 1 16 0M12 13l4-5"/>', image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>', play: '<path d="M7 4l13 8-13 8z"/>', pause: '<path d="M8 5v14M16 5v14"/>', dash: '<rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/>',
  /* complaint categories */
  road: '<path d="M6 21L9 3M18 21L15 3M12 5v3M12 11v3M12 17v3"/>', manhole: '<circle cx="12" cy="12" r="9"/><path d="M7 9h10M6 12h12M7 15h10"/>', trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/>',
  bulb: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.8.8 1 1.5 1 2.5h6c0-1 .2-1.7 1-2.5A6 6 0 0 0 12 3z"/>', drop: '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/>',
  signal: '<rect x="8" y="2" width="8" height="20" rx="3"/><circle cx="12" cy="7" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="17" r="1.5"/>', tree: '<circle cx="12" cy="9" r="6"/><path d="M12 15v7M9 22h6"/>'
};
const ic = (n, size = 22) => `<svg class="i" viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[n] || P.pin}</svg>`;
const CAT_IC = { 'Roads and Infrastructure': 'road', 'Manholes and Drainage': 'manhole', 'Waste Management and Sanitation': 'trash', 'Streetlights and Electrical Safety': 'bulb', 'Water Supply': 'drop', 'Traffic and Public Safety': 'signal', 'Public Spaces': 'tree', 'Other Civic Issue': 'pin' };
const catIc = (c, s = 24) => ic(CAT_IC[c] || 'pin', s);
const MARK = `<svg class="mark" viewBox="0 0 64 64" aria-hidden="true"><defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2f66dc"/><stop offset="1" stop-color="#0e2a68"/></linearGradient><linearGradient id="ls" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffc47a"/><stop offset="1" stop-color="#ff8c1a"/></linearGradient></defs><rect width="64" height="64" rx="18" fill="url(#lg)"/><rect x="2" y="2" width="60" height="60" rx="16" fill="none" stroke="#fff" stroke-opacity=".22" stroke-width="2"/><circle cx="32" cy="29" r="11.5" fill="url(#ls)"/><g fill="#fff"><rect x="23" y="34" width="18" height="5" rx="1.6"/><rect x="17" y="39" width="30" height="5" rx="1.6" opacity=".88"/><rect x="11" y="44" width="42" height="5" rx="1.6" opacity=".72"/></g><path d="M9 55c4-3.4 8-3.4 11.5 0s8 3.4 11.5 0 8-3.4 11.5 0 8 3.4 11.5 0" fill="none" stroke="#3ccb2c" stroke-width="3" stroke-linecap="round"/></svg>`;

function toast(m) { const t = $('#toast'); t.textContent = m; t.classList.add('on'); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('on'), 3500); }
function setSession(r) { S.token = r.token; S.role = r.role; S.name = r.name || ''; localStorage.setItem('sdh_token', r.token); localStorage.setItem('sdh_role', r.role); localStorage.setItem('sdh_name', S.name); }
function logout(expired) { S.token = S.role = null; ['sdh_token', 'sdh_role', 'sdh_name'].forEach(k => localStorage.removeItem(k)); if (expired) toast('Session expired. Log in again.'); location.hash = '#/'; route(); }

async function api(path, { method = 'GET', json, form } = {}) {
  const h = {}; if (S.token) h.Authorization = 'Bearer ' + S.token;
  let body; if (json) { h['Content-Type'] = 'application/json'; body = JSON.stringify(json); } else if (form) body = form;
  const r = await fetch(path, { method, headers: h, body });
  if (r.status === 401 && S.token) { logout(true); throw new Error('Session expired'); }
  const t = await r.text(); let d; try { d = JSON.parse(t); } catch { d = t; }
  if (!r.ok) throw new Error(d && d.detail ? (Array.isArray(d.detail) ? d.detail.map(x => x.msg).join('; ') : d.detail) : 'Request failed (' + r.status + ')');
  return d;
}
const blobCache = {};
async function mediaURL(id) {   // media is private: fetched with the bearer token, never a public URL
  if (blobCache[id]) return blobCache[id];
  const r = await fetch('/api/media/' + id, { headers: { Authorization: 'Bearer ' + S.token } });
  if (!r.ok) throw new Error('Media unavailable');
  return blobCache[id] = URL.createObjectURL(await r.blob());
}
async function fillMedia(root) {
  for (const el of root.querySelectorAll('[data-mid]')) {
    try { el.src = await mediaURL(el.dataset.mid); } catch { el.replaceWith(Object.assign(document.createElement('div'), { className: 'mute sm', textContent: 'Media unavailable' })); }
  }
}
const CLOSED = ['Resolved', 'Rejected'];
const chipSev = s => s ? `<span class="chip sev-${esc(s)}">${esc(s)}</span>` : `<span class="chip">Analysing</span>`;
const chipSt = s => `<span class="chip ${CLOSED.includes(s) || s === 'Reopened' ? 'st-' + esc(s) : 'st-open'}">${esc(s)}</span>`;
const empty = (icon, msg, sub = '') => `<div class="empty">${ic(icon, 40)}<div><b>${esc(msg)}</b></div>${sub ? `<div class="sm">${esc(sub)}</div>` : ''}</div>`;
const LIFECYCLE = ['Complaint Registered', 'Forwarded to Department', 'Complaint Acknowledged', 'Under Review', 'Field Officer Assigned', 'Work In Progress', 'Resolved'];

/* ---------- IndexedDB drafts (offline / interrupted upload queue) ---------- */
const idb = {
  db: null,
  open() { return this.db ? Promise.resolve(this.db) : new Promise((res, rej) => { const q = indexedDB.open('sudhaar', 1); q.onupgradeneeded = () => q.result.createObjectStore('drafts', { keyPath: 'id' }); q.onsuccess = () => res(this.db = q.result); q.onerror = () => rej(q.error); }); },
  async tx(mode, fn) { const db = await this.open(); return new Promise((res, rej) => { const t = db.transaction('drafts', mode); const r = fn(t.objectStore('drafts')); t.oncomplete = () => res(r.result); t.onerror = () => rej(t.error); }); },
  put(d) { return this.tx('readwrite', s => s.put(d)); }, all() { return this.tx('readonly', s => s.getAll()); }, del(id) { return this.tx('readwrite', s => s.delete(id)); }
};

/* ---------- chrome: header, side nav, bottom tabs ---------- */
const NAV = {
  officer: [['#/dept', 'Complaints', 'list']],
  super_admin: [['#/admin/overview', 'Overview', 'dash'], ['#/admin/complaints', 'Complaints', 'list'], ['#/admin/departments', 'Departments', 'building'], ['#/admin/routing', 'Routing', 'map'], ['#/admin/audit', 'Audit log', 'shield'], ['-', 'Sudhaar AI'], ['#/ai', 'AI live feed', 'cpu'], ['#/ai/runs', 'AI complaint runs', 'activity']],
  ai_monitor: [['#/ai', 'Live feed', 'cpu'], ['#/ai/runs', 'Complaint runs', 'activity'], ['#/ai/chat', 'Chatbot answers', 'chat']],
};
let unread = 0;
async function renderHeader() {
  const staff = S.token && S.role !== 'citizen';
  document.body.classList.toggle('staff', !!staff);
  const roleLabel = { officer: 'Department officer', super_admin: 'Super Admin', ai_monitor: 'AI monitor' }[S.role] || '';
  const helpBtn = `<button class="hbtn" id="chat-fab" aria-label="Open help chat" title="Help" style="padding:0 8px 0 6px"><img class="botico" src="/static/chatbot.svg" alt="" width="30" height="30"><span class="lbl">Help</span></button>`;
  const right = !S.token ? `${helpBtn}<a class="hbtn" href="#/staff">${ic('shield', 18)}<span class="lbl">Staff</span></a>` : staff
    ? `<span class="who">${esc(S.name)}${S.name === roleLabel ? '' : `<small>${roleLabel}</small>`}</span>${helpBtn}<button class="hbtn" id="lo" aria-label="Log out">${ic('logout', 18)}<span class="lbl">Log out</span></button>`
    : `${helpBtn}<button class="hbtn" id="lo" aria-label="Log out">${ic('logout', 18)}<span class="lbl">Log out</span></button>`;
  const hh = location.hash || '#/';
  const nav = staff ? '' : `<nav class="hnav" aria-label="Primary">${[['#/', 'Home'], ['#/about', 'About'], ['#/privacy', 'Privacy'], ['#/accessibility', 'Accessibility']].map(([h2, l]) => `<a href="${h2}" class="${(h2 === '#/' ? (hh === '#/' || hh === '' || hh === '#/home') : hh.startsWith(h2)) ? 'on' : ''}">${l}</a>`).join('')}</nav>`;
  $('#top').innerHTML = `<a class="brand" href="#/" aria-label="Sudhaar home">${MARK}<span><b>सुधार · Sudhaar</b><small>Report. Resolve. Improve.</small></span></a>${nav}<div class="sp"></div>${right}`;
  document.body.dataset.route = hh.startsWith('#/report') ? 'report' : 'other';
  document.body.dataset.wide = (!staff && (hh === '#/' || hh === '' || hh.startsWith('#/about') || hh === '#/privacy' || hh === '#/accessibility')) ? '1' : '0';
  renderFooter();
  const lo = $('#lo'); if (lo) lo.onclick = () => logout();
  const h = location.hash || '#/';
  // citizen bottom tabs
  const tabs = $('#tabs');
  if (S.token && S.role === 'citizen') {
    const on = x => h.startsWith(x) ? 'on' : '';
    tabs.hidden = false; tabs.innerHTML = `<a href="#/home" class="${on('#/home')} ${on('#/c/')}">${ic('home')}Home</a><a href="#/report" class="go ${on('#/report')}"><span class="disc">${ic('camera', 28)}</span>Report</a><a href="#/alerts" class="${on('#/alerts')}">${ic('bell')}Alerts${unread ? `<span class="badge">${unread}</span>` : ''}</a>`;
  } else tabs.hidden = true;
  // staff side nav
  const side = $('#side');
  if (staff && NAV[S.role]) {
    side.hidden = false;
    side.innerHTML = NAV[S.role].map(([href, label, icon]) => href === '-' ? `<div class="grp">${label}</div>` : `<a href="${href}" class="${h === href || (href.length > 6 && h.startsWith(href + '/')) ? 'on' : ''}">${ic(icon, 20)}${label}</a>`).join('');
  } else side.hidden = true;
  if (S.token && S.role === 'citizen') refreshBell();
}
async function refreshBell() {
  try { unread = (await api('/api/notifications')).filter(x => !x.read).length; const a = $('#tabs a[href="#/alerts"]'); if (a) { const b = a.querySelector('.badge'); if (b) b.remove(); if (unread) a.insertAdjacentHTML('beforeend', `<span class="badge">${unread}</span>`); } } catch { }
}
async function showNotifications() {
  const list = await api('/api/notifications'); await api('/api/notifications/read', { method: 'POST' }); unread = 0; refreshBell();
  $('#app').innerHTML = `<h1>Alerts</h1>${list.length ? list.map(n => `<a class="citem" href="#/c/${esc(n.complaint_code)}" style="margin:8px 0"><div class="row"><div class="cic">${ic('bell')}</div><div class="grow"><div>${esc(n.message)}</div><div class="mute xs">${ago(n.created_at)}</div></div></div></a>`).join('') : empty('bell', 'No alerts yet', 'You will be notified when a department updates your complaint.')}`;
}

/* ---------- router ---------- */
async function route() {
  timers.forEach(clearInterval); timers = []; stopCamera();
  const h = location.hash || '#/'; const app = $('#app');
  window.scrollTo(0, 0); document.title = pageTitle(h);
  try {
    if (!S.meta) S.meta = await api('/api/meta');
    await renderHeader();
    if (h === '#/' || h === '') return S.token ? go(S.role) : landing();
    if (h === '#/login') return citizenLogin();
    if (h === '#/staff') return staffLogin();
    if (h.startsWith('#/about')) return about(h.split('/')[2]);
    if (h === '#/privacy') return privacy();
    if (h === '#/accessibility') return accessibility();
    if (!S.token) { location.hash = '#/'; return; }
    const R_ = S.role;
    if (R_ === 'citizen') {
      if (h === '#/home') return citizenHome();
      if (h === '#/report') return report();
      if (h === '#/alerts') return showNotifications();
      if (h.startsWith('#/c/')) return citizenDetail(decodeURIComponent(h.slice(4)));
    } else if (R_ === 'officer') {
      if (h === '#/dept') return deptHome();
      if (h.startsWith('#/d/')) return deptDetail(decodeURIComponent(h.slice(4)));
    } else if (R_ === 'super_admin') {
      if (h.startsWith('#/admin')) return adminHome(h.split('/')[2] || 'overview', h.split('/')[3]);
      if (h.startsWith('#/d/')) return deptDetail(decodeURIComponent(h.slice(4)));
    }
    if ((R_ === 'ai_monitor' || R_ === 'super_admin') && h.startsWith('#/ai')) return aiHome(h.split('/')[2] || 'live', h.split('/')[3]);
    go(R_);
  } catch (e) { app.innerHTML = `<div class="err">${ic('alert')}<div>${esc(e.message)}<div><a href="#/">Go home</a></div></div></div>`; }
}
function go(role) { const to = role === 'citizen' ? '#/home' : role === 'super_admin' ? '#/admin/overview' : role === 'ai_monitor' ? '#/ai' : '#/dept'; if (location.hash === to) route(); else location.hash = to; }
window.addEventListener('hashchange', route);

/* ---------- landing & auth ---------- */
const feat = (icon, t, d) => `<div class="feat"><div class="ficon">${ic(icon, 26)}</div><h3>${t}</h3><p>${d}</p></div>`;
const FEATURES = [
  ['camera', 'Live evidence only', 'Photos and videos are captured live in the app and stamped with location, date and time. No gallery uploads.'],
  ['map', 'Routed to the right owner', 'Location and category decide whether a municipal, state or national department receives your complaint.'],
  ['cpu', 'AI-assisted checks', 'Sudhaar checks the evidence, looks for duplicate reports and rates severity so urgent problems rise first.'],
  ['eye', 'Track every step', 'Seven clear stages from Registered to Resolved, with an alert each time something changes.'],
  ['shield', 'Private by design', 'Departments never see your mobile number or name. Media is only opened by authorised officers.'],
  ['cloud', 'Built for weak networks', 'If an upload is interrupted, your complaint is kept on your device and retried automatically.']
];
const HERO_ART = `<img src="/static/hero-ghat.svg" alt="" width="640" height="360" decoding="async">`;
const catTiles = () => `<div class="catgrid">${S.meta.categories.map(c => `<div class="cattile"><span class="cic">${catIc(c, 26)}</span>${esc(c)}</div>`).join('')}</div>`;
const lifecycle = () => `<ol class="life">${LIFECYCLE.map(l => `<li>${esc(l)}</li>`).join('')}</ol>`;
function landing() {
  $('#app').innerHTML = `<section class="hero"><div class="hero-copy">
    <span class="eyebrow">${ic('shield', 15)}Citizen grievance platform &middot; Varanasi pilot</span>
    <div class="dv">सुधार</div><h1 class="tl">Report. Resolve. Improve.</h1>
    <p class="lede">Report a civic problem with one live photo. We route it to the right department and you follow it to the fix.</p>
    <div class="cta-row"><a class="btn accent" href="#/login">${ic('camera', 22)}Report a problem</a><a class="btn hero-ghost" href="#/about">About Sudhaar</a></div>
    <ul class="trust"><li>${ic('check', 16)}Live photo only</li><li>${ic('check', 16)}Private by design</li><li>${ic('check', 16)}Tracked to resolution</li></ul></div>
    <div class="hero-art" aria-hidden="true">${HERO_ART}</div></section>
  <section class="section"><div class="section-head"><div><span class="kicker">Why Sudhaar</span><h2>A complaint that does not get lost</h2></div></div><div class="feat-grid">${FEATURES.map(f => feat(...f)).join('')}</div></section>
  <section class="section"><div class="section-head"><div><span class="kicker">How it works</span><h2>Three simple steps</h2></div></div>
    <div class="steps3" style="margin-top:22px">
      <div class="step3"><h3>Report</h3><p>Pick a category, take a live photo or video. Location and time are stamped on it.</p></div>
      <div class="step3"><h3>Resolve</h3><p>Sudhaar checks the evidence, finds who owns the road or pipe, and sends it to that department.</p></div>
      <div class="step3"><h3>Improve</h3><p>Follow every step like a parcel. When it is fixed, confirm it or reopen it.</p></div></div></section>
  <section class="section"><div class="section-head"><div><span class="kicker">What you can report</span><h2>Everyday civic problems</h2></div><a href="#/about/report">See all details</a></div>${catTiles()}</section>
  <section class="section"><div class="split" style="align-items:center"><div><span class="kicker">Transparency</span><h2 style="margin-top:0">Follow it from report to fix</h2><p class="mute">Every complaint moves through the same seven stages. You get an alert at each one, and when the department says it is fixed, you decide whether it really is.</p><a class="btn" href="#/about/how">How Sudhaar works</a></div><div class="card" style="margin:0">${lifecycle()}</div></div></section>
  <section class="cta-band"><div><h2>Seen a pothole, a broken light or an overflowing drain?</h2><p>Log in with your mobile number and report it with one live photo.</p></div><a class="btn accent" href="#/login">${ic('camera', 22)}Report a problem</a></section>
  <p class="center sm mute" style="text-align:center">Department officer or administrator? <a href="#/staff">Staff login</a></p>`;
}
function citizenLogin() {
  $('#app').innerHTML = `<div class="auth card"><div class="logo-big">${ic('pin', 30)}</div><h1>Log in with your mobile</h1>
  <div id="s1"><label for="mob">Mobile number</label><input id="mob" inputmode="numeric" autocomplete="tel" placeholder="10-digit number" maxlength="14">
  <p class="field-note">We send a one-time password. Your number stays private from departments.</p><button class="primary big" id="send">Send OTP</button></div>
  <div id="s2" hidden><label for="otp">6-digit OTP</label><input id="otp" class="otp-input" inputmode="numeric" autocomplete="one-time-code" maxlength="6"><div id="dev"></div><button class="primary big" id="ver" style="margin-top:12px">Verify and continue</button><button class="ghost" id="chg" style="width:100%;margin-top:6px">Use a different number</button></div>
  <div id="msg" class="err" hidden></div></div>`;
  const err = m => { const e = $('#msg'); e.hidden = !m; e.innerHTML = m ? `${ic('alert')}<div>${esc(m)}</div>` : ''; };
  $('#send').onclick = async () => {
    err(''); try {
      const r = await api('/api/auth/otp', { method: 'POST', json: { mobile: $('#mob').value } });
      $('#s1').hidden = true; $('#s2').hidden = false; $('#otp').focus();
      if (r.dev_otp) $('#dev').innerHTML = `<div class="notice info" style="margin-top:8px">Test mode: your OTP is <b>${esc(r.dev_otp)}</b> (no SMS gateway connected).</div>`;
    } catch (e) { err(e.message); }
  };
  $('#chg').onclick = () => { $('#s2').hidden = true; $('#s1').hidden = false; err(''); };
  $('#ver').onclick = async () => { err(''); try { setSession(await api('/api/auth/verify', { method: 'POST', json: { mobile: $('#mob').value, code: $('#otp').value } })); location.hash = '#/home'; } catch (e) { err(e.message); } };
  $('#mob').onkeydown = e => { if (e.key === 'Enter') $('#send').click(); }; $('#otp').onkeydown = e => { if (e.key === 'Enter') $('#ver').click(); };
}
function staffLogin() {
  $('#app').innerHTML = `<div class="auth card"><div class="logo-big">${ic('shield', 30)}</div><h1>Staff login</h1><p class="mute sm" style="margin-top:-4px">Department officers, Super Admin and the Sudhaar AI monitor.</p>
  <label for="u">Username</label><input id="u" autocomplete="username" autocapitalize="none" spellcheck="false">
  <label for="p">Password</label><div class="pw-wrap"><input id="p" type="password" autocomplete="current-password"><button type="button" id="eye" aria-label="Show password">Show</button></div>
  <button class="primary big" id="go" style="margin-top:16px">Sign in</button><div id="msg" class="err" hidden></div></div>`;
  const run = async () => {
    const m = $('#msg'); m.hidden = true; const b = $('#go'); b.disabled = true;
    try { const r = await api('/api/staff/login', { method: 'POST', json: { username: $('#u').value, password: $('#p').value } }); setSession(r); go(r.role); }
    catch (e) { m.hidden = false; m.innerHTML = `${ic('alert')}<div>${esc(e.message)}</div>`; } finally { b.disabled = false; }
  };
  $('#go').onclick = run;
  $('#p').onkeydown = e => { if (e.key === 'Enter') run(); };   // NB: never return false here - it cancels every keystroke
  $('#u').onkeydown = e => { if (e.key === 'Enter') $('#p').focus(); };
  $('#eye').onclick = () => { const p = $('#p'); const show = p.type === 'password'; p.type = show ? 'text' : 'password'; $('#eye').textContent = show ? 'Hide' : 'Show'; };
  $('#u').focus();
}

/* ---------- citizen home ---------- */
const progressOf = st => { const i = LIFECYCLE.indexOf(st); return st === 'Rejected' ? 7 : st === 'Reopened' ? 2 : i + 1; };
const miniBar = st => `<div class="mini ${CLOSED.includes(st) ? 'done' : ''}">${LIFECYCLE.map((_, i) => `<i class="${i < progressOf(st) ? 'on' : ''}"></i>`).join('')}</div>`;
async function citizenHome() {
  const [list, drafts] = await Promise.all([api('/api/complaints'), idb.all().catch(() => [])]);
  const openN = list.filter(c => !CLOSED.includes(c.status)).length, doneN = list.filter(c => c.status === 'Resolved').length;
  $('#app').innerHTML = `<h1>${list.length ? 'Your complaints' : 'Welcome'}</h1>
  <a class="btn accent big" href="#/report" style="min-height:60px;font-size:1.1rem">${ic('camera', 26)}Report a problem</a>
  ${list.length ? `<div class="grid g3" style="margin-top:12px;grid-template-columns:1fr 1fr"><div class="kpi"><b>${openN}</b><span>In progress</span></div><div class="kpi"><b>${doneN}</b><span>Fixed</span></div></div>` : ''}
  ${drafts.length ? `<h2>Waiting to upload</h2>${drafts.map(d => `<div class="card" data-d="${esc(d.id)}"><div class="row"><div class="cic">${catIc(d.category)}</div><div class="grow"><b>${esc(d.category)}</b><div class="mute sm">${esc(d.status || 'Waiting for connection')}</div></div></div><div class="row" style="margin-top:10px"><button class="primary grow" data-act="retry">Retry now</button><button data-act="del">Discard</button></div></div>`).join('')}` : ''}
  ${list.length ? `<ul class="clist" style="margin-top:14px">${list.map(c => `<li><a class="citem ${CLOSED.includes(c.status) ? 'done' : ''}" href="#/c/${esc(c.code)}"><div class="row" style="flex-wrap:nowrap"><div class="cic">${catIc(c.category)}</div><div class="grow"><b class="mono">${esc(c.code)}</b><div class="sm">${esc(c.category)}</div><div class="mute xs">${esc(c.department || 'Department being identified')} - ${ago(c.created_at)}</div></div>${chipSt(c.status)}</div>${miniBar(c.status)}</a></li>`).join('')}</ul>` : empty('camera', 'Nothing reported yet', 'See a pothole, open manhole or garbage heap? Tap Report a problem.')}`;
  $('#app').querySelectorAll('[data-d]').forEach(card => {
    card.querySelector('[data-act=retry]').onclick = async () => { await flushDrafts(true); citizenHome(); };
    card.querySelector('[data-act=del]').onclick = async () => { if (confirm('Discard this unsent complaint and its media?')) { await idb.del(card.dataset.d); citizenHome(); } };
  });
  timers.push(setInterval(refreshBell, 30000));
}

/* ---------- report wizard ---------- */
let R = null;
const cam = { stream: null, video: null, canvas: null, raf: 0, rec: null, chunks: [], t0: 0, timer: 0 };
function newReport() { return { step: 1, category: null, photo: null, video: null, loc: null, desc: '', token: null, skew: 0, capturedAt: null, clientId: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random() }; }
function report() { if (!R) R = newReport(); drawReport(); }
const STEP_TITLES = ['What is the problem?', 'Capture live evidence', 'Review and send'];
function stepBar() { return `<div class="steps" role="img" aria-label="Step ${R.step} of 3">${[1, 2, 3].map(i => `<span class="${R.step >= i ? 'on' : ''}"></span>`).join('')}</div><div class="mute sm">Step ${R.step} of 3</div>`; }
function drawReport() {
  stopCamera();
  if (R.step === 1) {
    $('#app').innerHTML = `${stepBar()}<h1>${STEP_TITLES[0]}</h1><div class="cats">${S.meta.categories.map(c => `<button class="cat ${R.category === c ? 'sel' : ''}" data-c="${esc(c)}" aria-pressed="${R.category === c}"><span class="cic">${catIc(c, 26)}</span>${esc(c)}</button>`).join('')}</div>
    <div class="row" style="margin-top:18px"><button id="cancel">Cancel</button><div class="grow"></div><button class="primary" id="next" ${R.category ? '' : 'disabled'}>Next: take photo${ic('next', 18)}</button></div>`;
    $('#app').querySelectorAll('.cat').forEach(b => b.onclick = () => { R.category = b.dataset.c; drawReport(); });
    $('#next').onclick = () => { R.step = 2; drawReport(); };
    $('#cancel').onclick = () => { R = null; location.hash = '#/home'; };
  } else if (R.step === 2) drawCapture();
  else drawReview();
}
const locText = () => !R.loc ? 'Finding your location…' : `${R.loc.lat.toFixed(5)}, ${R.loc.lon.toFixed(5)} - ${R.loc.source === 'gps' ? 'GPS' + (R.loc.acc ? ` (±${Math.round(R.loc.acc)} m)` : '') : 'pinned by you'}`;

function drawCapture() {
  $('#app').innerHTML = `${stepBar()}<h1>${STEP_TITLES[1]}</h1><div class="mute" style="margin:-4px 0 8px;display:flex;gap:8px;align-items:center">${catIc(R.category, 18)}${esc(R.category)}</div>
  <div class="card"><div class="row" style="flex-wrap:nowrap"><div class="cic">${ic('pin')}</div><div class="grow"><b>Location</b><div id="loctxt" class="mute sm">${esc(locText())}</div></div><button id="pin">Pin on map</button></div><div id="mapbox"></div></div>
  <div id="camerr"></div><div class="cam" id="camwrap"><canvas id="cv"></canvas><span class="rec" id="recbadge" hidden>● REC 0s</span></div>
  <div class="shutter"><button class="vid" id="recbtn" disabled aria-label="Record video">${ic('video', 26)}</button><button class="snap" id="snap" disabled aria-label="Take photo">${ic('camera', 32)}</button></div>
  <p class="mute sm" style="text-align:center;margin-top:0">Live capture only. Gallery photos and old videos can't be used. Location, date and time are stamped on the media.</p>
  <h3>Your evidence</h3><div class="shots" id="shots"></div>
  <div class="row" style="margin-top:18px"><button id="back">${ic('back', 18)}Back</button><div class="grow"></div><button class="primary" id="next" disabled>Next: review${ic('next', 18)}</button></div>`;
  $('#back').onclick = () => { R.step = 1; drawReport(); };
  $('#next').onclick = () => { R.step = 3; drawReport(); };
  $('#pin').onclick = openPinMap;
  renderShots(); locate(); startCamera();
}
function updateCaptureButtons() {
  const ready = !!(R.loc && cam.stream);
  const s = $('#snap'), r = $('#recbtn'), n = $('#next'); if (!s) return;
  s.disabled = !ready || !!cam.rec; r.disabled = !ready && !cam.rec; n.disabled = !(R.photo || R.video) || !R.loc || !!cam.rec;
}
function locate() {
  if (R.loc) return updateCaptureButtons();
  if (!navigator.geolocation) { $('#loctxt').textContent = 'GPS unavailable on this device. Pin the location on the map.'; return openPinMap(); }
  navigator.geolocation.getCurrentPosition(p => {
    if (R.loc && R.loc.source === 'manual') return;
    R.loc = { lat: p.coords.latitude, lon: p.coords.longitude, acc: p.coords.accuracy, source: 'gps' };
    const t = $('#loctxt'); if (t) t.textContent = locText(); updateCaptureButtons();
  }, e => { const t = $('#loctxt'); if (t) t.textContent = 'Location permission is off or GPS is unavailable. Please pin the problem location on the map.'; if (!R.loc) openPinMap(); },
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 });
}
function openPinMap() {
  const box = $('#mapbox'); if (!box) return;
  const start = R.loc ? [R.loc.lat, R.loc.lon] : VARANASI; let pick = null;
  box.innerHTML = `<div class="map" id="map"></div><div class="row"><div class="grow mute sm" id="picktxt">Tap the map to drop a pin on the problem spot.</div><button id="pcancel">Cancel</button><button class="primary" id="pok" disabled>Use this location</button></div>`;
  if (typeof L === 'undefined') {   // map library unreachable (offline): numeric fallback
    box.innerHTML = `<div class="notice">Map unavailable offline. Enter coordinates:</div><div class="row"><input id="mlat" placeholder="Latitude" class="grow"><input id="mlon" placeholder="Longitude" class="grow"><button class="primary" id="mset">Use</button></div>`;
    $('#mset').onclick = () => { const la = parseFloat($('#mlat').value), lo = parseFloat($('#mlon').value); if (isFinite(la) && isFinite(lo)) setManual(la, lo); }; return;
  }
  const map = L.map('map').setView(start, 16); let mk = null;
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap contributors' }).addTo(map);
  if (R.loc) L.circleMarker(start, { radius: 6 }).addTo(map).bindTooltip('Your GPS position');
  map.on('click', e => { pick = e.latlng; if (mk) mk.setLatLng(pick); else mk = L.marker(pick).addTo(map); $('#picktxt').textContent = `${pick.lat.toFixed(6)}, ${pick.lng.toFixed(6)}`; $('#pok').disabled = false; });
  $('#pok').onclick = () => setManual(pick.lat, pick.lng);
  $('#pcancel').onclick = () => { box.innerHTML = ''; };
  setTimeout(() => map.invalidateSize(), 100);
}
function setManual(lat, lon) { R.loc = { lat, lon, source: 'manual' }; $('#mapbox').innerHTML = ''; $('#loctxt').textContent = locText(); updateCaptureButtons(); toast('Location pinned manually'); }

async function ensureCaptureSession() {
  if (R.token) return;
  const s = await api('/api/capture-session', { method: 'POST' }); R.token = s.capture_token; R.skew = s.iat * 1000 - Date.now();
}
const nowIso = () => new Date(Date.now() + (R.skew || 0)).toISOString();

async function startCamera() {
  const err = $('#camerr');
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { err.innerHTML = `<div class="err">This browser can't access the camera. Open Sudhaar over HTTPS (or localhost) in a modern browser.</div>`; return; }
  try {
    try { cam.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 960 } }, audio: true }); }
    catch (e) { if (e.name === 'NotAllowedError') throw e; cam.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false }); }
  } catch (e) {
    err.innerHTML = `<div class="err"><b>Camera access is needed.</b><br>Sudhaar only accepts live photos and videos so that every complaint shows real, current evidence. Allow camera access in your browser's site settings (tap the 🔒 icon near the address bar), then press retry.<br><button id="cretry" style="margin-top:8px">Retry camera</button></div>`;
    $('#cretry').onclick = () => { err.innerHTML = ''; startCamera(); }; return;
  }
  cam.video = Object.assign(document.createElement('video'), { srcObject: cam.stream, muted: true, playsInline: true }); await cam.video.play();
  cam.canvas = $('#cv'); const ctx = cam.canvas.getContext('2d');
  const draw = () => {
    const v = cam.video; if (!v.videoWidth) { cam.raf = requestAnimationFrame(draw); return; }
    if (cam.canvas.width !== v.videoWidth) { cam.canvas.width = v.videoWidth; cam.canvas.height = v.videoHeight; const w = $('#camwrap'); if (w) w.style.aspectRatio = v.videoWidth + '/' + v.videoHeight; }
    const W = cam.canvas.width, H = cam.canvas.height; ctx.drawImage(v, 0, 0, W, H);
    // Visible overlay burned into the pixels: lat, lon, date, time (spec §4.3)
    const d = new Date(Date.now() + (R.skew || 0)); const fs = Math.max(14, Math.round(W / 38));
    const l1 = R.loc ? `Lat ${R.loc.lat.toFixed(6)}  Lon ${R.loc.lon.toFixed(6)}${R.loc.source === 'manual' ? '  (pinned)' : ''}` : 'Location pending…';
    const l2 = `${d.toLocaleDateString()}  ${d.toLocaleTimeString()}  ·  Sudhaar LIVE`;
    ctx.fillStyle = 'rgba(0,0,0,.55)'; ctx.fillRect(0, H - fs * 3.1, W, fs * 3.1);
    ctx.fillStyle = '#fff'; ctx.font = `600 ${fs}px sans-serif`; ctx.textBaseline = 'top'; ctx.fillText(l1, fs * .6, H - fs * 2.8); ctx.fillText(l2, fs * .6, H - fs * 1.5);
    cam.raf = requestAnimationFrame(draw);
  };
  draw(); updateCaptureButtons();
  $('#snap').onclick = takePhoto; $('#recbtn').onclick = toggleRecord;
}
function stopCamera() {
  cancelAnimationFrame(cam.raf); clearInterval(cam.timer);
  if (cam.rec && cam.rec.state !== 'inactive') { try { cam.rec.onstop = null; cam.rec.stop(); } catch { } }
  cam.rec = null; if (cam.stream) cam.stream.getTracks().forEach(t => t.stop()); cam.stream = null; cam.video = null;
}
async function takePhoto() {
  try { await ensureCaptureSession(); } catch (e) { return toast(e.message); }
  const at = nowIso(), loc = { ...R.loc };
  cam.canvas.toBlob(b => { R.photo = { blob: b, at, loc }; R.capturedAt = R.capturedAt || at; renderShots(); updateCaptureButtons(); toast('Photo captured'); }, 'image/jpeg', 0.9);
}
async function toggleRecord() {
  if (cam.rec) return cam.rec.stop();
  try { await ensureCaptureSession(); } catch (e) { return toast(e.message); }
  const out = cam.canvas.captureStream(25); cam.stream.getAudioTracks().forEach(t => out.addTrack(t));
  const mime = ['video/webm;codecs=vp8,opus', 'video/webm', 'video/mp4'].find(m => window.MediaRecorder && MediaRecorder.isTypeSupported(m));
  if (!mime) return toast('Video recording is not supported in this browser');
  const at = nowIso(), loc = { ...R.loc }; cam.chunks = [];
  cam.rec = new MediaRecorder(out, { mimeType: mime, videoBitsPerSecond: 1500000 });
  cam.rec.ondataavailable = e => e.data.size && cam.chunks.push(e.data);
  cam.rec.onstop = () => { clearInterval(cam.timer); const b = new Blob(cam.chunks, { type: mime.split(';')[0] }); cam.rec = null; R.video = { blob: b, at, loc }; R.capturedAt = R.capturedAt || at; const rb = $('#recbadge'); if (rb) rb.hidden = true; const rbt = $('#recbtn'); if (rbt) { rbt.classList.remove('recording'); rbt.setAttribute('aria-label','Record video'); } renderShots(); updateCaptureButtons(); toast('Video recorded'); };
  cam.rec.start(1000); cam.t0 = Date.now(); $('#recbtn').classList.add('recording'); $('#recbtn').setAttribute('aria-label','Stop recording'); $('#recbadge').hidden = false; updateCaptureButtons();
  cam.timer = setInterval(() => { const s = Math.round((Date.now() - cam.t0) / 1000); $('#recbadge').textContent = `● REC ${s}s`; if (s >= 30) cam.rec && cam.rec.stop(); }, 500);
}
function renderShots() {
  const el = $('#shots'); if (!el) return;
  const one = (k, o, tag) => o ? `<figure>${tag(URL.createObjectURL(o.blob))}<figcaption>${k} · ${new Date(o.at).toLocaleTimeString()}</figcaption><button class="x" data-rm="${k}" aria-label="Remove ${k}">×</button></figure>` : '';
  el.innerHTML = one('photo', R.photo, u => `<img src="${u}" alt="photo">`) + one('video', R.video, u => `<video src="${u}" controls playsinline></video>`) || '<span class="mute sm">Nothing captured yet. Take a photo, record a video, or both.</span>';
  el.querySelectorAll('[data-rm]').forEach(b => b.onclick = () => { R[b.dataset.rm] = null; if (!R.photo && !R.video) { R.capturedAt = null; R.token = null; } renderShots(); updateCaptureButtons(); });
}


function drawReview() {
  $('#app').innerHTML = `${stepBar()}<h1>${STEP_TITLES[2]}</h1><div class="card"><div class="row" style="flex-wrap:nowrap"><div class="cic">${catIc(R.category)}</div><div class="grow"><b>${esc(R.category)}</b><div class="mute sm">${ic('pin', 15)} ${esc(locText())}</div></div></div>
  <div class="shots" style="margin-top:12px">${R.photo ? `<figure><img src="${URL.createObjectURL(R.photo.blob)}" alt="Your photo"></figure>` : ''}${R.video ? `<figure><video src="${URL.createObjectURL(R.video.blob)}" controls playsinline></video></figure>` : ''}</div>
  <label for="desc">Add a note <span class="mute">(optional)</span></label><textarea id="desc" maxlength="1000" placeholder="What did you see? Why is it unsafe? Did anything happen here?">${esc(R.desc)}</textarea></div>
  <div id="up" hidden><div class="progress"><i id="bar"></i></div><div class="mute sm" id="uptxt"></div></div><div id="msg"></div>
  <div class="row"><button id="back">${ic('back', 18)}Back</button><div class="grow"></div><button class="primary" id="submit">${ic('send', 18)}Send complaint</button></div>`;
  $('#back').onclick = () => { R.desc = $('#desc').value; R.step = 2; drawReport(); };
  $('#submit').onclick = submitReport;
}
function buildForm(d) {
  const f = new FormData();
  f.append('category', d.category); f.append('description', d.desc || ''); f.append('lat', d.loc.lat); f.append('lon', d.loc.lon); f.append('loc_source', d.loc.source);
  f.append('captured_at', d.capturedAt); f.append('capture_token', d.token); f.append('client_id', d.clientId);
  if (d.photo) f.append('photo', d.photo.blob, 'photo.jpg'); if (d.video) f.append('video', d.video.blob, 'video.' + (d.video.blob.type.includes('mp4') ? 'mp4' : 'webm'));
  return f;
}
function upload(d, onProgress) {   // XHR for upload progress; resolves {ok,status,data} or rejects on network failure
  return new Promise((res, rej) => {
    const x = new XMLHttpRequest(); x.open('POST', '/api/complaints'); x.setRequestHeader('Authorization', 'Bearer ' + S.token);
    x.upload.onprogress = e => e.lengthComputable && onProgress && onProgress(e.loaded / e.total);
    x.onload = () => { let data; try { data = JSON.parse(x.responseText); } catch { data = {}; } res({ ok: x.status < 300, status: x.status, data }); };
    x.onerror = () => rej(new Error('network')); x.ontimeout = () => rej(new Error('network')); x.timeout = 180000; x.send(buildForm(d));
  });
}
async function submitReport() {
  R.desc = $('#desc').value; const d = { id: R.clientId, clientId: R.clientId, category: R.category, desc: R.desc, loc: R.loc, photo: R.photo, video: R.video, capturedAt: R.capturedAt, token: R.token, created: new Date().toISOString(), status: 'Uploading' };
  $('#submit').disabled = true; $('#back').disabled = true; $('#up').hidden = false; $('#msg').innerHTML = '';
  try {
    const r = await upload(d, p => { $('#bar').style.width = Math.round(p * 100) + '%'; $('#uptxt').textContent = `Uploading… ${Math.round(p * 100)}%`; });
    if (r.ok) { R = null; return success(r.data.code); }   // success shown ONLY after server confirmation
    if (r.status >= 500) throw new Error('network');
    $('#msg').innerHTML = `<div class="err">${ic('alert')}<div>${esc(r.data.detail || 'Submission rejected')}</div></div>`; $('#submit').disabled = false; $('#back').disabled = false;
  } catch (e) {
    d.status = 'Waiting for connection - will retry automatically'; await idb.put(d).catch(() => { });
    $('#msg').innerHTML = `<div class="notice">${ic('alert')}<div><b>Upload didn't finish.</b> Your complaint is saved on this phone and will upload when the connection returns. It is <b>not</b> submitted yet.<br><a href="#/home">See pending uploads</a></div></div>`;
    $('#up').hidden = true; R = null;
  }
}
function success(code) {
  $('#app').innerHTML = `<div style="text-align:center;padding:24px 0"><div class="done-mark">${ic('check', 44)}</div><h1>Complaint registered</h1><p class="mute">Your complaint ID</p><div class="code">${esc(code)}</div>
  <p class="mute" style="max-width:34ch;margin:14px auto">Sudhaar is checking the evidence and sending it to the responsible department. We'll alert you at every step.</p>
  <div class="row" style="justify-content:center"><a class="btn primary" href="#/c/${esc(code)}">Track this complaint</a><a class="btn" href="#/home">Home</a></div></div>`;
}
async function flushDrafts(manual) {   // retry queued uploads; idempotent on the server via client_id
  if (S.role !== 'citizen' || !S.token) return;
  for (const d of await idb.all().catch(() => [])) {
    try {
      const r = await upload(d);
      if (r.ok) { await idb.del(d.id); toast(`Draft submitted: ${r.data.code}`); }
      else if (r.status < 500) { d.status = 'Needs attention: ' + (r.data.detail || 'rejected'); await idb.put(d); if (manual) toast(d.status); }
    } catch { if (manual) toast('Still offline. Will retry automatically.'); }
  }
}
window.addEventListener('online', () => flushDrafts(false)); setInterval(() => navigator.onLine && flushDrafts(false), 30000);

/* ---------- citizen: complaint detail ---------- */
async function citizenDetail(code) {
  const load = async () => {
    const c = await api('/api/complaints/' + encodeURIComponent(code));
    const own = c.media.filter(m => m.role === 'original'), proof = c.media.filter(m => m.role === 'resolution');
    const tag = m => m.kind === 'photo' ? `<img data-mid="${m.id}" alt="${esc(m.role)} photo">` : `<video data-mid="${m.id}" controls playsinline></video>`;
    const rejected = c.status === 'Rejected', idx = rejected ? 6 : Math.max(0, LIFECYCLE.indexOf(c.status));
    const labels = ['Registered', 'Forwarded to department', 'Acknowledged', 'Under review', 'Field officer assigned', 'Work in progress', rejected ? 'Rejected' : 'Resolved'];
    const done = (c.status === 'Resolved' || rejected), reopened = c.status === 'Reopened';
    $('#app').innerHTML = `<p style="margin:0"><a href="#/home" class="row" style="gap:4px;text-decoration:none">${ic('back', 18)}My complaints</a></p>
    <div class="card"><div class="row" style="flex-wrap:nowrap"><div class="cic">${catIc(c.category)}</div><div class="grow"><h1 style="margin:0;font-size:1.2rem" class="mono nowrap">${esc(c.code)}</h1><div class="mute sm">${esc(c.category)}</div></div></div>
    <div style="margin:14px 0 2px"><ol class="stepper ${rejected ? 'bad' : ''}" aria-label="Progress">${labels.map((l, i) => `<li class="${i <= idx ? 'on' : ''} ${i === idx ? 'now' : ''}" title="${l}"><i>${ic(rejected && i === 6 ? 'x' : 'check', 14)}</i></li>`).join('')}</ol>
    <div class="stepcap">${reopened ? 'Reopened - back with the department' : labels[idx]}<small>${done ? (rejected ? 'The department closed this complaint' : 'Step 7 of 7') : reopened ? 'You reopened this complaint' : `Step ${idx + 1} of 7 - next: ${labels[Math.min(idx + 1, 6)]}`}</small></div></div>
    <p style="margin:12px 0 2px"><b>Department:</b> ${esc(c.department || 'Being identified')}</p><p class="sm mute" style="margin:0">${ic('pin', 15)} ${c.lat.toFixed(5)}, ${c.lon.toFixed(5)} (${c.loc_source === 'gps' ? 'GPS' : 'pinned by you'})</p>${c.description ? `<p class="sm" style="margin:8px 0 0">“${esc(c.description)}”</p>` : ''}</div>
    ${c.citizen_confirmed ? `<div class="notice ok">${ic('check')}<div>You confirmed this is fixed. Thank you.</div></div>` : ''}
    ${c.can_confirm || c.can_reopen ? `<div class="card"><b>${c.status === 'Resolved' ? 'The department says this is fixed. Is it?' : 'Not satisfied with the outcome?'}</b><div class="row" style="margin-top:10px">${c.can_confirm ? `<button class="primary grow" id="ok">${ic('check', 18)}Yes, it is fixed</button>` : ''}${c.can_reopen ? `<button class="danger grow" id="reopen">Still a problem - reopen</button>` : ''}</div></div>` : ''}
    ${proof.length ? `<h2>Proof from the department</h2><div class="mediaGrid">${proof.map(tag).join('')}</div>` : ''}
    <h2>Progress</h2><div class="card"><ul class="timeline">${[...c.timeline].reverse().map(t => `<li><div class="t">${esc(t.status)}</div>${t.note ? `<div class="sm">${esc(t.note)}</div>` : ''}<div class="mute xs">${fmt(t.created_at)}</div></li>`).join('')}</ul></div>
    <h2>Your evidence</h2><div class="mediaGrid">${own.map(tag).join('')}</div>`;
    fillMedia($('#app'));
    const ok = $('#ok'); if (ok) ok.onclick = async () => { await api(`/api/complaints/${code}/confirm`, { method: 'POST' }); toast('Thanks for confirming'); load(); };
    const ro = $('#reopen'); if (ro) ro.onclick = async () => { const reason = prompt('What is still wrong? (optional)'); if (reason === null) return; await api(`/api/complaints/${code}/reopen`, { method: 'POST', json: { reason } }); toast('Complaint reopened'); load(); };
  };
  await load(); timers.push(setInterval(() => { if (!document.hidden) load().catch(() => { }); }, 30000));
}

/* ---------- department console ---------- */
const prioOrder = ['Critical', 'High', 'Medium', 'Low'];
const complaintRow = (c, href, extra = '') => `<li><a class="citem sev-${esc(c.severity || '')} ${CLOSED.includes(c.status) ? 'done' : ''}" href="${href}"><div class="row" style="flex-wrap:nowrap"><div class="cic">${catIc(c.category)}</div><div class="grow"><b class="mono">${esc(c.code)}</b>${c.reopen_count ? ' <span class="chip st-Reopened">Reopened</span>' : ''}<div class="sm">${esc(c.category)}</div><div class="mute xs">${extra}${ago(c.created_at)}${c.validity_score != null ? ` - evidence ${Number(c.validity_score).toFixed(1)}/10` : ''}</div></div><div style="text-align:right;display:grid;gap:4px;justify-items:end">${chipSev(c.severity)}${chipSt(c.status)}</div></div></a></li>`;
async function deptHome() {
  const f = { status: sessionStorage.f_status || '', severity: sessionStorage.f_sev || '' };
  const [list, all] = await Promise.all([api('/api/dept/complaints?' + new URLSearchParams(Object.entries(f).filter(([, v]) => v))), api('/api/dept/complaints')]);
  const open = list.filter(c => !CLOSED.includes(c.status)), closed = list.filter(c => CLOSED.includes(c.status));
  const cnt = sv => all.filter(c => c.severity === sv && !CLOSED.includes(c.status)).length;
  $('#app').innerHTML = `<h1>Complaints for your department</h1>
  <div class="grid g4">${prioOrder.map(s => `<button class="kpi sev-${s} ${f.severity === s ? 'sel' : ''}" data-sev="${s}"><b>${cnt(s)}</b><span>${s} open</span></button>`).join('')}</div>
  <div class="card row"><div class="grow"><label for="fs" style="margin-top:0">Status</label><select id="fs"><option value="">All</option>${S.meta.statuses.map(s => `<option ${s === f.status ? 'selected' : ''}>${esc(s)}</option>`).join('')}</select></div>${f.status || f.severity ? '<button id="clr">Clear filters</button>' : ''}</div>
  <p class="mute sm">Listed most urgent first. Severity decides work order only; it never rejects a complaint. AI findings and scores support your review, so verify on site.</p>
  ${open.length ? `<ul class="clist">${open.map(c => complaintRow(c, '#/d/' + esc(c.code))).join('')}</ul>` : empty('check', 'No open complaints', f.status || f.severity ? 'Try clearing the filters.' : 'New complaints will appear here.')}
  ${closed.length ? `<details style="margin-top:18px"><summary>Closed (${closed.length})</summary><ul class="clist" style="margin-top:10px">${closed.map(c => complaintRow(c, '#/d/' + esc(c.code))).join('')}</ul></details>` : ''}`;
  $('#fs').onchange = e => { sessionStorage.f_status = e.target.value; deptHome(); };
  $('#app').querySelectorAll('[data-sev]').forEach(b => b.onclick = () => { sessionStorage.f_sev = f.severity === b.dataset.sev ? '' : b.dataset.sev; deptHome(); });
  const clr = $('#clr'); if (clr) clr.onclick = () => { sessionStorage.f_status = ''; sessionStorage.f_sev = ''; deptHome(); };
  timers.push(setInterval(() => { if (!document.hidden && !$('select:focus')) deptHome().catch(() => { }); }, 45000));
}

function evidencePanel(c) {
  const ev = c.evidence || {}, br = (ev.score_breakdown || {}), ai = c.ai || {}, int = ev.internal || {}, ext = ev.external || {}, w = ev.weather || {}, sv = ev.street_view || {};
  const sevi = ai.severity || {};
  return `<div class="grid g2"><div class="card"><h3 style="margin-top:0">Evidence validity <span class="mute sm">(internal)</span></h3><div class="score">${c.validity_score == null ? '-' : Number(c.validity_score).toFixed(1)}<span class="mute" style="font-size:1rem"> / 10</span></div><div class="bar"><i style="width:${(c.validity_score || 0) * 10}%"></i></div>
  <details><summary>How this was calculated</summary>${Object.entries(br.parts || {}).map(([k, v]) => `<div class="sm row" style="gap:6px"><span class="grow">${esc(k.replace(/_/g, ' '))}</span><b>+${v}</b></div>`).join('')}<p class="mute sm">${esc(br.note || 'Provisional formula.')}</p></details>${ev.enriched === false || ext.pending ? '<p class="mute sm">External sources still being checked…</p>' : ''}</div>
  <div class="card"><h3 style="margin-top:0">Severity and priority</h3><div>${chipSev(c.severity)} <span class="mute sm">Priority ${c.priority ?? '-'} (1 = most urgent)</span></div><ul class="sm" style="padding-left:18px">${(sevi.reasons || []).map(r => `<li>${esc(r)}</li>`).join('')}</ul></div></div>
  <div class="card"><h3 style="margin-top:0">AI findings</h3><div class="sm">Engine: ${esc(ai.engine || 'none')}. ${ai.analysed ? `Detected: <b>${esc((ai.detected || []).join(', ') || 'nothing specific')}</b> (confidence ${Math.round((ai.confidence || 0) * 100)}%)${ai.matches_category === false ? ' <span class="chip sev-High">may not match category</span>' : ''}` : 'No computer-vision engine configured, or analysis failed. Review the media manually.'}</div><p class="mute sm" style="margin-bottom:0">${esc(ai.disclaimer || 'AI findings are supporting information only.')}</p></div>
  <div class="card"><h3 style="margin-top:0">Supporting evidence</h3><ul class="sm" style="padding-left:18px;margin:0"><li><b>Sudhaar reports:</b> ${int.independent_reporters ?? 0} independent citizen(s) reported similar issues within ${int.radius_m || 150} m ${int.nearby_codes && int.nearby_codes.length ? '(' + int.nearby_codes.map(esc).join(', ') + ')' : ''}.</li>
  <li><b>External sources:</b> ${ext.independent_sources ?? 0} independent (${ext.raw_items ?? 0} items; reposts counted once)${ext.adapters_configured === false ? ' - no external adapters configured' : ''}.</li>
  <li><b>Weather:</b> ${w.relevant ? (w.available ? `rain, last days (mm): ${esc((w.precip_mm_last_days || []).join(', '))}${w.heavy_rain ? ' - heavy rain' : ''}` : 'unavailable') : 'not relevant or pending'}</li>
  <li><b>Street View history:</b> ${sv.available ? `imagery ${esc(sv.imagery_date || '')} (historical context only)` : 'not available'}</li></ul></div>
  <div class="card"><h3 style="margin-top:0">Why it was routed here</h3><div class="sm">Level: <b>${esc(c.gov_level)}</b> - confidence: <b>${esc((c.routing || {}).confidence)}</b>${(c.routing || {}).fallback ? ' <span class="chip sev-High">fallback - verify jurisdiction</span>' : ''}<ol style="padding-left:18px;margin-bottom:0">${((c.routing || {}).steps || []).map(s => `<li>${esc(s)}</li>`).join('')}</ol></div></div>`;
}
async function deptDetail(code) {
  const admin = S.role === 'super_admin';
  const c = await api((admin ? '/api/admin/complaints/' : '/api/dept/complaints/') + encodeURIComponent(code));
  const fos = admin ? [] : await api('/api/dept/field-officers').catch(() => []);
  const tag = m => (m.kind === 'photo' ? `<img data-mid="${m.id}" alt="">` : `<video data-mid="${m.id}" controls playsinline></video>`) + `<div class="mute xs">${m.role} - ${m.lat != null ? m.lat.toFixed(5) + ', ' + m.lon.toFixed(5) : 'no GPS'} - ${fmt(m.captured_at)}<br>sha256 ${esc((m.sha256 || '').slice(0, 12))}…</div>`;
  const orig = c.media.filter(m => m.role === 'original'), proof = c.media.filter(m => m.role === 'resolution');
  const can = !admin && c.allowed_next.length;
  $('#app').innerHTML = `<p style="margin:0"><a href="${admin ? '#/admin/complaints' : '#/dept'}" class="row" style="gap:4px;text-decoration:none">${ic('back', 18)}Back</a></p>
  <div class="row" style="margin:6px 0"><h1 class="grow mono" style="margin:0">${esc(c.code)}</h1>${chipSev(c.severity)} ${chipSt(c.status)}</div>
  <div class="mute">${esc(c.category)} - ${esc(c.department)} - received ${fmt(c.created_at)}${c.reopen_count ? ` - reopened ${c.reopen_count}×` : ''}</div>
  ${admin ? `<p><a class="btn" href="#/ai/c/${esc(c.code)}">${ic('cpu', 18)}See how the AI handled this</a></p>` : ''}
  ${c.description ? `<div class="card"><b>Citizen's note:</b> “${esc(c.description)}”</div>` : ''}
  <div class="split"><div>
  <h2 style="margin-top:.6em">Original live media</h2><div class="mediaGrid">${orig.map(m => `<div>${tag(m)}</div>`).join('')}</div>
  <h2>Location</h2><div class="card"><div class="sm">${c.lat.toFixed(6)}, ${c.lon.toFixed(6)} - <b>${c.loc_source === 'gps' ? 'Automatic GPS' : 'Pinned by citizen'}</b> - captured ${fmt(c.captured_at)} - <a target="_blank" rel="noopener" href="https://www.openstreetmap.org/?mlat=${c.lat}&mlon=${c.lon}#map=18/${c.lat}/${c.lon}">Open map</a></div><div class="map" id="dmap"></div><p class="mute sm" style="margin:0">GPS and time are supporting information, not proof that media is unaltered.</p></div>
  ${evidencePanel(c)}
  ${proof.length ? `<h2>Resolution proof</h2><div class="mediaGrid">${proof.map(m => `<div>${tag(m)}</div>`).join('')}</div>` : ''}</div>
  <div class="stick"><h2 style="margin-top:.6em">${admin ? 'Read-only view' : 'Actions'}</h2><div class="card" id="actions">${can ? `
    <div class="row">${c.allowed_next.filter(s => !CLOSED.includes(s)).map(s => `<button data-st="${esc(s)}">${esc(s)}</button>`).join('')}</div>
    <label for="fo">Field officer <span class="mute sm">(needed for “Field Officer Assigned”)</span></label><select id="fo"><option value="">Select…</option>${fos.map(f => `<option value="${f.id}">${esc(f.name)}</option>`).join('')}</select>
    <label for="rem">Remarks</label><textarea id="rem" placeholder="Visible in the complaint history"></textarea><label class="row" style="font-weight:400"><input type="checkbox" id="vis" checked> Show these remarks to the citizen</label>
    <div class="row" style="margin-top:8px"><button id="addrem">Add remark only</button></div>
    <h3>Resolution proof</h3><input type="file" id="rf" accept="image/*,video/*" multiple><div class="row" style="margin-top:8px"><button id="uprf">Upload proof</button></div>
    <div class="row" style="margin-top:16px">${c.allowed_next.includes('Resolved') ? '<button class="primary grow" data-st="Resolved">Mark resolved</button>' : ''}${c.allowed_next.includes('Rejected') ? '<button class="danger grow" data-st="Rejected">Reject (remarks required)</button>' : ''}</div>` : `<p class="mute" style="margin:0">${admin ? 'Super Admin can view and re-route; department officers act on complaints.' : 'This complaint is closed. The citizen can reopen it if the problem persists.'}</p>`}</div>
  <h2>History</h2><div class="card"><ul class="timeline">${[...c.timeline].reverse().map(t => `<li><div class="t">${esc(t.status)} ${t.citizen_visible ? '' : '<span class="chip">internal</span>'}</div>${t.note ? `<div class="sm">${esc(t.note)}</div>` : ''}<div class="mute xs">${esc(t.actor)} - ${fmt(t.created_at)}</div></li>`).join('')}</ul></div></div></div>`;
  fillMedia($('#app'));
  if (typeof L !== 'undefined') { const m = L.map('dmap').setView([c.lat, c.lon], 17); L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap contributors' }).addTo(m); L.marker([c.lat, c.lon]).addTo(m); setTimeout(() => m.invalidateSize(), 100); } else $('#dmap').remove();
  const act = async fn => { try { await fn(); deptDetail(code); } catch (e) { toast(e.message); } };
  $('#app').querySelectorAll('[data-st]').forEach(b => b.onclick = () => act(() => api(`/api/dept/complaints/${code}/status`, { method: 'POST', json: { status: b.dataset.st, remarks: $('#rem').value, field_officer_id: $('#fo').value ? +$('#fo').value : null, visible: $('#vis').checked } })));
  const ar = $('#addrem'); if (ar) ar.onclick = () => act(() => api(`/api/dept/complaints/${code}/remarks`, { method: 'POST', json: { remarks: $('#rem').value, visible: $('#vis').checked } }));
  const up = $('#uprf'); if (up) up.onclick = () => act(async () => {
    const fl = [...$('#rf').files]; if (!fl.length) throw new Error('Choose photo or video files first');
    const f = new FormData(); f.append('remarks', $('#rem').value); fl.forEach(x => f.append(x.type.startsWith('video') ? 'video' : 'photo', x));
    await api(`/api/dept/complaints/${code}/resolution`, { method: 'POST', form: f }); toast('Resolution proof uploaded');
  });
}

/* ---------- super admin ---------- */
async function adminHome(tab, arg) {
  const out = (title, h) => $('#app').innerHTML = `<h1>${title}</h1>${h}`;
  if (tab === 'overview') {
    const o = await api('/api/admin/overview');
    const crit = o.departments.reduce((a, d) => a + (d.critical_open || 0), 0);
    out('Platform overview', `<div class="grid g4"><div class="kpi"><b>${o.totals.n}</b><span>Total complaints</span></div><div class="kpi"><b>${o.totals.open_n || 0}</b><span>Open</span></div><div class="kpi sev-Critical"><b>${crit}</b><span>Critical and open</span></div><a class="kpi" href="#/admin/routing" style="text-decoration:none;color:inherit"><b>${o.low_confidence_routing.length}</b><span>Routing needs review</span></a></div>
    <h2>Departments</h2><div class="card">${o.departments.map(d => { const t = d.total || 0, op = d.open_count || 0, rs = d.resolved || 0; return `<a href="#/admin/complaints/${d.id}" style="display:block;text-decoration:none;color:inherit;padding:10px 0;border-bottom:1px solid var(--line)"><div class="row"><b class="grow">${esc(d.short)}${d.is_fallback ? ' <span class="chip">fallback</span>' : ''}</b><span class="mute sm">${t} total - ${op} open${d.critical_open ? ` - <b style="color:var(--crit)">${d.critical_open} critical</b>` : ''}</span></div><div class="split-bar" style="margin-top:6px" title="${rs} resolved, ${op} open"><i style="width:${t ? rs / t * 100 : 0}%;background:var(--ok)"></i><i style="width:${t ? op / t * 100 : 0}%;background:var(--ganga-2)"></i></div></a>`; }).join('')}<div class="mute xs" style="margin-top:8px">Bars: green resolved, blue open.</div></div>`);
  } else if (tab === 'complaints') {
    const [list, ov] = await Promise.all([api('/api/admin/complaints' + (arg ? '?dept_id=' + arg : '')), api('/api/admin/overview')]);
    out('All complaints', `<div class="card"><label for="fd" style="margin-top:0">Department</label><select id="fd"><option value="">All departments</option>${ov.departments.map(d => `<option value="${d.id}" ${String(d.id) === arg ? 'selected' : ''}>${esc(d.short)}</option>`).join('')}</select></div>
    ${list.length ? `<ul class="clist">${list.map(c => complaintRow(c, '#/d/' + esc(c.code), esc(c.department || '-') + ' - ')).join('')}</ul>` : empty('list', 'No complaints here yet')}`);
    $('#fd').onchange = e => location.hash = '#/admin/complaints' + (e.target.value ? '/' + e.target.value : '');
  } else if (tab === 'departments') {
    const o = await api('/api/admin/overview');
    out('Departments', `<div class="card scroll"><table><tr><th>Name</th><th>Short</th><th>Level</th><th>Functions</th><th>Jurisdiction</th></tr>${o.departments.map(d => `<tr><td>${esc(d.name)}</td><td>${esc(d.short)}</td><td>${esc(d.level)}</td><td>${esc(JSON.parse(d.functions).join(', '))}</td><td>${esc(d.jurisdiction)}</td></tr>`).join('')}</table></div>
    <h2>Add a department</h2><div class="card"><div class="grid g2"><div><label for="dn">Name</label><input id="dn"></div><div><label for="ds">Short code</label><input id="ds"></div><div><label for="dl">Government level</label><select id="dl"><option>local</option><option>state</option><option>central</option></select></div><div><label for="df">Functions (comma separated)</label><input id="df" placeholder="roads, drainage"></div><div><label for="dj">Jurisdiction</label><input id="dj"></div><div><label for="du">Officer username</label><input id="du" autocapitalize="none"></div><div><label for="dp">Officer password (min 8)</label><input id="dp" type="password" autocomplete="new-password"></div></div>
    <p class="field-note">Valid functions: roads, drainage, sanitation, lighting, water, traffic, public_spaces, general</p><button class="primary" id="dadd">Create department and officer account</button></div>`);
    $('#dadd').onclick = async () => { try { await api('/api/admin/departments', { method: 'POST', json: { name: $('#dn').value, short: $('#ds').value, level: $('#dl').value, functions: $('#df').value.split(',').map(s => s.trim()).filter(Boolean), jurisdiction: $('#dj').value, officer_username: $('#du').value, officer_password: $('#dp').value } }); toast('Department created'); adminHome('departments'); } catch (e) { toast(e.message); } };
  } else if (tab === 'routing') {
    const [z, o] = await Promise.all([api('/api/admin/zones'), api('/api/admin/overview')]);
    out('Routing', `<div class="notice">${ic('alert')}<div>Zones below are <b>illustrative placeholders</b> for the Varanasi pilot. Replace them with surveyed road-ownership and jurisdiction data before real use.</div></div>
    <h2>Needs routing review</h2><div class="card">${o.low_confidence_routing.length ? o.low_confidence_routing.map(c => `<div class="row" style="margin:8px 0"><a class="grow" href="#/d/${esc(c.code)}"><b class="mono">${esc(c.code)}</b> - ${esc(c.category)} ${chipSev(c.severity)}</a><select data-r="${esc(c.code)}" style="width:auto" aria-label="Reassign ${esc(c.code)}"><option value="">Reassign to…</option>${o.departments.filter(d => !d.is_fallback).map(d => `<option value="${d.id}">${esc(d.short)}</option>`).join('')}</select></div>`).join('') : '<span class="mute">Nothing pending.</span>'}</div>
    <h2>Jurisdiction zones</h2><div class="card scroll"><table><tr><th>Name</th><th>Kind</th><th>Owner</th><th>Buffer</th><th>Categories</th></tr>${z.map(r => `<tr><td>${esc(r.name)}<div class="mute xs">${esc(r.note || '')}</div></td><td>${esc(r.kind)}</td><td>${esc(r.owner_level)}</td><td>${r.buffer_m} m</td><td>${esc(r.categories)}</td></tr>`).join('')}</table></div>`);
    $('#app').querySelectorAll('[data-r]').forEach(s => s.onchange = async () => { if (!s.value) return; try { await api(`/api/admin/complaints/${s.dataset.r}/reassign`, { method: 'POST', json: { dept_id: +s.value, reason: 'Manual routing review' } }); toast('Reassigned'); adminHome('routing'); } catch (e) { toast(e.message); } });
  } else if (tab === 'audit') {
    const [log, v] = await Promise.all([api('/api/admin/audit?limit=300'), api('/api/admin/audit/verify')]);
    out('Audit log', `<div class="${v.intact ? 'notice ok' : 'err'}">${ic(v.intact ? 'shield' : 'alert')}<div>Hash chain: <b>${v.intact ? 'intact' : 'BROKEN at entry ' + v.broken_at}</b> (${v.checked} entries checked). The log is append-only.</div></div><div class="card scroll"><table><tr><th>Time</th><th>Actor</th><th>Action</th><th>Complaint</th><th>Detail</th></tr>${log.map(a => `<tr><td class="xs">${fmt(a.ts)}</td><td>${esc(a.actor_name || a.actor_role)}</td><td><span class="chip">${esc(a.action)}</span></td><td class="mono">${esc(a.complaint_code || '')}</td><td class="sm">${esc(a.detail || '')}</td></tr>`).join('')}</table></div>`);
  }
}

/* ---------- Sudhaar AI monitor: replay exactly how the AI worked ---------- */
const STAGE_IC = { intake: 'inbox', vision: 'eye', internal: 'users', external: 'globe', weather: 'cloud', street_view: 'map', severity: 'alert', score: 'gauge', routing: 'map', forward: 'send', final: 'check', chatbot: 'chat', fallback: 'alert' };
const STATUS_LABEL = { ok: 'Done', warn: 'Done, with a warning', error: 'Failed', skipped: 'Skipped', running: 'Running…' };
function kv(o) {
  if (o == null || o === '') return '<span class="mute">-</span>';
  if (Array.isArray(o)) return o.length ? `<ul style="margin:0;padding-left:18px">${o.map(x => `<li>${typeof x === 'object' ? kv(x) : esc(x)}</li>`).join('')}</ul>` : '<span class="mute">none</span>';
  if (typeof o === 'object') { const e = Object.entries(o); return e.length ? `<dl class="kv">${e.map(([k, v]) => `<dt>${esc(k.replace(/_/g, ' '))}</dt><dd>${kv(v)}</dd>`).join('')}</dl>` : '<span class="mute">none</span>'; }
  return esc(o);
}
function stepCard(s, withCode) {
  const hasIn = s.inputs && Object.keys(s.inputs).length, hasOut = s.outputs && Object.keys(s.outputs).length;
  return `<div class="pstep ${esc(s.status)}"><div class="ph"><div class="cic">${ic(STAGE_IC[s.stage] || 'cpu', 18)}</div><div class="grow"><b>${esc(s.title)}</b>${withCode && s.complaint_code ? ` <a class="mono xs" href="#/ai/c/${esc(s.complaint_code)}">${esc(s.complaint_code)}</a>` : ''}<div class="xs mute">${STATUS_LABEL[s.status] || esc(s.status)} - ${fmtT(s.started_at)}</div></div><span class="ms">${s.duration_ms != null ? s.duration_ms + ' ms' : ''}</span></div>
  ${(s.notes || []).length ? `<ul class="notes">${s.notes.map(n => `<li>${esc(n)}</li>`).join('')}</ul>` : ''}
  ${hasIn ? `<details><summary class="sm">What it received</summary>${kv(s.inputs)}</details>` : ''}${hasOut ? `<details><summary class="sm">What it produced</summary>${kv(s.outputs)}</details>` : ''}</div>`;
}
async function aiHome(tab, arg) {
  if (tab === 'live') {
    const ov = await api('/api/ai/overview'), E = ov.engines;
    const eng = (on, name, hint) => `<div class="engine"><span class="dot ${on ? 'on' : 'off'}"></span><div><b class="sm">${name}</b><div class="xs mute">${on ? 'Connected' : hint}</div></div></div>`;
    $('#app').innerHTML = `<div class="row"><h1 class="grow" style="margin:0">AI live feed</h1><span class="live" id="lv"><i></i>Live</span><button id="pz">${ic('pause', 18)}Pause</button></div>
    <p class="mute sm">Every step the AI takes on a complaint, as it happens: what it received, what it decided, how long it took. Open a complaint to replay its whole pipeline.</p>
    <div class="grid g4"><div class="kpi"><b>${ov.runs}</b><span>Complaints processed</span></div><div class="kpi"><b id="runc">${ov.running}</b><span>Steps running now</span></div><div class="kpi"><b>${ov.stages.reduce((a, s) => a + (s.errors || 0), 0)}</b><span>Failed steps</span></div><div class="kpi"><b>${ov.chat_answers}</b><span>Chatbot answers</span></div></div>
    <h2>Engines</h2><div class="grid g3">${eng(E.claude_vision || (E.yolo && E.yolo.length), (E.yolo && E.yolo.length) ? 'Vision: YOLO (' + E.yolo.map(esc).join(' + ') + ')' : 'Vision: Claude' + (E.claude_model ? ' (' + E.claude_model + ')' : ''), 'Set SUDHAAR_YOLO_MODELS or ANTHROPIC_API_KEY')}${eng(E.news, 'News search', 'Set NEWSAPI_KEY')}${eng(E.weather, 'Weather (Open-Meteo)', E.offline ? 'Offline mode' : 'Unavailable')}${eng(E.street_view, 'Street View history', 'Set GOOGLE_MAPS_KEY')}</div>
    ${E.offline ? `<div class="notice info" style="margin-top:12px">${ic('alert')}<div>Server is in offline mode: external lookups are skipped.</div></div>` : ''}
    <h2>Latest steps</h2><div id="feed"></div>`;
    let paused = false, sig = '';
    const draw = async () => {
      if (paused) return;
      try {
        const r = await api('/api/ai/feed'); const s2 = JSON.stringify(r.steps.map(x => [x.id, x.status, x.duration_ms]));
        $('#runc').textContent = r.running;
        if (s2 !== sig) { sig = s2; $('#feed').innerHTML = r.steps.length ? `<div class="pipe">${[...r.steps].reverse().map(s => stepCard(s, true)).join('')}</div>` : empty('cpu', 'No AI activity yet', 'Submit a complaint as a citizen and watch each step appear here.'); }
      } catch { }
    };
    $('#pz').onclick = () => { paused = !paused; $('#pz').innerHTML = paused ? `${ic('play', 18)}Resume` : `${ic('pause', 18)}Pause`; $('#lv').classList.toggle('off', paused); $('#lv').lastChild.textContent = paused ? 'Paused' : 'Live'; if (!paused) draw(); };
    await draw(); timers.push(setInterval(draw, 2500));
  } else if (tab === 'runs') {
    const runs = await api('/api/ai/runs');
    $('#app').innerHTML = `<h1>Complaint runs</h1><p class="mute sm">One row per complaint the AI pipeline has processed. Open one to replay it step by step.</p>${runs.length ? `<ul class="clist">${runs.map(r => `<li><a class="citem sev-${esc(r.severity || '')}" href="#/ai/c/${esc(r.code)}"><div class="row" style="flex-wrap:nowrap"><div class="cic">${catIc(r.category)}</div><div class="grow"><b class="mono">${esc(r.code)}</b><div class="sm">${esc(r.category || '')}</div><div class="mute xs">${r.steps} steps - ${r.total_ms ?? 0} ms - ${ago(r.started)}${r.errors ? ` - <b style="color:var(--crit)">${r.errors} failed</b>` : ''}${r.warns ? ` - ${r.warns} warning(s)` : ''}${r.running ? ' - running…' : ''}</div></div><div style="display:grid;gap:4px;justify-items:end">${chipSev(r.severity)}<span class="mute xs">${r.validity_score != null ? 'evidence ' + Number(r.validity_score).toFixed(1) : ''}</span></div></div></a></li>`).join('')}</ul>` : empty('activity', 'No runs yet', 'Complaints appear here after a citizen submits one.')}`;
  } else if (tab === 'chat') {
    const rows = await api('/api/ai/chat');
    $('#app').innerHTML = `<h1>Chatbot answers</h1><p class="mute sm">Questions the helper chatbot received and which rule answered them. Messages are shown exactly as typed; no account is attached.</p>${rows.length ? `<div class="pipe">${rows.map(s => stepCard(s, false)).join('')}</div>` : empty('chat', 'No chatbot questions yet', 'Use the ? button on any page to ask one.')}`;
  } else if (tab === 'c' && arg) {
    const load = async () => {
      const d = await api('/api/ai/complaints/' + encodeURIComponent(arg)), c = d.complaint, st = d.steps;
      const total = st.reduce((a, s) => a + (s.duration_ms || 0), 0), running = st.some(s => s.status === 'running');
      const orig = c.media.filter(m => m.role === 'original');
      $('#app').innerHTML = `<p style="margin:0"><a href="#/ai/runs" class="row" style="gap:4px;text-decoration:none">${ic('back', 18)}All runs</a></p>
      <div class="row" style="margin:6px 0"><h1 class="grow mono" style="margin:0">${esc(c.code)}</h1>${chipSev(c.severity)} ${chipSt(c.status)}${running ? '<span class="live"><i></i>Running</span>' : ''}</div>
      <div class="mute">${esc(c.category)} - ${esc(c.department || 'no department yet')} - evidence ${c.validity_score != null ? Number(c.validity_score).toFixed(1) + '/10' : 'pending'}</div>
      ${orig.length ? `<div class="mediaGrid" style="margin-top:12px;grid-template-columns:repeat(auto-fit,minmax(160px,220px))">${orig.map(m => m.kind === 'photo' ? `<img data-mid="${m.id}" alt="citizen evidence">` : `<video data-mid="${m.id}" controls playsinline></video>`).join('')}</div>` : ''}
      <h2>AI pipeline replay <span class="mute sm">${st.length} steps, ${total} ms of work</span></h2>
      ${st.length ? `<div class="pipe">${st.map(s => stepCard(s, false)).join('')}</div>` : empty('cpu', 'No trace for this complaint', 'It may have been submitted before AI tracing was added.')}`;
      fillMedia($('#app')); return running;
    };
    if (await load()) timers.push(setInterval(async () => { try { if (!(await load())) { timers.forEach(clearInterval); timers = []; } } catch { } }, 2500));
  }
}

/* ---------- helper chatbot ---------- */
(() => {
  const log = $('#chat-log'), inp = $('#chat-input'); let spoke = false;
  const add = (t, c) => { const d = Object.assign(document.createElement('div'), { className: 'msg ' + c, textContent: t }); log.append(d); log.scrollTop = log.scrollHeight; return d; };
  const typing = () => { const d = document.createElement('div'); d.className = 'msg tp'; d.setAttribute('aria-label', 'Sahayak is typing'); d.innerHTML = '<i></i><i></i><i></i>'; log.append(d); log.scrollTop = log.scrollHeight; return d; };
  const SUGG = ['How do I report a problem?', 'How do I track my complaint?', 'Is my mobile number private?'];
  const welcome = () => { add('Namaste! I am Sahayak. Ask me how to report, track a complaint, or about privacy. Hindi, English and Hinglish all work.', 'b');
    const c = document.createElement('div'); c.className = 'sugg'; SUGG.forEach(q => { const b = document.createElement('button'); b.type = 'button'; b.textContent = q; b.onclick = () => { c.remove(); inp.value = q; send(); }; c.append(b); }); log.append(c); };
  document.addEventListener('click', e => { if (!e.target.closest('#chat-fab')) return; const c = $('#chat'); c.hidden = !c.hidden; if (!c.hidden) inp.focus(); if (!log.children.length) welcome(); });
  $('#chat-x').onclick = () => $('#chat').hidden = true;
  const send = async () => {
    const m = inp.value.trim(); if (!m) return; inp.value = ''; add(m, 'u'); const sg = $('.sugg', log); if (sg) sg.remove();
    const t = typing();
    try { const r = await api('/api/chat', { method: 'POST', json: { message: m } }); t.remove(); add(r.reply, 'b'); if (spoke && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(r.reply); u.lang = r.lang === 'hi' ? 'hi-IN' : 'en-IN'; speechSynthesis.speak(u); } } catch { t.remove(); add('Sorry, I could not reach the server.', 'b'); }
    spoke = false;
  };
  $('#chat-send').onclick = send; inp.onkeydown = e => { if (e.key === 'Enter') send(); };   // never `return false` from a key handler: it blocks typing
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) $('#chat-mic').hidden = true;
  else $('#chat-mic').onclick = () => { const r = new SR(); r.lang = 'hi-IN'; r.onresult = e => { inp.value = e.results[0][0].transcript; spoke = true; send(); }; r.onerror = () => toast('Voice input failed'); r.start(); };
})();


/* ---------- public information pages ---------- */
const pageTitle = h => {
  const t = { '#/': 'Report. Resolve. Improve.', '#/login': 'Log in', '#/staff': 'Staff login', '#/about': 'About', '#/privacy': 'Privacy and data', '#/accessibility': 'Accessibility', '#/home': 'My complaints', '#/report': 'Report a problem', '#/alerts': 'Alerts' };
  const k = h.startsWith('#/about') ? '#/about' : h;
  return (t[k] ? t[k] + ' | ' : '') + 'Sudhaar';
};
const faq = (q, a) => `<details><summary>${q}</summary><p>${a}</p></details>`;
const FAQS = [
  ['Do I need an account?', 'You log in with your 10-digit mobile number and a one-time password. There is nothing to install and no password to remember.'],
  ['Why can I not upload a photo from my gallery?', 'Live capture proves the problem exists right now, at that place. Sudhaar stamps the location, date and time on every photo or video, so departments can trust the evidence.'],
  ['Who can see my name and mobile number?', 'Departments never receive your mobile number or name. They see the complaint, the evidence and the location only.'],
  ['How is the department chosen?', 'Sudhaar uses the category and the exact location to decide who owns the road, drain or pipe: a municipal, state or national authority. If it is not sure, the complaint goes to a general grievance desk and is flagged for an administrator to check.'],
  ['What does the AI do?', 'It helps with checking evidence, finding duplicate reports and rating severity. People at the department decide and act. Scores are internal and are not shown to citizens.'],
  ['What if I have no internet when I submit?', 'The complaint is saved on your device and uploaded automatically when the connection returns. It is only shown as submitted after the server confirms it.'],
  ['What if the problem is not really fixed?', 'When a department marks a complaint as resolved you can confirm it, or reopen it with fresh proof.'],
  ['Is Sudhaar an emergency service?', `No. For fire, police or medical emergencies call <b>${esc(SITE.emergency)}</b> immediately.`],
  ['Which languages does the help chat understand?', 'English, Hindi and Hinglish. Voice input works where your browser supports it.']
];
const DEPTS = [
  ['VMC-ENG', 'local', 'Varanasi Municipal Corporation - Roads and Engineering'], ['VMC-DRN', 'local', 'Varanasi Municipal Corporation - Drainage and Sewerage'],
  ['VMC-SAN', 'local', 'Varanasi Municipal Corporation - Sanitation'], ['VMC-LGT', 'local', 'Varanasi Municipal Corporation - Street Lighting and Electrical'],
  ['VMC-PUB', 'local', 'Varanasi Municipal Corporation - Parks and Public Spaces'], ['JAL', 'local', 'Jal Sansthan Varanasi - Water Supply'],
  ['VTP', 'state', 'Varanasi Traffic Police'], ['UPPWD', 'state', 'UP Public Works Department - Varanasi Division'],
  ['NHAI', 'central', 'NHAI - Varanasi Project Implementation Unit']
];
const LEVEL = { local: 'Municipal', state: 'State', central: 'National' };
function openChat() { const f = $('#chat-fab'); if (f) f.click(); }
function contactBlock() {
  const rows = [SITE.operator && `<p>${ic('building', 18)} <b>${esc(SITE.operator)}</b></p>`, SITE.email && `<p>${ic('send', 18)} <a href="mailto:${esc(SITE.email)}">${esc(SITE.email)}</a></p>`,
    SITE.phone && `<p>${ic('help', 18)} <a href="tel:${esc(SITE.phone.replace(/\s/g, ''))}">${esc(SITE.phone)}</a></p>`, SITE.hours && `<p>${ic('clock', 18)} ${esc(SITE.hours)}</p>`].filter(Boolean).join('');
  return `<div class="contact-grid"><div class="card" style="margin:0"><h3 style="margin-top:0">Get help</h3><p class="mute">The Help chat answers questions about reporting, tracking and privacy in English, Hindi and Hinglish.</p><button class="primary" data-open-chat>${ic('chat', 18)}Open Help chat</button></div>
    <div class="card" style="margin:0"><h3 style="margin-top:0">Contact the operator</h3>${rows || '<p class="mute">Contact details will be published here by the operating authority before public launch.</p>'}</div></div>`;
}
function pageShell(kicker, title, lede) { return `<section class="page-hero"><span class="kicker">${kicker}</span><h1>${title}</h1><p>${lede}</p></section>`; }
function about(sec) {
  const SEC = [['mission', 'Mission'], ['how', 'How it works'], ['report', 'What you can report'], ['who', 'Who responds'], ['trust', 'Trust and privacy'], ['faq', 'FAQ'], ['contact', 'Contact']];
  $('#app').innerHTML = `${pageShell('About Sudhaar', 'Civic problems, fixed in the open.', 'Sudhaar is a civic grievance platform. A citizen reports with one live photo; Sudhaar checks it, sends it to the department that owns the problem, and keeps the citizen informed until it is fixed.')}
  <nav class="pills" aria-label="On this page">${SEC.map(([k, l]) => `<button type="button" data-s="${k}">${l}</button>`).join('')}</nav>
  <section class="section" id="s-mission"><div class="section-head"><div><span class="kicker">Mission</span><h2>Why we built Sudhaar</h2></div></div>
    <div class="prose"><p>Civic problems rarely stay unresolved because nobody cares. They stall because reports arrive without proof, land with the wrong department, or disappear without a trace.</p>
    <p>Sudhaar fixes that chain. Evidence is captured live so it can be trusted. The location decides who is responsible. Every step is visible to the citizen, and every action is recorded in an audit trail.</p></div>
    <div class="feat-grid" style="margin-top:18px">${FEATURES.slice(0, 3).map(f => feat(...f)).join('')}</div></section>
  <section class="section" id="s-how"><div class="section-head"><div><span class="kicker">How it works</span><h2>From photo to fix</h2></div></div>
    <div class="steps3" style="margin-top:22px"><div class="step3"><h3>Report</h3><p>Choose a category, take a live photo or video, and confirm the pin on the map. Add a short note if you like.</p></div>
    <div class="step3"><h3>Resolve</h3><p>Sudhaar checks the evidence, finds the responsible department and forwards it. Officers acknowledge, assign a field officer and work on it.</p></div>
    <div class="step3"><h3>Improve</h3><p>The department uploads proof of the fix. You confirm it, or reopen it with fresh proof if the problem remains.</p></div></div>
    <div class="card"><h3 style="margin-top:0">The seven stages of a complaint</h3>${lifecycle()}</div></section>
  <section class="section" id="s-report"><div class="section-head"><div><span class="kicker">Categories</span><h2>What you can report</h2></div></div>${catTiles()}</section>
  <section class="section" id="s-who"><div class="section-head"><div><span class="kicker">Responsibility</span><h2>Who responds</h2><p>Sudhaar sends each complaint to the authority that owns that road, drain or pipe at that location.</p></div></div>
    <ul class="dept-list">${DEPTS.map(([c, l, n]) => `<li><span class="tag ${l}">${LEVEL[l]}</span><div><b>${n}</b><div class="mono mute">${c}</div></div></li>`).join('')}</ul>
    <div class="notice info" style="margin-top:16px">${ic('alert')}<div><b>Pilot notice.</b> Jurisdiction maps are being verified for ${esc(SITE.city)}. If a complaint is routed wrongly, an administrator can reassign it.</div></div></section>
  <section class="section" id="s-trust"><div class="section-head"><div><span class="kicker">Trust</span><h2>Evidence you can rely on, data you can trust us with</h2></div></div>
    <div class="feat-grid">${[FEATURES[0], FEATURES[2], FEATURES[4]].map(f => feat(...f)).join('')}${feat('log', 'Tamper-evident audit trail', 'Views, downloads, status changes and uploads are written to an append-only, hash-chained log.')}</div>
    <p style="margin-top:14px"><a href="#/privacy">Read the privacy and data page</a></p></section>
  <section class="section" id="s-faq"><div class="section-head"><div><span class="kicker">Questions</span><h2>Frequently asked</h2></div></div><div class="faq">${FAQS.map(([q, a]) => faq(q, a)).join('')}</div></section>
  <section class="section" id="s-contact"><div class="section-head"><div><span class="kicker">Contact</span><h2>Need help?</h2></div></div>${contactBlock()}</section>
  <section class="cta-band"><div><h2>Ready to report a problem?</h2><p>It takes one live photo.</p></div><a class="btn accent" href="${S.token && S.role === 'citizen' ? '#/report' : '#/login'}">${ic('camera', 22)}Report a problem</a></section>`;
  const scrollTo = k => { const el = $('#s-' + k); if (el) el.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion:reduce)').matches ? 'auto' : 'smooth', block: 'start' }); };
  $$('.pills button').forEach(b => b.onclick = () => { $$('.pills button').forEach(x => x.classList.toggle('on', x === b)); scrollTo(b.dataset.s); });
  if (sec && SEC.some(([k]) => k === sec)) setTimeout(() => { scrollTo(sec); const b = $(`.pills button[data-s="${sec}"]`); if (b) b.classList.add('on'); }, 60);
}
function privacy() {
  const who = [['Citizen (you)', 'Your own complaints, photos, videos and their status history.'], ['Department officer', 'Complaints routed to their department, the evidence and the location. Never your mobile number or name.'],
    ['Platform administrator', 'All complaints, routing and the audit log, for oversight.'], ['Sudhaar AI monitor', 'A read-only record of each automated step. No access to citizen identity.']];
  $('#app').innerHTML = `${pageShell('Privacy and data', 'Your data, plainly explained.', 'What Sudhaar collects, who can see it, and how it is protected.')}
  <div class="prose">
  <section class="section"><h2>What we collect</h2><ul><li><b>Mobile number</b>, only to log you in with a one-time password.</li><li><b>Photos and videos</b> you capture, with the location, date and time stamped on them.</li><li><b>Your description</b> of the problem, if you add one.</li><li><b>Your complaints and their history</b>, so you can track them.</li></ul></section>
  <section class="section"><h2>Who can see what</h2><div class="card"><table><thead><tr><th>Who</th><th>What they can see</th></tr></thead><tbody>${who.map(([a, b]) => `<tr><td><b>${a}</b></td><td>${b}</td></tr>`).join('')}</tbody></table></div></section>
  <section class="section"><h2>How it is protected</h2><ul><li>Media is private. It is only served to signed-in users with permission, never through a public link.</li><li>Every view, download, status change and upload is written to an append-only, hash-chained audit log.</li><li>Uploads are checked on the server: file type, and a capture window that matches a live session.</li></ul></section>
  <section class="section"><h2>How long we keep it</h2><p>${SITE.retention ? esc(SITE.retention) : 'The retention period is set by the operating authority and will be published here before public launch.'}</p></section>
  <section class="section"><h2>Your choices</h2><ul><li>You can log out at any time. Signing out removes your session from this device.</li><li>Requests about your data go to the operating authority listed under Contact.</li></ul></section>
  </div><section class="section"><h2>Contact</h2>${contactBlock()}</section>`;
}
function accessibility() {
  $('#app').innerHTML = `${pageShell('Accessibility', 'Made to be usable by everyone.', 'Sudhaar aims to meet WCAG 2.1 level AA. Here is what is built in, and what to do if something does not work for you.')}
  <div class="feat-grid">${[['search', 'Adjustable text size', 'Use A-, A and A+ at the top of every page. Your choice is remembered on this device.'], ['eye', 'High contrast mode', 'Switch on Contrast for black text on white and strong outlines.'],
    ['list', 'Keyboard and screen readers', 'Every control can be reached with the keyboard. A skip link jumps to the main content, and controls have text labels.'], ['activity', 'Reduced motion', 'Animations switch off if your device asks for reduced motion.'],
    ['globe', 'Light and dark themes', 'Sudhaar follows your device setting.'], ['chat', 'Voice and chat help', 'The Help chat accepts typing or voice, in English, Hindi or Hinglish.']].map(f => feat(...f)).join('')}</div>
  <section class="section"><div class="section-head"><div><span class="kicker">Known limits</span><h2>Where we are still working</h2></div></div><div class="prose"><ul><li>Taking a photo needs a camera and a view of the problem. If you cannot do this, ask someone nearby to report on your behalf.</li><li>If the map is hard to use, you can type the latitude and longitude of the location instead.</li></ul></div></section>
  <section class="section"><div class="section-head"><div><span class="kicker">Feedback</span><h2>Tell us what is not working</h2></div></div>${contactBlock()}</section>`;
}

/* ---------- footer ---------- */
function skylinePath() {
  const pat = [[44, 'flat', 22], [30, 'dome', 30], [20, 'flat', 18], [36, 'spire', 56], [26, 'flat', 26], [34, 'dome', 36], [42, 'flat', 20], [30, 'spire', 44], [24, 'flat', 30], [40, 'dome', 28], [28, 'flat', 18], [38, 'spire', 62], [30, 'flat', 24], [34, 'dome', 32], [46, 'flat', 20], [26, 'spire', 40]];
  let d = 'M0 90V70', x = 0, i = 0;
  while (x < 1200) { const [w, t, h] = pat[i++ % pat.length], y = 90 - h;
    if (t === 'flat') d += `V${y}h${w}`; else if (t === 'dome') d += `V${y}q${w / 2} ${-w * .9} ${w} 0`; else d += `V${y}q${w * .1} ${-h * .5} ${w / 2} ${-h * .9}q${w * .4} ${h * .4} ${w / 2} ${h * .9}`;
    x += w; }
  return d + 'V90H0Z';
}
function renderFooter() {
  const f = $('#foot'); if (!f) return;
  const citizen = S.token && S.role === 'citizen';
  const contact = [SITE.operator && `<li>${esc(SITE.operator)}</li>`, SITE.email && `<li><a href="mailto:${esc(SITE.email)}">${esc(SITE.email)}</a></li>`, SITE.phone && `<li><a href="tel:${esc(SITE.phone.replace(/\s/g, ''))}">${esc(SITE.phone)}</a></li>`, SITE.hours && `<li>${esc(SITE.hours)}</li>`].filter(Boolean).join('');
  f.innerHTML = `<svg class="skyline" viewBox="0 0 1200 90" preserveAspectRatio="none" aria-hidden="true"><path fill="currentColor" d="${skylinePath()}"/></svg>
  <div class="slab"><div class="wrap"><div class="cols">
    <div><div class="fbrand">${MARK}<span><b>सुधार · Sudhaar</b><small>Report. Resolve. Improve.</small></span></div>
      <p>A civic grievance platform: report with one live photo, and follow it to the fix. Pilot city: ${esc(SITE.city)}.</p>
      <div class="emg">${ic('alert', 20)}<span>Sudhaar is not an emergency service. In an emergency call <b>${esc(SITE.emergency)}</b>.</span></div></div>
    <div><h4>Citizens</h4><ul><li><a href="${citizen ? '#/report' : '#/login'}">Report a problem</a></li><li><a href="${citizen ? '#/home' : '#/login'}">My complaints</a></li><li><a href="#/about/how">How it works</a></li><li><a href="#/about/faq">FAQ</a></li></ul></div>
    <div><h4>Information</h4><ul><li><a href="#/about">About Sudhaar</a></li><li><a href="#/privacy">Privacy and data</a></li><li><a href="#/accessibility">Accessibility</a></li><li><a href="#/staff">Staff login</a></li></ul></div>
    <div><h4>Contact</h4><ul>${contact || '<li>Published by the operating authority.</li>'}<li><a href="#" data-open-chat>Open Help chat</a></li></ul></div>
  </div><div class="bottom"><span>&copy; ${new Date().getFullYear()} Sudhaar. A pilot civic-tech platform.</span><span>Made for the people of ${esc(SITE.city.split(',')[0])}</span></div></div></div><div class="tri"></div>`;
}

/* ---------- user preferences: text size, contrast, connectivity ---------- */
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
function initPrefs() {
  const get = k => { try { return localStorage.getItem(k); } catch { return null; } }, set = (k, v) => { try { localStorage.setItem(k, v); } catch { } };
  const root = document.documentElement;
  const applyFs = v => { v = Math.min(1.3, Math.max(.9, v)); root.style.setProperty('--fs', v); set('sdh_fs', v); return v; };
  let fs = applyFs(parseFloat(get('sdh_fs')) || 1);
  $('#fs-dec').onclick = () => fs = applyFs(+(fs - .1).toFixed(2)); $('#fs-inc').onclick = () => fs = applyFs(+(fs + .1).toFixed(2)); $('#fs-reset').onclick = () => fs = applyFs(1);
  const hc = $('#hc'), applyHc = on => { if (on) root.dataset.contrast = 'high'; else delete root.dataset.contrast; hc.setAttribute('aria-pressed', String(on)); set('sdh_hc', on ? '1' : '0'); };
  applyHc(get('sdh_hc') === '1'); hc.onclick = () => applyHc(hc.getAttribute('aria-pressed') !== 'true');
  const net = $('#net'), upd = () => { net.hidden = navigator.onLine; }; window.addEventListener('online', upd); window.addEventListener('offline', upd); upd();
  document.addEventListener('click', e => { const o = e.target.closest('[data-open-chat]'); if (o) { e.preventDefault(); openChat(); } });
}
initPrefs();

route();
