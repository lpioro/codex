const $ = id => document.getElementById(id);
async function load() {
  const s = await chrome.storage.local.get(['endpoint','token','enabled','queue','lastError','lastSuccess','instanceId','deviceId','deviceName','deviceGroup']);
  $('endpoint').value = s.endpoint || '';
  $('token').value = s.token || '';
  $('enabled').checked = !!s.enabled;
  $('identity').textContent = s.deviceId ? (s.deviceName + (s.deviceGroup ? ' · '+s.deviceGroup : '') + ' · ID: '+s.deviceId+' · Instalacja: '+s.instanceId) : 'Jeszcze nie sparowano. Utwórz endpoint w dashboardzie i wpisz jego token.';
  $('status').textContent = 'Oczekujące: '+(s.queue || []).length+'. Ostatni zapis: '+(s.lastSuccess || 'brak')+'. '+(s.lastError || '');
}
$('settings').onsubmit = async e => {
  e.preventDefault();
  try {
    const url = new URL($('endpoint').value);
    if (url.username || url.password || url.search || url.hash || url.pathname !== '/') throw Error('Podaj sam adres domeny bez ścieżki.');
    if (url.protocol !== 'https:' && !(url.protocol === 'http:' && ['localhost','127.0.0.1'].includes(url.hostname))) throw Error('Wymagane HTTPS lub lokalny HTTP.');
    if ($('token').value.length < 32) throw Error('Token musi mieć co najmniej 32 znaki.');
    const granted = await chrome.permissions.request({origins:[url.origin+'/*']});
    if (!granted) throw Error('Nie przyznano dostępu do serwera.');
    const response = await chrome.runtime.sendMessage({type:'configure',config:{endpoint:url.origin,token:$('token').value,enabled:$('enabled').checked}});
    if (!response.ok) throw Error(response.error);
    await load();
    $('status').textContent = 'Sparowano: '+response.result.name+'. Przechwytywanie: '+($('enabled').checked ? 'włączone' : 'wyłączone');
  } catch(e) { $('status').textContent = e.message; }
};
$('clear').onclick = async () => { await chrome.runtime.sendMessage({type:'clearQueue'}); await load(); };
load();
