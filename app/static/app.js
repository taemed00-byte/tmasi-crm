/* ══════════════════════════════════════════════════════════
   TMASI CRM Application — Main JS
   ══════════════════════════════════════════════════════════ */

'use strict';

// ── State ─────────────────────────────────────────────────
const State = {
  token: null, user: null, currentView: 'whatsapp',
  waLines: [], selectedLineId: null,
  conversations: [], selectedConvId: null, selectedConv: null,
  patients: [], selectedPatientId: null,
  doctors: [], clinics: [], appointments: [],
  calWeekOffset: 0, noteMode: false, convFilter: 'open',
};

// ── API ────────────────────────────────────────────────────
async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (State.token) headers['Authorization'] = `Bearer ${State.token}`;
  const resp = await fetch(path, { ...options, headers });
  if (resp.status === 401) { doLogout(); return null; }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  if (resp.status === 204) return null;
  return resp.json();
}

async function apiForm(path, formData) {
  const headers = {};
  if (State.token) headers['Authorization'] = `Bearer ${State.token}`;
  const resp = await fetch(path, { method: 'POST', headers, body: formData });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || 'Upload failed');
  }
  return resp.json();
}

// ── Toast ──────────────────────────────────────────────────
function toast(msg, type) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'show' + (type ? ' ' + type : '');
  setTimeout(() => { el.className = ''; }, 3200);
}

// ── Horizontal scroll reset ────────────────────────────────
function resetHScroll() {
  const y = window.scrollY;
  document.documentElement.scrollLeft = 0;
  document.body.scrollLeft = 0;
  const ws = document.getElementById('workspace');
  if (ws) ws.scrollLeft = 0;
  const wa = document.getElementById('waWorkspace');
  if (wa) wa.scrollLeft = 0;
  window.scrollTo(0, y);
}

window.addEventListener('scroll', function() {
  if (window.scrollX !== 0) resetHScroll();
}, { passive: true });

// ── Auth ───────────────────────────────────────────────────
async function doLogin(e) {
  e.preventDefault();
  const username = document.getElementById('loginUsername').value.trim();
  const password = document.getElementById('loginPassword').value;
  const errEl = document.getElementById('loginError');
  errEl.textContent = '';
  try {
    const resp = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!resp.ok) throw new Error('Invalid credentials');
    const data = await resp.json();
    State.token = data.access_token;
    State.user = data.user;
    localStorage.setItem('tmasi_token', State.token);
    showApp();
  } catch (err) {
    errEl.textContent = err.message || 'Login failed';
  }
}

async function restoreSession() {
  const saved = localStorage.getItem('tmasi_token');
  if (!saved) return false;
  State.token = saved;
  try {
    State.user = await api('/api/auth/me');
    if (State.user) return true;
  } catch(e) {}
  State.token = null;
  localStorage.removeItem('tmasi_token');
  return false;
}

function doLogout() {
  State.token = null; State.user = null;
  localStorage.removeItem('tmasi_token');
  fetch('/api/auth/logout', { method: 'POST' }).catch(() => {});
  document.getElementById('app').classList.add('hidden');
  document.getElementById('loginScreen').classList.remove('hidden');
}

async function showApp() {
  document.getElementById('loginScreen').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');
  document.getElementById('sidebarUsername').textContent = State.user && (State.user.full_name || State.user.username) || 'User';
  document.getElementById('sidebarRole').textContent = formatRole(State.user && State.user.role);
  resetHScroll();
  await loadWaLines();
  switchView('whatsapp');
}

function formatRole(r) {
  if (!r) return '';
  return r.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
}

// ── Navigation ─────────────────────────────────────────────
function switchView(view) {
  State.currentView = view;
  document.querySelectorAll('.view').forEach(function(v) { v.classList.remove('active'); });
  document.querySelectorAll('.nav-item').forEach(function(n) { n.classList.remove('active'); });
  var viewEl = document.getElementById(view + 'View');
  if (viewEl) viewEl.classList.add('active');
  var navEl = document.querySelector('[data-view="' + view + '"]');
  if (navEl) navEl.classList.add('active');
  resetHScroll();
  if (view === 'whatsapp') loadWaLines();
  else if (view === 'patients') loadPatients();
  else if (view === 'calendar') renderCalendar();
  else if (view === 'bookings') loadBookings();
  else if (view === 'doctors') loadDoctors();
  else if (view === 'clinics') loadClinics();
  else if (view === 'users') loadUsers();
  else if (view === 'cases') loadCases();
  else if (view === 'finance') { loadInvoices(); loadFinanceKpis(); }
  else if (view === 'reports') loadReports();
}

// ── WhatsApp Lines ─────────────────────────────────────────
async function loadWaLines() {
  try {
    var lines = await api('/api/whatsapp/lines');
    State.waLines = lines || [];
    renderWaRail();
    if (State.waLines.length > 0 && !State.selectedLineId) {
      selectWaLine(State.waLines[0].id);
    } else if (State.selectedLineId) {
      loadConversations(State.selectedLineId);
    }
  } catch(err) { console.error('WA lines:', err); }
}

function renderWaRail() {
  var rail = document.getElementById('waRail');
  rail.innerHTML = '';
  State.waLines.forEach(function(line) {
    var btn = document.createElement('button');
    btn.className = 'wa-line-btn' + (line.id === State.selectedLineId ? ' active' : '');
    btn.title = line.label + '\n' + (line.display_phone_number || '');
    btn.innerHTML = '<div class="wa-line-badge">' + escHtml(line.short_code || '??') + '</div><div class="wa-line-count">' + (line.open_count || 0) + '</div>';
    btn.addEventListener('click', function() { selectWaLine(line.id); });
    rail.appendChild(btn);
  });
}

function selectWaLine(lineId) {
  State.selectedLineId = lineId;
  State.selectedConvId = null;
  State.selectedConv = null;
  renderWaRail();
  loadConversations(lineId);
  showEmptyState();
  resetHScroll();
}

// ── Conversations ──────────────────────────────────────────
async function loadConversations(lineId) {
  var listEl = document.getElementById('convItems');
  listEl.innerHTML = '<div class="loading">Loading…</div>';
  var search = (document.getElementById('convSearch') && document.getElementById('convSearch').value) || '';
  try {
    var result = await api('/api/whatsapp/conversations?line_id=' + lineId + '&status=' + State.convFilter + '&search=' + encodeURIComponent(search) + '&limit=100');
    State.conversations = (result && result.items) || [];
    renderConversationList();
  } catch(err) {
    listEl.innerHTML = '<div class="error-msg">' + escHtml(err.message) + '</div>';
  }
}

function renderConversationList() {
  var listEl = document.getElementById('convItems');
  var line = State.waLines.find(function(l) { return l.id === State.selectedLineId; });
  document.getElementById('convListTitle').textContent = (line && line.label) || 'Conversations';
  if (!State.conversations.length) {
    listEl.innerHTML = '<div class="loading">No conversations</div>';
    return;
  }
  listEl.innerHTML = '';
  State.conversations.forEach(function(conv) {
    var el = document.createElement('div');
    el.className = 'conv-item' + (conv.id === State.selectedConvId ? ' active' : '');
    var name = conv.patient_name || conv.customer_name || conv.customer_phone || conv.customer_whatsapp_id;
    var initials = getInitials(name);
    var timeStr = conv.last_message_at ? relTime(conv.last_message_at) : '';
    var patientBadge = conv.has_patient_file ? '<span class="badge badge-patient">📋</span>' : '';
    var priorityBadge = conv.priority === 'urgent' ? '<span class="badge badge-urgent">Urgent</span>' : conv.priority === 'high' ? '<span class="badge badge-high">High</span>' : '';
    var unreadBadge = conv.unread_count > 0 ? '<span class="badge-unread">' + conv.unread_count + '</span>' : '';
    el.innerHTML = '<div class="conv-avatar">' + escHtml(initials) + '</div><div class="conv-info"><div class="conv-name-row"><span class="conv-name">' + escHtml(name) + '</span><span class="conv-time">' + timeStr + '</span></div><div class="conv-preview-row"><span class="conv-preview">' + escHtml(conv.last_message_preview || '') + '</span><div class="conv-badges">' + patientBadge + priorityBadge + unreadBadge + '</div></div></div>';
    el.addEventListener('click', function(ev) {
      ev.stopPropagation();
      openConversation(conv.id);
    });
    listEl.appendChild(el);
  });
}

// ── Open Conversation ──────────────────────────────────────
async function openConversation(convId) {
  State.selectedConvId = convId;
  renderConversationList();
  var caseDetail = document.getElementById('caseDetail');
  caseDetail.classList.remove('empty-state');
  document.getElementById('chatHeader').innerHTML = '<span style="padding:0 14px;color:#999">Loading…</span>';
  document.getElementById('chatBody').innerHTML = '<div class="loading">Loading messages…</div>';
  resetHScroll();
  try {
    var conv = await api('/api/whatsapp/conversations/' + convId);
    State.selectedConv = conv;
    renderChatHeader(conv);
    renderMessages(conv.messages || []);
    renderPatientDrawer(conv);
    scrollChatToBottom();
    resetHScroll();
  } catch(err) {
    document.getElementById('chatBody').innerHTML = '<div class="error-msg">' + escHtml(err.message) + '</div>';
  }
}

function showEmptyState() {
  var caseDetail = document.getElementById('caseDetail');
  caseDetail.classList.add('empty-state');
}

function renderChatHeader(conv) {
  var name = (conv.patient && conv.patient.name) || conv.customer_name || conv.customer_phone || conv.customer_whatsapp_id;
  var initials = getInitials(name);
  var line = State.waLines.find(function(l) { return l.id === conv.whatsapp_line_id; });
  document.getElementById('chatHeader').innerHTML = '<div class="chat-header-avatar">' + escHtml(initials) + '</div><div class="chat-header-info"><div class="chat-header-name">' + escHtml(name) + '</div><div class="chat-header-sub">' + escHtml(conv.customer_phone || conv.customer_whatsapp_id) + ' · ' + escHtml((line && line.label) || conv.line_label || '') + '</div></div><div class="chat-header-actions"><select id="convStatusSel" class="btn btn-sm btn-secondary" style="padding:3px 6px;font-size:11px" onchange="updateConvStatus(this.value)"><option value="open"' + (conv.status==='open'?' selected':'') + '>Open</option><option value="pending"' + (conv.status==='pending'?' selected':'') + '>Pending</option><option value="resolved"' + (conv.status==='resolved'?' selected':'') + '>Resolved</option></select><select id="convPrioritySel" class="btn btn-sm btn-secondary" style="padding:3px 6px;font-size:11px" onchange="updateConvPriority(this.value)"><option value="low"' + (conv.priority==='low'?' selected':'') + '>Low</option><option value="normal"' + (conv.priority==='normal'?' selected':'') + '>Normal</option><option value="high"' + (conv.priority==='high'?' selected':'') + '>High</option><option value="urgent"' + (conv.priority==='urgent'?' selected':'') + '>Urgent</option></select></div>';
}

async function updateConvStatus(val) {
  if (!State.selectedConvId) return;
  await api('/api/whatsapp/conversations/' + State.selectedConvId, { method: 'PATCH', body: JSON.stringify({ status: val }) });
}
async function updateConvPriority(val) {
  if (!State.selectedConvId) return;
  await api('/api/whatsapp/conversations/' + State.selectedConvId, { method: 'PATCH', body: JSON.stringify({ priority: val }) });
}

// ── Messages ───────────────────────────────────────────────
function renderMessages(messages) {
  var body = document.getElementById('chatBody');
  if (!messages.length) { body.innerHTML = '<div class="loading">No messages yet</div>'; return; }
  body.innerHTML = '';
  var lastDate = null;
  messages.forEach(function(msg) {
    var msgDate = new Date(msg.timestamp || msg.created_at);
    var dateStr = msgDate.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    if (dateStr !== lastDate) {
      var sep = document.createElement('div');
      sep.className = 'date-separator';
      sep.textContent = dateStr;
      body.appendChild(sep);
      lastDate = dateStr;
    }
    body.appendChild(createMessageEl(msg));
  });
}

