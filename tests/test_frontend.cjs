// Run with: node tests/test_frontend.cjs
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {style:{}, value:'', textContent:'', classList:{remove(){},add(){},contains(){return false;},toggle(){}}, addEventListener(){}, replaceChildren(){}});
  return elements.get(id);
}
const context = vm.createContext({
  document: {getElementById:element, hasElement:id=>elements.has(id), querySelectorAll:()=>[], querySelector:()=>null, addEventListener(){}, documentElement:{classList:{remove(){},toggle(){}},dataset:{}}},
  window: {addEventListener(){},getSelection(){return {removeAllRanges(){}}}},
  localStorage: {getItem(){return null;},setItem(){}},
  setTimeout:()=>1, setInterval:()=>1, clearTimeout(){}, console, assert
});
const html = fs.readFileSync('wontnote/gui/web/index.html','utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
vm.runInContext(scripts.at(-1)[1], context);
vm.runInContext(fs.readFileSync('wontnote/gui/web/preferences.js','utf8'), context);
(async () => {
  await vm.runInContext(`(async () => {
    renderNotesList = () => {};
    let resetArgs;
    apiCall = async (...args) => { resetArgs = args; return {success:false,error:'test'}; };
    openResetModal();
    assert.equal(document.hasElement('resetPasswordInput'), false);
    document.getElementById('resetConfirmInput').value = 'CONFIRM';
    handleResetInputChange('CONFIRM');
    assert.equal(document.getElementById('resetExecuteBtn').disabled, false);
    await executeResetVault();
    assert.deepEqual(resetArgs, ['reset_vault', 'CONFIRM']);

    const saved = [];
    apiCall = async (method, note) => { saved.push(JSON.parse(JSON.stringify(note))); return {success:true}; };
    currentNotes = [{id:'a',title:'First'},{id:'b',title:'Second'}];
    activeNoteId = 'a'; triggerAutosave();
    activeNoteId = 'b'; triggerAutosave();
    assert.equal(await flushSaves(), true);
    assert.deepEqual(saved.map(n => n.id), ['a','b']);
    activeNoteId = 'a'; currentNotes[0].title = 'Pending'; triggerAutosave();
    apiCall = async () => ({success:false});
    assert.equal(await flushSaves(), false);
    assert.equal(dirtyNotes.size, 1);
    apiCall = async () => ({success:true});
    assert.equal(await flushSaves(), true);
    assert.equal(dirtyNotes.size, 0);
    applyTheme('dark'); assert.equal(currentTheme, 'light');
    applyTheme('sage'); assert.equal(document.documentElement.dataset.theme, 'sage');
    assert.ok(Object.keys(fontMap).length >= 35);
    applyFont('georgia',true); assert.equal(currentNotes[0].font,'georgia');
    applyFontSize(20); assert.equal(currentNotes[0].font_size,20);
    assert.equal(document.getElementById('editorContent').style.fontSize,'20px');
    const preferences = new Map();
    writePref = (key,value) => preferences.set(key,value);
    readPref = (key,fallback) => preferences.get(key) || fallback;
    setPreference('autosave','300'); assert.equal(preferences.get('wn_autosave'),'300');
    setPreference('autosave','-1'); assert.equal(preferences.get('wn_autosave'),'300');
    setPreference('line_height','2.2'); assert.equal(document.getElementById('editorContent').style.lineHeight,'2.2');
    setPreference('spellcheck',false); assert.equal(document.getElementById('editorContent').spellcheck,false);
    let savedViaShortcut=false;
    flushSaves=async()=>{savedViaShortcut=true;return true;};
    handleAppKeydown({key:'s',ctrlKey:true,preventDefault(){}});
    assert.equal(savedViaShortcut,true);
    let shortcutFormat=null;
    document.activeElement={closest:selector=>selector==='#editorContent'?{}:null};
    execFormat=command=>{shortcutFormat=command;};
    handleAppKeydown({key:'b',ctrlKey:true,preventDefault(){}});
    assert.equal(shortcutFormat,'bold');
    shortcutFormat=null; document.activeElement={closest:()=>null};
    handleAppKeydown({key:'b',ctrlKey:true,preventDefault(){}});
    assert.equal(shortcutFormat,null);
    clearSensitiveUI(); assert.equal(currentNotes.length,0); assert.equal(activeNoteId,null); assert.equal(dirtyNotes.size,0);
    assert.equal(document.getElementById('editorTitleInput').value,'');
  })()`, context);
  console.log('Frontend regressions passed: note switching, failed save retry, theme migration, note typography.');
})().catch(error => {console.error(error);process.exitCode=1;});
