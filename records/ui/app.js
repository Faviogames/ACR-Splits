"use strict";
const token = location.hash.slice(1);
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
const text = (id, value) => { if ($(id).textContent !== value) $(id).textContent = value; };
function toast(message) { $("toast").textContent = message; $("toast").classList.add("visible"); clearTimeout(toastTimer); toastTimer = setTimeout(() => $("toast").classList.remove("visible"), 4200); }
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
}
function historyTable(containerId, items, limit) {
  const container = $(containerId);
  const visible = limit ? items.slice(0,limit) : items;
  const signature = JSON.stringify(visible);
  if (container.dataset.signature === signature) return;
  container.dataset.signature = signature;
  container.replaceChildren();
  if (!visible.length) { const empty = document.createElement("p"); empty.className="empty-message"; empty.textContent="Tu próxima pasada empieza aquí. Abre la app antes de salir y completa un tramo."; container.append(empty); return; }
  const table = document.createElement("table"); table.className="history-table";
  const header = table.createTHead().insertRow();
  for (const label of ["Tramo / Coche", "Estado", "Tiempo total", "Penalización"]) { const th=document.createElement("th"); th.scope="col"; th.textContent=label; header.append(th); }
  const body = table.createTBody();
  for (const item of visible) {
    const row = body.insertRow(); row.className="history-row"; row.tabIndex=0; row.setAttribute("aria-label",`${item.stage}, ${formatTime(item.official_time_ms)}. Ver resultado`);
    const stage=row.insertCell(); stage.className="stage-cell";
    const name=document.createElement("strong"); name.textContent=item.stage;
    const country=document.createElement("span"); country.className="small-country"; country.textContent=item.country; name.append(country);
    const car=document.createElement("small"); car.textContent=item.car; stage.append(name,car);
    const badge=document.createElement("span"); badge.className="local-chip"; badge.textContent=item.publication_status==='pending'?'Pendiente':item.publication_status==='accepted'?'Publicada':'Local'; row.insertCell().append(badge);
    const time=row.insertCell(); time.className="time-cell"; time.textContent=formatTime(item.official_time_ms);
    const penalty=row.insertCell(); penalty.className="penalty-cell"; penalty.textContent=`+${(item.penalty_ms/1000).toLocaleString("es-ES",{maximumFractionDigits:3})} s`;
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
  const items = state.history;
  const selected = items.find(item=>item.id===selectedId) || items[0];
  const running = state.live && ["recording","waiting_result"].includes(state.status);
  text("connection-label",state.connected?"ACR conectado":"Esperando ACR"); $("connection-dot").className="dot"+(state.connected?" green":"");
  $("auto-toggle").checked=state.auto_capture;
  text("settings-auto",state.auto_capture?"Desactivar":"Activar");
  text("player-name",state.account?.signed_in?state.account.name:"Entrar con Discord");
  const profileLabel=state.account?.signed_in?(state.account.name_chosen?'Cerrar sesión de '+state.account.name:'Elegir tu nombre de piloto'):'Entrar con Discord';
  document.querySelector('.profile').title=profileLabel;
  document.querySelector('.profile').setAttribute('aria-label',profileLabel);
  text("history-count",String(items.length));
  if (running) {
    text("hero-location","TRAMO ACTUAL · POR CONFIRMAR"); text("hero-stage",state.live.track_label.replace(/^\[MOD\]\s*/,"")); text("hero-car",state.live.car);
    text("result-heading",state.status==="recording"?"EN TRAMO":"RELOJ DETENIDO");
    text("main-timer",formatTime(state.live.clock_ms)); text("raw-time",formatTime(state.live.clock_ms)); text("penalty-time","Pendiente"); text("total-time","Pendiente");
    text("action-note",state.start_observed?"Inicio registrado. Esperaremos el resultado oficial del juego.":"Captura parcial: la aplicación no vio el inicio de esta pasada.");
    $("result-source").hidden=true; $("publish-button").disabled=true; $("export-button").disabled=true;
  } else {
    text("hero-location",selected?`${selected.country.toLocaleUpperCase("es")} · MAPA MOD`:"TUS MAPAS. TUS TIEMPOS.");
    text("hero-stage",selected?.stage || "Listos para la salida"); text("hero-car",selected?.car || "Abre Assetto Corsa Rally y carga un mapa mod");
    text("result-heading","ÚLTIMA PASADA"); text("main-timer",formatTime(selected?.official_time_ms)); text("raw-time",formatTime(selected?.raw_time_ms));
    text("penalty-time",selected?"+"+formatTime(selected.penalty_ms):"—"); text("total-time",formatTime(selected?.official_time_ms));
    text("action-note",selected?.publication_status==='accepted'?"Publicado automáticamente tras comprobar la trazada y los tiempos.":selected?.publication_status==='pending'?(validationReasons[selected.validation_reason]||"Pendiente de comprobación automática."):selected?"Guardado en este PC. Tú decides qué compartes.":"Abre la app antes de salir. La captura empieza automáticamente.");
    $("result-source").hidden=!selected; $("publish-button").disabled=!selected||publishing; $("export-button").disabled=!selected;
  }
  text("result-local",running?"Guardando en este PC":"Guardado local");
  const [title,description,color] = statuses[state.status] || statuses.attention;
  text("status-title",title); text("status-description",state.error || description); $("status-dot").className="dot"+(color?" "+color:"");
  historyTable("recent-history",items,2);
  const search=$("history-search").value.toLocaleLowerCase("es");
  historyTable("all-history",items.filter(item=>`${item.stage} ${item.car} ${item.country}`.toLocaleLowerCase("es").includes(search)));
  text("history-summary",`${items.length} ${items.length===1?"pasada guardada":"pasadas guardadas"}`);
  if(!state.account?.signed_in)accountChecked=false;
  else if(!accountChecked&&!accountLoading)loadAccount();
}
async function loadAccount(){
  accountLoading=true;
  try{
    const profile=await api('/api/account');accountChecked=true;
    if(profile.name_chosen){text('player-name',profile.name);api('/api/sync',{}).then(refresh).catch(error=>toast(error.message));}
    else if(!$('publish-dialog').open&&!$('name-dialog').open)$('name-dialog').showModal();
  }catch(error){accountChecked=true;toast('No se pudo comprobar tu nombre. Pulsa tu perfil para reintentar.');}
  finally{accountLoading=false;}
}
async function refresh() { try {state=await api("/api/state");render();}catch(error){text("connection-label","App desconectada");text("status-title","No se pudo conectar con la app");text("status-description","Cierra y vuelve a abrir ACR MOD RECORDS.");} }
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
  publishing=true;$('dialog-ok').disabled=true;$('dialog-ok').textContent='Enviando…';
  try{const result=await api('/api/publish',{id:publishId});$('publish-dialog').close();toast(result.status==='accepted'?'Pasada validada y publicada automáticamente.':validationReasons[result.validation?.reason]||'La pasada necesita revisión.');await refresh();}
  catch(error){toast(error.message);}
  finally{publishing=false;$('dialog-ok').disabled=false;$('dialog-ok').textContent='Enviar pasada';render();}
});document.querySelector(".dialog-close").addEventListener("click",()=>$("publish-dialog").close());
$("export-button").addEventListener("click",()=>{
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
  if(window.chrome?.webview)window.chrome.webview.postMessage({action:'website'});
  else window.open('https://acrsplits.online','_blank','noopener,noreferrer');
});
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
    $('name-dialog').close();text('player-name',profile.name);await refresh();toast('Nombre de piloto guardado: '+profile.name);
  }catch(error){text('name-error',error.message);}
  finally{$('save-name').disabled=false;$('pilot-name').disabled=false;$('name-confirm').disabled=false;}
});
refresh();setInterval(refresh,750);