function createMessageEl(msg) {
  var row = document.createElement('div');
  var dir = msg.direction === 'note' ? 'note' : (msg.direction === 'outbound' ? 'outbound' : 'inbound');
  row.className = 'msg-row ' + dir;
  var timeStr = new Date(msg.timestamp || msg.created_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  var statusIcon = '';
  var statusClass = '';
  if (msg.direction === 'outbound') {
    if (msg.status === 'failed') { statusIcon = '✕'; statusClass = 'failed'; }
    else if (msg.status === 'read') { statusIcon = '✓✓'; statusClass = 'read'; }
    else if (msg.status === 'delivered') { statusIcon = '✓✓'; statusClass = 'delivered'; }
    else { statusIcon = '✓'; }
  }
  var contentHtml = '';
  // Treat as image if message_type is image OR mime type is image/*
  var isImage = msg.message_type === 'image' ||
    (msg.media_mime_type && msg.media_mime_type.startsWith('image/'));
  if (isImage && msg.media_url) {
    var fallbackLink = '<a href="' + escHtml(msg.media_url) + '" target="_blank" class="msg-doc-link">' +
      '<span class="msg-doc-icon">🖼</span><span class="msg-doc-name">' +
      escHtml(msg.media_name || 'Image') + '</span></a>';
    contentHtml = '<a href="' + escHtml(msg.media_url) + '" target="_blank">' +
      '<img src="' + escHtml(msg.media_url) + '" class="msg-image" alt="Image" loading="lazy" ' +
      'onerror="this.parentElement.outerHTML=\'' + fallbackLink.replace(/'/g, "\\'").replace(/"/g, '&quot;') + '\'"></a>';
    // Only show caption if it's not a bare filename (i.e. user typed actual caption text)
    if (msg.body && msg.body !== msg.media_name) {
      contentHtml += '<div style="margin-top:3px;font-size:12px">' + escHtml(msg.body) + '</div>';
    }
  } else if ((msg.message_type === 'document' || msg.message_type === 'audio' || msg.message_type === 'video') && msg.media_url) {
    var icon = msg.message_type === 'audio' ? '🎵' : msg.message_type === 'video' ? '🎥' : '📎';
    contentHtml = '<a href="' + escHtml(msg.media_url) + '" target="_blank" class="msg-doc-link"><span class="msg-doc-icon">' + icon + '</span><span class="msg-doc-name">' + escHtml(msg.media_name || msg.body || 'File') + '</span></a>';
  } else {
    contentHtml = '<div>' + escHtml(msg.body || '') + '</div>';
  }
  row.innerHTML = '<div class="msg-bubble">' + contentHtml + '<div class="msg-time">' + timeStr + (statusIcon ? '<span class="msg-status ' + statusClass + '">' + statusIcon + '</span>' : '') + '</div></div>';
  return row;
}

function appendMessage(msg) {
  var body = document.getElementById('chatBody');
  var noMsg = body.querySelector('.loading');
  if (noMsg) noMsg.remove();
  body.appendChild(createMessageEl(msg));
  scrollChatToBottom();
}

function scrollChatToBottom() {
  var body = document.getElementById('chatBody');
  if (body) body.scrollTop = body.scrollHeight;
}

// ── Send Message ───────────────────────────────────────────
async function sendMessage() {
  if (!State.selectedConvId) return;
  var input = document.getElementById('composerInput');
  var text = input.value.trim();
  if (!text) return;
  input.value = '';
  input.style.height = '';
  try {
    var msg = await api('/api/whatsapp/send', {
      method: 'POST',
      body: JSON.stringify({ conversation_id: State.selectedConvId, message: text, is_note: State.noteMode }),
    });
    if (msg) appendMessage(msg);
  } catch(err) {
    toast(err.message || 'Failed to send', 'error');
    input.value = text;
  }
}

async function sendMedia(file) {
  if (!State.selectedConvId || !file) return;
  var fd = new FormData();
  fd.append('conversation_id', State.selectedConvId);
  fd.append('file', file);
  fd.append('caption', '');
  try {
    var result = await apiForm('/api/whatsapp/send-media', fd);
    await openConversation(State.selectedConvId);
    if (result && result.wa_sent === false) {
      toast('File saved in CRM but WhatsApp delivery failed — check your token/line config', 'error');
    } else {
      toast('File sent', 'success');
    }
  } catch(err) { toast(err.message || 'Failed', 'error'); }
}

// ── Patient Drawer ─────────────────────────────────────────
function renderPatientDrawer(conv) {
  var drawer = document.getElementById('patientDrawer');
  var p = conv.patient;
  if (p) {
    var docHtml = renderDocList(p.documents || []);
    var sel = function(arr, cur) { return arr.map(function(v) { return '<option value="' + v + '"' + (cur === v ? ' selected' : '') + '>' + cap(v.replace(/_/g,' ')) + '</option>'; }).join(''); };
    drawer.innerHTML = '<div class="patient-drawer-header"><h4>📋 Patient File</h4><span class="status-pill status-' + (p.status||'new') + '">' + (p.status||'new') + '</span></div><div class="patient-drawer-body"><div class="save-feedback" id="patientSaveFeedback">Patient file saved. Conversation stays open.</div><div class="patient-form"><div class="section-label">Contact Info</div><div class="field"><label>Name *</label><input id="pf_name" type="text" value="' + escHtml(p.name||'') + '"></div><div class="field row2"><div><label>Phone *</label><input id="pf_phone" value="' + escHtml(p.phone||'') + '"></div><div><label>Email</label><input id="pf_email" value="' + escHtml(p.email||'') + '"></div></div><div class="field row2"><div><label>Country</label><input id="pf_country" value="' + escHtml(p.country||'') + '"></div><div><label>City</label><input id="pf_city" value="' + escHtml(p.city||'') + '"></div></div><div class="field"><label>Location</label><input id="pf_location" value="' + escHtml(p.location||'') + '"></div><div class="section-label mt-8">Request</div><div class="field"><label>Service / Request Type</label><input id="pf_service" value="' + escHtml(p.service_type||'') + '"></div><div class="field"><label>Details</label><textarea id="pf_details" rows="3">' + escHtml(p.request_details||'') + '</textarea></div><div class="field row2"><div><label>Priority</label><select id="pf_priority">' + sel(['low','normal','high','urgent'],p.priority) + '</select></div><div><label>Status</label><select id="pf_status">' + sel(['new','active','follow_up','discharged','inactive'],p.status) + '</select></div></div><button class="btn btn-primary btn-full mt-8" onclick="savePatientFile(\'' + p.id + '\')">Save Patient File</button><button class="btn btn-secondary btn-full" style="margin-top:6px" onclick="viewPatient(\'' + p.id + '\')">View Full Profile</button><button class="btn btn-secondary btn-full" style="margin-top:6px;background:#e8f5e9;color:#2e7d32;border-color:#a5d6a7" onclick="syncPatientMedia(\'' + p.id + '\')">📎 Sync Chat Attachments to File</button><div class="section-label mt-8">Additional Files</div><input type="file" id="pf_file_input" style="display:none" onchange="uploadPatientDoc(\'' + p.id + '\',this)"><button class="btn btn-secondary btn-sm mt-8" onclick="document.getElementById(\'pf_file_input\').click()">Attach File</button><div id="pf_docs_list" style="margin-top:8px">' + docHtml + '</div></div></div>';
  } else {
    var phone = conv.customer_phone || ('+' + conv.customer_whatsapp_id);
    var line = State.waLines.find(function(l) { return l.id === conv.whatsapp_line_id; });
    var defaultSvc = (line && line.default_service) || '';
    var sel2 = function(arr, cur) { return arr.map(function(v) { return '<option value="' + v + '"' + (cur === v ? ' selected' : '') + '>' + cap(v.replace(/_/g,' ')) + '</option>'; }).join(''); };
    drawer.innerHTML = '<div class="patient-drawer-header"><h4>📋 Patient File</h4><span style="font-size:10px;opacity:0.7">Not created</span></div><div class="patient-drawer-body"><p class="text-sm text-muted" style="margin-bottom:12px">No patient file yet. Fill in the details and click <strong>Save as New Patient</strong> — all attachments from this chat will be linked automatically.</p><div class="patient-form"><div class="section-label">Contact Info</div><div class="field"><label>Name *</label><input id="pf_name" type="text" value="' + escHtml(conv.customer_name||'') + '"></div><div class="field row2"><div><label>Phone *</label><input id="pf_phone" value="' + escHtml(phone) + '"></div><div><label>Email</label><input id="pf_email" value=""></div></div><div class="field row2"><div><label>Country</label><input id="pf_country" value=""></div><div><label>City</label><input id="pf_city" value=""></div></div><div class="field"><label>Location</label><input id="pf_location" value=""></div><div class="section-label mt-8">Request</div><div class="field"><label>Service / Request Type</label><input id="pf_service" value="' + escHtml(defaultSvc) + '"></div><div class="field"><label>Details</label><textarea id="pf_details" rows="3"></textarea></div><div class="field row2"><div><label>Priority</label><select id="pf_priority">' + sel2(['low','normal','high','urgent'],'normal') + '</select></div><div><label>Status</label><select id="pf_status">' + sel2(['new','active','follow_up','discharged'],'new') + '</select></div></div><button class="btn btn-primary btn-full mt-8" onclick="createPatientFromConv()">💾 Save as New Patient</button></div></div>';
  }
}

function renderDocList(docs) {
  if (!docs || !docs.length) return '<span class="text-sm text-muted">No files</span>';
  return docs.map(function(d) { return '<div class="doc-item"><span class="doc-icon">' + docIcon(d.mime_type) + '</span><div class="doc-info"><a href="' + escHtml(d.url) + '" target="_blank" class="doc-name">' + escHtml(d.original_name || d.file_name) + '</a></div></div>'; }).join('');
}

function docIcon(mime) {
  if (!mime) return '📎';
  if (mime.startsWith('image/')) return '🖼';
  if (mime === 'application/pdf') return '📄';
  if (mime.includes('word')) return '📝';
  return '📎';
}

async function createPatientFromConv() {
  if (!State.selectedConvId) return;
  var name = document.getElementById('pf_name') && document.getElementById('pf_name').value.trim();
  var phone = document.getElementById('pf_phone') && document.getElementById('pf_phone').value.trim();
  if (!name || !phone) { toast('Name and phone are required', 'error'); return; }
  try {
    await api('/api/patients', {
      method: 'POST',
      body: JSON.stringify({
        name: name, phone: phone,
        email: (document.getElementById('pf_email') && document.getElementById('pf_email').value.trim()) || null,
        country: (document.getElementById('pf_country') && document.getElementById('pf_country').value.trim()) || null,
        city: (document.getElementById('pf_city') && document.getElementById('pf_city').value.trim()) || null,
        location: (document.getElementById('pf_location') && document.getElementById('pf_location').value.trim()) || null,
        service_type: (document.getElementById('pf_service') && document.getElementById('pf_service').value.trim()) || null,
        request_details: (document.getElementById('pf_details') && document.getElementById('pf_details').value.trim()) || null,
        priority: (document.getElementById('pf_priority') && document.getElementById('pf_priority').value) || 'normal',
        status: (document.getElementById('pf_status') && document.getElementById('pf_status').value) || 'new',
        conversation_id: State.selectedConvId,
      }),
    });
    toast('Patient file created. Conversation stays open.', 'success');
    var conv = await api('/api/whatsapp/conversations/' + State.selectedConvId);
    State.selectedConv = conv;
    renderPatientDrawer(conv);
    renderMessages(conv.messages || []);
    renderChatHeader(conv);
    renderConversationList();
  } catch(err) { toast(err.message || 'Failed to create patient', 'error'); }
}

async function savePatientFile(patientId) {
  var name = document.getElementById('pf_name') && document.getElementById('pf_name').value.trim();
  var phone = document.getElementById('pf_phone') && document.getElementById('pf_phone').value.trim();
  if (!name || !phone) { toast('Name and phone are required', 'error'); return; }
  try {
    await api('/api/patients/' + patientId, {
      method: 'PATCH',
      body: JSON.stringify({
        name: name, phone: phone,
        email: (document.getElementById('pf_email') && document.getElementById('pf_email').value.trim()) || null,
        country: (document.getElementById('pf_country') && document.getElementById('pf_country').value.trim()) || null,
        city: (document.getElementById('pf_city') && document.getElementById('pf_city').value.trim()) || null,
        location: (document.getElementById('pf_location') && document.getElementById('pf_location').value.trim()) || null,
        service_type: (document.getElementById('pf_service') && document.getElementById('pf_service').value.trim()) || null,
        request_details: (document.getElementById('pf_details') && document.getElementById('pf_details').value.trim()) || null,
        priority: (document.getElementById('pf_priority') && document.getElementById('pf_priority').value) || null,
        status: (document.getElementById('pf_status') && document.getElementById('pf_status').value) || null,
      }),
    });
    var fb = document.getElementById('patientSaveFeedback');
    if (fb) { fb.classList.add('show'); setTimeout(function() { fb.classList.remove('show'); }, 3000); }
    toast('Patient file saved. Conversation stays open.', 'success');
  } catch(err) { toast(err.message || 'Save failed', 'error'); }
}

async function uploadPatientDoc(patientId, input) {
  var file = input.files[0];
  if (!file) return;
  var fd = new FormData();
  fd.append('file', file);
  fd.append('description', '');
  try {
    await apiForm('/api/patients/' + patientId + '/documents', fd);
    toast('File uploaded', 'success');
    var patient = await api('/api/patients/' + patientId);
    var docsEl = document.getElementById('pf_docs_list');
    if (docsEl) docsEl.innerHTML = renderDocList(patient.documents);
    input.value = '';
  } catch(err) { toast(err.message || 'Upload failed', 'error'); }
}

function viewPatient(patientId) {
  State.selectedPatientId = patientId;
  switchView('patients');
}

// ── Patients View ──────────────────────────────────────────
async function loadPatients(search) {
  search = search || '';
  var listEl = document.getElementById('patientsList');
  listEl.innerHTML = '<div class="loading">Loading…</div>';
  try {
    var result = await api('/api/patients?search=' + encodeURIComponent(search) + '&limit=100');
    State.patients = (result && result.items) || [];
    renderPatientList();
    if (State.selectedPatientId) openPatient(State.selectedPatientId);
  } catch(err) { listEl.innerHTML = '<div class="error-msg">' + escHtml(err.message) + '</div>'; }
}

function renderPatientList() {
  var listEl = document.getElementById('patientsList');
  if (!State.patients.length) { listEl.innerHTML = '<div class="loading">No patients</div>'; return; }
  listEl.innerHTML = '';
  State.patients.forEach(function(p) {
    var el = document.createElement('div');
    el.className = 'patient-list-item' + (p.id === State.selectedPatientId ? ' active' : '');
    el.innerHTML = '<div class="p-name">' + escHtml(p.name) + '</div><div class="p-sub">' + escHtml(p.phone) + ' · <span class="status-pill status-' + (p.status||'new') + '">' + (p.status||'new') + '</span></div>';
    el.addEventListener('click', function() { openPatient(p.id); });
    listEl.appendChild(el);
  });
}

async function openPatient(patientId) {
  State.selectedPatientId = patientId;
  renderPatientList();
  var panel = document.getElementById('patientDetailPanel');
  panel.innerHTML = '<div class="loading">Loading…</div>';
  try {
    var p = await api('/api/patients/' + patientId);
    renderPatientDetail(p, panel);
  } catch(err) { panel.innerHTML = '<div class="error-msg">' + escHtml(err.message) + '</div>'; }
}

function renderPatientDetail(p, panel) {
  var docs = (p.documents || []).concat(p.media_files || []);
  var docsHtml = docs.length ? docs.map(function(d) {
    return '<div class="doc-item"><span class="doc-icon">' + docIcon(d.mime_type) + '</span><div class="doc-info"><a href="' + escHtml(d.url) + '" target="_blank" class="doc-name">' + escHtml(d.original_name || d.file_name) + '</a><div class="doc-meta">' + escHtml(d.mime_type||'') + '</div></div></div>';
  }).join('') : '<span class="text-sm text-muted">No documents</span>';

  var convsHtml = (p.conversations || []).map(function(c) {
    return '<div style="padding:6px 0;border-bottom:1px solid #f0f2f5;font-size:12px"><div style="display:flex;justify-content:space-between"><span>' + escHtml(c.last_message_preview || '(no messages)') + '</span><span class="status-pill status-' + c.status + '">' + c.status + '</span></div><div class="text-sm text-muted">' + (c.last_message_at ? relTime(c.last_message_at) : '') + '</div></div>';
  }).join('') || '<span class="text-sm text-muted">No conversations</span>';

  var apptsHtml = (p.appointments || []).map(function(a) {
    return '<div style="padding:6px 0;border-bottom:1px solid #f0f2f5;font-size:12px"><div style="display:flex;justify-content:space-between"><span>' + escHtml(a.title || 'Appointment') + '</span><span class="status-pill status-' + a.status + '">' + a.status + '</span></div><div class="text-sm text-muted">' + new Date(a.appointment_date).toLocaleString() + '</div></div>';
  }).join('') || '<span class="text-sm text-muted">No appointments</span>';

  panel.innerHTML = '<div class="page-header"><h2>' + escHtml(p.name) + '</h2><div style="display:flex;gap:8px"><span class="status-pill status-' + (p.status||'new') + '">' + (p.status||'new') + '</span><button class="btn btn-primary btn-sm" onclick="showEditPatientModal(\'' + p.id + '\')">Edit</button><button class="btn btn-secondary btn-sm" onclick="showNewBookingModal(\'' + p.id + '\')">Book</button></div></div><div class="patient-detail-inner"><div class="patient-section"><h4>Contact Information</h4><div class="patient-field-grid"><div class="patient-field"><label>Phone</label><p>' + escHtml(p.phone||'—') + '</p></div><div class="patient-field"><label>Email</label><p>' + escHtml(p.email||'—') + '</p></div><div class="patient-field"><label>Country</label><p>' + escHtml(p.country||'—') + '</p></div><div class="patient-field"><label>City</label><p>' + escHtml(p.city||'—') + '</p></div></div></div><div class="patient-section"><h4>Request</h4><div class="patient-field"><label>Service Type</label><p>' + escHtml(p.service_type||'—') + '</p></div>' + (p.request_details ? '<div class="patient-field" style="margin-top:6px"><label>Details</label><p style="white-space:pre-wrap">' + escHtml(p.request_details) + '</p></div>' : '') + '</div><div class="patient-section"><h4>Documents</h4><input type="file" id="pt_file_input" style="display:none" onchange="uploadFromPatientView(\'' + p.id + '\',this)"><button class="btn btn-secondary btn-sm" onclick="document.getElementById(\'pt_file_input\').click()" style="margin-bottom:8px">Attach File</button>' + docsHtml + '</div><div class="patient-section"><h4>Conversations</h4>' + convsHtml + '</div><div class="patient-section"><h4>Appointments</h4>' + apptsHtml + '</div></div>';
}

async function uploadFromPatientView(patientId, input) {
  var file = input.files[0];
  if (!file) return;
  var fd = new FormData();
  fd.append('file', file);
  fd.append('description', '');
  try {
    await apiForm('/api/patients/' + patientId + '/documents', fd);
    toast('File uploaded', 'success');
    openPatient(patientId);
    input.value = '';
  } catch(err) { toast(err.message || 'Upload failed', 'error'); }
}

function showEditPatientModal(patientId) {
  var p = State.patients.find(function(x) { return x.id === patientId; });
  if (!p) return;
  document.getElementById('modalTitle').textContent = 'Edit Patient';
  document.getElementById('modalBody').innerHTML = '<div class="field"><label>Name *</label><input id="ep_name" value="' + escHtml(p.name||'') + '"></div><div class="field"><label>Phone *</label><input id="ep_phone" value="' + escHtml(p.phone||'') + '"></div><div class="field"><label>Email</label><input id="ep_email" value="' + escHtml(p.email||'') + '"></div><div class="field"><label>Country</label><input id="ep_country" value="' + escHtml(p.country||'') + '"></div><div class="field"><label>City</label><input id="ep_city" value="' + escHtml(p.city||'') + '"></div><div class="field"><label>Service Type</label><input id="ep_service" value="' + escHtml(p.service_type||'') + '"></div><div class="field"><label>Details</label><textarea id="ep_details">' + escHtml(p.request_details||'') + '</textarea></div>';
  document.getElementById('modalSaveBtn').onclick = async function() {
    try {
      await api('/api/patients/' + patientId, { method: 'PATCH', body: JSON.stringify({ name: document.getElementById('ep_name').value.trim(), phone: document.getElementById('ep_phone').value.trim(), email: document.getElementById('ep_email').value.trim() || null, country: document.getElementById('ep_country').value.trim() || null, city: document.getElementById('ep_city').value.trim() || null, service_type: document.getElementById('ep_service').value.trim() || null, request_details: document.getElementById('ep_details').value.trim() || null }) });
      closeModal(); toast('Patient updated', 'success'); loadPatients();
    } catch(err) { toast(err.message, 'error'); }
  };
  showModal();
}

function showNewPatientModal() {
  document.getElementById('modalTitle').textContent = 'New Patient';
  document.getElementById('modalBody').innerHTML = [
    '<div class="field"><label>Name *</label><input id="np_name" placeholder="Full name"></div>',
    '<div class="field"><label>Phone *</label><input id="np_phone" placeholder="+20..."></div>',
    '<div class="field"><label>Email</label><input id="np_email" placeholder="(optional)"></div>',
    '<div class="field row2"><div><label>Country</label><input id="np_country"></div><div><label>City</label><input id="np_city"></div></div>',
    '<div class="field"><label>Service / Request Type</label><input id="np_service"></div>',
    '<div class="field"><label>Details</label><textarea id="np_details" rows="3"></textarea></div>',
    '<div class="field row2"><div><label>Priority</label><select id="np_priority"><option value="low">Low</option><option value="normal" selected>Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></div><div><label>Status</label><select id="np_status"><option value="new" selected>New</option><option value="active">Active</option><option value="follow_up">Follow-up</option><option value="discharged">Discharged</option></select></div></div>',
  ].join('');
  document.getElementById('modalSaveBtn').onclick = async function() {
    var name = document.getElementById('np_name').value.trim();
    var phone = document.getElementById('np_phone').value.trim();
    if (!name || !phone) { toast('Name and phone are required', 'error'); return; }
    try {
      var p = await api('/api/patients', {
        method: 'POST',
        body: JSON.stringify({
          name: name, phone: phone,
          email: document.getElementById('np_email').value.trim() || null,
          country: document.getElementById('np_country').value.trim() || null,
          city: document.getElementById('np_city').value.trim() || null,
          service_type: document.getElementById('np_service').value.trim() || null,
          request_details: document.getElementById('np_details').value.trim() || null,
          priority: document.getElementById('np_priority').value || 'normal',
          status: document.getElementById('np_status').value || 'new',
        }),
      });
      closeModal();
      toast('Patient created', 'success');
      await loadPatients();
      openPatient(p.id);
    } catch(err) { toast(err.message || 'Failed to create patient', 'error'); }
  };
  showModal();
}

async function syncPatientMedia(patientId) {
  if (!State.selectedConvId) { toast('No conversation selected', 'error'); return; }
  try {
    var result = await api('/api/patients/' + patientId + '/sync-media', {
      method: 'POST',
      body: JSON.stringify({ conversation_id: State.selectedConvId }),
    });
    var msg = result.linked > 0
      ? result.linked + ' file(s) added to patient file.'
      : 'All files already linked — patient file is up to date.';
    toast(msg, 'success');
    // Refresh drawer with updated patient data
    var conv = await api('/api/whatsapp/conversations/' + State.selectedConvId);
    State.selectedConv = conv;
    renderPatientDrawer(conv);
  } catch(err) { toast(err.message || 'Sync failed', 'error'); }
}

// ── Calendar ───────────────────────────────────────────────
async function renderCalendar() {
  var offset = State.calWeekOffset;
  var today = new Date();
  var startOfWeek = new Date(today);
  startOfWeek.setDate(today.getDate() - today.getDay() + offset * 7);
  startOfWeek.setHours(0,0,0,0);
  var endOfWeek = new Date(startOfWeek);
  endOfWeek.setDate(startOfWeek.getDate() + 6);
  endOfWeek.setHours(23,59,59,999);
  document.getElementById('calWeekLabel').textContent = startOfWeek.toLocaleDateString('en-GB',{day:'numeric',month:'short'}) + ' – ' + endOfWeek.toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});
  try {
    var appts = await api('/api/bookings?start_date=' + startOfWeek.toISOString() + '&end_date=' + endOfWeek.toISOString());
    State.appointments = appts || [];
    renderCalendarGrid(startOfWeek, appts || []);
  } catch(err) { document.getElementById('calGrid').innerHTML = '<div class="error-msg">' + escHtml(err.message) + '</div>'; }
}

