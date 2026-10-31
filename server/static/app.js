let token = '', currentView = 'overview', refreshId = 0, refreshTimer;
const $ = id => document.getElementById(id);
const views = {
  overview:['Przegląd bezpieczeństwa','Aktywność, sygnały i kondycja Twoich instalacji w jednym miejscu.','Przegląd'],
  events:['Strumień zdarzeń','Pełna treść promptów z kontekstem urządzenia, zespołu i reguł.','Zdarzenia'],
  alerts:['Centrum alertów','Zdarzenia, które wymagają Twojej uwagi.','Alerty'],
  endpoints:['Endpointy przeglądarek','Zarządzaj instalacjami, tokenami i dostępem do kolektora.','Endpointy'],
  groups:['Grupy i zespoły','Porządkuj urządzenia i analizuj ruch wybranego zespołu.','Grupy'],
  rules:['Reguły wykrywania','Buduj detektory, sprawdzaj dopasowania i zarządzaj sygnałami.','Reguły']
};
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'}});
  const data = await response.json();
  if (!response.ok) throw Error(response.status===401 ? 'Sesja lub token są nieprawidłowe.' : data.error || 'Błąd API: '+response.status);
  return data;
}
function node(tag,text,cls) {const el=document.createElement(tag); el.textContent=text; if(cls)el.className=cls; return el;}
async function run(fn) {try {await fn();} catch(e){$('error').textContent=e.message;if(!$('login').hidden)$('login-error').textContent=e.message;}}
function query() {
  return new URLSearchParams({q:$('search').value,provider:$('provider').value,severity:$('severity').value,
    endpoint_id:$('endpoint-filter').value,group:$('group-filter').value,range:$('time-filter').value,action:$('action-filter').value});
}
function switchView(view) {
  if (!views[view]) return;
  currentView=view;
  for(const key of Object.keys(views)) $('panel-'+key).hidden=key!==view;
  for(const button of document.querySelectorAll('nav [data-view]')) {
    button.classList.toggle('active',button.dataset.view===view);
    button.setAttribute('aria-current',button.dataset.view===view?'page':'false');
  }
  [$('view-title').textContent,$('view-description').textContent,$('view-crumb').textContent]=views[view];
}
document.querySelectorAll('[data-view]').forEach(button=>button.onclick=()=>switchView(button.dataset.view));
function eventCards(target,events) {
  target.replaceChildren();
  if(!events.length) target.append(node('p','Brak zdarzeń dla wybranych filtrów. Spróbuj innej grupy lub zakresu czasu.','empty-state'));
  for(const event of events) {
    const card=node('article','','card prompt-card');
    const meta=node('div','','d-flex flex-wrap gap-2 align-items-center');
    meta.append(node('small',event.provider+' · '+new Date(event.received_at).toLocaleString('pl-PL'),'prompt-meta me-auto'));
    for(const match of event.matches) meta.append(node('span',match.severity+' · '+match.name,'badge signal '+match.severity));
    if(event.action==='blocked')meta.append(node('span','Zatrzymane przez wtyczkę','badge signal critical'));
    if(event.action==='allowed')meta.append(node('span','Dozwolone przez politykę','badge signal info'));
    card.append(meta,node('div',(event.endpoint_name||'Nieprzypisany endpoint')+' · '+(event.endpoint_group||'Bez grupy'),'small text-body-secondary mt-2 text-break'),node('pre',event.prompt));
    target.append(card);
  }
}
async function refresh() {
  if(!token) return;
  const id=++refreshId;
  try {
    const params=query();
    const [events,rules,endpoints,groups,analytics,alerts]=await Promise.all([
      api('/api/events?'+params),api('/api/rules'),api('/api/endpoints'),api('/api/groups'),
      api('/api/analytics?'+params),api('/api/events?'+params+'&alerts=1')
    ]);
    if(id!==refreshId||!token) return;
    renderEndpoints(endpoints); renderGroups(groups);
    eventCards($('events'),events); eventCards($('alerts-list'),alerts);
    $('total').textContent=analytics.total.toLocaleString('pl-PL');
    $('flagged').textContent=analytics.alerts.toLocaleString('pl-PL');
    $('critical-total').textContent=analytics.critical.toLocaleString('pl-PL');
    $('endpoint-total').textContent=analytics.endpoints;
    $('blocked-total').textContent=analytics.blocked;
    $('rule-count').textContent=rules.filter(r=>r.enabled).length;
    $('alert-rate').textContent=(analytics.total ? Math.round(100*analytics.alerts/analytics.total) : 0)+'% wybranego ruchu';
    $('nav-events').textContent=analytics.total; $('nav-alerts').textContent=analytics.alerts;
    $('count').textContent=events.length+' z '+analytics.total+' zdarzeń · maks. 1000 w liście';
    $('scope-label').textContent='Dane dla wybranych filtrów'+($('search').value?' · Szukasz: '+$('search').value:'');
    $('updated-at').textContent='Aktualizacja: '+new Date(analytics.generated_at).toLocaleTimeString('pl-PL');
    renderLineChart(analytics.buckets);
    renderAlertChart(analytics.buckets);
    distribution('severity-chart',analytics.severity,{critical:'#db6875',warning:'#eea052',info:'#5288dc'},key=>{$('severity').value=key;run(refresh);}, {critical:'Krytyczne',warning:'Ostrzeżenia',info:'Informacyjne'});
    distribution('provider-chart',analytics.providers,{chatgpt:'#3b9c8a',claude:'#d98f61',gemini:'#6f80da'},key=>{$('provider').value=key;run(refresh);});
    $('top-rules').replaceChildren();
    if(!analytics.top_rules.length)$('top-rules').append(node('p','Brak dopasowań w tym zakresie.','small text-body-secondary'));
    for(const rule of analytics.top_rules) {
      const row=node('div','','distribution-row wide'); row.append(node('span',rule.name,'top-rule-label'),node('strong',String(rule.count)));$('top-rules').append(row);
    }
    $('recent-alerts').replaceChildren();
    if(!alerts.length)$('recent-alerts').append(node('p','Brak sygnałów w wybranym zakresie.','empty-state m-3'));
    for(const event of alerts.slice(0,5)) {
      const level=['critical','warning','info'].find(l=>event.matches.some(m=>m.severity===l));
      const row=node('div','','recent-row'),body=node('div','','recent-text');
      body.append(node('strong',event.matches.map(m=>m.name).join(' · ')),node('small',(event.endpoint_name||'Nieprzypisany')+' · '+event.provider));
      const button=node('button','Zobacz →','btn btn-link btn-sm');
      button.onclick=()=>{switchView('alerts');};
      row.append(node('span',level,'badge signal '+level),body,node('small',new Date(event.received_at).toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'})),button);
      $('recent-alerts').append(row);
    }
    $('rules').replaceChildren();
    for(const rule of rules) {
      const row=node('div','','rule-row');
      row.append(node('div',rule.name+' · '+(rule.type==='email'?'E-mail':rule.type==='pesel'?'PESEL':'„'+rule.contains+'”')+(rule.enabled?'':' · wyłączona'),'rule-description mb-2'),node('span',rule.severity,'badge signal '+rule.severity));
      const remove=node('button','Usuń','btn btn-sm btn-outline-secondary float-end');remove.onclick=()=>run(async()=>{await api('/api/rules/'+rule.id,{method:'DELETE'});await refresh();});
      const edit=node('button','Edytuj','btn btn-sm btn-outline-secondary ms-2');edit.onclick=()=>{fillRule(rule);$('rule-type').focus();};
      row.append(remove,edit);$('rules').append(row);
    }
    $('error').textContent='';
  } catch(e) {if(id===refreshId) $('error').textContent=e.message; throw e;}
}
function resetFilters() {
  for(const key of ['search','provider','severity','group-filter','endpoint-filter','action-filter'])$(key).value='';
  $('time-filter').value='24h';run(refresh);
}
$('reset-filters').onclick=resetFilters;
$('refresh').onclick=()=>run(refresh);
for(const id of ['search','provider','severity','endpoint-filter','time-filter','group-filter','action-filter'])$(id).onchange=()=>run(refresh);
$('auth').onsubmit=e=>{
  e.preventDefault();token=$('token').value;
  run(async()=>{await refresh();$('token').value='';$('login-error').textContent='';$('login').hidden=true;$('workspace').hidden=false;$('status').textContent='Kolektor połączony';$('status').classList.add('connected');switchView('overview');clearInterval(refreshTimer);refreshTimer=setInterval(()=>{if(token&&$('auto-refresh').checked&&!document.hidden)run(refresh);},30000);});
};
$('logout').onclick=()=>{
  token='';refreshId++;clearInterval(refreshTimer);
  for(const id of ['events','alerts-list','recent-alerts','rules','endpoints','groups-list','top-rules','activity-chart','alert-chart','provider-chart','severity-chart'])$(id).replaceChildren();
  $('workspace').hidden=true;$('login').hidden=false;$('token').value='';hideEndpointToken();resetEndpointForm();fillRule({});
  $('status').textContent='Rozłączono';$('status').classList.remove('connected');$('error').textContent='';
};
const SVG='http://www.w3.org/2000/svg';
function svgNode(tag,attributes={},text) {const el=document.createElementNS(SVG,tag);for(const [key,value]of Object.entries(attributes))el.setAttribute(key,value);if(text!==undefined)el.textContent=text;return el;}
function chartRoot(target,label) {
  const root=svgNode('svg',{viewBox:'0 0 720 240',role:'img','aria-label':label});
  root.append(svgNode('title',{},label));$(target).replaceChildren(root);return root;
}
function renderLineChart(buckets) {
  const root=chartRoot('activity-chart','Prompty i alerty w czasie. Każdy punkt ma opis z liczbą zdarzeń.');
  const max=Math.max(1,...buckets.map(b=>b.events)),x=i=>42+i*650/(buckets.length-1),y=n=>200-160*n/max;
  for(let n=0;n<=4;n++){const v=Math.ceil(max*n/4);root.append(svgNode('line',{x1:42,x2:700,y1:y(v),y2:y(v),stroke:'#edf0f5'}),svgNode('text',{x:32,y:y(v)+3,'text-anchor':'end',fill:'#9aa4b3','font-size':10},String(v)));}
  for(const [field,color]of [['events','#4d84d8'],['alerts','#ec8a48']]) {
    const points=buckets.map((b,i)=>x(i)+','+y(b[field])).join(' ');
    if(field==='events')root.append(svgNode('polygon',{points:'42,200 '+points+' 692,200',fill:'#edf3fc'}));
    root.append(svgNode('polyline',{points,fill:'none',stroke:color,'stroke-width':2.5,'stroke-linejoin':'round'}));
    buckets.forEach((b,i)=>{const point=svgNode('circle',{cx:x(i),cy:y(b[field]),r:3,fill:color});point.append(svgNode('title',{},new Date(b.at).toLocaleString('pl-PL')+' · '+field+': '+b[field]));root.append(point);});
  }
  const sameDay=(Date.parse(buckets.at(-1).at)-Date.parse(buckets[0].at))<86400000;
  for(const i of [0,Math.floor(buckets.length/3),Math.floor(2*buckets.length/3),buckets.length-1]){
    const text=new Date(buckets[i].at).toLocaleString('pl-PL',sameDay?{hour:'2-digit',minute:'2-digit'}:{day:'2-digit',month:'2-digit'});
    root.append(svgNode('text',{x:x(i),y:225,'text-anchor':i===0?'start':i===buckets.length-1?'end':'middle',fill:'#9aa4b3','font-size':10},text));
  }
}
function renderAlertChart(buckets) {
  const root=chartRoot('alert-chart','Liczba promptów z alertami: informacyjne, ostrzeżenia i krytyczne w czasie.');
  const max=Math.max(1,...buckets.map(b=>b.alerts)),width=650/buckets.length;
  const colors={info:'#6d98db',warning:'#efac6b',critical:'#db6b7a'};
  for(let n=0;n<4;n++)root.append(svgNode('line',{x1:35,x2:705,y1:200-n*50,y2:200-n*50,stroke:'#edf0f5'}));
  buckets.forEach((bucket,i)=>{
    let base=200;
    for(const level of ['info','warning','critical']){
      const height=170*bucket[level]/max;
      const rect=svgNode('rect',{x:40+i*width,y:base-height,width:Math.max(2,width-4),height,fill:colors[level],rx:2});
      rect.append(svgNode('title',{},new Date(bucket.at).toLocaleString('pl-PL')+' · '+level+': '+bucket[level]));
      root.append(rect);base-=height;
    }
    if(i%Math.ceil(buckets.length/6)===0)root.append(svgNode('text',{x:40+i*width,y:222,fill:'#96a1b1','font-size':10},new Date(bucket.at).toLocaleString('pl-PL',{day:'2-digit',month:'2-digit',hour:'2-digit'})));
  });
}
function distribution(target,counts,colors,click,labels={}) {
  const el=$(target);el.replaceChildren();
  const maximum=Math.max(1,...Object.values(counts));
  if(!Object.values(counts).some(Boolean))el.append(node('p','Brak danych dla wybranych filtrów.','small text-body-secondary'));
  for(const [key,count]of Object.entries(counts)){
    const row=node('button','','distribution-row');row.type='button';row.setAttribute('aria-label',(labels[key]||key)+': '+count+', filtruj');
    const track=node('span','','bar-track'),svg=svgNode('svg',{viewBox:'0 0 100 8',preserveAspectRatio:'none','aria-hidden':'true'});
    svg.append(svgNode('rect',{x:0,y:0,width:100*count/maximum,height:8,fill:colors[key]||'#7291c6',rx:2}));track.append(svg);
    row.append(node('span',labels[key]||key),track,node('strong',String(count)));row.onclick=()=>click(key);el.append(row);
  }
}
function renderGroups(groups) {
  const selected=$('group-filter').value;
  $('group-filter').replaceChildren(new Option('Wszystkie grupy',''),new Option('Bez grupy','__none__'));
  $('group-options').replaceChildren();$('groups-list').replaceChildren();
  if(!groups.length)$('groups-list').append(node('p','Dodaj grupę i przypisz do niej endpointy.','empty-state'));
  for(const group of groups){
    $('group-filter').append(new Option(group.name,group.name));$('group-options').append(new Option(group.name,group.name));
    const card=node('section','','card group-card'),body=node('div','','card-body p-4'),stats=node('div','','group-stats');
    body.append(node('h2',group.name));
    for(const [value,label]of [[group.endpoint_count,'Endpointy'],[group.event_count,'Logi · cała historia']]){
      const stat=node('div','');stat.append(node('strong',String(value)),node('span',label));stats.append(stat);
    }
    body.append(stats);
    const actions=node('div','','d-flex gap-2 flex-wrap'),view=node('button','Analizuj ruch','btn btn-sm btn-primary'),edit=node('button','Zmień nazwę','btn btn-sm btn-outline-secondary'),remove=node('button','Usuń','btn btn-sm btn-outline-secondary');
    view.onclick=()=>{$('group-filter').value=group.name;switchView('overview');run(refresh);};
    edit.onclick=()=>{$('group-id').value=group.id;$('group-name').value=group.name;$('save-group').textContent='Zapisz';};
    remove.disabled=group.endpoint_count>0;remove.title=remove.disabled?'Najpierw przenieś endpointy do innej grupy':'Usuń pustą grupę';
    remove.onclick=()=>run(async()=>{await api('/api/groups/'+group.id,{method:'DELETE'});await refresh();});
    actions.append(view,edit,remove);body.append(actions);card.append(body);$('groups-list').append(card);
  }
  $('group-filter').value=selected;
}
$('group-form').onsubmit=e=>{e.preventDefault();run(async()=>{const id=$('group-id').value;await api('/api/groups'+(id?'/'+id:''),{method:'POST',body:JSON.stringify({name:$('group-name').value})});$('group-form').reset();$('group-id').value='';$('save-group').textContent='Dodaj grupę';await refresh();});};
$('cancel-group').onclick=()=>{$('group-form').reset();$('group-id').value='';$('save-group').textContent='Dodaj grupę';};
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


function hideEndpointToken() {
  $('endpoint-token').value = '';
  $('endpoint-secret').hidden = true;
  $('endpoint-pairing').textContent = '';
}
function showEndpointToken(result) {
  $('endpoint-token').value = result.token;
  $('endpoint-pairing').textContent = 'ID endpointu: '+result.id+'. Rotacja tokena rozłącza poprzednią instalację.';
  $('endpoint-secret').hidden = false;
}
function resetEndpointForm() {
  $('endpoint-form').reset(); $('endpoint-edit-id').value=''; $('save-endpoint').textContent='Dodaj';
}
function renderEndpoints(endpoints) {
  const selected = $('endpoint-filter').value;
  $('endpoint-filter').replaceChildren(new Option('Wszystkie endpointy',''),new Option('Nieprzypisane / starsze wersje','legacy'));
  $('endpoints').replaceChildren();
  if (!endpoints.length) $('endpoints').append(node('p','Brak endpointów. Dodaj pierwszą instalację, aby otrzymać jej token.','small text-body-secondary'));
  for (const endpoint of endpoints) {
    $('endpoint-filter').append(new Option(endpoint.name + (endpoint.group_name ? ' · '+endpoint.group_name : ''),endpoint.id));
    const row = node('div','','border-top py-3');
    const recent = endpoint.last_seen && Date.now()-Date.parse(endpoint.last_seen)<180000;
    const state = endpoint.revoked ? 'Dostęp cofnięty' : !endpoint.instance_id ? 'Oczekuje na sparowanie' : recent ? 'Ostatnio widziany' : 'Brak świeżego kontaktu';
    row.append(node('strong',endpoint.name),node('span',' · '+(endpoint.group_name || 'Bez grupy')+' · '+state,'small text-body-secondary'));
    row.append(node('div','ID: '+endpoint.id+' · Logi: '+endpoint.event_count+' · Wersja: '+(endpoint.version || '—'),'small text-body-secondary text-break'));
    row.append(node('div','Kontakt: '+(endpoint.last_seen ? new Date(endpoint.last_seen).toLocaleString('pl-PL') : 'jeszcze brak'),'small text-body-secondary'));
    const controls = node('div','','d-flex gap-2 flex-wrap mt-2');
    const edit = node('button','Edytuj','btn btn-sm btn-outline-secondary');
    edit.onclick=()=>{$('endpoint-edit-id').value=endpoint.id; $('endpoint-name').value=endpoint.name; $('endpoint-group').value=endpoint.group_name; $('save-endpoint').textContent='Zapisz';};
    const rotate = node('button','Nowy token / ponowne parowanie','btn btn-sm btn-outline-secondary');
    rotate.onclick=()=>run(async()=>{hideEndpointToken(); const result=await api('/api/endpoints/'+endpoint.id+'/rotate',{method:'POST',body:'{}'}); showEndpointToken(result); await refresh();});
    const revoke = node('button','Cofnij dostęp','btn btn-sm btn-outline-danger'); revoke.disabled=!!endpoint.revoked;
    revoke.onclick=()=>run(async()=>{await api('/api/endpoints/'+endpoint.id+'/revoke',{method:'POST',body:'{}'}); hideEndpointToken(); await refresh();});
    controls.append(edit,rotate,revoke); row.append(controls); $('endpoints').append(row);
  }
  $('endpoint-filter').value=selected;
}
$('endpoint-form').onsubmit=e=>{
  e.preventDefault();
  run(async()=>{
    hideEndpointToken();
    const id=$('endpoint-edit-id').value;
    const result=await api('/api/endpoints'+(id ? '/'+id : ''),{method:'POST',body:JSON.stringify({name:$('endpoint-name').value,group_name:$('endpoint-group').value})});
    resetEndpointForm();
    if (result.token) showEndpointToken(result);
    await refresh();
  });
};
$('reset-endpoint').onclick=resetEndpointForm;
$('hide-endpoint-token').onclick=hideEndpointToken;
$('copy-endpoint-token').onclick=()=>run(async()=>{await navigator.clipboard.writeText($('endpoint-token').value); $('endpoint-pairing').textContent='Token skopiowany. Wklej go w ustawieniach jednej wtyczki.';});
