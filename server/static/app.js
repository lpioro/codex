let token = '';
const $ = id => document.getElementById(id);
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}});
  if (!response.ok) throw new Error(response.status === 401 ? 'Nieprawidłowy token.' : 'Błąd API: ' + response.status);
  return response.json();
}
function node(tag, text, cls) { const el = document.createElement(tag); el.textContent = text; if(cls) el.className = cls; return el; }
async function refresh() {
  try {
    const params = new URLSearchParams({q: $('search').value, provider: $('provider').value, severity: $('severity').value});
    const [events, rules] = await Promise.all([api('/api/events?' + params), api('/api/rules')]);
    $('events').replaceChildren();
    $('count').textContent = events.length + ' zdarzeń · widok obejmuje ostatnie 1000 zapisów';
    if (!events.length) $('events').append(node('p', 'Brak zdarzeń. Włącz przechwytywanie we wtyczce i wyślij prompt.'));
    for (const event of events) {
      const card = node('article', '');
      card.append(node('small', event.provider + ' · ' + new Date(event.received_at).toLocaleString('pl-PL')));
      for (const match of event.matches) card.append(node('span', match.severity + ' · ' + match.name, 'badge ' + match.severity));
      card.append(node('pre', event.prompt)); $('events').append(card);
    }
    $('rules').replaceChildren();
    for (const rule of rules) {
      const row = node('div', '', 'rule-row');
      row.append(node('span', rule.name + ' · „' + rule.contains + '”'), node('span', rule.severity, 'badge ' + rule.severity));
      const button = node('button', 'Usuń'); button.onclick = () => run(async () => {await api('/api/rules/' + rule.id, {method:'DELETE'}); await refresh();});
      row.append(button); $('rules').append(row);
    }
    $('error').textContent = '';
  } catch (e) { $('error').textContent = e.message; throw e; }
}
async function run(fn) { try { await fn(); } catch(e) { $('error').textContent = e.message; } }
$('auth').onsubmit = e => {e.preventDefault(); token = $('token').value; run(async () => {await refresh(); $('token').value = ''; $('login').hidden = true; $('workspace').hidden = false; $('status').textContent = 'Połączono';});};
$('logout').onclick = () => {token=''; $('events').replaceChildren(); $('rules').replaceChildren(); $('workspace').hidden=true; $('login').hidden=false; $('status').textContent='Rozłączono';};
$('refresh').onclick = () => run(refresh);
for (const id of ['search','provider','severity']) $(id).onchange = () => run(refresh);
$('rule').onsubmit = e => {e.preventDefault(); run(async () => {await api('/api/rules', {method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(e.target)))}); e.target.reset(); await refresh();});};
