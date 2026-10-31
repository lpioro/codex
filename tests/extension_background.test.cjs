const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const {webcrypto} = require('node:crypto');

test('each installation keeps its identity, sends metadata and protects queued events during reconfiguration', async () => {
  const state = {}, calls = [];
  let listener, alarm, offline = false;
  const token = 'a'.repeat(43), otherToken = 'b'.repeat(43);
  const chrome = {
    storage:{local:{
      get:async keys => Object.fromEntries((typeof keys === 'string' ? [keys] : keys).filter(k => k in state).map(k => [k,structuredClone(state[k])])),
      set:async values => Object.assign(state,structuredClone(values))
    }},
    runtime:{
      getManifest:()=>({version:'0.3.0'}), getURL:path=>'chrome-extension://test/'+path,
      onMessage:{addListener:fn=>listener=fn}, onStartup:{addListener:()=>{}}
    },
    alarms:{create:()=>{}, onAlarm:{addListener:fn=>alarm=fn}},
    action:{onClicked:{addListener:()=>{}}}
  };
  const fetch = async (url, options) => {
    if (offline) throw Error('offline');
    const data=JSON.parse(options.body);
    calls.push({url,data});
    if (url.endsWith('/api/heartbeat')) return {ok:true,json:async()=>({id:'device-a',name:'Laptop A',group_name:'QA'})};
    return {ok:true,json:async()=>({id:data.id})};
  };
  vm.runInNewContext(fs.readFileSync('extension/background.js','utf8'),{chrome,crypto:webcrypto,fetch,URL,AbortSignal,Error});
  const settings={url:'chrome-extension://test/options.html'};
  const content={url:'https://chatgpt.com/c/demo',tab:{id:1}};
  const send=(message,sender=settings)=>new Promise(resolve=>listener(message,sender,resolve));
  assert.equal((await send({type:'configure',config:{endpoint:'https://collector.example.com',token,enabled:true}})).ok,true);
  const instance=state.instanceId;
  assert.match(instance,/^[0-9a-f-]{36}$/);
  assert.equal(state.deviceId,'device-a');
  await send({type:'capture',event:{id:'event-one',provider:'chatgpt',prompt:'hello'}},content);
  const event=calls.find(c=>c.url.endsWith('/api/events')).data;
  assert.equal(event.endpoint_id,'device-a');
  assert.equal(event.instance_id,instance);
  assert.equal(event.version,'0.3.0');
  assert.equal(state.queue.length,0);
  offline=true;
  await send({type:'capture',event:{id:'queued',provider:'chatgpt',prompt:'pending'}},content);
  assert.equal(state.queue.length,1);
  const changed=await send({type:'configure',config:{endpoint:'https://other.example.com',token:otherToken,enabled:true}});
  assert.equal(changed.ok,false);
  assert.equal(state.token,token);
  await send({type:'clearQueue'});
  assert.equal(state.queue.length,0);
  offline=false;
  await alarm();
  assert.equal(state.instanceId,instance);
  assert.ok(calls.filter(c=>c.url.endsWith('/api/heartbeat')).every(c=>c.data.instance_id===instance));
  assert.equal(listener({type:'configure',config:{}},content,()=>{}),undefined);
});
