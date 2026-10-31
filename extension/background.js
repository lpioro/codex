let serial = Promise.resolve();
function enqueue(fn) { serial = serial.then(fn).catch(() => {}); return serial; }
async function flush() {
  const {endpoint, token, queue = []} = await chrome.storage.local.get(['endpoint','token','queue']);
  if (!endpoint || !token) return;
  const pending = [...queue];
  while (pending.length) {
    try {
      const response = await fetch(endpoint + '/api/events', {
        method:'POST', headers:{'Content-Type':'application/json', Authorization:'Bearer '+token},
        body:JSON.stringify(pending[0]), signal:AbortSignal.timeout(10000), redirect:'error', credentials:'omit'
      });
      if (!response.ok) {
        await chrome.storage.local.set({lastError:'API: '+response.status});
        break;
      }
      pending.shift();
      await chrome.storage.local.set({queue:pending, lastError:'', lastSuccess:new Date().toISOString()});
    } catch { await chrome.storage.local.set({lastError:'Brak połączenia z kolektorem'}); break; }
  }
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (message.type !== 'capture') return;
  const expected = {'chatgpt.com':'chatgpt','claude.ai':'claude','gemini.google.com':'gemini'};
  let host; try { host = new URL(sender.url).hostname; } catch { return; }
  if (!sender.tab || expected[host] !== message.event?.provider) return;
  enqueue(async () => {
    const {enabled, queue = []} = await chrome.storage.local.get(['enabled','queue']);
    if (!enabled || typeof message.event.prompt !== 'string' || message.event.prompt.length > 100000) return;
    if (queue.length >= 100) {
      await chrome.storage.local.set({lastError:'Kolejka pełna (100). Nowy prompt nie został zapisany.'});
      return;
    }
    queue.push(message.event);
    await chrome.storage.local.set({queue});
    await flush();
  }).then(() => reply({ok:true}));
  return true;
});
chrome.alarms.create('retry', {periodInMinutes:1});
chrome.alarms.onAlarm.addListener(() => enqueue(flush));
chrome.action.onClicked.addListener(() => chrome.runtime.openOptionsPage());
