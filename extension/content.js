(() => {
  const provider = {'chatgpt.com':'chatgpt', 'claude.ai':'claude', 'gemini.google.com':'gemini'}[location.hostname];
  let last = '', lastAt = 0;
  function capture() {
    const editors = {
      chatgpt: '#prompt-textarea',
      claude: '[contenteditable="true"][role="textbox"], .ProseMirror[contenteditable="true"]',
      gemini: 'rich-textarea [contenteditable="true"]'
    };
    const editor = document.querySelector(editors[provider]);
    const prompt = (editor?.value ?? editor?.innerText ?? '').trim();
    if (!prompt || prompt.length > 100000) return;
    if (prompt === last && Date.now() - lastAt < 1500) return;
    last = prompt; lastAt = Date.now();
    chrome.runtime.sendMessage({type:'capture', event:{id:crypto.randomUUID(), provider, prompt}}).catch(() => {});
  }
  document.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && !e.ctrlKey && !e.altKey && !e.metaKey &&
        e.target.closest('#prompt-textarea, [contenteditable="true"], textarea')) capture();
  }, true);
  document.addEventListener('click', e => {
    const button = e.target.closest('button');
    if (!button) return;
    const label = [button.getAttribute('aria-label'), button.getAttribute('data-testid')].join(' ').toLowerCase();
    if (/send-button|send message|send prompt|wyślij|wyslij/.test(label)) capture();
  }, true);
})();