function renderCalendarGrid(startOfWeek, appts) {
  var grid = document.getElementById('calGrid');
  var days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  var today = new Date();
  var html = '<div class="calendar-grid">';
  days.forEach(function(d) { html += '<div class="calendar-day-header">' + d + '</div>'; });
  for (var i = 0; i < 7; i++) {
    var day = new Date(startOfWeek);
    day.setDate(startOfWeek.getDate() + i);
    var isToday = day.toDateString() === today.toDateString();
    var dayAppts = appts.filter(function(a) { return new Date(a.appointment_date).toDateString() === day.toDateString(); });
    html += '<div class="calendar-day' + (isToday ? ' today' : '') + '"><div class="cal-day-num">' + day.getDate() + '</div>' + dayAppts.map(function(a) { return '<div class="cal-event status-' + a.status + '" onclick="showApptDetail(this)" data-appt=\'' + escHtml(JSON.stringify(a)) + '\' title="' + escHtml(a.patient_name||a.title||'') + '">' + new Date(a.appointment_date).toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',hour12:false}) + ' ' + escHtml(a.patient_name||a.title||'Appt') + '</div>'; }).join('') + '</div>';
  }
  html += '</div>';
  grid.innerHTML = html;
}

function showApptDetail(el) {
  try {
    var a = JSON.parse(el.getAttribute('data-appt'));
    document.getElementById('apptDetailPanel').innerHTML = '<div class="appt-detail-panel"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><h4>' + escHtml(a.title||'Appointment') + '</h4><span class="status-pill status-' + a.status + '">' + a.status + '</span></div><div class="appt-detail-row"><label>Patient:</label><a href="#" onclick="viewPatient(\'' + a.patient_id + '\');return false">' + escHtml(a.patient_name||'—') + '</a></div><div class="appt-detail-row"><label>Doctor:</label><span>' + escHtml(a.doctor_name||'—') + '</span></div><div class="appt-detail-row"><label>Date:</label><span>' + new Date(a.appointment_date).toLocaleString() + '</span></div><div class="appt-detail-row"><label>Service:</label><span>' + escHtml(a.service_type||'—') + '</span></div>' + (a.notes ? '<div class="appt-detail-row"><label>Notes:</label><span>' + escHtml(a.notes) + '</span></div>' : '') + '<div style="margin-top:10px;display:flex;gap:6px"><button class="btn btn-sm btn-primary" onclick="editApptStatus(\'' + a.id + '\',\'confirmed\')">Confirm</button><button class="btn btn-sm btn-danger" onclick="editApptStatus(\'' + a.id + '\',\'cancelled\')">Cancel</button></div></div>';
  } catch(e) {}
}

async function editApptStatus(apptId, status) {
  try {
    await api('/api/bookings/' + apptId, { method: 'PATCH', body: JSON.stringify({ status: status }) });
    toast('Appointment ' + status, 'success');
    renderCalendar();
  } catch(err) { toast(err.message, 'error'); }
}

// ── Bookings ───────────────────────────────────────────────
async function loadBookings() {
  var el = document.getElementById('bookingsTable');
  el.innerHTML = '<tr><td colspan="7" class="loading">Loading…</td></tr>';
  try {
    var results = await Promise.all([api('/api/bookings'), api('/api/patients'), api('/api/doctors'), api('/api/clinics')]);
    State.appointments = results[0] || [];
    State.patients = (results[1] && results[1].items) || [];
    State.doctors = results[2] || [];
    State.clinics = results[3] || [];
    renderBookingsTable();
  } catch(err) { el.innerHTML = '<tr><td colspan="7" class="error-msg">' + escHtml(err.message) + '</td></tr>'; }
}

function renderBookingsTable() {
  var el = document.getElementById('bookingsTable');
  if (!State.appointments.length) { el.innerHTML = '<tr><td colspan="7" class="loading">No bookings</td></tr>'; return; }
  el.innerHTML = State.appointments.map(function(a) {
    return '<tr><td><a href="#" onclick="viewPatient(\'' + a.patient_id + '\');return false">' + escHtml(a.patient_name||'—') + '</a></td><td>' + escHtml(a.doctor_name||'—') + '</td><td>' + escHtml(a.clinic_name||'—') + '</td><td>' + new Date(a.appointment_date).toLocaleString() + '</td><td>' + escHtml(a.service_type||'—') + '</td><td><span class="status-pill status-' + a.status + '">' + a.status + '</span></td><td><button class="btn btn-sm btn-primary" onclick="editApptStatus(\'' + a.id + '\',\'confirmed\')">Confirm</button> <button class="btn btn-sm btn-danger" onclick="editApptStatus(\'' + a.id + '\',\'cancelled\')">Cancel</button></td></tr>';
  }).join('');
}

function showNewBookingModal(patientId) {
  document.getElementById('modalTitle').textContent = 'New Booking';
  var pOpts = State.patients.map(function(p) { return '<option value="' + p.id + '"' + (p.id===patientId?' selected':'') + '>' + escHtml(p.name) + '</option>'; }).join('');
  var dOpts = '<option value="">— No doctor —</option>' + State.doctors.map(function(d) { return '<option value="' + d.id + '">' + escHtml(d.name) + '</option>'; }).join('');
  var cOpts = '<option value="">— No clinic —</option>' + State.clinics.map(function(c) { return '<option value="' + c.id + '">' + escHtml(c.name) + '</option>'; }).join('');
  document.getElementById('modalBody').innerHTML = '<div class="field"><label>Patient *</label><select id="bk_patient">' + pOpts + '</select></div><div class="field"><label>Doctor</label><select id="bk_doctor">' + dOpts + '</select></div><div class="field"><label>Clinic</label><select id="bk_clinic">' + cOpts + '</select></div><div class="field"><label>Title</label><input id="bk_title"></div><div class="field"><label>Date & Time *</label><input id="bk_date" type="datetime-local"></div><div class="field"><label>Service Type</label><input id="bk_service"></div><div class="field"><label>Notes</label><textarea id="bk_notes"></textarea></div>';
  document.getElementById('modalSaveBtn').onclick = async function() {
    var dateVal = document.getElementById('bk_date').value;
    if (!dateVal) { toast('Date is required', 'error'); return; }
    try {
      await api('/api/bookings', { method: 'POST', body: JSON.stringify({ patient_id: document.getElementById('bk_patient').value, doctor_id: document.getElementById('bk_doctor').value || null, clinic_id: document.getElementById('bk_clinic').value || null, title: document.getElementById('bk_title').value.trim() || null, appointment_date: new Date(dateVal).toISOString(), service_type: document.getElementById('bk_service').value.trim() || null, notes: document.getElementById('bk_notes').value.trim() || null }) });
      closeModal(); toast('Booking created', 'success');
      if (State.currentView === 'bookings') loadBookings();
      else if (State.currentView === 'calendar') renderCalendar();
    } catch(err) { toast(err.message, 'error'); }
  };
  showModal();
}

// ── Doctors ────────────────────────────────────────────────
async function loadDoctors() {
  var el = document.getElementById('doctorsTable');
  el.innerHTML = '<tr><td colspan="5" class="loading">Loading…</td></tr>';
  try {
    var results = await Promise.all([api('/api/doctors'), api('/api/clinics')]);
    State.doctors = results[0] || [];
    State.clinics = results[1] || [];
    var tbody = document.getElementById('doctorsTable');
    if (!State.doctors.length) { tbody.innerHTML = '<tr><td colspan="5" class="loading">No doctors</td></tr>'; return; }
    tbody.innerHTML = State.doctors.map(function(d) { return '<tr><td><strong>' + escHtml(d.name) + '</strong></td><td>' + escHtml(d.specialty||'—') + '</td><td>' + escHtml(d.clinic_name||'—') + '</td><td>' + escHtml(d.phone||'—') + '</td><td><button class="btn btn-sm btn-secondary" onclick="showEditDoctorModal(\'' + d.id + '\')">Edit</button> <button class="btn btn-sm btn-danger" onclick="deleteDoctor(\'' + d.id + '\')">Remove</button></td></tr>'; }).join('');
  } catch(err) { el.innerHTML = '<tr><td colspan="5" class="error-msg">' + escHtml(err.message) + '</td></tr>'; }
}

function showNewDoctorModal() {
  document.getElementById('modalTitle').textContent = 'Add Doctor';
  var cOpts = '<option value="">— No clinic —</option>' + State.clinics.map(function(c) { return '<option value="' + c.id + '">' + escHtml(c.name) + '</option>'; }).join('');
  document.getElementById('modalBody').innerHTML = '<div class="field"><label>Name *</label><input id="dr_name"></div><div class="field"><label>Specialty</label><input id="dr_specialty"></div><div class="field"><label>Phone</label><input id="dr_phone"></div><div class="field"><label>Email</label><input id="dr_email"></div><div class="field"><label>Clinic</label><select id="dr_clinic">' + cOpts + '</select></div><div class="field"><label>Bio</label><textarea id="dr_bio"></textarea></div>';
  document.getElementById('modalSaveBtn').onclick = async function() {
    var name = document.getElementById('dr_name').value.trim();
    if (!name) { toast('Name required', 'error'); return; }
    try {
      await api('/api/doctors', { method: 'POST', body: JSON.stringify({ name: name, specialty: document.getElementById('dr_specialty').value.trim() || null, phone: document.getElementById('dr_phone').value.trim() || null, email: document.getElementById('dr_email').value.trim() || null, clinic_id: document.getElementById('dr_clinic').value || null, bio: document.getElementById('dr_bio').value.trim() || null }) });
      closeModal(); toast('Doctor added', 'success'); loadDoctors();
    } catch(err) { toast(err.message, 'error'); }
  };
  showModal();
}

function showEditDoctorModal(docId) {
  var d = State.doctors.find(function(x) { return x.id === docId; });
  if (!d) return;
  var cOpts = '<option value="">— No clinic —</option>' + State.clinics.map(function(c) { return '<option value="' + c.id + '"' + (c.id===d.clinic_id?' selected':'') + '>' + escHtml(c.name) + '</option>'; }).join('');
  document.getElementById('modalTitle').textContent = 'Edit Doctor';
  document.getElementById('modalBody').innerHTML = '<div class="field"><label>Name *</label><input id="dr_name" value="' + escHtml(d.name||'') + '"></div><div class="field"><label>Specialty</label><input id="dr_specialty" value="' + escHtml(d.specialty||'') + '"></div><div class="field"><label>Phone</label><input id="dr_phone" value="' + escHtml(d.phone||'') + '"></div><div class="field"><label>Email</label><input id="dr_email" value="' + escHtml(d.email||'') + '"></div><div class="field"><label>Clinic</label><select id="dr_clinic">' + cOpts + '</select></div><div class="field"><label>Bio</label><textarea id="dr_bio">' + escHtml(d.bio||'') + '</textarea></div>';
  document.getElementById('modalSaveBtn').onclick = async function() {
    try {
      await api('/api/doctors/' + docId, { method: 'PATCH', body: JSON.stringify({ name: document.getElementById('dr_name').value.trim(), specialty: document.getElementById('dr_specialty').value.trim() || null, phone: document.getElementById('dr_phone').value.trim() || null, email: document.getElementById('dr_email').value.trim() || null, clinic_id: document.getElementById('dr_clinic').value || null, bio: document.getElementById('dr_bio').value.trim() || null }) });
      closeModal(); toast('Doctor updated', 'success'); loadDoctors();
    } catch(err) { toast(err.message, 'error'); }
  };
  showModal();
}

async function deleteDoctor(docId) {
  if (!confirm('Remove this doctor?')) return;
  try { await api('/api/doctors/' + docId, { method: 'DELETE' }); toast('Doctor removed', 'success'); loadDoctors(); }
  catch(err) { toast(err.message, 'error'); }
}

// ── Clinics ────────────────────────────────────────────────
async function loadClinics() {
  var el = document.getElementById('clinicsTable');
  el.innerHTML = '<tr><td colspan="5" class="loading">Loading…</td></tr>';
  try {
    State.clinics = await api('/api/clinics') || [];
    if (!State.clinics.length) { el.innerHTML = '<tr><td colspan="5" class="loading">No clinics</td></tr>'; return; }
    el.innerHTML = State.clinics.map(function(c) { return '<tr><td><strong>' + escHtml(c.name) + '</strong></td><td>' + escHtml([c.city,c.country].filter(Boolean).join(', ')||'—') + '</td><td>' + escHtml(c.phone||'—') + '</td><td>' + escHtml(c.specialties||'—') + '</td><td><button class="btn btn-sm btn-secondary" onclick="showEditClinicModal(\'' + c.id + '\')">Edit</button> <button class="btn btn-sm btn-danger" onclick="deleteClinic(\'' + c.id + '\')">Remove</button></td></tr>'; }).join('');
  } catch(err) { el.innerHTML = '<tr><td colspan="5" class="error-msg">' + escHtml(err.message) + '</td></tr>'; }
}

function showNewClinicModal() {
  document.getElementById('modalTitle').textContent = 'Add Clinic';
  document.getElementById('modalBody').innerHTML = '<div class="field"><label>Name *</label><input id="cl_name"></div><div class="field"><label>Address</label><input id="cl_address"></div><div class="field"><label>City</label><input id="cl_city"></div><div class="field"><label>Country</label><input id="cl_country"></div><div class="field"><label>Phone</label><input id="cl_phone"></div><div class="field"><label>Email</label><input id="cl_email"></div><div class="field"><label>Specialties (comma-separated)</label><input id="cl_specialties"></div>';
  document.getElementById('modalSaveBtn').onclick = async function() {
    var name = document.getElementById('cl_name').value.trim();
    if (!name) { toast('Name required', 'error'); return; }
    try {
      await api('/api/clinics', { method: 'POST', body: JSON.stringify({ name: name, address: document.getElementById('cl_address').value.trim() || null, city: document.getElementById('cl_city').value.trim() || null, country: document.getElementById('cl_country').value.trim() || null, phone: document.getElementById('cl_phone').value.trim() || null, email: document.getElementById('cl_email').value.trim() || null, specialties: document.getElementById('cl_specialties').value.trim() || null }) });
      closeModal(); toast('Clinic added', 'success'); loadClinics();
    } catch(err) { toast(err.message, 'error'); }
  };
  showModal();
}

function showEditClinicModal(clinicId) {
  var c = State.clinics.find(function(x) { return x.id === clinicId; });
  if (!c) return;
  document.getElementById('modalTitle').textContent = 'Edit Clinic';
  document.getElementById('modalBody').innerHTML = '<div class="field"><label>Name *</label><input id="cl_name" value="' + escHtml(c.name||'') + '"></div><div class="field"><label>Address</label><input id="cl_address" value="' + escHtml(c.address||'') + '"></div><div class="field"><label>City</label><input id="cl_city" value="' + escHtml(c.city||'') + '"></div><div class="field"><label>Country</label><input id="cl_country" value="' + escHtml(c.country||'') + '"></div><div class="field"><label>Phone</label><input id="cl_phone" value="' + escHtml(c.phone||'') + '"></div><div class="field"><label>Email</label><input id="cl_email" value="' + escHtml(c.email||'') + '"></div><div class="field"><label>Specialties</label><input id="cl_specialties" value="' + escHtml(c.specialties||'') + '"></div>';
  document.getElementById('modalSaveBtn').onclick = async function() {
    try {
      await api('/api/clinics/' + clinicId, { method: 'PATCH', body: JSON.stringify({ name: document.getElementById('cl_name').value.trim(), address: document.getElementById('cl_address').value.trim() || null, city: document.getElementById('cl_city').value.trim() || null, country: document.getElementById('cl_country').value.trim() || null, phone: document.getElementById('cl_phone').value.trim() || null, email: document.getElementById('cl_email').value.trim() || null, specialties: document.getElementById('cl_specialties').value.trim() || null }) });
      closeModal(); toast('Clinic updated', 'success'); loadClinics();
    } catch(err) { toast(err.message, 'error'); }
  };
  showModal();
}

async function deleteClinic(clinicId) {
  if (!confirm('Remove this clinic?')) return;
  try { await api('/api/clinics/' + clinicId, { method: 'DELETE' }); toast('Clinic removed', 'success'); loadClinics(); }
  catch(err) { toast(err.message, 'error'); }
}

// ── Users ──────────────────────────────────────────────────
async function loadUsers() {
  var el = document.getElementById('usersTable');
  el.innerHTML = '<tr><td colspan="5" class="loading">Loading…</td></tr>';
  try {
    var users = await api('/api/users') || [];
    if (!users.length) { el.innerHTML = '<tr><td colspan="5" class="loading">No users</td></tr>'; return; }
    el.innerHTML = users.map(function(u) { return '<tr><td><strong>' + escHtml(u.username) + '</strong></td><td>' + escHtml(u.full_name||'—') + '</td><td>' + escHtml(u.email||'—') + '</td><td><span class="status-pill status-open">' + escHtml(formatRole(u.role)) + '</span></td><td><span class="' + (u.is_active ? 'status-pill status-active' : 'status-pill status-cancelled') + '">' + (u.is_active ? 'Active' : 'Inactive') + '</span> <button class="btn btn-sm btn-secondary" onclick="showEditUserModal(\'' + u.id + '\',\'' + escHtml(u.username) + '\',\'' + escHtml(u.full_name||'') + '\',\'' + escHtml(u.email||'') + '\',\'' + u.role + '\',' + u.is_active + ')">Edit</button>' + (State.user && u.id !== State.user.id ? ' <button class="btn btn-sm btn-danger" onclick="toggleUserActive(\'' + u.id + '\',' + !u.is_active + ')">' + (u.is_active ? 'Deactivate' : 'Activate') + '</button>' : '') + '</td></tr>'; }).join('');
  } catch(err) { el.innerHTML = '<tr><td colspan="5" class="error-msg">' + escHtml(err.message) + '</td></tr>'; }
}

function showNewUserModal() {
  document.getElementById('modalTitle').textContent = 'Add User';
  document.getElementById('modalBody').innerHTML = '<div class="field"><label>Username *</label><input id="usr_username"></div><div class="field"><label>Password *</label><input id="usr_password" type="password"></div><div class="field"><label>Full Name</label><input id="usr_fullname"></div><div class="field"><label>Email</label><input id="usr_email" type="email"></div><div class="field"><label>Role</label><select id="usr_role"><option value="agent">Agent</option><option value="case_manager">Case Manager</option><option value="finance">Finance</option><option value="clinic_admin">Clinic Admin</option><option value="doctor">Doctor</option><option value="super_admin">Super Admin</option></select></div>';
  document.getElementById('modalSaveBtn').onclick = async function() {
    var u = document.getElementById('usr_username').value.trim();
    var p = document.getElementById('usr_password').value;
    if (!u || !p) { toast('Username and password required', 'error'); return; }
    try {
      await api('/api/users', { method: 'POST', body: JSON.stringify({ username: u, password: p, full_name: document.getElementById('usr_fullname').value.trim() || null, email: document.getElementById('usr_email').value.trim() || null, role: document.getElementById('usr_role').value }) });
      closeModal(); toast('User created', 'success'); loadUsers();
    } catch(err) { toast(err.message, 'error'); }
  };
  showModal();
}

function showEditUserModal(id, username, fullName, email, role) {
  document.getElementById('modalTitle').textContent = 'Edit User: ' + username;
  document.getElementById('modalBody').innerHTML = '<div class="field"><label>Full Name</label><input id="usr_fullname" value="' + escHtml(fullName) + '"></div><div class="field"><label>Email</label><input id="usr_email" value="' + escHtml(email) + '"></div><div class="field"><label>Role</label><select id="usr_role"><option value="agent"' + (role==='agent'?' selected':'') + '>Agent</option><option value="case_manager"' + (role==='case_manager'?' selected':'') + '>Case Manager</option><option value="finance"' + (role==='finance'?' selected':'') + '>Finance</option><option value="clinic_admin"' + (role==='clinic_admin'?' selected':'') + '>Clinic Admin</option><option value="doctor"' + (role==='doctor'?' selected':'') + '>Doctor</option><option value="super_admin"' + (role==='super_admin'?' selected':'') + '>Super Admin</option></select></div><div class="field"><label>New Password (leave blank to keep)</label><input id="usr_password" type="password"></div>';
  document.getElementById('modalSaveBtn').onclick = async function() {
    var body = { full_name: document.getElementById('usr_fullname').value.trim() || null, email: document.getElementById('usr_email').value.trim() || null, role: document.getElementById('usr_role').value };
    var pw = document.getElementById('usr_password').value;
    if (pw) body.password = pw;
    try {
      await api('/api/users/' + id, { method: 'PATCH', body: JSON.stringify(body) });
      closeModal(); toast('User updated', 'success'); loadUsers();
    } catch(err) { toast(err.message, 'error'); }
  };
  showModal();
}

async function toggleUserActive(userId, active) {
  try { await api('/api/users/' + userId, { method: 'PATCH', body: JSON.stringify({ is_active: active }) }); toast(active ? 'User activated' : 'User deactivated', 'success'); loadUsers(); }
  catch(err) { toast(err.message, 'error'); }
}

// ── Modal ──────────────────────────────────────────────────
function showModal() { document.getElementById('modalOverlay').classList.remove('hidden'); }
function closeModal() { document.getElementById('modalOverlay').classList.add('hidden'); }

// ── Utilities ──────────────────────────────────────────────
function escHtml(str) {
  if (str == null) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function getInitials(name) {
  if (!name) return '?';
  var parts = String(name).trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0,2).toUpperCase();
  return (parts[0][0] + parts[parts.length-1][0]).toUpperCase();
}
function cap(str) { if (!str) return ''; return str.charAt(0).toUpperCase() + str.slice(1); }
function relTime(isoStr) {
  var d = new Date(isoStr), now = new Date(), diff = (now - d) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff/60) + 'm';
  if (diff < 86400) return Math.floor(diff/3600) + 'h';
  if (diff < 604800) return Math.floor(diff/86400) + 'd';
  return d.toLocaleDateString('en-GB',{day:'numeric',month:'short'});
}
function debounce(fn, ms) {
  var timer;
  return function() { var args = arguments; clearTimeout(timer); timer = setTimeout(function() { fn.apply(null, args); }, ms); };
}

// ── Boot ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async function() {
  document.getElementById('loginForm').addEventListener('submit', doLogin);
  var input = document.getElementById('composerInput');
  input.addEventListener('keydown', function(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
  input.addEventListener('input', function() { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 120) + 'px'; });
  document.getElementById('sendBtn').addEventListener('click', sendMessage);
  document.getElementById('attachBtn').addEventListener('click', function() { document.getElementById('fileInput').click(); });
  document.getElementById('fileInput').addEventListener('change', function(e) { var file = e.target.files[0]; if (file) sendMedia(file); e.target.value = ''; });
  document.getElementById('noteBtn').addEventListener('click', function() {
    State.noteMode = !State.noteMode;
    input.classList.toggle('note-mode', State.noteMode);
    document.getElementById('noteBtn').classList.toggle('active', State.noteMode);
    input.placeholder = State.noteMode ? 'Internal note (not sent to customer)…' : 'Type a message…';
  });
  document.getElementById('convSearch').addEventListener('input', debounce(function() { if (State.selectedLineId) loadConversations(State.selectedLineId); }, 400));
  document.querySelectorAll('.filter-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      document.querySelectorAll('.filter-btn').forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      State.convFilter = btn.dataset.filter;
      if (State.selectedLineId) loadConversations(State.selectedLineId);
    });
  });
  document.getElementById('modalClose').addEventListener('click', closeModal);
  document.getElementById('modalCancel').addEventListener('click', closeModal);
  document.getElementById('modalOverlay').addEventListener('click', function(e) { if (e.target === document.getElementById('modalOverlay')) closeModal(); });
  document.getElementById('calPrev').addEventListener('click', function() { State.calWeekOffset--; renderCalendar(); });
  document.getElementById('calNext').addEventListener('click', function() { State.calWeekOffset++; renderCalendar(); });
  document.getElementById('calToday').addEventListener('click', function() { State.calWeekOffset = 0; renderCalendar(); });
  document.getElementById('patientSearch').addEventListener('input', debounce(function(e) { loadPatients(e.target.value.trim()); }, 400));
  var restored = await restoreSession();
  if (restored) showApp();
  else document.getElementById('loginScreen').classList.remove('hidden');
  setInterval(function() { if (window.scrollX !== 0 || document.body.scrollLeft !== 0) resetHScroll(); }, 500);
});


