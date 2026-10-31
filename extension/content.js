(() => {
  const provider={'chatgpt.com':'chatgpt','claude.ai':'claude','gemini.google.com':'gemini'}[location.hostname];
  let blocking=true,logging=false,pending=false,replaying=false,last='',lastAt=0;
  const editors={
    chatgpt:'#prompt-textarea',
    claude:'[contenteditable="true"][role="textbox"], .ProseMirror[contenteditable="true"]',
    gemini:'rich-textarea [contenteditable="true"]'
  };
  function editor() {return [...document.querySelectorAll(editors[provider])].find(el=>el.getClientRects().length);}
  function text(el) {return (el?.value??el?.innerText??'').trim();}
  function sendButton(target) {
    const button=target?.closest?.('button,[role="button"],input[type="submit"]');
    if(!button)return null;
    const label=[button.getAttribute('aria-label'),button.getAttribute('data-testid'),button.getAttribute('class')].join(' ').toLowerCase();
    return /send-button|composer-submit-button|send message|send prompt|wyślij|wyslij/.test(label)?button:null;
  }
  function availableButton() {
    return [...document.querySelectorAll('button,[role="button"],input[type="submit"]')].map(sendButton).find(button=>button&&button.getClientRects().length&&!button.disabled&&button.getAttribute('aria-disabled')!=='true');
  }
  function stop(event) {event.preventDefault();event.stopImmediatePropagation();}
  function dismiss() {document.getElementById('walleeguard-guard-banner')?.remove();}
  function banner(title,details) {
    dismiss();
    const panel=document.createElement('aside');panel.id='walleeguard-guard-banner';panel.setAttribute('role','alert');
    const heading=document.createElement('strong');heading.textContent='WalleeGuard · '+title;
    const reason=document.createElement('p');reason.textContent=details;
    const close=document.createElement('button');close.textContent='Zamknij';close.type='button';close.onclick=dismiss;
    const settings=document.createElement('button');settings.textContent='Ustawienia ochrony';settings.type='button';settings.onclick=()=>chrome.runtime.sendMessage({type:'openSettings'}).catch(()=>{});
    panel.append(heading,reason,close,settings);document.documentElement.append(panel);
  }
  function capture(prompt) {
    if(!logging||!prompt||prompt.length>100000)return;
    if(prompt===last&&Date.now()-lastAt<1500)return;
    last=prompt;lastAt=Date.now();
    chrome.runtime.sendMessage({type:'capture',event:{id:crypto.randomUUID(),provider,prompt}}).catch(()=>{});
  }
  async function checkAndSend(el,button) {
    if(pending)return;
    const prompt=text(el);
    if(!el||!prompt) {banner('Nie można sprawdzić promptu','Nie rozpoznano edytora lub treści. Wysyłka pozostaje zatrzymana.');return;}
    pending=true;
    banner('Sprawdzanie promptu…','Treść jest sprawdzana lokalnie według krytycznych reguł kolektora.');
    let timer;
    try {
      const response=await Promise.race([
        chrome.runtime.sendMessage({type:'preflight',event:{id:crypto.randomUUID(),provider,prompt}}),
        new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Przekroczono czas sprawdzania. Wysyłka pozostaje zatrzymana.')),12000);})
      ]);
      if(!response?.ok)throw Error(response?.error||'Rozszerzenie jest niedostępne. Odśwież kartę.');
      const verdict=response.result;
      if(!verdict||!['allow','block','disabled'].includes(verdict.decision))throw Error('Nieprawidłowa decyzja ochrony.');
      if(verdict.decision==='block') {
        banner('Wysyłka zablokowana','Krytyczne reguły: '+verdict.matches.map(m=>m.name).join(', ')+'. Popraw prompt i spróbuj ponownie.');return;
      }
      if(!el.isConnected||text(el)!==prompt)throw Error('Treść promptu zmieniła się podczas sprawdzania. Sprawdź go ponownie.');
      const send=button?.isConnected?button:availableButton(),form=el.closest('form');
      if(!send&&!form)throw Error('Nie znaleziono przycisku wysyłania. Wysyłka pozostaje zatrzymana.');
      if(send&&(send.disabled||send.getAttribute('aria-disabled')==='true'))throw Error('Przycisk wysyłania jest nieaktywny. Spróbuj ponownie.');
      dismiss();
      // Only this synchronous replay bypasses our capture listeners.
      replaying=true;
      try {if(send)send.click();else form.requestSubmit();}
      finally {replaying=false;}
      if(verdict.decision==='disabled')capture(prompt);
    } catch(error) {banner('Wysyłka zatrzymana',error.message);}
    finally {clearTimeout(timer);pending=false;}
  }
  function intent(event) {
    const el=editor();
    if(event.type==='keydown')return event.key==='Enter'&&!event.shiftKey&&!event.isComposing&&el&&(event.target===el||el.contains(event.target));
    if(event.type==='submit')return el&&event.target.contains(el);
    return !!sendButton(event.target);
  }
  function intercept(event) {
    if(replaying||!intent(event))return;
    const el=editor();
    if(!blocking){capture(text(el));return;}
    stop(event);
    // Empty editor clicks are harmless; do not attempt to replay them.
    if(el&&!text(el)){banner('Brak tekstu do sprawdzenia','Dodaj treść promptu. Załączniki nie są analizowane.');return;}
    checkAndSend(el,sendButton(event.target));
  }
  for(const name of ['keydown','click','submit'])window.addEventListener(name,intercept,true);
  // Stop earlier pointer handlers and alternate Enter handlers from sending before checking.
  for(const name of ['pointerdown','mousedown'])window.addEventListener(name,event=>{
    if(blocking&&!replaying&&sendButton(event.target))stop(event);
  },true);
  for(const name of ['keypress','keyup'])window.addEventListener(name,event=>{
    const el=editor();
    if(blocking&&!replaying&&event.key==='Enter'&&!event.shiftKey&&!event.isComposing&&el&&(event.target===el||el.contains(event.target)))stop(event);
  },true);
  chrome.storage.local.get(['blockingEnabled','enabled']).then(settings=>{
    blocking=settings.blockingEnabled!==false;logging=!!settings.enabled;
  }).catch(()=>{});
  chrome.storage.onChanged.addListener((changes,area)=>{
    if(area!=='local')return;
    if(changes.blockingEnabled){blocking=changes.blockingEnabled.newValue!==false;if(!blocking)dismiss();}
    if(changes.enabled)logging=!!changes.enabled.newValue;
  });
})();
