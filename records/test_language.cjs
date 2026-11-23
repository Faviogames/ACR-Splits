// Run directly with Node; no bundling or desktop build.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const i18n = require('./ui/i18n.js');
const label = {textContent:'  Ajustes  ',parentElement:{tagName:'BUTTON'}};
const live = {textContent:'Piloto local',parentElement:{tagName:'SPAN'}};
const script = {textContent:'Sesión',parentElement:{tagName:'SCRIPT'}};
const search = {
  attrs:{placeholder:'Buscar tramo o coche'},
  hasAttribute(key){return Object.hasOwn(this.attrs,key);},
  getAttribute(key){return this.attrs[key];},
  setAttribute(key,value){this.attrs[key]=value;},
};
global.NodeFilter={SHOW_TEXT:4};
global.document={
  body:{querySelectorAll(){return [search];}},documentElement:{},
  createTreeWalker(){let index=0;const nodes=[label,live,script];return {nextNode(){return nodes[index++];}};},
};
assert.equal(i18n.language,'en');
i18n.translateStatic();
assert.equal(label.textContent,'  Settings  ');
assert.equal(search.attrs.placeholder,'Search stage or car');
assert.equal(script.textContent,'Sesión');
live.textContent='Grecia'; // A pilot name must survive a language change.
i18n.setLanguage('es');
assert.equal(label.textContent,'  Ajustes  ');
assert.equal(live.textContent,'Grecia');
assert.equal(search.attrs.placeholder,'Buscar tramo o coche');
assert.equal(document.documentElement.lang,'es');
assert.equal(i18n.t('Captura en pausa'),'Captura en pausa');
i18n.setLanguage('en');
assert.equal(label.textContent,'  Settings  ');
assert.equal(i18n.t('Captura en pausa'),'Capture paused');
assert.equal(i18n.t('El servicio rechazó la solicitud (503).'),'The service rejected the request (503).');
assert.equal(i18n.t('constructor'),'constructor');
assert.equal(i18n.t('Seyabei'),'Seyabei');
// Check every Spanish static string in the actual template is translated.
const html=fs.readFileSync(__dirname+'/ui/index.html','utf8');
assert.doesNotMatch(html,/data-view="(?:settings|ranking)"|id="view-(?:settings|ranking)"/);
assert.match(html,/<div class="topbar-right"><select id="language-select"/);
const app=fs.readFileSync(__dirname+'/ui/app.js','utf8');
const ids=new Set([...html.matchAll(/\bid="([^"]+)"/g)].map(match=>match[1]));
for(const [,id] of app.matchAll(/(?:\$|text)\(["']([^"']+)["']/g))assert.ok(ids.has(id),`UI refers to missing element: ${id}`);
assert.doesNotMatch(app,/loadRanking|renderRanking|\/api\/leaderboard/);
for(const match of html.matchAll(/>([^<>]+)</g)){
  const value=match[1].trim();
  if(/[áéíóúñÁÉÍÓÚÑ]/.test(value)&&value!=='Español')assert.notEqual(i18n.t(value),value,`Missing translation: ${value}`);
}
console.log('PASS: English/Spanish UI, repeated switching, placeholders, script and pilot preservation');