// ════════════════════════════════════════════════════════════
// CASES
// ════════════════════════════════════════════════════════════

const CaseState = { filter: 'open', selectedId: null, debounceTimer: null };

function setCaseFilter(f, btn) {
  CaseState.filter = f;
  document.querySelectorAll('[data-cfilter]').forEach(function(b) { b.classList.remove('active'); });
  if (btn) btn.classList.add('active');
  loadCases();
}

function debouncedLoadCases() {
  clearTimeout(CaseState.debounceTimer);
  CaseState.debounceTimer = setTimeout(loadCases, 350);
}

async function loadCases() {
  var listEl = document.getElementById('casesList');
  listEl.innerHTML = '<div class="loading">Loading…</div>';
  var search = (document.getElementById('caseSearch') && document.getElementById('caseSearch').value) || '';
  var params = 'limit=100&skip=0';
  if (CaseState.filter === 'open') params += '&status_group=open';
  if (CaseState.filter === 'closed') params += '&status_group=closed';
  if (search) params += '&search=' + encodeURIComponent(search);
  try {
    var result = await api('/api/cases?' + params);
    var items = (result && result.items) || [];
    listEl.innerHTML = '';
    if (!items.length) { listEl.innerHTML = '<div class="loading">No cases found</div>'; return; }
    items.forEach(function(c) {
      var el = document.createElement('div');
      el.className = 'case-list-item' + (c.id === CaseState.selectedId ? ' active' : '');
      el.innerHTML =
        '<div class="case-num">' + escHtml(c.case_number) + '</div>' +
        '<div class="case-title">' + escHtml(c.title) + '</div>' +
        '<div class="case-meta">' +
          '<span class="case-badge badge-status-' + (c.status||'') + '">' + escHtml(c.status||'') + '</span>' +
          '<span class="case-badge badge-priority-' + (c.priority||'') + '">' + escHtml(c.priority||'') + '</span>' +
          (c.patient_name ? '<span style="font-size:10px;color:#666">' + escHtml(c.patient_name) + '</span>' : '') +
        '</div>';
      el.addEventListener('click', function() { openCase(c.id); });
      listEl.appendChild(el);
    });
  } catch(err) {
    listEl.innerHTML = '<div class="error-msg">' + escHtml(err.message) + '</div>';
  }
}

