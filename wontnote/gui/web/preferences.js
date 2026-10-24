/* Small preferences live in Settings; the note workspace stays unchanged. */
let lastActivity = Date.now();
let autoLockRunning = false;
const preferenceDefaults = {
  autosave:'800', line_height:'1.9', spellcheck:'true', word_count:'true',
  auto_lock:'5', lock_minimize:'true', compact:'false', reduce_motion:'false'
};
const preferenceControls = {
  autosave:'prefAutosave', line_height:'prefLineHeight', spellcheck:'prefSpellcheck', word_count:'prefWordCount',
  auto_lock:'prefAutoLock', lock_minimize:'prefLockMinimize', compact:'prefCompact', reduce_motion:'prefReduceMotion'
};
function setPreference(key, value) {
  if(!(key in preferenceDefaults))return;
  const allowed={autosave:['300','800','1500'],line_height:['1.6','1.9','2.2'],auto_lock:['0','1','5','15','30']};
  const text=String(value);
  if(allowed[key] ? !allowed[key].includes(text) : !['true','false'].includes(text))return;
  writePref('wn_'+key,text);applyPreferences();lastActivity=Date.now();
}
function applyPreferences() {
  const editor=document.getElementById('editorContent');
  const spacing=readPref('wn_line_height',preferenceDefaults.line_height);
  editor.style.lineHeight=['1.6','1.9','2.2'].includes(spacing)?spacing:'1.9';
  editor.spellcheck=readPref('wn_spellcheck','true')==='true';
  document.documentElement.classList.toggle('compact-notes',readPref('wn_compact','false')==='true');
  document.documentElement.classList.toggle('reduce-motion',readPref('wn_reduce_motion','false')==='true');
  const showCount=readPref('wn_word_count','true')==='true';
  ['editorWordCharCount','footerWordCharCount'].forEach(id=>{document.getElementById(id).style.visibility=showCount?'visible':'hidden';});
}
function syncPreferenceControls() {
  for(const [key,id] of Object.entries(preferenceControls)){
    const el=document.getElementById(id), value=readPref('wn_'+key,preferenceDefaults[key]);
    if(el.type==='checkbox')el.checked=value==='true';else el.value=value;
  }
}
const shortcuts = [
 ['Ctrl+N','Create a new note'], ['Ctrl+S','Save now'], ['Ctrl+F','Search notes'],
 ['Ctrl+L','Lock the vault'], ['Ctrl+,','Open settings'], ['F1','Open shortcut help'],
 ['Ctrl+B','Bold'], ['Ctrl+I','Italic'], ['Ctrl+U','Underline'],
 ['Ctrl+Shift+X','Strikethrough'], ['Ctrl+Shift+7','Numbered list'], ['Ctrl+Shift+8','Bulleted list'],
 ['Ctrl+Z','Undo'], ['Ctrl+Y / Ctrl+Shift+Z','Redo'],
 ['Ctrl+Shift+P','Pin or unpin note'], ['Ctrl+Shift+T','Go to note title'],
 ['Ctrl+Shift+E','Go to note body'], ['Alt+↑ / Alt+↓','Previous / next note in list'],
 ['Delete','Delete selected note outside the editor'], ['Esc','Close topmost window / clear search']
];
function renderShortcuts() {
  const host=document.getElementById('shortcutList');host.replaceChildren();
  shortcuts.forEach(([key,description])=>{
    const row=document.createElement('div');row.className='shortcut-row';
    const label=document.createElement('span');label.textContent=description;
    const kbd=document.createElement('kbd');kbd.textContent=key;row.append(label,kbd);host.appendChild(row);
  });
}
function mainIsOpen() {return !document.getElementById('view-main').classList.contains('view-hidden');}
function clearSensitiveUI() {
  clearTimeout(autosaveTimer);currentNotes=[];activeNoteId=null;dirtyNotes.clear();contextMenuNoteId=null;
  activeFilter='all';searchQuery='';
  ['editorContent','notesListContainer','sidebarFolders'].forEach(id=>document.getElementById(id).replaceChildren());
  ['editorTitleInput','searchInput','loginPassword','setupPwd','setupConf','pwdChangeCur','pwdChangeNew','pwdChangeConf','resetConfirmInput','recoveryKeyInput'].forEach(id=>{document.getElementById(id).value='';});
  ['editorTitleBreadcrumb','editorFolderBreadcrumb','editorFolderMeta','editorModifiedMeta','displayRecoveryKeyText','editorWordCharCount','footerWordCharCount','toastMessage'].forEach(id=>{document.getElementById(id).textContent='';});
  ['countAllNotes','countPinnedNotes','countTrashNotes','notesCountBadge'].forEach(id=>{document.getElementById(id).textContent='0';});
  document.querySelectorAll('[id^="modal-"]').forEach(el=>{el.classList.add('hidden');el.classList.remove('flex');});
  document.getElementById('noteContextMenu').classList.add('hidden');
  document.getElementById('globalToast').classList.add('hidden');
  document.getElementById('editorFolderSelect').replaceChildren();
  window.getSelection()?.removeAllRanges();showEditorEmpty();
}
async function checkIdleLock() {
  const minutes=Number(readPref('wn_auto_lock','5'));
  if(!mainIsOpen() || autoLockRunning || ![1,5,15,30].includes(minutes) || Date.now()-lastActivity<minutes*60000)return;
  autoLockRunning=true;
  try {await handleLockVault();} finally {autoLockRunning=false;lastActivity=Date.now();}
}
['pointerdown','keydown','input','wheel'].forEach(type=>document.addEventListener(type,()=>{lastActivity=Date.now();},{passive:true}));
setInterval(checkIdleLock,1000);
function navigateNote(direction) {
  const cards=[...document.querySelectorAll('#notesListContainer .note-ctx-btn')];
  const index=cards.findIndex(el=>el.dataset.noteId===activeNoteId);
  const target=cards[Math.max(0,Math.min(cards.length-1,index+direction))];
  if(target)selectNote(target.dataset.noteId);
}
function handleAppKeydown(e) {
  const key=e.key.toLowerCase(), mod=e.ctrlKey||e.metaKey;
  if(key==='escape'){
    const open=['modal-reset-vault','modal-recovery-input','modal-recovery-display','modal-settings'].find(id=>!document.getElementById(id).classList.contains('hidden'));
    if(open){e.preventDefault();({ 'modal-reset-vault':closeResetModal,'modal-recovery-input':closeRecoveryModal,'modal-recovery-display':closeRecoveryDisplayModal,'modal-settings':closeSettingsModal })[open]();return;}
    closeCtxMenu();
    if(document.activeElement?.id==='searchInput'){document.getElementById('searchInput').value='';handleSearch('');}
    return;
  }
  if(!mainIsOpen() || sessionLocking)return;
  const modal=document.querySelector('[id^="modal-"]:not(.hidden)');
  if(key==='f1'){e.preventDefault();openSettingsModal();switchSettingsTab('shortcuts');return;}
  if(mod && key==='l'){e.preventDefault();handleLockVault();return;}
  if(modal)return;
  if(mod && key===','){e.preventDefault();openSettingsModal();return;}
  if(mod && key==='s'){e.preventDefault();flushSaves();return;}
  if(mod && key==='n'){e.preventDefault();handleNewNote();return;}
  if(mod && key==='f'){e.preventDefault();document.getElementById('searchInput').focus();return;}
  if(mod && e.shiftKey && key==='p'){e.preventDefault();handleTogglePin();return;}
  if(mod && e.shiftKey && key==='t'){e.preventDefault();document.getElementById('editorTitleInput').focus();return;}
  if(mod && e.shiftKey && key==='e'){e.preventDefault();document.getElementById('editorContent').focus();return;}
  if(e.altKey && ['arrowup','arrowdown'].includes(key)){e.preventDefault();navigateNote(key==='arrowup'?-1:1);return;}
  const inEditor=document.activeElement?.closest('#editorContent');
  if(mod && inEditor){
    let command=e.shiftKey?{x:'strikeThrough','7':'insertOrderedList','8':'insertUnorderedList',z:'redo'}[key]:{b:'bold',i:'italic',u:'underline',z:'undo',y:'redo'}[key];
    if(e.shiftKey && e.code==='Digit7')command='insertOrderedList';
    if(e.shiftKey && e.code==='Digit8')command='insertUnorderedList';
    if(command){e.preventDefault();execFormat(command);return;}
  }
  if(key==='delete' && activeNoteId && !document.activeElement?.closest('input, textarea, select, [contenteditable]')){e.preventDefault();handleDeleteCurrentNote();}
}
window.addEventListener('keydown',handleAppKeydown);
document.getElementById('editorContent').addEventListener('drop',event=>{
  event.preventDefault();const text=event.dataTransfer?.getData('text/plain');
  if(text){document.getElementById('editorContent').focus();document.execCommand('insertText',false,text);handleContentInput();}
});
