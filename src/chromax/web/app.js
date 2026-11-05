'use strict';
let token = '';
let refreshTimer;
const $ = id => document.getElementById(id);
const notice = message => { $('notice').textContent = message; };
async function api(path, data) {
  if (!token) throw new Error('Connect with your local access token first.');
  const response = await fetch(path, { method: data ? 'POST' : 'GET', cache: 'no-store',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: data ? JSON.stringify(data) : undefined });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}
const gib = bytes => (bytes / 1073741824).toFixed(1) + ' GB';
async function refresh() {
  try {
    const s = await api('/v1/status');
    $('connection').textContent = 'Connected to ' + s.hostname;
    const m = s.memory;
    if (m.MemTotal) {
      const used = m.MemTotal - m.MemAvailable;
      $('memory').textContent = gib(used);
      $('memory-detail').textContent = 'of ' + gib(m.MemTotal) + ' total';
      $('memory-bar').style.width = (used / m.MemTotal * 100) + '%';
    }
    $('storage').textContent = gib(s.disk.used);
    $('storage-detail').textContent = gib(s.disk.free) + ' available';
    $('storage-bar').style.width = (s.disk.used / s.disk.total * 100) + '%';
    $('cpu').textContent = s.load[0].toFixed(2);
    $('cpu-bar').style.width = Math.min(100, s.load[0] / s.cpus * 100) + '%';
    $('cpu-detail').textContent = s.cpus + ' cores · ' + s.architecture;
    const hours = Math.floor((s.uptime_seconds || 0) / 3600);
    $('uptime').textContent = hours ? hours + 'h ' + Math.floor(s.uptime_seconds % 3600 / 60) + 'm' : Math.floor((s.uptime_seconds || 0) / 60) + ' minutes';
    $('host').textContent = s.hostname;
    $('kernel').textContent = 'Linux ' + s.kernel;
    const model = await api('/v1/model');
    $('model-status').textContent = model.sha256 ? 'Local GGUF · ' + gib(model.bytes) : 'Provision a GGUF model to get started';
  } catch (error) { notice(error.message); }
}
$('auth').addEventListener('submit', async event => {
  event.preventDefault(); token = $('token').value.trim();
  try {
    await api('/v1/status'); $('token').value = ''; $('connect').hidden = true;
    notice(''); await refresh(); clearInterval(refreshTimer); refreshTimer = setInterval(refresh, 10000);
  } catch (error) { token = ''; notice(error.message); }
});
function message(role, text) {
  const container = document.createElement('div'); container.className = 'message ' + role;
  const avatar = document.createElement('span'); avatar.className = 'avatar'; avatar.textContent = role === 'user' ? '↗' : '✳';
  const paragraph = document.createElement('p'); paragraph.textContent = text;
  container.append(avatar, paragraph); $('conversation').append(container);
  $('conversation').scrollTop = $('conversation').scrollHeight;
}
$('ask-form').addEventListener('submit', async event => {
  event.preventDefault(); const question = $('question').value.trim(); if (!question) return;
  $('send').disabled = true; notice(''); message('user', question); $('question').value = '';
  try { const response = await api('/v1/ask', { question }); message('assistant', response.answer); }
  catch (error) { message('assistant', error.message); }
  finally { $('send').disabled = false; $('question').focus(); }
});
document.querySelectorAll('[data-question]').forEach(button => button.addEventListener('click', () => {
  $('question').value = button.dataset.question; $('question').focus();
}));
async function plan(action, args) {
  try {
    const p = await api('/v1/plans', { action, arguments: args });
    $('plan').hidden = false;
    $('plan').textContent = p.summary + '\n\nReview and apply in your local console:\nsudo chromaxctl apply ' + p.id + ' --confirm ' + p.id + '\n\nExpires in 15 minutes. No change has been made.';
  } catch (error) { notice(error.message); }
}
$('hostname-form').addEventListener('submit', event => { event.preventDefault(); plan('hostname', { name: $('hostname').value.trim() }); });
$('service-form').addEventListener('submit', event => { event.preventDefault(); plan('service-restart', { service: $('service').value }); });