async function openCase(caseId) {
  CaseState.selectedId = caseId;
  // Highlight in list
  document.querySelectorAll('.case-list-item').forEach(function(el) { el.classList.remove('active'); });
  document.querySelectorAll('.case-list-item').forEach(function(el) {
    if (el.querySelector('.case-num') && el.querySelector('.case-num').parentElement === el) {
      // check by re-rendering is simpler
    }
  });
  loadCases(); // re-render list with active highlight

  var panel = document.getElementById('caseDetailPanel');
  panel.innerHTML = '<div class="case-detail-inner"><div class="loading">Loading case…</div></div>';
  try {
    var c = await api('/api/cases/' + caseId);
    renderCaseDetail(c);
  } catch(err) {
    panel.innerHTML = '<div class="case-detail-inner"><div class="error-msg">' + escHtml(err.message) + '</div></div>';
  }
}

function renderCaseDetail(c) {
  var panel = document.getElementById('caseDetailPanel');
  var assigneeLabel = c.assignee_name || 'Unassigned';
  var slaStr = c.sla_due_at ? new Date(c.sla_due_at).toLocaleString('en-GB', {day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}) : '—';
  var slaClass = c.sla_breached ? 'color:#b71c1c;font-weight:600' : '';

  panel.innerHTML =
    '<div class="case-detail-inner">' +
    '<div class="case-detail-header">' +
      '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">' +
        '<h3>' + escHtml(c.title) + '</h3>' +
        '<span style="font-size:10px;color:#999;white-space:nowrap">' + escHtml(c.case_number) + '</span>' +
      '</div>' +
      '<div class="case-detail-meta">' +
        '<span class="case-badge badge-status-' + c.status + '">' + escHtml(c.status) + '</span>' +
        '<span class="case-badge badge-priority-' + c.priority + '">' + escHtml(c.priority) + '</span>' +
        '<span class="case-badge" style="background:#e3f2fd;color:#1565c0">' + escHtml(c.type) + '</span>' +
      '</div>' +
      '<div class="case-info-grid" style="margin:10px 0">' +
        '<div class="case-info-item"><label>Patient</label>' + escHtml(c.patient_name || '—') + '</div>' +
        '<div class="case-info-item"><label>Assigned To</label>' + escHtml(assigneeLabel) + '</div>' +
        '<div class="case-info-item"><label>Doctor</label>' + escHtml(c.doctor_name || '—') + '</div>' +
        '<div class="case-info-item"><label>Clinic</label>' + escHtml(c.clinic_name || '—') + '</div>' +
        '<div class="case-info-item"><label>Country</label>' + escHtml(c.country_of_origin || '—') + '</div>' +
        '<div class="case-info-item"><label>SLA Due</label><span style="' + slaClass + '">' + slaStr + '</span></div>' +
        '<div class="case-info-item"><label>Est. Cost</label>' + (c.estimated_cost ? escHtml(c.currency + ' ' + c.estimated_cost.toLocaleString()) : '—') + '</div>' +
        '<div class="case-info-item"><label>Tasks</label>' + c.tasks_done + ' / ' + c.tasks_total + '</div>' +
      '</div>' +
      '<div class="case-detail-actions">' +
        '<select class="btn btn-secondary btn-sm" onchange="caseStatusChange(\'' + c.id + '\',this)" style="font-size:11px">' +
          ['intake','triage','active','pending_provider','pending_patient','treatment','follow_up','closed','cancelled'].map(function(s) {
            return '<option value="' + s + '"' + (c.status===s?' selected':'') + '>' + s + '</option>';
          }).join('') +
        '</select>' +
        '<button class="btn btn-secondary btn-sm" onclick="showAddNoteModal(\'' + c.id + '\')">+ Note</button>' +
        '<button class="btn btn-secondary btn-sm" onclick="showAddTaskModal(\'' + c.id + '\')">+ Task</button>' +
        '<button class="btn btn-primary btn-sm" onclick="showEscalateModal(\'' + c.id + '\')">⬆ Escalate</button>' +
      '</div>' +
    '</div>' +
    '<div class="case-tabs">' +
      '<button class="case-tab active" onclick="switchCaseTab(this,\'notes\')">Notes (' + (c.notes||[]).length + ')</button>' +
      '<button class="case-tab" onclick="switchCaseTab(this,\'tasks\')">Tasks (' + (c.tasks||[]).length + ')</button>' +
      '<button class="case-tab" onclick="switchCaseTab(this,\'info\')">Details</button>' +
    '</div>' +
    '<div id="caseTabNotes" class="case-tab-content active">' + renderNotesList(c.notes || []) + '</div>' +
    '<div id="caseTabTasks" class="case-tab-content">' + renderTasksList(c.tasks || [], c.id) + '</div>' +
    '<div id="caseTabInfo" class="case-tab-content">' + renderCaseInfo(c) + '</div>' +
    '</div>';
}

