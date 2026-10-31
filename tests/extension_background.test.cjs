const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const {webcrypto} = require('node:crypto');

test('each installation keeps its identity, sends metadata and protects queued events during reconfiguration', async () => {
  const state = {}, calls = [];
  let listener, alarm, offline = false, denied = false;
  const token = 'a'.repeat(43), otherToken = 'b'.repeat(43);
  const chrome = {
    storage:{local:{
      get:async keys => Object.fromEntries((typeof keys === 'string' ? [keys] : keys).filter(k => k in state).map(k => [k,structuredClone(state[k])])),
      set:async values => Object.assign(state,structuredClone(values))
    }},
    runtime:{
      getManifest:()=>({version:'0.4.0'}), getURL:path=>'chrome-extension://test/'+path,
      onMessage:{addListener:fn=>listener=fn}, onStartup:{addListener:()=>{}}
    },
    alarms:{create:()=>{}, onAlarm:{addListener:fn=>alarm=fn}},
    action:{onClicked:{addListener:()=>{}}}
  };
  const fetch = async (url, options) => {
    if (offline) throw Error('offline');
    const data=JSON.parse(options.body);
    calls.push({url,data});
    if(url.endsWith('/api/policy')&&denied)return {ok:false,status:401,json:async()=>({error:'Revoked'})};
    if(url.endsWith('/api/policy'))return {ok:true,json:async()=>({version:'v1',rules:[{id:1,name:'Secret',type:'contains',contains:'secret',severity:'critical'}]})};
    if (url.endsWith('/api/heartbeat')) return {ok:true,json:async()=>({id:'device-a',name:'Laptop A',group_name:'QA'})};
    return {ok:true,json:async()=>({id:data.id})};
  };
  const context=vm.createContext({chrome,crypto:webcrypto,fetch,URL,AbortSignal,Error,TextEncoder});
  context.importScripts=name=>vm.runInContext(fs.readFileSync('extension/'+name,'utf8'),context);
  vm.runInContext(fs.readFileSync('extension/background.js','utf8'),context);
  const settings={url:'chrome-extension://test/options.html'};
  const content={url:'https://chatgpt.com/c/demo',tab:{id:1}};
  const send=(message,sender=settings)=>new Promise(resolve=>listener(message,sender,resolve));
  assert.equal((await send({type:'configure',config:{endpoint:'https://collector.example.com',token,enabled:true}})).ok,true);
  const instance=state.instanceId;
  const blocked=await send({type:'preflight',event:{id:'blocked',provider:'chatgpt',prompt:'a SECRET'}},content);
  assert.equal(blocked.result.decision,'block');
  await send({type:'clearQueue'}); // Wait for the serialized audit queue.
  assert.ok(calls.some(call=>call.url.endsWith('/api/events')&&call.data.action==='blocked'));
  assert.ok(calls.filter(call=>call.url.endsWith('/api/policy')).every(call=>!('prompt' in call.data)));

  assert.match(instance,/^[0-9a-f-]{36}$/);
  assert.equal(state.deviceId,'device-a');
  await send({type:'capture',event:{id:'event-one',provider:'chatgpt',prompt:'hello'}},content);
  const event=calls.find(c=>c.url.endsWith('/api/events')&&c.data.id==='event-one').data;
  assert.equal(event.endpoint_id,'device-a');
  assert.equal(event.instance_id,instance);
  assert.equal(event.version,'0.4.0');
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
  state.enabled=false;offline=true;
  state.blockingPolicy.fetchedAt=Date.now()-120000;
  assert.equal((await send({type:'preflight',event:{id:'cached',provider:'chatgpt',prompt:'SECRET'}},content)).result.decision,'block');
  assert.equal((await send({type:'preflight',event:{id:'cached-safe',provider:'chatgpt',prompt:'hello'}},content)).result.decision,'allow');
  state.blockingPolicy.fetchedAt=Date.now()-301000;
  assert.equal((await send({type:'preflight',event:{id:'expired',provider:'chatgpt',prompt:'hello'}},content)).ok,false);
  offline=false;denied=true;state.blockingPolicy.fetchedAt=Date.now()-120000;
  assert.equal((await send({type:'preflight',event:{id:'revoked',provider:'chatgpt',prompt:'hello'}},content)).ok,false);
  await send({type:'disableBlocking'});
  assert.equal((await send({type:'preflight',event:{id:'disabled',provider:'chatgpt',prompt:'secret'}},content)).result.decision,'disabled');

});
