"use strict";
const token = location.hash.slice(1);
// Keep local JSON export available in source for diagnostics, hidden in normal use.
const EXPORT_ENABLED=false;
const t=value=>AppI18n.t(value);
let state = null, selectedId = null, currentView = "session", toastTimer, compact = false;
let publishing=false,publishId=null;
let accountChecked=false,accountLoading=false;
const validationReasons={route_reference_missing:'Este tramo todavía no tiene una referencia de ruta en el servidor.',start_position_mismatch:'La posición de salida no coincide con la referencia del tramo.',stage_distance_mismatch:'La distancia recorrida no coincide con la longitud del tramo.',outside_route_corridor:'La trazada se aleja del corredor del tramo.',route_progress_mismatch:'El progreso de la carrera no coincide con la ruta.',position_jump:'Se detectó un salto de posición que necesita revisión.',route_shortcut:'Se detectó un salto de progreso en el recorrido.',finish_position_mismatch:'La posición final no coincide con la llegada del tramo.',route_checkpoints_missing:'Faltan puntos de control del recorrido.'};
const $ = id => document.getElementById(id);
const formatTime = value => {
  if (!Number.isFinite(value)) return "—";
  const ms = Math.max(0, Math.round(value));
  return `${String(Math.floor(ms / 60000)).padStart(2,"0")}:${String(Math.floor(ms / 1000) % 60).padStart(2,"0")}.${String(ms % 1000).padStart(3,"0")}`;
};
const text = (id, value, translate=true) => { if(translate)value=t(value); if ($(id).textContent !== value) $(id).textContent = value; };
function toast(message) { message=t(message); $("toast").textContent = message; $("toast").classList.add("visible"); clearTimeout(toastTimer); toastTimer = setTimeout(() => $("toast").classList.remove("visible"), 4200); }
async function api(path, data) {
  const options = {headers:{"X-App-Token":token}};
  if (data !== undefined) { options.method="POST"; options.headers["Content-Type"]="application/json"; options.body=JSON.stringify(data); }
  const response = await fetch(path, options);
  if (!response.ok) throw new Error((await response.json()).error || "No se pudo completar la acción");
  return response.json();
}
function showView(view) {
  currentView = view;
  document.querySelectorAll(".view").forEach(node => node.classList.toggle("active", node.id === `view-${view}`));
  document.querySelectorAll(".nav-item").forEach(node => node.classList.toggle("active", node.dataset.view === view));
  if(view==='ranking')loadRanking();
}
let rankingRequest=0,rankingRows=[],rankingStage=null,rankingStatus='empty';
async function loadRanking(){
  const selected=state?.history.find(item=>item.id===selectedId)||state?.history[0];
  rankingStage=selected;rankingRows=[];rankingStatus=selected?'loading':'empty';renderRanking();
  const request=++rankingRequest;if(!selected)return;
  try{const result=await api('/api/leaderboard?stage='+encodeURIComponent(selected.stage_game_id));if(request!==rankingRequest)return;
    rankingRows=result.records.filter(row=>row.status==='accepted'&&Number.isSafeInteger(row.total_ms)&&row.total_ms>0).sort((a,b)=>a.total_ms-b.total_ms||Date.parse(a.date)-Date.parse(b.date));rankingStatus='ready';
  }catch{if(request!==rankingRequest)return;rankingStatus='error';}
  renderRanking();
}
function renderRanking(){
  const signature=JSON.stringify([AppI18n.language,rankingStatus,rankingStage?.id,rankingRows,state?.account?.id]);
  if($('ranking-board').dataset.signature===signature)return;
  $('ranking-board').dataset.signature=signature;
  text('ranking-stage',rankingStage?.stage||t('Completa un tramo para ver su clasificación.'),false);
  const mine=rankingRows.findIndex(row=>row.pilot_id===state?.account?.id),best=rankingRows[0],personal=rankingRows[mine];
  text('ranking-position',mine>=0?'#'+(mine+1):'—');text('ranking-best',formatTime(personal?.total_ms));text('ranking-gap',personal?'+'+formatTime(personal.total_ms-best.total_ms):'—');
  const container=$('ranking-board');container.replaceChildren();
  if(rankingStatus!=='ready'||!rankingRows.length){const note=document.createElement('p');note.className='empty-message';note.textContent=t(rankingStatus==='loading'?'Cargando clasificación…':rankingStatus==='error'?'No se pudo cargar la clasificación. Vuelve a intentarlo.':rankingStatus==='empty'?'Completa un tramo para ver su clasificación.':'Todavía no hay tiempos publicados.');container.append(note);return;}
  const table=document.createElement('table');table.className='history-table';const header=table.createTHead().insertRow();
  for(const label of ['Posición','Piloto','Coche','Tiempo total']){const cell=document.createElement('th');cell.textContent=t(label);header.append(cell);}
  const body=table.createTBody();
  rankingRows.slice(0,5).forEach((row,index)=>{const tr=body.insertRow();tr.insertCell().textContent=['🥇','🥈','🥉'][index]||String(index+1);const driver=tr.insertCell();
    if(/^[A-Za-z]{2}$/.test(row.country_code||'')){const flag=document.createElement('img');flag.src='/flags/'+row.country_code.toLowerCase()+'.svg';flag.alt=row.country_code;flag.className='ranking-flag';driver.append(flag);}
    driver.append(document.createTextNode(row.pilot));tr.insertCell().textContent=row.car.replace(/([a-z])([A-Z])/g,'$1 $2').replaceAll('_',' ');const timing=tr.insertCell();timing.className='time-cell';timing.textContent=formatTime(row.total_ms);
  });container.append(table);
}
function historyTable(containerId, items, limit) {
  const container = $(containerId);
  const visible = limit ? items.slice(0,limit) : items;
  const signature = AppI18n.language+JSON.stringify(visible);
  if (container.dataset.signature === signature) return;
  container.dataset.signature = signature;
  container.replaceChildren();
  if (!visible.length) { const empty = document.createElement("p"); empty.className="empty-message"; empty.textContent="Tu próxima pasada empieza aquí. Abre la app antes de salir y completa un tramo."; empty.textContent=t(empty.textContent); container.append(empty); return; }
  const table = document.createElement("table"); table.className="history-table";
  const header = table.createTHead().insertRow();
  for (const label of ["Tramo / Coche", "Estado", "Tiempo total", "Penalización"]) { const th=document.createElement("th"); th.scope="col"; th.textContent=t(label); header.append(th); }
  const body = table.createTBody();
  for (const item of visible) {
    const row = body.insertRow(); row.className="history-row"; row.tabIndex=0; row.setAttribute("aria-label",`${item.stage}, ${formatTime(item.official_time_ms)}. ${t('Ver resultado')}`);
    const stage=row.insertCell(); stage.className="stage-cell";
    const name=document.createElement("strong"); name.textContent=item.stage;
    const country=document.createElement("span"); country.className="small-country"; country.textContent=t(item.country); name.append(country);
    const car=document.createElement("small"); car.textContent=item.car; stage.append(name,car);
    const badge=document.createElement("span"); badge.className="local-chip"; badge.textContent=t(item.publication_status==='pending'?'Pendiente':item.publication_status==='accepted'?'Publicada':item.publication_status==='rejected'?'Rechazada':'Local'); row.insertCell().append(badge);
    const time=row.insertCell(); time.className="time-cell"; time.textContent=formatTime(item.official_time_ms);
    const penalty=row.insertCell(); penalty.className="penalty-cell"; penalty.textContent=`+${(item.penalty_ms/1000).toLocaleString(AppI18n.language,{maximumFractionDigits:3})} s`;
    const select=()=>{selectedId=item.id;showView("session");render();}; row.addEventListener("click",select); row.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();select();}});
  }
  container.append(table);
}
const statuses = {
  preparing:["Preparando la sesión","Esperando un guardado estable antes de capturar.","amber"],
  game_closed:["Lista para la siguiente salida","Abre ACR y carga un mapa mod. Nosotros esperamos aquí.",""],
  ready:["Lista para la siguiente salida","Detectamos el inicio y grabamos por ti.","green"],
  recording:["Grabando automáticamente","Concéntrate en el tramo. La pasada se guarda en este PC.","red"],
  waiting_result:["Esperando el resultado del juego","Si terminaste, sal de resultados para que ACR guarde el tiempo.","amber"],
  paused:["Captura en pausa","Activa la captura automática cuando quieras volver a correr.",""],
  attention:["Revisa la conexión con ACR","No se ha detenido ni modificado el juego.","amber"]
};
function render() {
  if (!state) return;
  if(AppI18n.language!==state.language)AppI18n.setLanguage(state.language);
  $("language-select").value=AppI18n.language;
  $('export-button').hidden=!EXPORT_ENABLED;
  const items = state.history;
  const selected = items.find(item=>item.id===selectedId) || items[0];
  const running = state.live && ["recording","waiting_result"].includes(state.status);
  text("connection-label",state.connected?"ACR conectado":"Esperando ACR"); $("connection-dot").className="dot"+(state.connected?" green":"");
  $("auto-toggle").checked=state.auto_capture;
  text("settings-auto",state.auto_capture?"Desactivar":"Activar");
  text("player-name",state.account?.signed_in?state.account.name:t("Entrar con Discord"),false);
  const profileLabel=state.account?.signed_in?(state.account.name_chosen?(AppI18n.language==='es'?'Cerrar sesión de ':'Sign out of ')+state.account.name:'Elegir tu nombre de piloto'):'Entrar con Discord';
  document.querySelector('.profile').title=t(profileLabel);
  document.querySelector('.profile').setAttribute('aria-label',t(profileLabel));
  text("history-count",String(items.length));
  if (running) {
    text("hero-location","TRAMO ACTUAL · POR CONFIRMAR"); text("hero-stage",state.live.track_label.replace(/^\[MOD\]\s*/,""),false); text("hero-car",state.live.car,false);
    text("result-heading",state.status==="recording"?"EN TRAMO":"RELOJ DETENIDO");
    text("main-timer",formatTime(state.live.clock_ms)); text("raw-time",formatTime(state.live.clock_ms)); text("penalty-time","Pendiente"); text("total-time","Pendiente");
    text("action-note",state.start_observed?"Inicio registrado. Esperaremos el resultado oficial del juego.":"Captura parcial: la aplicación no vio el inicio de esta pasada.");
    $("result-source").hidden=true; $("publish-button").disabled=true; $("export-button").disabled=true;
  } else {
    text("hero-location",selected?`${t(selected.country).toLocaleUpperCase(AppI18n.language)} · ${t("MAPA MOD")}`:"TUS MAPAS. TUS TIEMPOS.");
    text("hero-stage",selected?.stage || t("Listos para la salida"),false); text("hero-car",selected?.car || t("Abre Assetto Corsa Rally y carga un mapa mod"),false);
    text("result-heading","ÚLTIMA PASADA"); text("main-timer",formatTime(selected?.official_time_ms)); text("raw-time",formatTime(selected?.raw_time_ms));
    text("penalty-time",selected?"+"+formatTime(selected.penalty_ms):"—"); text("total-time",formatTime(selected?.official_time_ms));
    text("action-note",selected?.publication_status==='accepted'?"Publicado automáticamente tras comprobar la trazada y los tiempos.":selected?.publication_status==='pending'?(validationReasons[selected.validation_reason]||"Pendiente de comprobación automática."):selected?"Guardado en este PC. Tú decides qué compartes.":"Abre la app antes de salir. La captura empieza automáticamente.");
    $("result-source").hidden=!selected; $("publish-button").disabled=!selected||publishing; $("export-button").disabled=!selected;
  }
  text("result-local",running?"Guardando en este PC":"Guardado local");
  const [title,description,color] = statuses[state.status] || statuses.attention;
  text("status-title",title); text("status-description",state.error || description); $("status-dot").className="dot"+(color?" "+color:"");
  historyTable("recent-history",items,2);
  if(currentView==='ranking')renderRanking();
  const search=$("history-search").value.toLocaleLowerCase(AppI18n.language);
  historyTable("all-history",items.filter(item=>`${item.stage} ${item.car} ${item.country}`.toLocaleLowerCase(AppI18n.language).includes(search)));
  text("history-summary",`${items.length} ${items.length===1?t("pasada guardada"):t("pasadas guardadas")}`);
  if(!state.account?.signed_in)accountChecked=false;
  else if(!accountChecked&&!accountLoading)loadAccount();
}
async function loadAccount(){
  accountLoading=true;
  try{
    const profile=await api('/api/account');accountChecked=true;
    if(profile.name_chosen){text('player-name',profile.name,false);api('/api/sync',{}).then(refresh).catch(error=>toast(error.message));}
    else if(!$('publish-dialog').open&&!$('name-dialog').open)$('name-dialog').showModal();
  }catch(error){accountChecked=true;toast('No se pudo comprobar tu nombre. Pulsa tu perfil para reintentar.');}
  finally{accountLoading=false;}
}
async function refresh() { try {state=await api("/api/state");render();}catch(error){text("connection-label","App desconectada");text("status-title","No se pudo conectar con la app");text("status-description","Cierra y vuelve a abrir ACR LAPS ONLINE.");} }
async function setAuto(enabled) { try {await api("/api/auto",{enabled});await refresh();toast(enabled?"Captura automática activada":"Captura en pausa. Tus pasadas guardadas se conservan.");}catch(error){toast(error.message);await refresh();} }
function toggleCompact() {
  compact=!compact;document.body.classList.toggle("compact",compact);if(compact)showView("session");
  window.chrome?.webview?.postMessage({action:"compact",enabled:compact});
}
document.querySelectorAll("[data-view]").forEach(node=>node.addEventListener("click",()=>showView(node.dataset.view)));
document.querySelector(".brand").addEventListener("click",event=>{event.preventDefault();showView("session");});
$("auto-toggle").addEventListener("change",event=>setAuto(event.target.checked));
$("settings-auto").addEventListener("click",()=>setAuto(!state?.auto_capture));
$("history-search").addEventListener("input",render);
$("compact-button").addEventListener("click",toggleCompact);$("settings-compact").addEventListener("click",toggleCompact);
$("publish-button").addEventListener("click",()=>{
  const result=state?.history.find(item=>item.id===selectedId)||state?.history[0];if(!result)return;
  if(!result.can_publish){toast('Esta pasada no conserva una captura completa desde la salida. Haz un nuevo intento con la app abierta.');return;}
  if(!state.account?.signed_in){toast('Pulsa Entrar con Discord arriba a la derecha antes de enviar.');return;}
  if(!state.account?.name_chosen){$('name-dialog').showModal();return;}
  if(result.publication_status){
    if(result.publication_status==='pending'){toast(validationReasons[result.validation_reason]||'Comprobando el envío…');api('/api/sync',{}).then(refresh).catch(error=>toast(error.message));}
    else toast('Esta pasada ya está publicada.');return;
  }
  publishId=result.id;$('publish-dialog').showModal();
});
$("dialog-ok").addEventListener("click",async()=>{
  if(publishing||!publishId)return;
  publishing=true;$('dialog-ok').disabled=true;text('dialog-ok','Enviando…');
  try{const result=await api('/api/publish',{id:publishId});$('publish-dialog').close();toast(result.status==='accepted'?'Pasada validada y publicada automáticamente.':validationReasons[result.validation?.reason]||'La pasada necesita revisión.');await refresh();}
  catch(error){toast(error.message);}
  finally{publishing=false;$('dialog-ok').disabled=false;text('dialog-ok','Enviar pasada');render();}
});document.querySelector(".dialog-close").addEventListener("click",()=>$("publish-dialog").close());
$("export-button").addEventListener("click",()=>{
  if(!EXPORT_ENABLED)return;
  const result=state?.history.find(item=>item.id===selectedId)||state?.history[0];if(!result)return;
  if(window.chrome?.webview){window.chrome.webview.postMessage({action:"export",result});return;}
  const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:"application/json"}));const link=document.createElement("a");link.href=url;link.download="ACR-MOD-RECORDS-resultado.json";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
