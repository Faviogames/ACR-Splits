"use strict";
const AppI18n=(()=>{
  let language='en';
  const pairs={
    'CLASIFICACIÓN ONLINE':'ONLINE LEADERBOARD','Tu posición':'Your position','Tu mejor tiempo':'Your best time','Diferencia con el récord':'Gap to world record','Ver clasificación completa':'View full leaderboard','Actualizar':'Refresh','Posición':'Position','Piloto':'Player','Coche':'Car','Completa un tramo para ver su clasificación.':'Complete a stage to view its leaderboard.','Cargando clasificación…':'Loading leaderboard…','No se pudo cargar la clasificación. Vuelve a intentarlo.':'Could not load the leaderboard. Please try again.','Todavía no hay tiempos publicados.':'No published times yet.',
    'TU PADDOCK':'YOUR PADDOCK','Principal':'Main','Sesión':'Session','Mis tiempos':'My times','Clasificación':'Leaderboards','Ajustes':'Settings',
    'ACR LAPS ONLINE, sesión':'ACR LAPS ONLINE, session','En este PC':'On this PC','Tus pasadas, bajo tu control.':'Your runs, your control.','VERSIÓN · 0.8.1':'VERSION · 0.8.1',
    'Conectando…':'Connecting…','Captura automática':'Automatic capture','Alternar ventana compacta':'Toggle compact window','Piloto local':'Local driver',
    'TUS MAPAS. TUS TIEMPOS.':'YOUR STAGES. YOUR TIMES.','Listos para la salida':'Ready for the start','Abre Assetto Corsa Rally y carga un mapa mod':'Open Assetto Corsa Rally and load a modded stage',
    'IMAGEN CONCEPTUAL':'CONCEPT IMAGE','ÚLTIMA PASADA':'LATEST RUN','Resultado leído del juego':'Result read from the game','Guardado local':'Saved locally','Conducción':'Driving time','Penalización':'Penalty','Tiempo total':'Total time',
    'Publicar resultado':'Publish result','Exportar resultado':'Export result','Guardado en este PC. Tú decides qué compartes.':'Saved on this PC. You decide what to share.',
    'MIS ÚLTIMAS PASADAS':'MY RECENT RUNS','Ver todas':'View all','CADA PASADA CUENTA':'EVERY RUN COUNTS','Resultados reales guardados en este PC. Tu próxima referencia está aquí.':'Real results saved on this PC. Find your next benchmark here.',
    'Buscar tramo o coche':'Search stage or car','Paleohori, Skoda…':'Paleohori, Skoda…','EL SIGUIENTE DESTINO':'YOUR NEXT DESTINATION','La clasificación':'The leaderboards','Un lugar para los récords de nuestros mapas.':'A home for community stage records.',
    'ACCESO ANTICIPADO':'EARLY ACCESS','Tu próxima referencia está online.':'Your next benchmark is online.','Consulta las mejores pasadas aceptadas en nuestra web. Los envíos se comprueban y publican automáticamente cuando pasan los controles de ruta.':'Explore the best accepted runs on our website. Uploads are checked and published automatically when they pass the route checks.',
    'Tu pasada':'Your run','Publicar':'Publish','La captura es automática; el envío requiere tu confirmación y una sesión de Discord.':'Capture is automatic; uploading requires your confirmation and Discord sign-in.','Abrir clasificación web':'Open web leaderboards',
    'A TU MANERA':'YOUR WAY','Preparada para correr':'Ready to drive','Lo esencial para centrarte en el tramo.':'Everything you need to focus on the stage.',
    'Abre la app antes de salir. Cuando el cronómetro arranca, guardamos la pasada.':'Open the app before starting. Capture begins when the stage clock starts.','Activada':'Enabled','Tu resultado oficial':'Your official result',
    'Al terminar, sal de la pantalla de resultados. Esperaremos a que ACR guarde el tiempo con sus penalizaciones.':'After finishing, leave the results screen. We wait for ACR to save the time and its penalties.','Solo lectura':'Read only','Mapas de Stage Exporter':'Stage Exporter stages',
    'Confirmamos el mapa con su identificador del guardado. Solo los tramos del catálogo local de Stage Exporter entran en Mis tiempos.':'We identify the stage from the game save. Only stages in the local Stage Exporter catalogue appear in My times.','Catálogo local':'Local catalogue',
    'Ventana compacta':'Compact window','Un panel pequeño para consultar el estado. También puedes minimizar la aplicación.':'A small panel to check capture status. You can also minimize the app.','Abrir modo compacto':'Open compact mode','Tu privacidad':'Your privacy',
    'Las trazas completas permanecen en tu PC. Solo al confirmar un envío compartes tus tiempos y una traza compacta privada.':'Full traces stay on your PC. Only a confirmed upload shares your times and a private compact trace.','Local':'Local',
    'Los resultados del guardado son locales y modificables. Esta versión aún no valida atajos ni certifica récords.':'Local save files can be modified. Server route checks assess plausibility; they do not certify a run as cheat-free.',
    'Preparando la sesión':'Preparing the session','Tus resultados se guardan en este PC.':'Your results are saved on this PC.','Cerrar aplicación':'Close app','Guardar y cerrar':'Save and close','Cerrar':'Close',
    'Enviar tu pasada':'Upload your run','Compartirás tu nombre de piloto, tramo, coche y tiempos con ACR LAPS ONLINE. La traza compacta se guardará de forma privada en Supabase para revisarla. El servidor comprobará la trazada y publicará el resultado automáticamente si pasa los controles. Los casos dudosos quedan pendientes con un motivo.':'Your pilot name, stage, car and times will be shared with ACR LAPS ONLINE. A compact trace will be stored privately in Supabase for review. The server checks the route and publishes runs that pass. Uncertain cases remain pending with a reason.',
    'Enviar pasada':'Upload run','Elegir nombre más tarde':'Choose a name later','TU IDENTIDAD EN PISTA':'YOUR IDENTITY ON STAGE','Elige tu nombre de piloto.':'Choose your pilot name.',
    'Aparecerá junto a tus récords. Solo puedes elegirlo una vez y queda vinculado a tu cuenta de Discord, también si cambias de PC.':'It appears beside your records. You can choose it only once and it stays linked to your Discord account, even if you change PC.',
    'Nombre de piloto':'Pilot name','De 2 a 32 caracteres. Empieza con una letra. Puedes usar letras, números, espacios, punto, guion y guion bajo.':'Use 2–32 characters, starting with a letter. Letters, numbers, spaces, dots, hyphens and underscores are allowed.',
    'He revisado el nombre y entiendo que no podré cambiarlo.':'I have checked my name and understand that I cannot change it.','Guardar nombre definitivo':'Save permanent name','Cerrar sesión de Discord':'Sign out of Discord',
    'Idioma':'Language','Elige el idioma de la aplicación.':'Choose your app language.',
    'Este tramo todavía no tiene una referencia de ruta en el servidor.':'This stage does not have a server route reference yet.','La posición de salida no coincide con la referencia del tramo.':'The start position does not match the stage reference.',
    'La distancia recorrida no coincide con la longitud del tramo.':'The recorded distance does not match the stage length.','La trazada se aleja del corredor del tramo.':'The trace leaves the stage corridor.','El progreso de la carrera no coincide con la ruta.':'Recorded progress does not match the route.',
    'Se detectó un salto de posición que necesita revisión.':'A position jump requires review.','Se detectó un salto de progreso en el recorrido.':'A route progress jump requires review.','La posición final no coincide con la llegada del tramo.':'The finish position does not match the stage reference.','Faltan puntos de control del recorrido.':'Some route checkpoints are missing.',
    'No se pudo completar la acción':'The action could not be completed','Tu próxima pasada empieza aquí. Abre la app antes de salir y completa un tramo.':'Your next run starts here. Open the app before starting and complete a stage.',
    'Tramo / Coche':'Stage / Car','Estado':'Status','Pendiente':'Pending','Publicada':'Published','Rechazada':'Rejected','Ver resultado':'View result',
    'Esperando un guardado estable antes de capturar.':'Waiting for a stable game save before capturing.','Lista para la siguiente salida':'Ready for the next start','Abre ACR y carga un mapa mod. Nosotros esperamos aquí.':'Open ACR and load a modded stage. We will wait here.',
    'Detectamos el inicio y grabamos por ti.':'We detect the start and capture your run.','Grabando automáticamente':'Capturing automatically','Concéntrate en el tramo. La pasada se guarda en este PC.':'Focus on the stage. Your run is saved on this PC.',
    'Esperando el resultado del juego':'Waiting for the game result','Si terminaste, sal de resultados para que ACR guarde el tiempo.':'If you finished, leave the results screen so ACR can save your time.','Captura en pausa':'Capture paused','Activa la captura automática cuando quieras volver a correr.':'Enable automatic capture when you are ready to drive again.',
    'Revisa la conexión con ACR':'Check the ACR connection','No se ha detenido ni modificado el juego.':'The game has not been stopped or modified.','ACR conectado':'ACR connected','Esperando ACR':'Waiting for ACR','Desactivar':'Disable','Activar':'Enable','Entrar con Discord':'Sign in with Discord','Elegir tu nombre de piloto':'Choose your pilot name',
    'TRAMO ACTUAL · POR CONFIRMAR':'CURRENT STAGE · UNCONFIRMED','EN TRAMO':'ON STAGE','RELOJ DETENIDO':'CLOCK STOPPED','Inicio registrado. Esperaremos el resultado oficial del juego.':'Start recorded. Waiting for the official game result.',
    'Captura parcial: la aplicación no vio el inicio de esta pasada.':'Partial capture: the app did not observe the start of this run.','MAPA MOD':'MODDED STAGE','Publicado automáticamente tras comprobar la trazada y los tiempos.':'Published automatically after route and time checks.','Pendiente de comprobación automática.':'Awaiting automatic checks.',
    'Abre la app antes de salir. La captura empieza automáticamente.':'Open the app before starting. Capture begins automatically.','Guardando en este PC':'Saving on this PC','pasada guardada':'saved run','pasadas guardadas':'saved runs',
    'No se pudo comprobar tu nombre. Pulsa tu perfil para reintentar.':'Could not check your pilot name. Select your profile to retry.','App desconectada':'App disconnected','No se pudo conectar con la app':'Could not connect to the app','Cierra y vuelve a abrir ACR LAPS ONLINE.':'Close and reopen ACR LAPS ONLINE.',
    'Captura automática activada':'Automatic capture enabled','Captura en pausa. Tus pasadas guardadas se conservan.':'Capture paused. Your saved runs are preserved.',
    'Esta pasada no conserva una captura completa desde la salida. Haz un nuevo intento con la app abierta.':'This run has no complete capture from the start. Try again with the app open.','Pulsa Entrar con Discord arriba a la derecha antes de enviar.':'Select Sign in with Discord at the top right before uploading.',
    'Comprobando el envío…':'Checking your upload…','Esta pasada ya está publicada.':'This run is already published.','Enviando…':'Uploading…','Pasada validada y publicada automáticamente.':'Run checked and published automatically.','La pasada necesita revisión.':'This run needs review.',
    'Aplicación cerrada. Puedes cerrar esta ventana.':'App closed. You can close this window.','Resultado exportado en tu PC.':'Result exported to your PC.','Sesión cerrada en este PC.':'Signed out on this PC.','Completa el acceso en tu navegador y vuelve a la app.':'Complete sign-in in your browser, then return to the app.',
    'No se pudo conectar. Comprueba Internet y vuelve a intentarlo.':'Could not connect. Check your Internet connection and try again.','Inicia sesión con Discord primero.':'Sign in with Discord first.','Inicia sesión con Discord':'Sign in with Discord','Se requiere una cuenta de Discord.':'A Discord account is required.',
    'La sesión ha caducado. Vuelve a entrar con Discord.':'Your session expired. Sign in with Discord again.','El inicio de sesión ha caducado. Inténtalo desde la app.':'Sign-in expired. Start again from the app.','Discord no devolvió un código válido.':'Discord did not return a valid code.',
    'La configuración online no es válida.':'Online configuration is invalid.','Windows no pudo proteger o recuperar la sesión. Vuelve a iniciar sesión.':'Windows could not protect or restore your session. Please sign in again.','No se pudo comprobar el nombre de piloto.':'Could not check your pilot name.',
    'Escribe tu nombre de piloto':'Enter your pilot name','Ese nombre ya está ocupado. Elige otro.':'That name is already taken. Choose another.','Ya elegiste tu nombre de piloto. No se puede cambiar.':'You already chose your pilot name. It cannot be changed.',
    'Usa de 2 a 32 caracteres: empieza con una letra y utiliza letras, números, espacios, punto, guion o guion bajo.':'Use 2–32 characters: start with a letter and use letters, numbers, spaces, dots, hyphens or underscores.',
    'El nombre de esta cuenta ya se eligió en otra sesión. Vuelve a abrir la app.':'This account chose its name in another session. Reopen the app.','No se pudo confirmar tu nombre. Vuelve a intentarlo.':'Could not confirm your name. Please try again.',
    'El servidor no confirmó la pasada.':'The server did not confirm the run.','El servidor no confirmó el estado del envío.':'The server did not confirm the upload status.','No se pudo preparar la captura.':'Could not prepare the capture.','No se pudo actualizar el estado del envío.':'Could not refresh the upload status.',
    'Esta pasada no tiene un inicio completo y un resultado nuevo del guardado. Haz una nueva captura con la app abierta.':'This run has no observed start and new game result. Capture a new run with the app open.',
    'Ruta de captura no válida.':'Invalid capture path.','Muestra demasiado grande.':'Sample too large.','La captura contiene muestras no válidas.':'The capture contains invalid samples.','La captura es demasiado larga.':'The capture is too long.',
    'Sesión no autorizada':'Unauthorized session','Solicitud no válida':'Invalid request','Host no permitido':'Host not allowed','Origen no permitido':'Origin not allowed','Solicitud demasiado grande':'Request too large','Ruta inexistente':'Route not found',
    'Todavía no encontramos un guardado de ACR.':'No ACR save file found yet.','No se pudo leer el resultado del juego; se reintentará.':'Could not read the game result. We will try again.','La captura se detuvo por un error. Reinicia la aplicación.':'Capture stopped after an error. Restart the app.',
    'La pasada no tiene una captura completa publicable.':'This run has no complete capture eligible for upload.','No encontramos la captura original en esta app.':'The original capture could not be found in this app.','El guardado excede el limite de lectura':'The game save exceeds the read limit','Se espera un objeto':'An object is required','auto_capture debe ser booleano':'auto_capture must be a boolean','Idioma no válido':'Invalid language',
    'España':'Spain','Grecia':'Greece','Bélgica':'Belgium','México':'Mexico','Portugal':'Portugal','Italia':'Italy','Finlandia':'Finland','Suecia':'Sweden','Croacia':'Croatia','Japón':'Japan','Nueva Zelanda':'New Zealand','Montecarlo':'Monte Carlo','Estonia':'Estonia','Mapa mod':'Modded stage',
  };
  const reverse=new Map(Object.entries(pairs).map(([es,en])=>[en,es]));
  function t(value){
    const service=typeof value==='string'&&value.match(/^El servicio rechazó la solicitud \((\d+)\)\.$/);
    if(service&&language==='en')return `The service rejected the request (${service[1]}).`;
    return language==='es'?(reverse.get(value)||value):(Object.hasOwn(pairs,value)?pairs[value]:value);
  }
  let staticContent;
  function translateStatic(root=document.body){
    if(!staticContent){
      staticContent=[];
      const walk=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
      let node;
      while((node=walk.nextNode())){
        if(!['SCRIPT','STYLE'].includes(node.parentElement?.tagName))staticContent.push({node,original:node.textContent,last:node.textContent});
      }
      for(const node of root.querySelectorAll('[aria-label],[title],[placeholder]')){
        for(const attr of ['aria-label','title','placeholder'])if(node.hasAttribute(attr))staticContent.push({node,attr,original:node.getAttribute(attr),last:node.getAttribute(attr)});
      }
    }
    // Only translate the initial UI; live results and pilot names belong to render().
    for(const item of staticContent){
      const current=item.attr?item.node.getAttribute(item.attr):item.node.textContent;
      if(current!==item.last)continue;
      const translated=item.original.replace(/\S(?:[\s\S]*\S)?/,text=>t(text));
      if(item.attr)item.node.setAttribute(item.attr,translated);else item.node.textContent=translated;
      item.last=translated;
    }
    document.documentElement.lang=language;
  }
  function setLanguage(value){language=value==='es'?'es':'en';translateStatic();}
  return {t,translateStatic,setLanguage,get language(){return language;},pairs};
})();
if(typeof module!=='undefined')module.exports=AppI18n;