function switchCaseTab(btn, tab) {
  document.querySelectorAll('.case-tab').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');
  document.querySelectorAll('.case-tab-content').forEach(function(el) { el.classList.remove('active'); });
  var el = document.getElementById('caseTab' + cap(tab));
  if (el) el.classList.add('active');
}

function renderNotesList(notes) {
  if (!notes.length) return '<p style="color:#999;font-size:12px;padding:10px 0">No notes yet.</p>';
  return notes.map(function(n) {
    var cls = n.note_type === 'escalation' ? 'escalation' : (!n.is_internal ? 'external' : '');
    return '<div class="case-note ' + cls + '">' +
      '<div class="case-note-header">' +
        '<span><span class="case-note-author">' + escHtml(n.author_name||'System') + '</span>' +
          ' <span class="case-note-type">' + escHtml(n.note_type) + '</span>' +
          (n.is_internal ? '' : ' <span class="case-note-type" style="background:#e8f5e9;color:#2e7d32">external</span>') +
        '</span>' +
        '<span>' + (n.created_at ? relTime(n.created_at) : '') + '</span>' +
      '</div>' +
      '<div>' + escHtml(n.body) + '</div>' +
    '</div>';
  }).join('');
}

function renderTasksList(tasks, caseId) {
  if (!tasks.length) return '<p style="color:#999;font-size:12px;padding:10px 0">No tasks yet.</p>';
  return tasks.map(function(t) {
    var done = t.status === 'done';
    return '<div class="case-task' + (done?' done':'') + '">' +
      '<input type="checkbox" class="task-check"' + (done?' checked':'') +
        ' onchange="toggleTask(\'' + (caseId||t.case_id) + '\',\'' + t.id + '\',this.checked)">' +
      '<div class="task-body">' +
        '<div class="task-title">' + escHtml(t.title) + '</div>' +
        '<div class="task-meta">' +
          (t.assignee_name ? 'Assigned to ' + escHtml(t.assignee_name) + ' · ' : '') +
          (t.due_at ? 'Due ' + new Date(t.due_at).toLocaleDateString('en-GB',{day:'numeric',month:'short'}) : '') +
        '</div>' +
      '</div>' +
    '</div>';
  }).join('');
}

