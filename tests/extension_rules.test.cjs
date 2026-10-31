const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const context=vm.createContext({});
vm.runInContext(fs.readFileSync('extension/rules.js','utf8'),context);
const evaluate=(policy,text)=>JSON.parse(JSON.stringify(context.WalleeRules.evaluate(policy,text)));
test('browser critical detectors match every server demo scenario',()=>{
  const fixture=JSON.parse(fs.readFileSync('server/demo_data.json','utf8'));
  const rules=fixture.rules.filter(r=>r.severity==='critical'&&r.enabled!==false);
  const names=new Set(rules.map(r=>r.name));
  for(const event of fixture.events){
    const result=evaluate({rules,version:'test'},event.prompt);
    const expected=event.expected.filter(name=>names.has(name)).sort();
    assert.deepEqual(result.matches.map(r=>r.name).sort(),expected,event.id);
    assert.equal(result.decision,expected.length?'block':'allow');
  }
});
test('Unicode casefold, invalid policies and invalid dates fail safely',()=>{
  const policy={version:'v1',rules:[{id:1,name:'Unicode',type:'contains',contains:'STRASSE',severity:'critical'}]};
  assert.equal(evaluate(policy,'Straße').decision,'block');
  assert.throws(()=>evaluate({rules:[{type:'regex',severity:'critical'}],version:'v1'},'hello'));
  assert.throws(()=>evaluate({rules:[],version:'v1'},'a'.repeat(100001)));
  const pesel={version:'v1',rules:[{name:'PESEL',type:'pesel',severity:'critical'}]};
  assert.equal(evaluate(pesel,'00000000000').decision,'allow');
  assert.equal(evaluate(pesel,'44051401458').decision,'block');
  assert.equal(evaluate(pesel,'44051401459').decision,'allow');
});
