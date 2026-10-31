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
    $('total').textContent = events.length;
    $('flagged').textContent = events.filter(e => e.matches.length).length;
    $('rule-count').textContent = rules.filter(r => r.enabled).length;
    $('count').textContent = events.length + ' zdarzeń · widok obejmuje ostatnie 1000 zapisów';
    if (!events.length) $('events').append(node('p', 'Posterunek gotowy. Włącz wtyczkę WalleeGuard i wyślij pierwszy prompt.', 'empty-state'));
    for (const event of events) {
      const card = node('article', '', 'card card-body prompt-card mb-3');
      const meta = node('div', '', 'd-flex flex-wrap gap-2 align-items-center');
      meta.append(node('small', event.provider + ' · ' + new Date(event.received_at).toLocaleString('pl-PL'), 'prompt-meta me-auto'));
      card.append(meta);
      for (const match of event.matches) meta.append(node('span', match.severity + ' · ' + match.name, 'badge signal ' + match.severity));
      card.append(node('pre', event.prompt)); $('events').append(card);
    }
    $('rules').replaceChildren();
    for (const rule of rules) {
      const row = node('div', '', 'rule-row');
      row.append(node('div', rule.name + ' · ' + (rule.type === 'email' ? 'E-mail' : rule.type === 'pesel' ? 'PESEL' : '„' + rule.contains + '”') + (rule.enabled ? '' : ' · wyłączona'), 'rule-description mb-2'), node('span', rule.severity, 'badge signal ' + rule.severity));
      const button = node('button', 'Usuń', 'btn btn-sm btn-outline-secondary float-end'); button.onclick = () => run(async () => {await api('/api/rules/' + rule.id, {method:'DELETE'}); await refresh();});
      const edit = node('button', 'Edytuj', 'btn btn-sm btn-outline-secondary ms-2');
      edit.onclick = () => { fillRule(rule); $('rule-type').focus(); };
      row.append(button, edit); $('rules').append(row);
    }
    $('error').textContent = '';
  } catch (e) { $('error').textContent = e.message; throw e; }
}
async function run(fn) { try { await fn(); } catch(e) { $('error').textContent = e.message; } }
$('auth').onsubmit = e => {e.preventDefault(); token = $('token').value; run(async () => {await refresh(); $('token').value = ''; $('login').hidden = true; $('workspace').hidden = false; $('status').textContent = 'Połączono'; $('status').classList.add('connected');});};
$('logout').onclick = () => {token=''; $('events').replaceChildren(); $('rules').replaceChildren(); $('workspace').hidden=true; $('login').hidden=false; fillRule({}); $('status').textContent='Rozłączono'; $('status').classList.remove('connected'); for (const id of ['total','flagged','rule-count']) $(id).textContent='0';};
$('refresh').onclick = () => run(refresh);
for (const id of ['search','provider','severity']) $(id).onchange = () => run(refresh);

const help = {
  contains: 'Dosłowny fragment tekstu bez rozróżniania wielkości liter.',
  email: 'Typowe adresy e-mail, np. osoba@example.com. To detektor, nie pełna walidacja RFC.',
  pesel: '11 cyfr, poprawna data urodzenia i suma kontrolna. Nie sprawdza, czy numer został nadany.'
};
function updateBuilder() {
  const kind = $('rule-type').value;
  $('contains-field').hidden = kind !== 'contains';
  $('rule-text').required = kind === 'contains';
  $('rule-help').textContent = help[kind];
  $('test-result').textContent = '';
}
function fillRule(rule) {
  $('rule').reset();
  $('rule-id').value = rule.id || '';
  $('rule-type').value = rule.type || 'contains';
  $('rule-name').value = rule.name || '';
  $('rule-text').value = rule.contains || '';
  $('rule-severity').value = rule.severity || 'warning';
  $('rule-enabled').checked = rule.enabled !== 0 && rule.enabled !== false;
  $('save-rule').textContent = rule.id ? 'Zapisz zmiany' : 'Zapisz regułę';
  updateBuilder();
}
function rulePayload() {
  return {name:$('rule-name').value, type:$('rule-type').value,
    contains:$('rule-text').value, severity:$('rule-severity').value, enabled:$('rule-enabled').checked};
}
$('rule-type').onchange = updateBuilder;
$('rule').oninput = () => { $('test-result').textContent = ''; };
$('template-email').onclick = () => fillRule({name:'Adres e-mail',type:'email',severity:'warning'});
$('template-pesel').onclick = () => fillRule({name:'Numer PESEL',type:'pesel',severity:'critical'});
$('reset-rule').onclick = () => fillRule({});
$('test-rule').onclick = () => {
  if (!$('rule').reportValidity()) return;
  run(async () => {
    const result = await api('/api/rules/test', {method:'POST',body:JSON.stringify({...rulePayload(),text:$('rule-sample').value})});
    $('test-result').textContent = result.matched ? 'Dopasowanie — reguła wykryła sygnał.' : 'Brak dopasowania' + ($('rule-enabled').checked ? '.' : ' — reguła jest wyłączona.');
  });
};
$('rule').onsubmit = e => {
  e.preventDefault();
  run(async () => {
    const id = $('rule-id').value;
    await api('/api/rules' + (id ? '/' + id : ''), {method:'POST',body:JSON.stringify(rulePayload())});
    fillRule({});
    await refresh();
  });
};
fillRule({});