function renderCaseInfo(c) {
  return '<div class="case-info-grid" style="margin-top:6px">' +
    '<div class="case-info-item"><label>Service Type</label>' + escHtml(c.service_type || '—') + '</div>' +
    '<div class="case-info-item"><label>Insurance</label>' + escHtml(c.insurance_provider || '—') + '</div>' +
    '<div class="case-info-item"><label>Policy #</label>' + escHtml(c.insurance_policy_number || '—') + '</div>' +
    '<div class="case-info-item"><label>Pre-auth</label>' + (c.insurance_pre_auth ? 'Yes' : 'No') + '</div>' +
    '<div class="case-info-item"><label>Opened</label>' + (c.opened_at ? new Date(c.opened_at).toLocaleString('en-GB') : '—') + '</div>' +
    '<div class="case-info-item"><label>Closed</label>' + (c.closed_at ? new Date(c.closed_at).toLocaleString('en-GB') : 'Open') + '</div>' +
    '</div>';
}

async function caseStatusChange(caseId, sel) {
  var newStatus = sel.value;
  try {
    await api('/api/cases/' + caseId + '/status', { method: 'POST', body: JSON.stringify({ status: newStatus }) });
    toast('Status updated to ' + newStatus, 'success');
    openCase(caseId);
  } catch(err) { toast(err.message, 'error'); sel.value = sel.dataset.prev || sel.value; }
}

async function toggleTask(caseId, taskId, checked) {
  try {
    await api('/api/cases/' + caseId + '/tasks/' + taskId, {
      method: 'PUT',
      body: JSON.stringify({ status: checked ? 'done' : 'pending' })
    });
    openCase(caseId);
  } catch(err) { toast(err.message, 'error'); }
}

function showAddNoteModal(caseId) {
  document.getElementById('modalTitle').textContent = 'Add Note';
  document.getElementById('modalBody').innerHTML =
    '<div class="field"><label>Note</label><textarea id="noteBody" rows="4" placeholder="Write your note…" style="width:100%;resize:vertical"></textarea></div>' +
    '<div class="field"><label>Type</label><select id="noteType"><option value="general">General</option><option value="medical">Medical</option><option value="financial">Financial</option><option value="escalation">Escalation</option></select></div>' +
    '<div class="field"><label><input type="checkbox" id="noteInternal" checked> Internal (staff only)</label></div>';
  document.getElementById('modalSaveBtn').onclick = async function() {
    var body = document.getElementById('noteBody').value.trim();
    if (!body) { toast('Note cannot be empty', 'error'); return; }
    try {
      await api('/api/cases/' + caseId + '/notes', { method: 'POST', body: JSON.stringify({
        body: body,
        note_type: document.getElementById('noteType').value,
        is_internal: document.getElementById('noteInternal').checked,
      })});
      closeModal(); toast('Note added', 'success'); openCase(caseId);
    } catch(err) { toast(err.message, 'error'); }
  };
  showModal();
}

function showAddTaskModal(caseId) {
  document.getElementById('modalTitle').textContent = 'Add Task';
  document.getElementById('modalBody').innerHTML =
    '<div class="field"><label>Title</label><input id="taskTitle" placeholder="Task title"></div>' +
    '<div class="field"><label>Description (optional)</label><textarea id="taskDesc" rows="2" style="width:100%"></textarea></div>' +
    '<div class="field"><label>Due Date (optional)</label><input id="taskDue" type="datetime-local"></div>';
  document.getElementById('modalSaveBtn').onclick = async function() {
    var title = document.getElementById('taskTitle').value.trim();
    if (!title) { toast('Title required', 'error'); return; }
    var due = document.getElementById('taskDue').value;
    try {
      await api('/api/cases/' + caseId + '/tasks', { method: 'POST', body: JSON.stringify({
        title: title,
        description: document.getElementById('taskDesc').value.trim() || null,
        due_at: due ? new Date(due).toISOString() : null,
      })});
      closeModal(); toast('Task added', 'success'); openCase(caseId);
    } catch(err) { toast(err.message, 'error'); }
  };
  showModal();
}

function showEscalateModal(caseId) {
  document.getElementById('modalTitle').textContent = 'Escalate Case';
  document.getElementById('modalBody').innerHTML =
    '<div class="field"><label>Reason</label><textarea id="escReason" rows="3" placeholder="Describe the escalation reason…" style="width:100%"></textarea></div>';
  document.getElementById('modalSaveBtn').onclick = async function() {
    var reason = document.getElementById('escReason').value.trim();
    if (!reason) { toast('Reason required', 'error'); return; }
    try {
      var r = await api('/api/cases/' + caseId + '/escalate', { method: 'POST', body: JSON.stringify({ reason: reason }) });
      closeModal(); toast('Case escalated — priority now ' + (r && r.new_priority || ''), 'success'); openCase(caseId);
    } catch(err) { toast(err.message, 'error'); }
  };
  showModal();
}

function showNewCaseModal() {
  var patientOpts = State.patients.length
    ? State.patients.map(function(p) { return '<option value="' + p.id + '">' + escHtml(p.name) + ' (' + escHtml(p.phone) + ')</option>'; }).join('')
    : '<option value="">— load patients first —</option>';
  document.getElementById('modalTitle').textContent = 'New Case';
  document.getElementById('modalBody').innerHTML =
    '<div class="field"><label>Patient *</label><select id="casePatient" style="width:100%"><option value="">Select patient…</option>' + patientOpts + '</select></div>' +
    '<div class="field"><label>Title *</label><input id="caseTitle" placeholder="Brief case title"></div>' +
    '<div class="field"><label>Type</label><select id="caseType"><option value="international_care">International Care</option><option value="medical_tourism">Medical Tourism</option><option value="local_booking">Local Booking</option><option value="emergency">Emergency</option><option value="second_opinion">Second Opinion</option><option value="insurance_claim">Insurance Claim</option><option value="teleconsultation">Teleconsultation</option></select></div>' +
    '<div class="field"><label>Priority</label><select id="casePriority"><option value="normal">Normal</option><option value="low">Low</option><option value="high">High</option><option value="urgent">Urgent</option><option value="critical">Critical</option></select></div>' +
    '<div class="field"><label>Description</label><textarea id="caseDesc" rows="2" style="width:100%"></textarea></div>' +
    '<div class="field"><label>Country of Origin</label><input id="caseCountry" placeholder="e.g. Saudi Arabia"></div>' +
    '<div class="field"><label>Est. Cost (USD)</label><input id="caseCost" type="number" placeholder="0"></div>';
  document.getElementById('modalSaveBtn').onclick = async function() {
    var patId = document.getElementById('casePatient').value;
    var title = document.getElementById('caseTitle').value.trim();
    if (!patId) { toast('Select a patient', 'error'); return; }
    if (!title) { toast('Title required', 'error'); return; }
    var cost = parseFloat(document.getElementById('caseCost').value) || null;
    try {
      var c = await api('/api/cases', { method: 'POST', body: JSON.stringify({
        patient_id: patId, title: title,
        type: document.getElementById('caseType').value,
        priority: document.getElementById('casePriority').value,
        description: document.getElementById('caseDesc').value.trim() || null,
        country_of_origin: document.getElementById('caseCountry').value.trim() || null,
        estimated_cost: cost, currency: 'USD',
      })});
      closeModal(); toast('Case ' + c.case_number + ' created', 'success');
      loadCases(); openCase(c.id);
    } catch(err) { toast(err.message, 'error'); }
  };
  showModal();
  if (!State.patients.length) loadPatients();
}


// ════════════════════════════════════════════════════════════
// FINANCE
// ════════════════════════════════════════════════════════════

async function loadFinanceKpis() {
  try {
    var s = await api('/api/finance/summary');
    var kpis = document.getElementById('financeKpis');
    if (!kpis) return;
    kpis.innerHTML =
      '<div class="kpi-card"><div class="kpi-label">Total Billed</div><div class="kpi-value blue">$' + (s.total_billed||0).toLocaleString() + '</div></div>' +
      '<div class="kpi-card"><div class="kpi-label">Collected</div><div class="kpi-value green">$' + (s.total_collected||0).toLocaleString() + '</div></div>' +
      '<div class="kpi-card"><div class="kpi-label">Outstanding</div><div class="kpi-value orange">$' + (s.outstanding||0).toLocaleString() + '</div></div>' +
      '<div class="kpi-card"><div class="kpi-label">Paid Invoices</div><div class="kpi-value">' + ((s.by_status&&s.by_status.paid)||0) + '</div></div>' +
      '<div class="kpi-card"><div class="kpi-label">Overdue</div><div class="kpi-value" style="color:#b71c1c">' + ((s.by_status&&s.by_status.overdue)||0) + '</div></div>';
  } catch(e) { console.warn('Finance KPIs:', e); }
}

async function loadInvoices() {
  var tbody = document.getElementById('invoicesTable');
  tbody.innerHTML = '<tr><td colspan="8" class="loading">Loading…</td></tr>';
  var status = document.getElementById('invoiceStatusFilter') ? document.getElementById('invoiceStatusFilter').value : '';
  var params = 'limit=100&skip=0' + (status ? '&status=' + status : '');
  try {
    var result = await api('/api/finance/invoices?' + params);
    var items = (result && result.items) || [];
    if (!items.length) { tbody.innerHTML = '<tr><td colspan="8" class="loading">No invoices found</td></tr>'; return; }
    tbody.innerHTML = items.map(function(inv) {
      var statusCls = 'inv-' + (inv.status||'draft');
      var balance = (inv.balance_due||0);
      var dueDateStr = inv.due_date ? new Date(inv.due_date).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'}) : '—';
      return '<tr>' +
        '<td><strong>' + escHtml(inv.invoice_number) + '</strong></td>' +
        '<td>' + escHtml(inv.patient_name||'—') + '</td>' +
        '<td>' + escHtml(inv.currency) + ' ' + (inv.total_amount||0).toLocaleString() + '</td>' +
        '<td style="color:#2e7d32">' + (inv.paid_amount||0).toLocaleString() + '</td>' +
        '<td style="color:' + (balance>0?'#e65100':'#2e7d32') + '">' + balance.toLocaleString() + '</td>' +
        '<td><span class="invoice-status ' + statusCls + '">' + escHtml(inv.status) + '</span></td>' +
        '<td>' + dueDateStr + '</td>' +
        '<td style="white-space:nowrap">' +
          '<button class="btn btn-secondary btn-sm" onclick="openInvoiceDetail(\'' + inv.id + '\')">View</button> ' +
          '<button class="btn btn-primary btn-sm" onclick="showRecordPaymentModal(\'' + inv.id + '\',' + balance + ',\'' + escHtml(inv.currency) + '\')">Pay</button>' +
        '</td>' +
      '</tr>';
    }).join('');
  } catch(err) {
    tbody.innerHTML = '<tr><td colspan="8"><div class="error-msg">' + escHtml(err.message) + '</div></td></tr>';
  }
}

