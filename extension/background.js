let serial = Promise.resolve();
function enqueue(fn) {
  const task = serial.then(fn);
  serial = task.catch(() => {});
  return task;
}
async function installation() {
  const {instanceId} = await chrome.storage.local.get('instanceId');
  if (instanceId) return instanceId;
  const id = crypto.randomUUID();
  await chrome.storage.local.set({instanceId:id});
  return id;
}
async function request(endpoint, token, path, data) {
  const response = await fetch(endpoint + path, {
    method:'POST', headers:{'Content-Type':'application/json', Authorization:'Bearer '+token},
    body:JSON.stringify(data), signal:AbortSignal.timeout(10000), redirect:'error', credentials:'omit'
  });
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'API: '+response.status);
  return result;
}
async function heartbeat(endpoint, token) {
  const info = await request(endpoint, token, '/api/heartbeat',
    {instance_id:await installation(), version:chrome.runtime.getManifest().version});
  await chrome.storage.local.set({deviceId:info.id, deviceName:info.name, deviceGroup:info.group_name});
  return info;
}
async function flush() {
  const {endpoint, token, queue = []} = await chrome.storage.local.get(['endpoint','token','queue']);
  if (!endpoint || !token) return;
  try {
    const info = await heartbeat(endpoint, token);
    const pending = [...queue];
    while (pending.length) {
      await request(endpoint, token, '/api/events', {...pending[0], endpoint_id:info.id,
        instance_id:await installation(), version:chrome.runtime.getManifest().version});
      pending.shift();
      await chrome.storage.local.set({queue:pending,lastError:'',lastSuccess:new Date().toISOString()});
    }
    await chrome.storage.local.set({lastError:''});
  } catch(e) { await chrome.storage.local.set({lastError:e.message || 'Brak połączenia z kolektorem'}); }
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  let task;
  const settingsPage = sender.url === chrome.runtime.getURL('options.html');
  if (settingsPage && message.type === 'configure') {
    task = async () => {
      const config = message.config;
      const url = new URL(config.endpoint);
      if (url.origin !== config.endpoint || (url.protocol !== 'https:' &&
          !(url.protocol === 'http:' && ['localhost','127.0.0.1'].includes(url.hostname)))) throw Error('Nieprawidłowy adres kolektora');
      if (typeof config.token !== 'string' || config.token.length < 32) throw Error('Nieprawidłowy token endpointu');
      const old = await chrome.storage.local.get(['endpoint','token','queue']);
      if ((old.endpoint !== config.endpoint || old.token !== config.token) && old.queue?.length)
        throw Error('Przed zmianą serwera lub tokena wyślij albo usuń oczekujące prompty.');
      const info = await heartbeat(config.endpoint, config.token);
      await chrome.storage.local.set({endpoint:config.endpoint,token:config.token,enabled:!!config.enabled,lastError:''});
      return info;
    };
  } else if (settingsPage && message.type === 'clearQueue') {
    task = () => chrome.storage.local.set({queue:[]});
  } else if (message.type === 'capture') {
    const expected = {'chatgpt.com':'chatgpt','claude.ai':'claude','gemini.google.com':'gemini'};
    let host; try { host = new URL(sender.url).hostname; } catch { return; }
    if (!sender.tab || expected[host] !== message.event?.provider) return;
    task = async () => {
      const {enabled,queue=[]} = await chrome.storage.local.get(['enabled','queue']);
      if (!enabled || typeof message.event.prompt !== 'string' || !message.event.prompt.trim() ||
          message.event.prompt.length > 100000 || typeof message.event.id !== 'string') return;
      if (queue.length >= 100) throw Error('Kolejka pełna (100). Nowy prompt nie został zapisany.');
      queue.push({id:message.event.id,provider:message.event.provider,prompt:message.event.prompt});
      await chrome.storage.local.set({queue});
      await flush();
    };
  } else { return; }
  enqueue(task).then(result => reply({ok:true,result})).catch(async e => {
    await chrome.storage.local.set({lastError:e.message}); reply({ok:false,error:e.message});
  });
  return true;
});
chrome.alarms.create('retry', {periodInMinutes:1});
chrome.alarms.onAlarm.addListener(() => enqueue(flush));
chrome.runtime.onStartup.addListener(() => enqueue(flush));
chrome.action.onClicked.addListener(() => chrome.runtime.openOptionsPage());
