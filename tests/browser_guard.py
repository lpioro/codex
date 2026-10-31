"""Optional browser integration check: requires Playwright and Chromium."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
POLICY = {'version':'test','rules':[{'id':1,'name':'Dane poufne','type':'contains','contains':'sekret','severity':'critical'}]}
CHROME = """
globalThis.__settings={blockingEnabled:true,enabled:false};
globalThis.__checks=0;globalThis.__fail=false;globalThis.__defer=false;
globalThis.chrome={
 storage:{local:{get:async()=>__settings},onChanged:{addListener:fn=>globalThis.__changed=fn}},
 runtime:{sendMessage:async message=>{
   if(message.type!=='preflight')return {ok:true};
   __checks++;
   if(__fail)throw Error('Brak polityki');
   if(__defer)await new Promise(resolve=>globalThis.__release=resolve);
   return {ok:true,result:WalleeRules.evaluate(__policy,message.event.prompt)};
 }}
};
"""
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('BROWSER_BIN','/usr/bin/chromium'),args=['--no-sandbox'])
    try:
        for provider,host,editor in [
            ('chatgpt','chatgpt.com','<textarea id="prompt-textarea"></textarea>'),
            ('claude','claude.ai','<div contenteditable="true" role="textbox"></div>'),
            ('gemini','gemini.google.com','<rich-textarea><div contenteditable="true"></div></rich-textarea>')]:
            context=browser.new_context(viewport={'width':1000,'height':700})
            content=(ROOT/'extension/content.js').read_text()
            context.add_init_script((ROOT/'extension/rules.js').read_text()+'\n'+CHROME+'\nglobalThis.__policy='+json.dumps(POLICY)+';\n'+content)
            html='''<!doctype html><html><head><title>Composer fixture</title></head><body><h1>AI composer test</h1><form>'''+editor+'''<button type="submit" data-testid="send-button" aria-label="Send message">Send</button></form><script>
            window.siteSends=0;
            window.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();siteSends++;}});
            document.querySelector('button').addEventListener('click',e=>{e.preventDefault();siteSends++;});
            document.querySelector('form').addEventListener('submit',e=>{e.preventDefault();siteSends++;});
            </script></body></html>'''
            context.route('**/*',lambda route:route.fulfill(status=200,content_type='text/html',body=html))
            page=context.new_page();page.goto('https://'+host+'/')
            page.add_style_tag(content=(ROOT/'extension/guard.css').read_text())
            target=page.locator('textarea,[contenteditable="true"]').first
            target.press('Enter')
            expect(page.locator('#walleeguard-guard-banner')).to_contain_text('Brak tekstu')
            assert page.evaluate('siteSends')==0
            target.fill('To jest sekret')
            target.press('Enter')
            expect(page.locator('#walleeguard-guard-banner')).to_contain_text('Wysyłka zablokowana')
            assert page.evaluate('siteSends')==0
            expect(target).to_have_value('To jest sekret') if provider=='chatgpt' else expect(target).to_have_text('To jest sekret')
            page.locator('button[aria-label="Send message"]').click()
            expect(page.locator('#walleeguard-guard-banner')).to_contain_text('Krytyczne reguły')
            assert page.evaluate('siteSends')==0
            target.press('Control+Enter')
            expect(page.locator('#walleeguard-guard-banner')).to_contain_text('Wysyłka zablokowana')
            assert page.evaluate('siteSends')==0
            page.locator('form').evaluate('(form)=>form.requestSubmit()')
            expect(page.locator('#walleeguard-guard-banner')).to_contain_text('Wysyłka zablokowana')
            assert page.evaluate('siteSends')==0
            target.fill('Bezpieczne pytanie')
            target.press('Enter')
            page.wait_for_function('() => siteSends===1')
            page.locator('button[aria-label="Send message"]').click()
            page.wait_for_function('() => siteSends===2')
            page.evaluate('() => {__fail=true;}')
            target.fill('Safe but no policy')
            target.press('Enter')
            expect(page.locator('#walleeguard-guard-banner')).to_contain_text('Brak polityki')
            assert page.evaluate('siteSends')==2
            page.evaluate('() => {__fail=false;__defer=true;}')
            target.fill('Sprawdzona wersja')
            target.press('Enter')
            page.wait_for_function('() => !!globalThis.__release')
            target.fill('Zmieniona wersja sekret')
            page.evaluate('() => __release()')
            expect(page.locator('#walleeguard-guard-banner')).to_contain_text('zmieniła się')
            assert page.evaluate('siteSends')==2
            page.evaluate('() => {__defer=false;}')
            target.fill('sekret');target.press('Enter')
            expect(page.locator('#walleeguard-guard-banner')).to_contain_text('Wysyłka zablokowana')
            if provider=='chatgpt':
                (ROOT/'dist').mkdir(exist_ok=True)
                page.screenshot(path=str(ROOT/'dist/walleeguard-blocking.png'))
            page.evaluate("() => __changed({blockingEnabled:{newValue:false}},'local')")
            target.press('Enter')
            page.wait_for_function('() => siteSends===3')
            context.close()
            print(provider+': critical Enter/click/Ctrl+Enter/submit blocked; safe replay once; offline and changed draft stopped; opt-out works')
    finally:
        browser.close()