$("exit-button").addEventListener("click",()=>{if(window.chrome?.webview)window.chrome.webview.postMessage({action:"close"});else api("/api/shutdown",{}).then(()=>toast("Aplicación cerrada. Puedes cerrar esta ventana.")).catch(error=>toast(error.message));});
window.chrome?.webview?.addEventListener("message",event=>{if(event.data?.action==="exported")toast("Resultado exportado en tu PC.");});
const profile=document.querySelector('.profile');
profile.tabIndex=0;profile.setAttribute('role','button');profile.style.cursor='pointer';
async function accountAction(){
  try{
    if(state?.account?.signed_in){
      if(!state.account.name_chosen){accountChecked=false;await loadAccount();return;}
      await api('/api/auth/logout',{});await refresh();toast('Sesión cerrada en este PC.');return;
    }
    const result=await api('/api/auth/start',{});
    if(window.chrome?.webview)window.chrome.webview.postMessage({action:'login',url:result.url});
    else location.assign(result.url);
    toast('Completa el acceso en tu navegador y vuelve a la app.');
  }catch(error){toast(error.message);}
}
profile.addEventListener('click',accountAction);
$('open-ranking').addEventListener('click',()=>{
  const stage=rankingStage?.stage_game_id;
  if(window.chrome?.webview)window.chrome.webview.postMessage({action:'website',stage:stage||null});
  else window.open('https://acrsplits.online'+(stage?'/#/stage/'+encodeURIComponent(stage):''),'_blank','noopener,noreferrer');
});
$('refresh-ranking').addEventListener('click',loadRanking);
profile.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();accountAction();}});
$('name-dialog').querySelector('.name-close').addEventListener('click',()=>$('name-dialog').close());
$('name-logout').addEventListener('click',async()=>{
  if($('save-name').disabled)return;
  try{await api('/api/auth/logout',{});$('name-dialog').close();await refresh();toast('Sesión cerrada en este PC.');}
  catch(error){text('name-error',error.message);}
});
$('pilot-name').addEventListener('input',()=>{$('name-confirm').checked=false;text('name-error','');});
$('name-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!$('name-form').reportValidity())return;
  $('save-name').disabled=true;text('name-error','');
  $('pilot-name').disabled=true;$('name-confirm').disabled=true;
  try{
    const profile=await api('/api/account',{name:$('pilot-name').value});
    $('name-dialog').close();text('player-name',profile.name,false);await refresh();toast((AppI18n.language==='es'?'Nombre de piloto guardado: ':'Pilot name saved: ')+profile.name);
  }catch(error){text('name-error',error.message);}
  finally{$('save-name').disabled=false;$('pilot-name').disabled=false;$('name-confirm').disabled=false;}
});
AppI18n.translateStatic();
$('language-select').addEventListener('change',async event=>{
  const language=event.target.value;
  try{await api('/api/language',{language});if(state)state.language=language;AppI18n.setLanguage(language);window.chrome?.webview?.postMessage({action:'language',language});render();}
  catch(error){toast(error.message);event.target.value=AppI18n.language;}
});
refresh();setInterval(refresh,750);