async function openInvoiceDetail(invoiceId) {
  try {
    var inv = await api('/api/finance/invoices/' + invoiceId);
    document.getElementById('modalTitle').textContent = 'Invoice ' + inv.invoice_number;
    var itemsHtml = (inv.items||[]).map(function(it) {
      return '<tr><td>' + escHtml(it.description) + '</td><td>' + it.quantity + '</td>' +
        '<td>' + (it.unit_price||0).toLocaleString() + '</td>' +
        '<td><strong>' + (it.total||0).toLocaleString() + '</strong></td></tr>';
    }).join('');
    var paymentsHtml = (inv.payments||[]).map(function(p) {
      return '<tr><td>' + escHtml(p.method) + '</td><td>' + (p.amount||0).toLocaleString() + ' ' + escHtml(p.currency||'') + '</td>' +
        '<td>' + escHtml(p.receiver_name||'') + '</td>' +
        '<td>' + (p.received_at ? new Date(p.received_at).toLocaleDateString('en-GB') : '') + '</td></tr>';
    }).join('');
    document.getElementById('modalBody').innerHTML =
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px;font-size:12px">' +
        '<div><label style="font-weight:600">Patient:</label> ' + escHtml(inv.patient_name||'—') + '</div>' +
        '<div><label style="font-weight:600">Status:</label> <span class="invoice-status inv-' + inv.status + '">' + inv.status + '</span></div>' +
        '<div><label style="font-weight:600">Currency:</label> ' + escHtml(inv.currency) + '</div>' +
        '<div><label style="font-weight:600">Due Date:</label> ' + (inv.due_date ? new Date(inv.due_date).toLocaleDateString('en-GB') : '—') + '</div>' +
      '</div>' +
      '<h4 style="font-size:12px;margin-bottom:6px">Line Items</h4>' +
      '<table class="data-table" style="width:100%;margin-bottom:12px"><thead><tr><th>Description</th><th>Qty</th><th>Unit Price</th><th>Total</th></tr></thead><tbody>' + (itemsHtml||'<tr><td colspan="4" style="color:#999">No items</td></tr>') + '</tbody></table>' +
      '<div style="text-align:right;font-size:13px;margin-bottom:12px">' +
        'Subtotal: <strong>' + (inv.subtotal||0).toLocaleString() + '</strong> &nbsp;' +
        'Tax: <strong>' + (inv.tax_amount||0).toLocaleString() + '</strong> &nbsp;' +
        'Discount: <strong>' + (inv.discount_amount||0).toLocaleString() + '</strong> &nbsp;' +
        '<strong>Total: ' + escHtml(inv.currency) + ' ' + (inv.total_amount||0).toLocaleString() + '</strong>' +
      '</div>' +
      '<h4 style="font-size:12px;margin-bottom:6px">Payments</h4>' +
      '<table class="data-table" style="width:100%"><thead><tr><th>Method</th><th>Amount</th><th>Received By</th><th>Date</th></tr></thead><tbody>' + (paymentsHtml||'<tr><td colspan="4" style="color:#999">No payments recorded</td></tr>') + '</tbody></table>' +
      '<div style="margin-top:10px;font-size:13px;text-align:right">Paid: <strong style="color:#2e7d32">' + (inv.paid_amount||0).toLocaleString() + '</strong> &nbsp; Balance: <strong style="color:#e65100">' + (inv.balance_due||0).toLocaleString() + '</strong></div>';
    document.getElementById('modalSaveBtn').textContent = 'Record Payment';
    document.getElementById('modalSaveBtn').onclick = function() { closeModal(); showRecordPaymentModal(inv.id, inv.balance_due, inv.currency); };
    showModal();
  } catch(err) { toast(err.message, 'error'); }
}

function showRecordPaymentModal(invoiceId, balanceDue, currency) {
  document.getElementById('modalTitle').textContent = 'Record Payment';
  document.getElementById('modalSaveBtn').textContent = 'Save';
  document.getElementById('modalBody').innerHTML =
    '<div class="field"><label>Amount (' + escHtml(currency||'USD') + ')</label><input id="payAmount" type="number" step="0.01" value="' + (balanceDue||0) + '" min="0.01"></div>' +
    '<div class="field"><label>Payment Method</label><select id="payMethod"><option value="cash">Cash</option><option value="card">Card</option><option value="bank_transfer">Bank Transfer</option><option value="insurance">Insurance</option><option value="other">Other</option></select></div>' +
    '<div class="field"><label>Reference # (optional)</label><input id="payRef" placeholder="Receipt or bank reference"></div>' +
    '<div class="field"><label>Notes (optional)</label><input id="payNotes"></div>';
  document.getElementById('modalSaveBtn').onclick = async function() {
    var amount = parseFloat(document.getElementById('payAmount').value);
    if (!amount || amount <= 0) { toast('Enter a valid amount', 'error'); return; }
    try {
      await api('/api/finance/invoices/' + invoiceId + '/payments', { method: 'POST', body: JSON.stringify({
        amount: amount,
        currency: currency || 'USD',
        method: document.getElementById('payMethod').value,
        reference_number: document.getElementById('payRef').value.trim() || null,
        notes: document.getElementById('payNotes').value.trim() || null,
      })});
      closeModal(); toast('Payment recorded', 'success'); loadInvoices(); loadFinanceKpis();
    } catch(err) { toast(err.message, 'error'); }
  };
  showModal();
}

function showNewInvoiceModal() {
  var patientOpts = State.patients.length
    ? State.patients.map(function(p) { return '<option value="' + p.id + '">' + escHtml(p.name) + ' (' + escHtml(p.phone) + ')</option>'; }).join('')
    : '<option value="">— load patients first —</option>';
  document.getElementById('modalTitle').textContent = 'New Invoice';
  document.getElementById('modalSaveBtn').textContent = 'Create';
  document.getElementById('modalBody').innerHTML =
    '<div class="field"><label>Patient *</label><select id="invPatient" style="width:100%"><option value="">Select patient…</option>' + patientOpts + '</select></div>' +
    '<div class="field"><label>Currency</label><select id="invCurrency"><option value="USD">USD</option><option value="EGP">EGP</option><option value="EUR">EUR</option><option value="GBP">GBP</option><option value="SAR">SAR</option><option value="AED">AED</option></select></div>' +
    '<div class="field"><label>Tax Amount</label><input id="invTax" type="number" step="0.01" value="0"></div>' +
    '<div class="field"><label>Discount Amount</label><input id="invDiscount" type="number" step="0.01" value="0"></div>' +
    '<div class="field"><label>Due Date</label><input id="invDue" type="date"></div>' +
    '<div class="field"><label>Notes</label><input id="invNotes" placeholder="Internal notes…"></div>' +
    '<p style="font-size:11px;color:#666;margin-top:4px">You can add line items after creating the invoice.</p>';
  document.getElementById('modalSaveBtn').onclick = async function() {
    var patId = document.getElementById('invPatient').value;
    if (!patId) { toast('Select a patient', 'error'); return; }
    var due = document.getElementById('invDue').value;
    try {
      var inv = await api('/api/finance/invoices', { method: 'POST', body: JSON.stringify({
        patient_id: patId,
        currency: document.getElementById('invCurrency').value,
        tax_amount: parseFloat(document.getElementById('invTax').value)||0,
        discount_amount: parseFloat(document.getElementById('invDiscount').value)||0,
        due_date: due ? new Date(due).toISOString() : null,
        notes: document.getElementById('invNotes').value.trim() || null,
        items: [],
      })});
      closeModal(); toast('Invoice ' + inv.invoice_number + ' created', 'success');
      loadInvoices(); loadFinanceKpis();
      openInvoiceDetail(inv.id);
    } catch(err) { toast(err.message, 'error'); }
  };
  showModal();
  if (!State.patients.length) loadPatients();
}


// ════════════════════════════════════════════════════════════
// REPORTS
// ════════════════════════════════════════════════════════════

async function loadReports() {
  try {
    var stats = await api('/api/reports/dashboard');
    renderReportsDashboard(stats, container);
  } catch(err) {
    container.innerHTML = '<div class="error-msg">' + escHtml(err.message) + '</div>';
  }
}

function renderReportsDashboard(s, container) {
  var c = s.cases || {}, p = s.patients || {}, f = s.finance || {}, w = s.whatsapp || {};

  var kpiHtml =
    '<div class="reports-grid">' +
      statCard('Open Cases', c.open||0, 'Cases being actively managed') +
      statCard('Cases Today', c.today||0, 'New cases opened today') +
      statCard('SLA Breached', c.sla_breached||0, 'Active cases past SLA', c.sla_breached > 0 ? '#b71c1c' : null) +
      statCard('SLA At Risk', c.sla_at_risk||0, 'Due within 4 hours', c.sla_at_risk > 0 ? '#e65100' : null) +
      statCard('Total Patients', p.total||0, 'All-time') +
      statCard('New Patients', p.new_this_month||0, 'This month') +
      statCard('Revenue (mo)', '$' + ((f.revenue_this_month||0)).toLocaleString(), 'Payments received this month', '#2e7d32') +
      statCard('Outstanding', '$' + ((f.outstanding||0)).toLocaleString(), 'Unpaid invoices', f.outstanding > 0 ? '#e65100' : null) +
      statCard('Open Chats', w.open_conversations||0, 'WhatsApp inbox') +
      statCard('Messages Today', w.messages_today||0, 'Inbound + outbound') +
    '</div>';

  var statusHtml = '<div class="chart-card"><h4>Cases by Status</h4>' +
    '<table class="data-table" style="width:100%"><thead><tr><th>Status</th><th>Count</th></tr></thead><tbody>' +
    Object.entries(c.by_status||{}).map(function(e) {
      return '<tr><td><span class="case-badge badge-status-' + e[0] + '">' + e[0] + '</span></td><td><strong>' + e[1] + '</strong></td></tr>';
    }).join('') +
    '</tbody></table></div>';

  var priorityHtml = '<div class="chart-card"><h4>Open Cases by Priority</h4>' +
    '<table class="data-table" style="width:100%"><thead><tr><th>Priority</th><th>Count</th></tr></thead><tbody>' +
    Object.entries(c.by_priority||{}).map(function(e) {
      return '<tr><td><span class="case-badge badge-priority-' + e[0] + '">' + e[0] + '</span></td><td><strong>' + e[1] + '</strong></td></tr>';
    }).join('') +
    '</tbody></table></div>';

  var countriesHtml = '<div class="chart-card"><h4>Top Patient Countries</h4>' +
    '<table class="data-table" style="width:100%"><thead><tr><th>Country</th><th>Patients</th></tr></thead><tbody>' +
    (p.top_countries||[]).map(function(row) {
      return '<tr><td>' + escHtml(row.country||'Unknown') + '</td><td>' + row.count + '</td></tr>';
    }).join('') +
    (!(p.top_countries||[]).length ? '<tr><td colspan="2" class="loading">No data</td></tr>' : '') +
    '</tbody></table></div>';

  var monthly = (c.monthly||[]);
  var maxCount = Math.max.apply(null, monthly.map(function(m){ return m.count||0; })) || 1;
  var barsHtml = '<div class="chart-card"><h4>New Cases - Last 6 Months</h4>' +
    '<div style="display:flex;align-items:flex-end;gap:8px;height:80px;padding-top:10px">' +
    monthly.map(function(m) {
      var h = Math.round(((m.count||0)/maxCount)*70);
      return '<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px">' +
        '<span style="font-size:10px;font-weight:600;color:#333">' + (m.count||0) + '</span>' +
        '<div style="width:100%;height:' + h + 'px;background:var(--color-primary);border-radius:3px 3px 0 0;min-height:2px"></div>' +
        '<span style="font-size:9px;color:#999;white-space:nowrap">' + escHtml(m.label) + '</span>' +
      '</div>';
    }).join('') +
    '</div></div>';

  container.innerHTML =
    kpiHtml +
    '<div class="chart-row">' + barsHtml + statusHtml + '</div>' +
    '<div class="chart-row">' + priorityHtml + countriesHtml + '</div>';
}

function statCard(label, value, sub, color) {
  return '<div class="stat-card">' +
    '<div class="stat-label">' + escHtml(label) + '</div>' +
    '<div class="stat-value"' + (color ? ' style="color:' + color + '"' : '') + '>' + escHtml(String(value)) + '</div>' +
    '<div class="stat-sub">' + escHtml(sub||'') + '</div>' +
  '</div>';
}
