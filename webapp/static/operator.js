"use strict";
const tg = window.Telegram.WebApp; tg.ready(); tg.expand();
try{ tg.setHeaderColor && tg.setHeaderColor("bg_color"); tg.setBackgroundColor && tg.setBackgroundColor("bg_color"); }catch(e){}
try{ tg.disableVerticalSwipes && tg.disableVerticalSwipes(); }catch(e){}
const INIT = tg.initData || "";
const $ = id => document.getElementById(id);
const esc = TGF.esc;
const sleep = ms => new Promise(r=>setTimeout(r, ms));
const isTouch = () => matchMedia("(pointer:coarse)").matches;
function haptic(k){ try{ tg.HapticFeedback && (k==="sel"?tg.HapticFeedback.selectionChanged():tg.HapticFeedback.impactOccurred(k||"light")); }catch(e){} }
function toast(t, ms){ const e=$("toast"); e.textContent=T(t); e.classList.remove("hide"); clearTimeout(e._t); e._t=setTimeout(()=>e.classList.add("hide"), ms||2200); }
function alert2(t){ t = T(t); try{ tg.showAlert(t); }catch(e){ toast(t, 3500); } }
function confirm2(t){ t = T(t); return new Promise(res=>{ try{ tg.showConfirm(t, ok=>res(!!ok)); }catch(e){ res(window.confirm(t)); } }); }

/* ---------- to'liq ekran (fullscreen) — admin mini app'dagidek ---------- */
function isFS(){ try{ return !!tg.isFullscreen; }catch(e){ return false; } }
function canFS(){ try{ return !!tg.requestFullscreen && (!tg.isVersionAtLeast || tg.isVersionAtLeast("8.0")); }catch(e){ return false; } }
function applyInsets(){
  let t = 0;
  try{ if(tg.isFullscreen) t = ((tg.contentSafeAreaInset&&tg.contentSafeAreaInset.top)||0) + ((tg.safeAreaInset&&tg.safeAreaInset.top)||0); }catch(e){}
  document.documentElement.style.setProperty("--fs-top", t+"px");
  document.querySelectorAll(".fsbtn").forEach(b=>b.classList.toggle("hide", !canFS()));
  document.querySelectorAll(".fssw").forEach(s=>s.classList.toggle("on", isFS()));
}
function toggleFS(){
  try{
    if(isFS()){ tg.exitFullscreen(); try{ localStorage.setItem("fs","0"); }catch(e){} }
    else if(canFS()){ tg.requestFullscreen(); try{ localStorage.setItem("fs","1"); }catch(e){} }
    else { tg.expand(); toast("To'liq ekran uchun Telegramni yangilang"); }
  }catch(e){ toast("Bu qurilmada to'liq ekran qo'llab-quvvatlanmaydi"); }
}
try{
  ["fullscreenChanged","safeAreaChanged","contentSafeAreaChanged"].forEach(ev=>tg.onEvent(ev, applyInsets));
  tg.onEvent("fullscreenFailed", ()=>toast("To'liq ekran ochilmadi"));
}catch(e){}
(function(){
  // Avval yoqilgan bo'lsa (yoki kompyuterda) — avtomatik to'liq ekran
  let pref = null; try{ pref = localStorage.getItem("fs"); }catch(e){}
  const p = (tg.platform||"").toLowerCase();
  const desk = ["tdesktop","macos","web","weba","webk"].includes(p);
  if(canFS() && !isFS() && (pref==="1" || (pref===null && desk))) setTimeout(()=>{ try{ tg.requestFullscreen(); }catch(e){} }, 250);
})();

/* ---------- saqlash: Telegram CloudStorage (qurilmalar orasida) + localStorage ---------- */
const LS = { get(k){ try{ return localStorage.getItem(k); }catch(e){ return null; } },
             set(k,v){ try{ localStorage.setItem(k,v); }catch(e){} }, del(k){ try{ localStorage.removeItem(k); }catch(e){} } };
const hasCloud = () => { try{ return !!(tg.CloudStorage && tg.isVersionAtLeast && tg.isVersionAtLeast("6.9")); }catch(e){ return false; } };
const Store = {
  get(k){ return new Promise(res=>{ const l=LS.get(k); if(!hasCloud()) return res(l);
    let done=false; const t=setTimeout(()=>{ if(!done){ done=true; res(l); } }, 1500);
    try{ tg.CloudStorage.getItem(k,(e,v)=>{ if(done) return; done=true; clearTimeout(t); res(e ? l : (v || l)); }); }catch(e){ done=true; clearTimeout(t); res(l); } }); },
  set(k,v){ LS.set(k,v); if(hasCloud()) try{ tg.CloudStorage.setItem(k, v); }catch(e){} },
  del(k){ LS.del(k); if(hasCloud()) try{ tg.CloudStorage.removeItem(k); }catch(e){} },
};

/* ---------- holat ---------- */
const ST = { op:{}, mk:LS.get("op_mk")||"", v:0, kick:false, chats:[], chatMap:{}, general:[], generalActive:[], generalClients:[], generalMap:{}, generalKind:"active", done:null, operators:[], folder:"all", q:"",
             newcount:0, notifyUnread:0, operatorUnread:0, inited:false, online:true };
let CUR = null, CH = null;
let SELM = null;   // tanlash rejimi: belgilangan xabarlar (Set) yoki null

function auth(){ return { operator_id: ST.op.id, token: ST.op.token }; }
async function api(path, method, body, signal){
  const b = Object.assign({ _init: INIT }, auth(), body||{});
  if(CH && CH.shared) b.shared = 1;
  const o = { method, headers:{ "X-Init-Data": INIT, "Content-Type":"application/json" }, signal };
  let r;
  if(method === "GET") r = await fetch(path + "?" + new URLSearchParams(b), o);
  else { o.body = JSON.stringify(b); r = await fetch(path, o); }
  let j; try{ j = await r.json(); }catch(e){ j = { ok:false, error:"Server javobi noto'g'ri" }; }
  if(r.status === 401 && ST.op.token){ onAuthFail(); }
  return j;
}
const GET = (p,b,s)=>api(p,"GET",b,s), POST = (p,b)=>api(p,"POST",b);
function fileUrl(fid, kind, name, mime){
  return "/api/file?" + new URLSearchParams({ fid, kind, name:name||"", mime:mime||"", mk: ST.mk });
}
function absUrl(u){ return new URL(u, location.href).href; }
function ini(n){ return ((n||"?").trim().charAt(0)||"?").toUpperCase(); }
const _AVA=[["#ff885e","#ff516a"],["#ffcd6a","#ffa85c"],["#82b1ff","#665fff"],["#a0de7e","#54cb68"],["#53edd6","#28c9b7"],["#72d5fd","#2a9ef1"],["#e0a2f3","#d669ed"]];
function avaBg(n){ let h=0; for(const ch of (n||"?")) h=(h*31+ch.charCodeAt(0))>>>0; const p=_AVA[h%7]; return `linear-gradient(135deg,${p[0]},${p[1]})`; }
function avaHtml(n, size){ return `<div class="ava" style="background:${avaBg(n)}${size?`;width:${size}px;height:${size}px;font-size:${Math.round(size*.4)}px`:""}">${esc(ini(n))}</div>`; }
function fmtSize(b){ if(!b) return ""; if(b<1024) return b+" B"; if(b<1048576) return (b/1024).toFixed(b<10240?1:0)+" KB"; return (b/1048576).toFixed(1)+" MB"; }
function fmtDur(s){ s=Math.max(0,Math.floor(s||0)); return Math.floor(s/60)+":"+String(s%60).padStart(2,"0"); }
const MON = LANG === "ru"
  ? ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"]
  : ["yanvar","fevral","mart","aprel","may","iyun","iyul","avgust","sentabr","oktabr","noyabr","dekabr"];
function dayLabel(ts){
  if(!ts) return ""; const d = new Date(ts.slice(0,10)+"T00:00:00"); const n = new Date(); n.setHours(0,0,0,0);
  const diff = Math.round((n - d)/86400000);
  if(diff === 0) return T("Bugun"); if(diff === 1) return T("Kecha");
  return d.getDate()+(LANG==="ru"?" ":"-")+MON[d.getMonth()] + (d.getFullYear()!==n.getFullYear()?" "+d.getFullYear():"");
}
const CT_LBL = {photo:"📷 Rasm",video:"🎥 Video",document:"📄 Hujjat",voice:"🎤 Ovozli xabar",audio:"🎵 Audio",sticker:"🎭 Stiker",animation:"🎞 GIF",location:"📍 Lokatsiya",contact:"👤 Kontakt",video_note:"📹 Video-xabar"};
function msgPreview(m){ if(!m) return ""; const t=(m.text||"").trim(); if(m.type==="text"||!m.type) return t; return (CT_LBL[m.type]||"📎 Fayl")+(t&&m.type!=="location"?" · "+t:""); }

/* ---------- ovozli bildirishnoma ---------- */
let _ac=null;
function _ensureAC(){ if(!_ac){ try{ _ac=new (window.AudioContext||window.webkitAudioContext)(); }catch(e){} } if(_ac&&_ac.state==="suspended"){ try{_ac.resume();}catch(e){} } return _ac; }
["touchstart","mousedown","keydown"].forEach(ev=>document.addEventListener(ev,_ensureAC,{passive:true}));
function _tone(c,f,t0,d,vol){ const o=c.createOscillator(),g=c.createGain(); o.connect(g); g.connect(c.destination); o.type="sine"; o.frequency.value=f;
  g.gain.setValueAtTime(.0001,t0); g.gain.exponentialRampToValueAtTime(vol,t0+.02); g.gain.exponentialRampToValueAtTime(.0001,t0+d); o.start(t0); o.stop(t0+d+.03); }
function beep(soft){
  try{ tg.HapticFeedback && tg.HapticFeedback.notificationOccurred("success"); }catch(e){}
  const m = LS.get("snd")||"on"; if(m==="off") return;
  const vol = (m==="low"||soft) ? .10 : .42; const c=_ensureAC(); if(!c||c.state!=="running") return;
  try{ const t=c.currentTime; _tone(c,1046,t,.16,vol); _tone(c,1568,t+.14,.26,vol); }catch(e){}
}

/* ---------- mavzu ---------- */
function applyScheme(){
  const th = LS.get("theme")||"auto";
  const dark = th==="dark" || (th==="auto" && tg.colorScheme==="dark");
  document.documentElement.setAttribute("data-scheme", dark?"dark":"light");
}
function setTheme(mode){
  LS.set("theme",mode);
  if(mode==="auto") document.documentElement.removeAttribute("data-theme"); else document.documentElement.setAttribute("data-theme",mode);
  document.querySelectorAll("#themeseg button").forEach(b=>b.classList.toggle("on",b.dataset.th===mode));
  applyScheme(); applyWallpaper();
}
try{ tg.onEvent("themeChanged", applyScheme); }catch(e){}
function setSnd(v){ LS.set("snd",v); document.querySelectorAll("#sndseg button").forEach(b=>b.classList.toggle("on",b.dataset.v===v)); }

/* ---------- fon (wallpaper) naqshi ---------- */
function patSvg(c){
  return `<svg xmlns='http://www.w3.org/2000/svg' width='140' height='140' viewBox='0 0 140 140'><g fill='none' stroke='${c}' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'>`+
    `<g transform='rotate(-32 30 26)'><rect x='14' y='19' width='32' height='14' rx='7'/><path d='M30 19v14'/></g>`+
    `<path d='M100 12v16M92 20h16'/><path d='M70 64c-4-6-15-4-13 4 1 6 13 12 13 12s12-6 13-12c2-8-9-10-13-4z'/>`+
    `<circle cx='26' cy='102' r='9'/><path d='M20 102h12'/><path d='M104 98h16v26a4 4 0 0 1-4 4h-8a4 4 0 0 1-4-4zM106 90h12v8h-12z'/>`+
    `<path d='M58 118l5 5 9-9'/><circle cx='124' cy='58' r='2.5'/><circle cx='52' cy='40' r='2.5'/><circle cx='88' cy='132' r='2.5'/>`+
    `<path d='M8 64h8M12 60v8'/><rect x='118' y='22' width='12' height='8' rx='4' transform='rotate(40 124 26)'/></g></svg>`;
}
function setPattern(){
  const dark = document.documentElement.getAttribute("data-scheme")==="dark";
  document.documentElement.style.setProperty("--pat", `url("data:image/svg+xml,${encodeURIComponent(patSvg(dark?"#ffffff":"#1b3a2a"))}")`);
}
let WP = { preset: LS.get("wp_preset")||"default", custom: false, dim: 0, blur: 0, ver: 0, url: "" };
const WP_LIST = [["default","Gulnora"],["mint","Yalpiz"],["ocean","Okean"],["sunset","Shafaq"],["lavender","Lavanda"],["sand","Qum"],["night","Tun"],["plain","Oddiy"]];
async function loadWallpaper(){
  try{
    const r = await GET("/api/wallpaper"); if(!r.ok) return;
    Object.assign(WP, r); LS.set("wp_preset", WP.preset);
    if(WP.custom) await fetchCustomWp();
    applyWallpaper();
  }catch(e){}
}
async function fetchCustomWp(){
  try{
    const resp = await fetch("/api/wallpaper?"+new URLSearchParams({ img: 1, oid: ST.op.id, mk: ST.mk, v: WP.ver }));
    if(!resp.ok){ WP.custom=false; return; }
    if(WP.url) URL.revokeObjectURL(WP.url);
    WP.url = URL.createObjectURL(await resp.blob());
  }catch(e){ WP.custom=false; }
}
function applyWallpaper(target){
  setPattern();
  const w = target || $("wall"); if(!w) return;
  w.className = (target ? "wallx " : "") + (WP.custom && WP.url ? "custom" : "wp-"+(WP.preset||"default"));
  w.style.backgroundImage = WP.custom && WP.url ? `url("${WP.url}")` : "";
  w.style.filter = WP.blur ? `blur(${WP.blur}px)` : "";
  const d = $("walldim"); if(d && !target) d.style.opacity = (WP.dim||0)/100;
}

/* ============================================================
   LOGIN / SESSIYA
   ============================================================ */
async function saveSession(){ Store.set("op_session", JSON.stringify(ST.op)); }
async function loadSession(){ try{ return JSON.parse(await Store.get("op_session")||"null"); }catch(e){ return null; } }
function saveAcc(login){ Store.set("saved_acc", JSON.stringify({ id:ST.op.id, name:ST.op.name, login, token:ST.op.token })); }
async function getAcc(){ try{ return JSON.parse(await Store.get("saved_acc")||"null"); }catch(e){ return null; } }
async function renderSaved(){
  const acc = await getAcc(), box = $("saved-box"), form = $("login-form");
  if(acc){
    box.innerHTML = `<div class="saved-card" data-act="quickEnter">
        <div class="s-ava" style="background:${avaBg(acc.name)}">${esc(ini(acc.name))}</div>
        <div style="min-width:0"><div class="s-name">${esc(acc.name)}</div><div class="s-login">@${esc(acc.login)}</div></div>
        <div class="s-go">Kirish ›</div></div>
      <div class="s-alt" data-act="showForm">Boshqa hisob bilan kirish</div>
      <div class="s-alt" style="color:var(--red)" data-act="forgetAcc">Saqlangan hisobni o'chirish</div>`;
    box.classList.remove("hide"); form.classList.add("hide");
  } else { box.classList.add("hide"); form.classList.remove("hide"); }
}
function showForm(){ $("login-form").classList.remove("hide"); $("saved-box").classList.add("hide"); setTimeout(()=>$("in-login").focus(),50); }
async function forgetAcc(){ Store.del("saved_acc"); $("in-login").value=""; $("in-pass").value=""; renderSaved(); }
async function quickEnter(){
  const acc = await getAcc(); if(!acc) return;
  $("login-err").textContent = "";
  ST.op = { id: acc.id, name: acc.name, token: acc.token };
  const r = await GET("/api/profile").catch(()=>({ok:false,error:"Internet aloqasi yo'q"}));
  if(!r.ok){
    ST.op = {}; showForm(); $("in-login").value = acc.login;
    $("login-err").textContent = r.error==="auth" || !r.error ? "Sessiya tugagan — parol bilan kiring." : r.error;
    return;
  }
  if(r.token){ ST.op.token = r.token; saveAcc(acc.login); }
  if(r.mk){ ST.mk = r.mk; LS.set("op_mk", r.mk); }
  saveSession(); enter();
}
async function doLogin(){
  const login = $("in-login").value.trim(), password = $("in-pass").value.trim(), err = $("login-err");
  err.textContent = "";
  if(!login || !password){ err.textContent = "Login va parolni kiriting"; return; }
  $("btn-login").disabled = true;
  let r; try{ r = await api("/api/login","POST",{ login, password }); }catch(e){ r = {ok:false,error:"Internet aloqasi yo'q"}; }
  $("btn-login").disabled = false;
  if(!r.ok){ err.textContent = r.error || "Xatolik"; haptic("heavy"); return; }
  ST.op = { id: r.operator_id, name: r.name, token: r.token };
  ST.mk = r.mk || ""; LS.set("op_mk", ST.mk);
  saveSession(); saveAcc(login); enter();
}
$("btn-login").onclick = doLogin;
$("in-pass").addEventListener("keydown", e=>{ if(e.key==="Enter") doLogin(); });
let _authFailShown = false;
function onAuthFail(){
  if(_authFailShown) return; _authFailShown = true;
  logout(true);
  $("login-err").textContent = "Sessiya tugadi yoki ish vaqti tugadi. Qayta kiring.";
  setTimeout(()=>_authFailShown=false, 3000);
}
function logout(silent){
  stopSync();
  clearInterval(opChatTimer); opChatTimer=null; OPCHAT=null;
  if(pinTimer){ clearInterval(pinTimer); pinTimer=null; }
  if(chanTimer){ clearInterval(chanTimer); chanTimer=null; }
  if(recActive()) finishRec(false);
  Store.del("op_session");
  ST.op = {}; ST.chats = []; ST.chatMap = {}; ST.operators=[]; ST.notifyUnread=0; ST.operatorUnread=0; ST.inited = false; ST.v = 0; CUR = null; CH = null;
  $("in-pass").value = "";
  closeAllOverlays(); renderSaved(); show("login");
}

/* ============================================================
   EKRANLAR + Telegram BackButton
   ============================================================ */
const SCREENS = ["login","app","chat","opchat","channel","listview"];
let CURSCREEN = "login";
function show(id, anim){
  const wide = id !== "login" && typeof isWide === "function" && isWide();
  document.body.classList.toggle("wide", wide);
  if(wide && anim === "in") anim = "fade";
  SCREENS.forEach(s=>{ const el=$(s); const on = s===id || (wide && s==="app");
    el.classList.toggle("hide", !on); if(s===id && anim){ el.classList.remove("in","fade"); void el.offsetWidth; el.classList.add(anim); } });
  const pe = $("pane-empty"); if(pe) pe.classList.toggle("hide", !(wide && id==="app"));
  CURSCREEN = id; updateBackBtn();
}
function topOverlay(){
  if(!$("viewer").classList.contains("hide")) return "viewer";
  if(!$("sheet").classList.contains("hide")) return "sheet";
  if(!$("mediamodal").classList.contains("hide")) return "media";
  return null;
}
function updateBackBtn(){
  try{ const need = !!topOverlay() || ["chat","opchat","channel","listview"].includes(CURSCREEN) || !!SELM;
    need ? tg.BackButton.show() : tg.BackButton.hide(); }catch(e){}
}
function goBack(){
  TGF.closeMenu();
  const o = topOverlay();
  if(o==="viewer") return closeViewer();
  if(o==="sheet") return closeSheet();
  if(o==="media") return closeMedia();
  if(CURSCREEN==="chat"){
    if(SELM) return endSelect();
    if(!$("csearch").classList.contains("hide")) return chatSearch();
    if(["cmdpanel","quickpanel","stickerpanel"].some(p=>!$(p).classList.contains("hide"))) return hidePanels();
    return backToList();
  }
  if(CURSCREEN==="opchat") return closeOperatorChat();
  if(CURSCREEN==="channel") return closeChannel();
  if(CURSCREEN==="listview") return closeList();
}
try{ tg.BackButton.onClick(goBack); }catch(e){}
document.addEventListener("keydown", e=>{ if(e.key==="Escape" && typeof recActive==="function" && recActive()){ e.preventDefault(); cancelRec(); return; }
  if(e.key==="Escape" && !document.querySelector(".tgf-menu,.tgf-dlg")){ if(CURSCREEN!=="app"||topOverlay()) { e.preventDefault(); goBack(); } } });
function closeAllOverlays(){ closeSheet(); closeViewer(); closeMedia(); TGF.closeMenu(); }

/* ---------- pastki oyna (sheet) ---------- */
function openSheet(html, onMount){
  // har safar yangi element: oldingi oynaning click handlerlari to'planib qolmasin
  const old = $("sheet-body"), nb = old.cloneNode(false); old.replaceWith(nb);
  const s = $("sheet"); nb.innerHTML = html; if(window.I18N) I18N.translate(nb); s.classList.remove("hide");
  $("sheet-body").scrollTop = 0; onMount && onMount($("sheet-body")); updateBackBtn();
}
function closeSheet(){ $("sheet").classList.add("hide"); $("sheet-body").innerHTML=""; updateBackBtn(); }
$("sheet").addEventListener("click", e=>{ if(e.target===$("sheet")) closeSheet(); });

/* ============================================================
   KIRISH
   ============================================================ */
let pinTimer = null;
function enter(){
  show("app","fade"); showTab("chats");
  renderChatList(); loadProfile(); loadWallpaper();
  startSync();
  flushQueue();
}

let ACTIVE_TAB = "chats";
function showTab(t){
  ACTIVE_TAB = t;
  ["chats","general","clients","prof"].forEach(x=>{ $("tab-"+x).classList.toggle("hide", x!==t); $("tb-"+x).classList.toggle("on", x===t); });
  if(t==="prof") loadProfile();
  if(t==="clients") loadClients();
  if(t==="general") loadGeneralChats();
  haptic("sel");
}

/* ============================================================
   SINXRONLASH (long-poll /api/sync)
   ============================================================ */
let syncGen = 0, syncCtl = null;
function startSync(){ stopSync(); const g = ++syncGen; syncLoop(g); }
function stopSync(){ syncGen++; try{ syncCtl && syncCtl.abort(); }catch(e){} }
function kickSync(){ ST.kick = true; try{ syncCtl && syncCtl.abort(); }catch(e){} }
function waitVisible(){ return new Promise(res=>{ const f=()=>{ if(!document.hidden){ document.removeEventListener("visibilitychange",f); res(); } }; document.addEventListener("visibilitychange",f); }); }
document.addEventListener("visibilitychange", ()=>{ if(!document.hidden && ST.op.token) kickSync(); });
function setConn(on){
  if(ST.online === on) return; ST.online = on;
  $("chats-title").innerHTML = on ? "Chatlar" : `<span id="conn"><span class="sp"></span>Ulanmoqda...</span>`;
}
async function syncLoop(gen){
  let fails = 0;
  while(gen === syncGen && ST.op.token){
    // Fonda (minimallashtirilgan) bo'lsa ham kuzatamiz — yangi xabarda ovoz chiqsin
    syncCtl = new AbortController();
    const p = Object.assign({ _init: INIT }, auth(), { v: ST.kick ? 0 : ST.v });
    ST.kick = false;
    if(CUR && CH){ p.order_id = CUR; p.after = CH.maxMid||0; p.since = CH.since||""; if(CH.shared) p.shared=1; if(chatVisible()) p.mark = 1; }
    const tmo = setTimeout(()=>{ try{ syncCtl.abort(); }catch(e){} }, 30000);
    try{
      const resp = await fetch("/api/sync?"+new URLSearchParams(p), { headers:{ "X-Init-Data": INIT }, signal: syncCtl.signal });
      clearTimeout(tmo);
      if(resp.status === 401){ onAuthFail(); return; }
      const r = await resp.json();
      if(gen !== syncGen) return;
      fails = 0; setConn(true);
      applySync(r);
    }catch(e){
      clearTimeout(tmo);
      if(gen !== syncGen) return;
      if(e.name === "AbortError" && ST.kick) continue;
      fails++; if(fails > 1) setConn(false);
      await sleep(Math.min(12000, 800 * fails));
    }
  }
}
function chatVisible(){ return CURSCREEN==="chat" && !document.hidden; }
function applySync(r){
  if(!r || !r.ok) return;
  if(r.token){ ST.op.token = r.token; saveSession(); getAcc().then(a=>{ if(a && a.id==ST.op.id){ a.token=r.token; Store.set("saved_acc", JSON.stringify(a)); } }); }
  if(r.mk){ ST.mk = r.mk; LS.set("op_mk", r.mk); }
  // yangi mijoz xabari / yangi murojaat — ovoz
  let ring = false;
  if(ST.inited){
    r.chats.forEach(c=>{
      const prev = ST.chatMap[c.order_id];
      if(c.last_sender==="client" && c.last_mid > (prev ? prev.last_mid : 0)){
        if(!(c.order_id===CUR && chatVisible())) ring = true;
      }
    });
    if(r.newcount > ST.newcount) ring = true;
    if((r.notify_unread||0)>ST.notifyUnread) ring = true;
  }
  ST.chats = r.chats; ST.chatMap = {}; r.chats.forEach(c=>ST.chatMap[c.order_id]=c);
  if(r.general_chats){
    ST.generalActive=r.general_chats;
    if(["active","unread","paused"].includes(ST.generalKind)) ST.general=r.general_chats;
    ST.generalMap={}; [...ST.generalActive,...ST.general].forEach(c=>ST.generalMap[c.order_id]=c);
    renderGeneralChats();
  }
  ST.newcount = r.newcount; ST.notifyUnread = r.notify_unread||0; ST.operatorUnread = r.operator_unread||0; ST.v = r.v; ST.inited = true;
  if(ring) beep();
  renderChatList(); updateBadges();
  if(ST.folder==="operators"&&Date.now()-_opPeersAt>8000) loadOperatorPeers();
  if(r.chat_error && CUR){ toast(r.chat_error, 3200); backToList(); return; }
  if(r.chat && CH && r.chat.order_id === CUR) mergeChat(r.chat, r.server_ts);
  if(CH && CUR) setPeerTyping(r.typing||[]);
  flushQueue();
}
function updateBadges(){
  const unread = ST.chats.filter(c=>!c.archived && (c.unread>0 || c.marked_unread)).length;
  const tot = unread + ST.newcount;
  const e = $("tb-badge"); e.textContent = tot>99?"99+":tot; e.classList.toggle("hide", !tot);
  const gu = ST.generalActive.reduce((n,c)=>n+(+c.unread||(+!!c.marked_unread)),0);
  const gb = $("tb-general-badge"); if(gb){ gb.textContent=gu>99?"99+":gu; gb.classList.toggle("hide",!gu); }
  const nb = $("notify-badge"); if(nb){ nb.textContent=ST.notifyUnread>99?"99+":ST.notifyUnread; nb.classList.toggle("hide",!ST.notifyUnread); }
  const all = ST.chats.filter(c=>!c.archived).length, rep = ST.chats.filter(c=>!c.archived && !c.paused && c.reply).length, arc = ST.chats.filter(c=>c.archived).length;
  const pz = ST.chats.filter(c=>c.paused).length;
  [["fc-all",unread],["fc-unread",rep],["fc-archived",arc],["fc-paused",pz],["fc-operators",ST.operatorUnread]].forEach(([id,n])=>{ const x=$(id); x.textContent=n; x.classList.toggle("hide",!n); });
  [["gfc-active",ST.generalActive.length],["gfc-unread",gu],["gfc-paused",ST.generalActive.filter(c=>c.paused).length]].forEach(([id,n])=>{
    const x=$(id); if(x){ x.textContent=n>99?"99+":n; x.classList.toggle("hide",!n); }
  });
  void all;
}

/* ============================================================
   CHATLAR RO'YXATI
   ============================================================ */
const ICK = '<svg class="ic" viewBox="0 0 24 24" style="width:16px;height:16px;color:var(--green)"><path d="M4 12l5 5L20 6"/></svg>';
const IPIN = '<svg class="ic pin" viewBox="0 0 24 24"><path d="M12 17v5M8 2h8M9 2l1 9M15 2l-1 9M6 11h12l-2 4H8l-2-4z"/></svg>';
$("folders").addEventListener("click", e=>{
  const b = e.target.closest("button[data-f]"); if(!b) return;
  ST.folder = b.dataset.f; document.querySelectorAll("#folders button").forEach(x=>x.classList.toggle("on", x===b));
  haptic("sel");
  if(["done","canceled","rejected"].includes(ST.folder)) loadDoneChats();
  else if(ST.folder==="operators") loadOperatorPeers();
  else renderChatList();
});
$("folders").addEventListener("wheel", e=>{
  const box=e.currentTarget;
  if(box.scrollWidth<=box.clientWidth)return;
  e.preventDefault();
  const delta=Math.abs(e.deltaX)>Math.abs(e.deltaY)?e.deltaX:e.deltaY;
  box.scrollBy({left:delta,behavior:"smooth"});
}, {passive:false});
function toggleSearch(){
  const box = $("chsearch"); const open = box.classList.contains("hide");
  box.classList.toggle("hide", !open);
  if(open) setTimeout(()=>$("ch-q").focus(), 50); else { $("ch-q").value=""; ST.q=""; renderChatList(); }
}
let _clT = null;
$("ch-q").addEventListener("input", ()=>{ ST.q = $("ch-q").value.trim().toLowerCase(); renderChatList();
  clearTimeout(_clT); _clT = setTimeout(searchClientsInList, 350); });
async function loadDoneChats(){
  $("chatlist").innerHTML = '<div class="spinner"></div>';
  const kind = ST.folder; ST.done = null;
  const r = await GET("/api/done_chats", { kind }).catch(()=>null);
  if(ST.folder !== kind) return;
  ST.done = r && r.ok ? r.chats : []; renderChatList();
}
let _opPeersAt=0;
async function loadOperatorPeers(){
  _opPeersAt=Date.now();
  $("chatlist").innerHTML = '<div class="spinner"></div>';
  const r = await GET("/api/operator_peers").catch(()=>null);
  if(ST.folder!=="operators") return;
  ST.operators = r&&r.ok ? r.operators : [];
  ST.operatorUnread = ST.operators.reduce((n,o)=>n+(+o.unread||0),0);
  renderChatList(); updateBadges();
}
function operatorRowHtml(o){
  const live=o.online?"Onlayn":"Oflayn";
  const state = `${live} · ${o.availability==="busy" ? "Band" : "Bo'sh"} · ${o.open_count||0} ta murojaat`;
  const viewing=o.viewing_order_id?`#${o.viewing_order_id} · ${esc(o.viewing_client||"Mijoz")} chatini ko'ryapti`:(o.last_text||"Ichki xabar yozish");
  return `<div class="crow oprow-chat" data-opid="${o.id}" data-name="${esc(o.name)}"><div class="cfront">${avaHtml(o.name)}
    <div class="mid"><div class="l1"><span class="op-presence-dot ${o.online?"online":"offline"}"></span><span class="nm">${esc(o.name)}</span><span class="opstate">${esc(state)}</span><span class="tm">${esc((o.last_at||"").slice(11,16))}</span></div>
    <div class="l2"><span class="pv ${o.viewing_order_id?"op-viewing":""}">${viewing}</span>${o.unread?`<span class="badge">${o.unread}</span>`:""}</div></div></div></div>`;
}
function chanRowHtml(){
  const n = ST.newcount;
  return `<div class="crow chanrow" data-act="openChannel"><div class="cfront">
    <div class="chanava"><svg class="ic" viewBox="0 0 24 24" style="width:24px;height:24px"><path d="M3 11l18-5v13L3 14v-3zM11.6 16.8a3 3 0 0 1-5.8-1.6"/></svg></div>
    <div class="mid"><div class="l1"><span class="nm">Yangi murojaatlar</span></div>
      <div class="l2"><span class="pv">${n ? `<span class="me">${n} ta murojaat qabul qilinishini kutyapti</span>` : "Yangi murojaatlar shu yerda paydo bo'ladi"}</span>${n?`<span class="badge">${n}</span>`:""}</div></div></div></div>`;
}
function waitInfo(c){
  const m=+c.waiting_min||0;
  if(!c.reply||c.paused||m<5)return {cls:"",html:""};
  const cls=m>=20?" wait-danger":" wait-warn";
  const label=m>=60?`${Math.floor(m/60)}s ${m%60}d`: `${m} daq`;
  return {cls,html:`<span class="wait-pill">⏳ ${label}</span>`};
}
function chatRowHtml(c, done){
  const draft = !done && c.draft ? TGF.toPlain(c.draft).trim() : "";
  let pv;
  if(draft && c.order_id!==CUR) pv = `<span class="dr">Qoralama:</span> ${esc(draft)}`;
  else pv = (c.last_sender==="operator" ? `<span class="me">Siz: </span>` : "") + esc(c.preview||"");
  if(!done && c.paused) pv = `<span class="pzl">⏸ ${esc(T("Pauzada"))}</span> ` + pv;
  const unread = !done && (c.unread || (c.marked_unread ? 1 : 0));
  const right = unread ? `<span class="badge">${c.marked_unread && !c.unread ? "" : c.unread}</span>` : (c.pinned ? IPIN : "");
  const tm = (c.last_sender==="operator" ? ICK : "") + esc(c.time||"");
  const st = (done ? (c.status==="canceled" ? "🔴 " : "") : "") + (c.rejected ? "🚫 " : "");
  const tags = (c.branch ? `<span class="brc">📍${esc(c.branch)}</span>` : "") + (c.tags||[]).slice(0,2).map(t=>`<span class="chip" style="font-size:10.5px;padding:1px 6px">${esc(t)}</span>`).join(" ");
  const close = !done && c.auto_close_at ? `<span class="autoclose-pill" data-close="${esc(c.auto_close_at)}">⏱ ${remainingLabel(c.auto_close_at)}</span>` : "";
  const wait = done ? {cls:"",html:""} : waitInfo(c);
  return `<div class="crow${c.pinned&&!done?" pinned":""}${c.order_id===CUR?" sel":""}${wait.cls}" data-oid="${c.order_id}" data-name="${esc(c.name)}" ${done?'data-done="1"':""}>
    ${done?"":`<div class="cacts"><button class="a1" data-sw="pin">${c.pinned?"Olib<br>tashlash":"Qadash"}</button><button class="a2" data-sw="read">${unread?"O'qilgan":"O'qilmagan"}</button><button class="a3" data-sw="arch">${c.archived?"Arxivdan":"Arxiv"}</button></div>`}
    <div class="cfront">${avaHtml(c.name)}
      <div class="mid"><div class="l1"><span class="nm">${st}${esc(c.name)}</span>${tags}<span class="tm">${tm}</span></div>
        <div class="l2"><span class="pv">${pv}</span>${wait.html}${close}${done && c.rating?`<span style="color:var(--orange);font-size:13px">${c.rating}★</span>`:""}${right}</div></div></div></div>`;
}
function remainingLabel(ts){
  if(!ts) return "";
  const due=new Date(ts.replace(" ","T")), left=Math.max(0,Math.ceil((due-Date.now())/1000));
  return left<=0 ? T("Yakunlanmoqda") : `${Math.floor(left/60)}:${String(left%60).padStart(2,"0")}`;
}
setInterval(()=>{
  document.querySelectorAll("[data-close]").forEach(x=>x.textContent="⏱ "+remainingLabel(x.dataset.close));
  if(CH&&CH.autoCloseAt&&CURSCREEN==="chat") updateSub();
},1000);
let _listPending = false;
function renderChatList(){
  if(CURSCREEN==="login") return;
  if(swRow || document.querySelector("#chatlist .crow.swiped")){ _listPending = true; return; }
  _listPending = false;
  const box = $("chatlist"); if(!box) return;
  const qq = ST.q;
  const match = c => !qq || (c.name||"").toLowerCase().includes(qq) || (c.phone||"").includes(qq) || (c.preview||"").toLowerCase().includes(qq) || ("#"+c.order_id)===qq;
  let html = "";
  if(ST.folder==="operators"){
    const list=(ST.operators||[]).filter(o=>!qq||(o.name||"").toLowerCase().includes(qq)||(o.last_text||"").toLowerCase().includes(qq));
    html=list.map(operatorRowHtml).join("")||`<div class="empty"><div class="big">👥</div>Boshqa faol operator yo'q</div>`;
  } else if(["done","canceled","rejected"].includes(ST.folder)){
    if(ST.done === null){ box.innerHTML = '<div class="spinner"></div>'; return; }
    const list = (ST.done||[]).filter(match);
    const emp = {done:["🗂","Yakunlangan suhbatlar yo'q"], canceled:["🔴","Bekor qilingan murojaatlar yo'q"], rejected:["🚫","Otkaz qilingan murojaatlar yo'q"]}[ST.folder];
    html = list.map(c=>chatRowHtml(c,true)).join("") || `<div class="empty"><div class="big">${emp[0]}</div>${emp[1]}</div>`;
  } else {
    let list = ST.chats.filter(match);
    if(ST.folder==="archived") list = list.filter(c=>c.archived);
    else list = list.filter(c=>!c.archived);
    if(ST.folder==="unread") list = list.filter(c=>!c.paused && (c.reply || c.unread || c.marked_unread));
    if(ST.folder==="paused") list = list.filter(c=>c.paused);
    list.sort((a,b)=> (b.pinned - a.pinned) || ((b.ts||"") > (a.ts||"") ? 1 : -1));
    if(ST.folder==="all" && !qq) html += chanRowHtml();
    html += list.map(c=>chatRowHtml(c,false)).join("");
    if(!list.length){
      html += ST.folder==="archived" ? `<div class="empty"><div class="big">🗄</div>Arxiv bo'sh.<br>Chatni chapga surib «Arxiv»ni bosing.</div>`
            : ST.folder==="unread" ? `<div class="empty"><div class="big">✅</div>Hamma mijozlarga javob berilgan</div>`
            : ST.folder==="paused" ? `<div class="empty"><div class="big">⏸</div>Pauzadagi suhbat yo'q</div>`
            : qq ? "" : `<div class="empty"><div class="big">💬</div>Faol suhbat yo'q.<br>Yangi murojaatlar yuqoridagi bo'limda.</div>`;
    }
  }
  if(qq) html += `<div id="cl-found"></div>`;
  const st = box.scrollTop; box.innerHTML = html; box.scrollTop = st;
  if(qq) searchClientsInList();
}
async function searchClientsInList(){
  const qq = ST.q; const slot = $("cl-found"); if(!qq || !slot) return;
  const r = await GET("/api/clients",{q:qq}).catch(()=>null);
  if(!r || !r.ok || ST.q!==qq || !$("cl-found")) return;
  $("cl-found").innerHTML = r.clients.length ? `<div class="sect">Mijozlar</div>` + r.clients.map(c=>`
    <div class="crow" data-oid="${c.last_order}" data-name="${esc(c.name)}" data-done="1"><div class="cfront">${avaHtml(c.name)}
      <div class="mid"><div class="l1"><span class="nm">${esc(c.name)}</span></div><div class="l2"><span class="pv">${esc(c.phone)} · ${c.cnt} murojaat</span></div></div></div></div>`).join("") : "";
}
/* bosish / o'ng tugma / bosib turish / surish */
const CL = $("chatlist");
CL.addEventListener("click", e=>{
  const sw = e.target.closest("[data-sw]");
  const row = e.target.closest(".crow"); if(!row) return;
  if(sw){ e.stopPropagation(); rowAction(+row.dataset.oid, sw.dataset.sw); closeSwipes(); return; }
  if(row.classList.contains("swiped")){ closeSwipes(); return; }
  if(row.dataset.act==="openChannel") return openChannel();
  if(row._lp){ row._lp=false; return; }
  if(row.dataset.opid) return openOperatorChat(+row.dataset.opid, row.dataset.name);
  openChat(+row.dataset.oid, row.dataset.name);
});
CL.addEventListener("contextmenu", e=>{
  const row = e.target.closest(".crow[data-oid]"); if(!row || row.dataset.done) return;
  e.preventDefault(); rowMenu(row, e.clientX, e.clientY);
});
function rowMenu(row, x, y){
  const c = ST.chatMap[+row.dataset.oid]; if(!c) return;
  const unread = c.unread || c.marked_unread;
  TGF.menu(x, y, [
    {label:"Ochish", icon:"<svg viewBox='0 0 24 24'><path d='M21 11.5a8.4 8.4 0 0 1-9 8.5 8.5 8.5 0 0 1-3.8-.9L3 20l1.9-5.2A8.5 8.5 0 0 1 12 3a8.4 8.4 0 0 1 9 8.5z'/></svg>", onClick:()=>openChat(c.order_id, c.name)},
    {label:c.pinned?"Qadashni olib tashlash":"Qadash", icon:"<svg viewBox='0 0 24 24'><path d='M12 17v5M8 2h8M9 2l1 9M15 2l-1 9M6 11h12l-2 4H8l-2-4z'/></svg>", onClick:()=>rowAction(c.order_id,"pin")},
    {label:unread?"O'qilgan deb belgilash":"O'qilmagan deb belgilash", icon:"<svg viewBox='0 0 24 24'><path d='M4 12l5 5L20 6'/></svg>", onClick:()=>rowAction(c.order_id,"read")},
    {label:c.archived?"Arxivdan chiqarish":"Arxivlash", icon:"<svg viewBox='0 0 24 24'><path d='M21 8v13H3V8M1 3h22v5H1zM10 12h4'/></svg>", onClick:()=>rowAction(c.order_id,"arch")},
    "sep",
    {label:"Yakunlash", icon:"<svg viewBox='0 0 24 24'><path d='M20 6L9 17l-5-5'/></svg>", onClick:()=>closeOrder(c.order_id)},
  ]);
}
async function rowAction(oid, act){
  const c = ST.chatMap[oid]; if(!c) return;
  const body = { order_id: oid };
  if(act==="pin"){ c.pinned = !c.pinned; body.pinned = c.pinned; }
  if(act==="arch"){ c.archived = !c.archived; body.archived = c.archived; if(c.archived) toast("Arxivga o'tkazildi"); }
  if(act==="read"){ const u = c.unread || c.marked_unread; if(u){ c.unread=0; c.marked_unread=false; body.marked_unread=false; body.read=1; } else { c.marked_unread=true; body.marked_unread=true; } }
  haptic(); renderChatList(); updateBadges();
  const r = await POST("/api/chat_state", body).catch(()=>null);
  if(!r || !r.ok) toast("Saqlanmadi");
}
/* surish (touch) */
let swRow=null, swX0=0, swY0=0, swDx=0, swMode=null, lpTimer=null;
function closeSwipes(except){ document.querySelectorAll(".crow.swiped").forEach(r=>{ if(r!==except){ r.classList.remove("swiped"); r.querySelector(".cfront").style.transform=""; } });
  if(!except && _listPending) setTimeout(renderChatList, 240); }
CL.addEventListener("touchstart", e=>{
  const row = e.target.closest(".crow[data-oid]"); if(!row || row.dataset.done) { swRow=null; return; }
  swRow=row; swX0=e.touches[0].clientX; swY0=e.touches[0].clientY; swDx=0; swMode=null;
  clearTimeout(lpTimer);
  lpTimer = setTimeout(()=>{ if(!swMode){ row._lp=true; haptic("medium"); rowMenu(row, Math.min(swX0, innerWidth-240), swY0); } }, 520);
}, {passive:true});
CL.addEventListener("touchmove", e=>{
  if(!swRow) return;
  const dx = e.touches[0].clientX - swX0, dy = e.touches[0].clientY - swY0;
  if(!swMode){ if(Math.abs(dx)>8 || Math.abs(dy)>8){ clearTimeout(lpTimer); swMode = Math.abs(dx)>Math.abs(dy) ? "h" : "v"; } }
  if(swMode!=="h") return;
  e.preventDefault();
  const base = swRow.classList.contains("swiped") ? -222 : 0;
  swDx = Math.max(-240, Math.min(0, base + dx));
  const f = swRow.querySelector(".cfront"); f.style.transition="none"; f.style.transform = `translateX(${swDx}px)`;
}, {passive:false});
CL.addEventListener("touchend", ()=>{
  clearTimeout(lpTimer);
  if(!swRow || swMode!=="h"){ swRow=null; if(_listPending) renderChatList(); return; }
  const f = swRow.querySelector(".cfront"); f.style.transition="";
  if(swDx < -70){ closeSwipes(swRow); swRow.classList.add("swiped"); f.style.transform="translateX(-222px)"; haptic("sel"); }
  else { swRow.classList.remove("swiped"); f.style.transform=""; }
  swRow=null; if(_listPending && !document.querySelector("#chatlist .crow.swiped")) setTimeout(renderChatList, 240);
});

/* ============================================================
   UMUMIY: BARCHA OPERATORLARNING MUROJAATLARI VA MIJOZLARI
   ============================================================ */
const GENERAL_HINTS={
  active:"Barcha operatorlarning jarayondagi murojaatlari",
  unread:"Javob kutayotgan umumiy murojaatlar",
  paused:"Barcha operatorlarning pauzadagi murojaatlari",
  done:"Barcha operatorlarning yakunlangan murojaatlari",
  canceled:"Barcha operatorlarning bekor qilingan murojaatlari",
  clients:"Barcha operatorlar ishlagan umumiy mijozlar"
};
const GENERAL_EMPTY={
  active:"Jarayondagi umumiy murojaat yo'q", unread:"Javobsiz murojaat yo'q",
  paused:"Pauzadagi murojaat yo'q", done:"Yakunlangan murojaat yo'q",
  canceled:"Bekor qilingan murojaat yo'q", clients:"Umumiy mijozlar hozircha yo'q"
};
let _generalT=null;
$("general-search").addEventListener("input", ()=>{
  clearTimeout(_generalT);
  _generalT=setTimeout(()=>ST.generalKind==="clients"?loadGeneralChats():renderGeneralChats(),220);
});
$("general-folders").addEventListener("click",e=>{
  const b=e.target.closest("button[data-g]"); if(!b)return;
  ST.generalKind=b.dataset.g;
  document.querySelectorAll("#general-folders button").forEach(x=>x.classList.toggle("on",x===b));
  haptic("sel"); loadGeneralChats();
});
$("general-folders").addEventListener("wheel",e=>{
  const box=e.currentTarget; if(box.scrollWidth<=box.clientWidth)return;
  e.preventDefault();
  const delta=Math.abs(e.deltaX)>Math.abs(e.deltaY)?e.deltaX:e.deltaY;
  box.scrollBy({left:delta,behavior:"smooth"});
},{passive:false});
async function loadGeneralChats(){
  const kind=ST.generalKind;
  $("general-hint").textContent=GENERAL_HINTS[kind]||GENERAL_HINTS.active;
  if((kind==="clients"?!ST.generalClients.length:!ST.general.length)) $("general-list").innerHTML='<div class="spinner"></div>';
  if(kind==="clients"){
    const r=await GET("/api/general_clients",{q:$("general-search").value.trim()}).catch(()=>null);
    if(ST.generalKind!==kind||!r||!r.ok)return;
    ST.generalClients=r.clients||[]; renderGeneralChats(); return;
  }
  const apiKind=kind==="unread"?"active":kind;
  const r=await GET("/api/general_chats",{kind:apiKind}).catch(()=>null);
  if(ST.generalKind!==kind||!r||!r.ok)return;
  ST.general=r.chats||[];
  if(apiKind==="active") ST.generalActive=ST.general;
  ST.generalMap={}; [...ST.generalActive,...ST.general].forEach(c=>ST.generalMap[c.order_id]=c);
  renderGeneralChats(); updateBadges();
}
function generalRowHtml(c){
  const closed=c.status==="done"||c.status==="canceled";
  const status=c.status==="done"?`<span class="me">Yakunlangan · </span>`:
    (c.status==="canceled"?`<span class="pzl">Bekor qilingan · </span>`:"");
  const pv=(c.paused?`<span class="pzl">⏸ ${esc(T("Pauzada"))}</span> `:"")+status+
    (c.last_sender==="operator"?`<span class="me">Javob: </span>`:"")+esc(c.preview||"");
  const unread=+c.unread||(c.marked_unread?1:0);
  const wait=closed?{cls:"",html:""}:waitInfo(c);
  return `<div class="crow${wait.cls}" data-oid="${c.order_id}" data-name="${esc(c.name)}"><div class="cfront">${avaHtml(c.name)}
    <div class="mid"><div class="l1"><span class="nm">${esc(c.name)}</span><span class="op-owner">${esc(c.operator_name||"Operator")}</span><span class="tm">${esc(c.time||"")}</span></div>
    <div class="l2"><span class="pv">${pv}</span>${wait.html}${unread?`<span class="badge">${unread>99?"99+":unread}</span>`:""}</div></div></div></div>`;
}
function generalClientRowHtml(c){
  const labels={in_progress:"Jarayonda",done:"Yakunlangan",canceled:"Bekor qilingan",new:"Yangi"};
  const uname=c.username?` · @${esc(c.username)}`:"";
  return `<div class="crow" data-oid="${c.last_order}" data-name="${esc(c.name)}"><div class="cfront">${avaHtml(c.name)}
    <div class="mid"><div class="l1"><span class="nm">${esc(c.name)}</span><span class="op-owner">${esc(c.operator_name||"Operator")}</span></div>
    <div class="l2"><span class="pv">${esc(c.phone||"")}${uname} · ${c.cnt||0} murojaat · ${labels[c.last_status]||""}</span></div></div></div></div>`;
}
function renderGeneralChats(){
  const box=$("general-list"); if(!box)return;
  const kind=ST.generalKind, qv=$("general-search").value.trim().toLowerCase();
  $("general-hint").textContent=GENERAL_HINTS[kind]||GENERAL_HINTS.active;
  let list;
  if(kind==="clients"){
    list=ST.generalClients;
  }else{
    list=ST.general;
    if(kind==="unread") list=list.filter(c=>(+c.unread||c.marked_unread));
    else if(kind==="paused") list=list.filter(c=>c.paused);
    list=list.filter(c=>!qv||(c.name||"").toLowerCase().includes(qv)||(c.phone||"").includes(qv)||(c.operator_name||"").toLowerCase().includes(qv)||(c.preview||"").toLowerCase().includes(qv));
  }
  const st=box.scrollTop;
  box.innerHTML=list.map(kind==="clients"?generalClientRowHtml:generalRowHtml).join("")||`<div class="empty"><div class="big">👥</div>${GENERAL_EMPTY[kind]||GENERAL_EMPTY.active}</div>`;
  box.scrollTop=st;
}
$("general-list").addEventListener("click",e=>{ const r=e.target.closest(".crow[data-oid]"); if(r)openChat(+r.dataset.oid,r.dataset.name,true); });

/* ============================================================
   MIJOZLARIM
   ============================================================ */
let _cliT=null;
$("cl-search").addEventListener("input", ()=>{ clearTimeout(_cliT); _cliT=setTimeout(loadClients, 300); });
async function loadClients(){
  const r = await GET("/api/clients",{ q: $("cl-search").value.trim() }).catch(()=>null);
  if(!r || !r.ok) return;
  $("clrows").innerHTML = r.clients.length ? r.clients.map(c=>`
    <div class="crow" data-oid="${c.last_order}" data-name="${esc(c.name)}"><div class="cfront">${avaHtml(c.name)}
      <div class="mid"><div class="l1"><span class="nm">${esc(c.name)}</span></div><div class="l2"><span class="pv">${esc(c.phone)} · ${c.cnt} murojaat</span></div></div></div></div>`).join("")
    : `<div class="empty"><div class="big">👥</div>Siz qabul qilgan mijozlar shu yerda ko'rinadi</div>`;
}
$("clrows").addEventListener("click", e=>{ const r=e.target.closest(".crow"); if(r) openChat(+r.dataset.oid, r.dataset.name); });

/* ============================================================
   CHAT
   ============================================================ */
const MSGS = $("msgs");
async function openChat(oid, name, shared=false){
  if(!oid) return;
  if(recActive()) finishRec(false);
  if(SELM) endSelect();
  saveDraftNow(); clearTimeout(_draftT);
  CUR = oid;
  CH = { oid, name: name||"", shared:!!shared, returnTab:ACTIVE_TAB, msgs: new Map(), order: [], pending: [], maxMid: 0, since: "", hasMore: false,
         loadingOlder: false, lastRead: 0, notes: [], pinned: null, tags: [], status: "", replyTo: null, editMid: null,
         fabN: 0, search: null, draftReady: false };
  $("c-name").textContent = name || ""; const av=$("c-ava"); av.textContent = ini(name); av.style.background = avaBg(name);
  $("c-sub").textContent = "yuklanmoqda..."; $("c-sub").classList.remove("typing");
  MSGS.innerHTML = '<div class="spinner"></div>';
  ["pinbar","notebanner","tagsbar","csearch","fab"].forEach(i=>$(i).classList.add("hide"));
  hidePanels(); clearReply(true);
  CMP.clear();
  const c = shared ? ST.generalMap[oid] : ST.chatMap[oid]; if(c){ c.unread = 0; c.marked_unread = false; }
  show("chat", "in"); applyWallpaper(); renderChatList(); updateBadges();
  let r;
  try{ r = await GET("/api/messages", { order_id: oid, mark: 1, shared:shared?1:"" }); }catch(e){ r = null; }
  if(CUR !== oid) return;
  if(!r || !r.ok){ MSGS.innerHTML = `<div class="empty">Yuklab bo'lmadi.<br><span class="s-alt" data-act="reopenChat">Qayta urinish</span></div>`; return; }
  CH.lastRead = r.last_read_mid || 0;
  applyMeta(r);
  CH.hasMore = r.has_more;
  r.messages.forEach(m=>addMsg(m));
  CH.since = r.server_ts;
  loadPendingFromQueue();
  renderTimeline({ toUnread: true });
  _lastDraft[oid] = r.draft || "";
  if(r.draft && !CH.editMid) CMP.setHTML(r.draft); else if(!isTouch()) CMP.focus();
  CH.draftReady = true;
  loadNote();
  kickSync();
}
function reopenChat(){ if(CUR) openChat(CUR, CH && CH.name, CH && CH.shared); }
function addMsg(m){
  if(!CH) return;
  if(!CH.msgs.has(m.mid)){ CH.order.push(m.mid); CH.order.sort((a,b)=>a-b); }
  CH.msgs.set(m.mid, m);
  if(!m.own && !m.kind && m.mid > (CH.lastClientMid||0)) CH.lastClientMid = m.mid;
  if(m.mid > CH.maxMid) CH.maxMid = m.mid;
}
function applyMeta(r){
  CH.status = r.status; CH.client = r.client || {}; CH.tags = r.tags || []; CH.pinned = r.pinned || null;
  CH.operatorName = r.operator_name || ""; CH.operatorId = r.operator_id || 0; CH.autoCloseAt = r.auto_close_at || "";
  CH.rejected = !!r.rejected;
  const pkey = p => JSON.stringify(((p||{}).history||[]).map(h=>[h.start,h.end]));
  const notesChanged = JSON.stringify((r.notes||[]).map(n=>n.id)) !== JSON.stringify(CH.notes.map(n=>n.id))
                       || pkey(r.pause) !== pkey(CH.pause);
  CH.notes = r.notes || [];
  CH.pause = r.pause || {};
  renderPausebar();
  CH.phone = (r.client && r.client.phone) || ""; CH.uname = (r.client && r.client.username) || "";
  CH.branch = (r.client && r.client.branch) || ""; CH.branchId = (r.client && r.client.branch_id) || 0;
  updateSub(); applyChatStatus(r.status); applyFulfill(r.fulfillment||""); renderPinbar(); renderTagsbar();
  return notesChanged;
}
function updateSub(){
  const s = $("c-sub"); if(s.classList.contains("typing")) return;
  const st = CH.status==="done" ? T("yakunlangan") : CH.status==="canceled" ? T("bekor qilingan") : "";
  s.textContent = [CH.operatorName ? T("Operator")+": "+CH.operatorName : "", CH.branch ? "📍 " + CH.branch : "", CH.phone,
    CH.autoCloseAt ? "⏱ "+remainingLabel(CH.autoCloseAt) : "", st, CH.rejected ? "🚫 " + T("Otkaz") : "", "#"+CH.oid].filter(Boolean).join(" · ");
}
let peerTypingTimer=null;
function setPeerTyping(names){
  if(!CH)return;
  clearTimeout(peerTypingTimer);
  const oid=CH.oid, list=[...new Set(names||[])];
  const s=$("c-sub");
  if(list.length){
    s.textContent=(list.length===1?list[0]:list.join(", "))+" yozmoqda…";
    s.classList.add("typing");
    peerTypingTimer=setTimeout(()=>{
      if(CH&&CH.oid===oid){ s.classList.remove("typing"); updateSub(); }
    },8500);
  }else{
    s.classList.remove("typing"); updateSub();
  }
}
function mergeChat(meta, serverTs){
  const notesChanged = applyMeta(meta);
  const fresh = [], updated = [];
  (meta.messages||[]).forEach(m=>{
    if(CH.msgs.has(m.mid)){ const old = CH.msgs.get(m.mid); if(old.text!==m.text || old.html!==m.html || old.edited!==m.edited){ CH.msgs.set(m.mid, m); updated.push(m); } }
    else { addMsg(m); fresh.push(m); }
  });
  if(serverTs) CH.since = serverTs;
  // yuborilayotgan (optimistik) nusxalarini olib tashlaymiz
  if(fresh.some(m=>m.own)){ const own = new Set(fresh.filter(m=>m.own).map(m=>m.mid)); CH.pending = CH.pending.filter(p=>!(p.mid && own.has(p.mid))); }
  const pf = fresh.length ? prevOf(fresh[0].mid) : null;
  if(notesChanged || fresh.some(m=>m.type==="photo") || (pf && pf.type==="photo")) { renderTimeline({ keep: true, newMids: fresh.map(m=>m.mid) }); }
  else {
    updated.forEach(m=>{ const n = $("m"+m.mid); if(n){ n.outerHTML = rowHtml(m, prevOf(m.mid), nextOf(m.mid), false); } });
    if(fresh.length) appendNew(fresh);
    if(updated.length) initVoicePlayers();
  }
  if(fresh.some(m=>!m.own) && chatVisible()) beep(true);
}
function prevOf(mid){ const i = CH.order.indexOf(mid); return i>0 ? CH.msgs.get(CH.order[i-1]) : null; }
function nextOf(mid){ const i = CH.order.indexOf(mid); return i>=0 && i<CH.order.length-1 ? CH.msgs.get(CH.order[i+1]) : null; }

/* ---------- vaqt chizig'i ---------- */
function sameGroup(a, b){
  if(!a || !b || a.kind || b.kind) return false;
  if(a.own !== b.own || isSys(a) || isSys(b)) return false;
  if((a.ts||"").slice(0,10) !== (b.ts||"").slice(0,10)) return false;
  return Math.abs(new Date((b.ts||"").replace(" ","T")) - new Date((a.ts||"").replace(" ","T"))) < 5*60000;
}
function isSys(m){ return m && m.own && m.type==="text" && /^(🔄|🏥 Filial tanlandi)/.test(m.text||""); }
function timelineItems(){
  const items = [];
  // Har bir rasm alohida xabar (albomga birlashtirilmaydi — Telegramga ham alohida boradi)
  CH.order.forEach(id=>items.push(CH.msgs.get(id)));
  CH.notes.forEach(n=>items.push({ kind:"note", ts:n.ts, note:n }));
  ((CH.pause||{}).history||[]).forEach(h=>items.push({ kind:"pause", ts:h.start, p:h }));
  CH.pending.forEach(p=>items.push(Object.assign({ kind:"pending" }, p)));
  items.sort((a,b)=>{ const ka=a.kind==="pending"?"9":(a.ts||""), kb=b.kind==="pending"?"9":(b.ts||""); return ka<kb?-1:ka>kb?1:((a.mid||0)-(b.mid||0)); });
  return items;
}
function renderTimeline(opt){
  opt = opt || {};
  const items = timelineItems();
  const prevH = MSGS.scrollHeight, prevTop = MSGS.scrollTop;
  const nearBottom = MSGS.scrollHeight - MSGS.scrollTop - MSGS.clientHeight < 140;
  let html = CH.hasMore ? `<div class="loadmore" id="loadmore">Oldingi xabarlar yuklanmoqda...</div>` : "";
  let lastDay = "", unreadPut = false;
  items.forEach((it, i)=>{
    const day = (it.ts||"").slice(0,10);
    if(day && day !== lastDay && it.kind!=="pending"){ html += `<div class="dsep"><span>${esc(dayLabel(it.ts))}</span></div>`; lastDay = day; }
    if(!unreadPut && CH.lastRead && !it.kind && !it.own && it.mid > CH.lastRead){ html += `<div class="unsep" id="unsep">O'qilmagan xabarlar</div>`; unreadPut = true; }
    if(it.kind==="note") html += noteHtml(it.note);
    else if(it.kind==="pause") html += pauseHtml(it.p);
    else if(it.kind==="pending") html += pendingHtml(it);
    else html += rowHtml(it, items[i-1], items[i+1], opt.newMids && opt.newMids.includes(it.mid));
  });
  if(!items.length) html += `<div class="empty" style="color:var(--b-in-t);opacity:.7"><div class="big">👋</div>Hali xabar yo'q</div>`;
  MSGS.innerHTML = html;
  initVoicePlayers(); bindMediaLoad();
  if(opt.prepend){ MSGS.scrollTop = MSGS.scrollHeight - prevH + prevTop; }
  else if(opt.toUnread && $("unsep")){ MSGS.scrollTop = $("unsep").offsetTop - 60; }
  else if(opt.keep && !nearBottom){ MSGS.scrollTop = prevTop; bumpFab(opt.newMids ? opt.newMids.length : 0); }
  else toBottom(true);
  if(CH.search && CH.search.q) applySearchMarks();
  markPicked();
}
function appendNew(list){
  const nearBottom = MSGS.scrollHeight - MSGS.scrollTop - MSGS.clientHeight < 140;
  list.forEach(m=>{
    const prev = prevOf(m.mid);
    // oldingi xabarning guruh/dum (tail) holatini yangilash
    if(prev){ const pn = $("m"+prev.mid); if(pn && !CH.pinnedAlbum){ pn.outerHTML = rowHtml(prev, prevOf(prev.mid), m, false); } }
    let pre = "";
    if(!prev || (prev.ts||"").slice(0,10) !== (m.ts||"").slice(0,10)) pre = `<div class="dsep"><span>${esc(dayLabel(m.ts))}</span></div>`;
    const firstPending = MSGS.querySelector(".mrow.pend");
    const html = pre + rowHtml(m, prev, null, true);
    if(firstPending) firstPending.insertAdjacentHTML("beforebegin", html); else MSGS.insertAdjacentHTML("beforeend", html);
  });
  const emp = MSGS.querySelector(".empty"); if(emp) emp.remove();
  initVoicePlayers(); bindMediaLoad(); refreshTicks();
  if(nearBottom || list.some(m=>m.own)) toBottom(); else bumpFab(list.filter(m=>!m.own).length);
}
function toBottom(instant){
  if(instant) MSGS.scrollTop = MSGS.scrollHeight;
  else MSGS.scrollTo({ top: MSGS.scrollHeight, behavior: "smooth" });
  CH && (CH.fabN = 0); $("fab-n").classList.add("hide");
}
function bumpFab(n){ if(!n) return; CH.fabN += n; $("fab-n").textContent = CH.fabN; $("fab-n").classList.remove("hide"); $("fab").classList.remove("hide"); }
MSGS.addEventListener("scroll", ()=>{
  if(!CH) return;
  const fromBottom = MSGS.scrollHeight - MSGS.scrollTop - MSGS.clientHeight;
  $("fab").classList.toggle("hide", fromBottom < 260);
  if(fromBottom < 60){ CH.fabN = 0; $("fab-n").classList.add("hide"); }
  if(MSGS.scrollTop < 120 && CH.hasMore && !CH.loadingOlder) loadOlder();
  TGF.closeMenu();
}, { passive: true });
/* rasmlar yuklanganda pastda turgan bo'lsak — pastga yopishib turamiz */
function bindMediaLoad(){
  MSGS.querySelectorAll("img:not([data-b]),video:not([data-b])").forEach(el=>{
    el.dataset.b = 1;
    const f = ()=>{ if(MSGS.scrollHeight - MSGS.scrollTop - MSGS.clientHeight < 420 && !(CH && CH.loadingOlder)) MSGS.scrollTop = MSGS.scrollHeight; };
    el.addEventListener(el.tagName==="IMG"?"load":"loadedmetadata", f, { once: true });
  });
}
async function loadOlder(){
  if(!CH || !CH.order.length) return;
  CH.loadingOlder = true; const oid = CUR;
  const r = await GET("/api/messages", { order_id: oid, before: CH.order[0], shared:CH.shared?1:"" }).catch(()=>null);
  if(CUR !== oid || !r || !r.ok){ if(CH) CH.loadingOlder = false; return; }
  r.messages.forEach(m=>addMsg(m)); CH.hasMore = r.has_more;
  renderTimeline({ prepend: true });
  setTimeout(()=>{ if(CH) CH.loadingOlder = false; }, 250);
}

/* ---------- bitta xabar HTML ---------- */
const CK1 = '<svg class="ck" viewBox="0 0 16 11"><path d="M1.5 5.8l3.2 3.2L14.5 1" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const CLK = '<svg class="ck" viewBox="0 0 16 16" style="width:13px;height:13px"><circle cx="8" cy="8" r="6.3" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 4.5V8l2.2 1.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>';
const ERRI = '<svg class="ck" viewBox="0 0 16 16" style="width:14px;height:14px"><circle cx="8" cy="8" r="7" fill="currentColor"/><path d="M8 4.2v4.6M8 11.2v.4" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/></svg>';
// Telegramdek: ✓ — yuborildi, ✓✓ — mijoz o'qidi.
// Bot API o'qilganlik belgisini bermaydi, shuning uchun mijoz shu xabardan keyin yozgan bo'lsa — o'qigan hisoblanadi.
const CK2 = '<svg class="ck ck2" viewBox="0 0 20 11"><path d="M1.2 5.8l3.2 3.2L14.2 1M8.6 8.6l.6.4L19 1" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
function isReadByClient(m){ return !!(CH && m.mid && m.mid < (CH.lastClientMid||0)); }
function metaHtml(m){
  return `<span class="meta">${m.edited?'<span class="ed">tahrirlangan</span> ':""}${esc(m.time||"")}${m.own?(isReadByClient(m)?CK2:CK1):""}</span>`;
}
// Mijoz yangi xabar yozganda — oldingi xabarlarimiz ✓✓ bo'ladi
function refreshTicks(){
  if(!CH) return;
  MSGS.querySelectorAll(".mrow.o[data-mid]").forEach(r=>{
    if(+r.dataset.mid < (CH.lastClientMid||0)){ const c = r.querySelector(".meta .ck:not(.ck2)"); if(c) c.outerHTML = CK2; } });
}
function docIcon(name, mime){
  const n=(name||"").toLowerCase(), mm=(mime||"").toLowerCase();
  if(n.endsWith(".pdf")||mm.includes("pdf")) return ["pdf","PDF"];
  if(/\.(docx?|rtf|odt|txt)$/.test(n)||mm.includes("word")) return ["doc", (n.split(".").pop()||"DOC").toUpperCase().slice(0,4)];
  if(/\.(xlsx?|csv|ods)$/.test(n)||mm.includes("sheet")||mm.includes("excel")) return ["xls", (n.split(".").pop()||"XLS").toUpperCase().slice(0,4)];
  if(/\.(png|jpe?g|webp|gif|heic)$/.test(n)||mm.startsWith("image/")) return ["img","IMG"];
  if(/\.(zip|rar|7z|tar|gz)$/.test(n)) return ["zip","ZIP"];
  const ext = n.includes(".") ? n.split(".").pop().toUpperCase().slice(0,4) : "FILE";
  return ["gen", ext];
}
function replyQuote(m){
  if(!m.reply_to) return "";
  const r = CH.msgs.get(m.reply_to) || m.reply; if(!r) return "";
  const who = r.own ? "Siz" : (CH.name || "Mijoz");
  const thumb = r.type==="photo" && r.file_id ? `<img src="${esc(fileUrl(r.file_id,"photo"))}">` : "";
  return `<div class="rq" data-jump="${m.reply_to}">${thumb}<div style="min-width:0"><div class="rqn">${esc(who)}</div><div class="rqt">${esc(msgPreview(r)||"Xabar")}</div></div></div>`;
}
function isEmojiOnly(t){
  t = (t||"").trim(); if(!t || t.length > 24) return false;
  try{ return /^(?:\p{Extended_Pictographic}|\p{Emoji_Component}|\u200d|\ufe0f|\s)+$/u.test(t) && !/^[\d#*\s]+$/.test(t); }catch(e){ return false; }
}
function textBlock(m){
  const html = TGF.render(m.html, m.text);
  const url = TGF.firstUrl(m.text||"");
  return `<div class="txt">${html}</div>${url && m.type==="text" ? TGF.linkCard(url) : ""}`;
}
function rowHtml(m, prev, next, isNew){
  if(isSys(m)) return `<div class="sysm" id="m${m.mid}"><span>${esc(m.text)}</span></div>`;
  const cls = m.own ? "o" : "c";
  const gstart = !sameGroup(prev, m), gend = !sameGroup(m, next);
  const rowCls = `mrow ${cls}${gstart?" gstart":""}${gend?" gend":""}${isNew?" new":""}`;
  const data = `id="m${m.mid}" data-mid="${m.mid}"`;
  const rq = replyQuote(m);
  const t = m.type || "text", fid = m.file_id;
  let bubCls = "bub", inner = "";
  if(m.album){
    const n = m.album.length, cap = m.album.find(x=>x.text);
    const cells = m.album.slice(0, 4).map((x,i)=>`<div class="cell" data-view="${x.mid}"><img loading="lazy" src="${esc(fileUrl(x.file_id,"photo"))}">${i===3&&n>4?`<div class="more">+${n-4}</div>`:""}</div>`).join("");
    bubCls += " media" + (cap ? "" : " nocap");
    inner = rq + `<div class="album ${n===2?"n2":n===3?"n3":n===4?"n4":"nmany"}">${cells}</div>` + (cap ? textBlock(cap) : "") + metaHtml(m.album[n-1]);
  } else if(t==="photo" && fid){
    bubCls += " media" + (m.text ? "" : " nocap");
    inner = rq + `<div class="ph" data-view="${m.mid}"><img loading="lazy" src="${esc(fileUrl(fid,"photo"))}" alt=""></div>` + (m.text ? textBlock(m) : "") + metaHtml(m);
  } else if((t==="video"||t==="animation"||t==="video_note") && fid){
    bubCls += " media" + (m.text ? "" : " nocap");
    const auto = t==="animation" ? "autoplay loop muted" : "muted";
    inner = rq + `<div class="vid" data-view="${m.mid}"><video ${auto} playsinline preload="metadata" src="${esc(fileUrl(fid,"video"))}#t=0.1"></video>${t!=="animation"?`<div class="play"><svg viewBox="0 0 24 24" width="26" height="26" fill="#fff"><path d="M8 5v14l11-7z"/></svg></div>`:""}${t==="animation"?'<div class="dur">GIF</div>':""}</div>` + (m.text ? textBlock(m) : "") + metaHtml(m);
  } else if(t==="sticker" && fid){
    bubCls += " stick";
    inner = `<img loading="lazy" src="${esc(fileUrl(fid,"sticker"))}">` + metaHtml(m);
  } else if((t==="voice"||t==="audio") && fid){
    inner = rq + `<div class="vp" data-src="${esc(fileUrl(fid,"voice"))}" data-fid="${esc(fid)}"><button class="pp" type="button"></button><div class="vw"><canvas></canvas><div class="vt">0:00</div></div></div>` + metaHtml(m);
  } else if(t==="document" && fid){
    const [k, lbl] = docIcon(m.file_name, m.mime_type);
    const nm = m.file_name || m.text || "Hujjat";
    const sz = [lbl, fmtSize(m.size)].filter(Boolean).join(" · ");
    inner = rq + `<div class="doc" data-doc="${m.mid}"><div class="di ${k}">${esc(lbl)}</div><div style="min-width:0"><div class="dn">${esc(nm)}</div><div class="ds">${esc(sz)}${k==="pdf"?" · ochish":""}</div></div></div>` +
            (m.text && m.text!==nm ? textBlock(m) : "") + metaHtml(m);
  } else if(t==="location" && (m.text||"").includes(",")){
    const [la, lo] = m.text.split(",");
    inner = `<a class="mapc tgf-a" href="https://maps.google.com/?q=${encodeURIComponent(la)},${encodeURIComponent(lo)}" target="_blank" rel="noopener"><div class="grid"></div><div class="pin">📍</div><div class="lab">Lokatsiya · xaritada ochish</div></a>` + metaHtml(m);
    bubCls += " media";
  } else if(t!=="text"){
    inner = rq + `<div class="txt"><b>${esc(CT_LBL[t]||"📎 Fayl")}</b>${m.text?"\n"+TGF.render(m.html, m.text):""}</div>` + metaHtml(m);
  } else if(isEmojiOnly(m.text)){
    bubCls += " emo";
    inner = rq + `<div class="emoj">${esc(m.text.trim())}</div>` + metaHtml(m);
  } else if(m.own && /^🧾 Hisob-kitob/.test(m.text||"")){
    bubCls += " billc";
    const body = (m.text||"").replace(/^🧾 Hisob-kitob[^:]*:?\s*/, "");
    const lines = body.split("\n").filter(x=>x.trim());
    inner = rq + `<div class="bh">🧾 ${esc(T("Hisob-kitob"))}</div>` + lines.map(l=>{
        if(/^─+$/.test(l.trim())) return `<div class="bsep"></div>`;
        if(/^💰/.test(l)) return `<div class="btot">${esc(l.replace(/^💰\s*/,""))}</div>`;
        return `<div class="bl">${esc(l)}</div>`; }).join("") + metaHtml(m);
  } else if(m.own && m.html && /^(📋|🏥|✅ Operator|✅ Оператор)/.test(m.text||"")){
    bubCls += " infoc";
    inner = rq + `<div class="ich">${PIN_IC}<span>${esc(T("Filial ma'lumoti"))}</span></div>` + textBlock(m) + metaHtml(m);
  } else {
    inner = rq + textBlock(m) + metaHtml(m);
  }
  const tail = gend && !bubCls.includes("stick") && !bubCls.includes("emo") ? " tail" : "";
  return `<div class="${rowCls}" ${data}><div class="${bubCls}${tail}">${inner}</div><div class="rpl-ic"><svg class="ic" viewBox="0 0 24 24" style="width:16px;height:16px"><path d="M9 17l-5-5 5-5M4 12h12a4 4 0 0 1 4 4v4"/></svg></div></div>`;
}
function noteHtml(n){
  return `<div class="note"><div class="nb"><div class="nh">🔒 ${esc(T("Ichki izoh"))} · ${esc(T(n.kind==="admin"?"Admin":"Operator"))} <span class="pz-keep">${esc(n.author)}</span></div><span class="pz-keep">${esc(n.text)}</span><div class="nt">${esc(n.time)} · ${esc(T("mijoz ko'rmaydi"))}</div></div></div>`;
}
function pendingHtml(p){
  const st = p.state==="failed" ? `<span class="meta fail" data-retry="${p.lid}">${ERRI} Yuborilmadi</span>`
           : `<span class="meta">${esc(p.time||"")}${CLK}</span>`;
  const rq = p.reply_mid ? replyQuote({ reply_to: p.reply_mid }) : "";
  return `<div class="mrow o gstart gend pend new" id="p${p.lid}" data-lid="${p.lid}"><div class="bub tail">${rq}<div class="txt">${TGF.render(p.html, p.text)}</div>${st}</div></div>`;
}

/* ---------- xabarlar bilan ishlash: bosish / o'ng tugma / bosib turish / surish ---------- */
MSGS.addEventListener("click", e=>{
  if(SELM){ const row = e.target.closest(".mrow[data-mid]"); if(row){ e.preventDefault(); e.stopPropagation(); toggleSel(+row.dataset.mid); } return; }
  const j = e.target.closest("[data-jump]"); if(j){ e.stopPropagation(); return jumpTo(+j.dataset.jump); }
  const v = e.target.closest("[data-view]"); if(v){ e.stopPropagation(); return openViewer(+v.dataset.view); }
  const d = e.target.closest("[data-doc]"); if(d){ e.stopPropagation(); return openDoc(+d.dataset.doc); }
  const rt = e.target.closest("[data-retry]"); if(rt){ e.stopPropagation(); return pendingMenu(rt.dataset.retry, e.clientX, e.clientY); }
  if(e.target.closest("a,.vp,.tgf-sp")) return;
  const row = e.target.closest(".mrow[data-mid]");
  if(row && isTouch() && !getSelection().toString()) msgMenu(+row.dataset.mid, e.clientX, e.clientY);
});
MSGS.addEventListener("dblclick", e=>{
  if(isTouch()) return;
  const row = e.target.closest(".mrow[data-mid]"); if(!row || e.target.closest("a,.vp,[data-view],[data-doc]")) return;
  getSelection().removeAllRanges(); setReply(+row.dataset.mid);
});
MSGS.addEventListener("contextmenu", e=>{
  const row = e.target.closest(".mrow[data-mid]"); if(!row) return;
  if(getSelection().toString() && row.contains(getSelection().anchorNode)) return;   // matn belgilangan — brauzer menyusi
  e.preventDefault(); msgMenu(+row.dataset.mid, e.clientX, e.clientY);
});
/* chapga surib javob berish (Telegram) */
let mRow=null, mX0=0, mY0=0, mDx=0, mMode=null;
MSGS.addEventListener("touchstart", e=>{
  const row = e.target.closest(".mrow[data-mid]"); mRow=row; mMode=null; mDx=0;
  if(row){ mX0=e.touches[0].clientX; mY0=e.touches[0].clientY; }
}, {passive:true});
MSGS.addEventListener("touchmove", e=>{
  if(!mRow) return;
  const dx = e.touches[0].clientX - mX0, dy = e.touches[0].clientY - mY0;
  if(!mMode && (Math.abs(dx)>10 || Math.abs(dy)>10)) mMode = (Math.abs(dx) > Math.abs(dy)*1.3 && dx<0) ? "h" : "v";
  if(mMode!=="h" || CH.status==="done" || CH.status==="canceled") return;
  mDx = Math.max(-80, Math.min(0, dx));
  mRow.style.transition="none"; mRow.style.transform = `translateX(${mDx}px)`;
  const ic = mRow.querySelector(".rpl-ic"); if(ic) ic.style.opacity = Math.min(1, -mDx/60);
  if(mDx <= -64 && !mRow._hv){ mRow._hv = true; haptic("light"); }
}, {passive:true});
MSGS.addEventListener("touchend", ()=>{
  if(!mRow) return;
  if(mMode==="h"){ mRow.style.transition=""; mRow.style.transform=""; const ic=mRow.querySelector(".rpl-ic"); if(ic) ic.style.opacity=0;
    if(mDx <= -64) setReply(+mRow.dataset.mid); }
  mRow._hv = false; mRow = null;
});
function msgMenu(mid, x, y){
  const m = CH.msgs.get(mid); if(!m) return;
  const open = CH.status==="new" || CH.status==="in_progress";
  const canEdit = m.own && m.cmid && m.type==="text" && !String(m.text||"").startsWith("👨‍💼 Admin");
  const media = m.file_id && ["photo","video","animation","document","voice","audio"].includes(m.type);
  const isPinned = CH.pinned && CH.pinned.mid === mid;
  TGF.menu(x, y, [
    {header: (m.own ? T("Siz") : (CH.name||T("Mijoz"))) + " · " + (m.ts||"").slice(0,16)},
    open && {label:"Javob berish", icon:"<svg viewBox='0 0 24 24'><path d='M9 17l-5-5 5-5M4 12h12a4 4 0 0 1 4 4v4'/></svg>", onClick:()=>setReply(mid)},
    (m.text && m.type!=="location") && {label: m.type==="text" ? "Nusxa olish" : "Izohni nusxalash", icon:"copy", onClick:()=>copyText(m.text)},
    (m.type==="photo" && m.file_id) && {label:"Rasmni nusxalash", icon:"<svg viewBox='0 0 24 24'><rect x='3' y='3' width='18' height='18' rx='3'/><circle cx='9' cy='9' r='2'/><path d='M21 15l-5-5L5 21'/></svg>", onClick:()=>copyImage(fileUrl(m.file_id,"photo"))},
    (m.file_id && ["document","video","voice","audio","animation"].includes(m.type)) && {label:"Fayl havolasini nusxalash", icon:"<svg viewBox='0 0 24 24'><path d='M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7'/><path d='M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7'/></svg>", onClick:()=>copyText(absUrl(mediaUrl(m)), "Havola nusxalandi")},
    {label:"Tanlash", icon:"<svg viewBox='0 0 24 24'><circle cx='12' cy='12' r='9'/><path d='M8 12l3 3 5-6'/></svg>", onClick:()=>startSelect(mid)},
    canEdit && open && {label:"Tahrirlash", icon:"<svg viewBox='0 0 24 24'><path d='M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7'/><path d='M18.5 2.5a2.1 2.1 0 0 1 3 3L12 15l-4 1 1-4z'/></svg>", onClick:()=>startEdit(mid)},
    {label:isPinned?"Qadashni olib tashlash":"Qadash", icon:"<svg viewBox='0 0 24 24'><path d='M12 17v5M8 2h8M9 2l1 9M15 2l-1 9M6 11h12l-2 4H8l-2-4z'/></svg>", onClick:()=>pinMsg(isPinned?0:mid)},
    media && {label:m.type==="document"?"Ochish / yuklab olish":"Yuklab olish", icon:"<svg viewBox='0 0 24 24'><path d='M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3'/></svg>", onClick:()=>openExternal(mediaUrl(m))},
    m.own && "sep",
    m.own && {label: m.cmid ? "O'chirish (mijozdan ham)" : "O'chirish (faqat yozishmadan)", danger:true, icon:"<svg viewBox='0 0 24 24'><path d='M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6'/></svg>", onClick:()=>deleteMsg(mid)},
  ]);
}
function mediaUrl(m){
  return fileUrl(m.file_id, m.type==="voice"||m.type==="audio" ? "voice" : m.type==="document" ? "document" : m.type==="photo" ? "photo" : "video", m.file_name, m.mime_type);
}
function toPng(blob){
  if(blob.type==="image/png") return Promise.resolve(blob);
  return new Promise((res, rej)=>{ const img = new Image();
    img.onload = ()=>{ const c = document.createElement("canvas"); c.width = img.naturalWidth; c.height = img.naturalHeight;
      c.getContext("2d").drawImage(img, 0, 0); URL.revokeObjectURL(img.src); c.toBlob(b=>b ? res(b) : rej(new Error("png")), "image/png"); };
    img.onerror = rej; img.src = URL.createObjectURL(blob); });
}
/* Rasmni buferga (boshqa chatga Ctrl+V bilan qo'yish mumkin); qurilma ruxsat bermasa — havolasi */
async function copyImage(url){
  try{
    if(!(navigator.clipboard && navigator.clipboard.write && window.ClipboardItem)) throw new Error("no");
    // Safari: blob Promise sifatida beriladi — foydalanuvchi harakati yo'qolmasin
    const png = fetch(url).then(r=>{ if(!r.ok) throw new Error("http"); return r.blob(); }).then(toPng);
    await navigator.clipboard.write([new ClipboardItem({ "image/png": png })]);
    toast("Rasm nusxalandi"); haptic("light");
  }catch(e){ copyText(absUrl(url), "Rasm havolasi nusxalandi"); }
}
function copyText(t, msg){
  const done = ()=>toast(msg || "Nusxa olindi");
  if(navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done, ()=>fallback());
  else fallback();
  function fallback(){ const a=document.createElement("textarea"); a.value=t; document.body.appendChild(a); a.select(); try{ document.execCommand("copy"); done(); }catch(e){} a.remove(); }
}
/* ---------- tanlash rejimi: bir nechta xabarni belgilab nusxa olish ---------- */
function startSelect(mid){
  SELM = new Set(); hidePanels(); MSGS.classList.add("selmode"); $("selbar").classList.remove("hide");
  document.querySelector("#selbar .seldelete").classList.remove("hide");
  if(mid) toggleSel(mid); else updSel(); updateBackBtn();
}
function endSelect(){
  SELM = null; MSGS.classList.remove("selmode"); $("selbar").classList.add("hide");
  MSGS.querySelectorAll(".mrow.picked").forEach(r=>r.classList.remove("picked")); updateBackBtn();
}
function toggleSel(mid){
  if(!SELM || !CH.msgs.has(mid)) return;
  SELM.has(mid) ? SELM.delete(mid) : SELM.add(mid); haptic("sel");
  const n = $("m"+mid); if(n) n.classList.toggle("picked", SELM.has(mid));
  if(!SELM.size) return endSelect();
  updSel();
}
function updSel(){ $("sel-n").textContent = T("{n} ta tanlandi", { n: SELM ? SELM.size : 0 }); }
function markPicked(){ if(SELM) SELM.forEach(mid=>{ const n = $("m"+mid); if(n) n.classList.add("picked"); }); }
function selContent(m){
  if(m.type==="text" || !m.type) return m.text || "";
  if(m.type==="location") return "📍 " + (m.text||"");
  const lbl = m.type==="document" ? "📄 " + (m.file_name || "Hujjat") : (CT_LBL[m.type] || "📎 Fayl");
  return lbl + (m.text && m.text!==m.file_name ? "\n" + m.text : "");
}
function copySel(){
  if(!SELM || !SELM.size) return;
  const list = CH.order.filter(mid=>SELM.has(mid)).map(mid=>CH.msgs.get(mid));
  const text = list.length===1 ? selContent(list[0])
    : list.map(m=>`${m.own ? T("Siz") : (CH.name || T("Mijoz"))}, [${(m.ts||"").slice(0,16)}]\n${selContent(m)}`).join("\n\n");
  copyText(text, T("{n} ta xabar nusxalandi", { n: list.length })); endSelect();
}
async function deleteSelected(){
  if(!SELM || !SELM.size) return;
  const own=[...SELM].filter(mid=>{ const m=CH&&CH.msgs.get(mid); return m&&m.own; });
  const skipped=SELM.size-own.length;
  if(!own.length){ alert2("Faqat operator yuborgan xabarlarni o'chirish mumkin"); return; }
  const note=skipped ? ` ${skipped} ta mijoz xabari o'chirilmaydi.` : "";
  if(!await confirm2(`${own.length} ta xabar mijoz chatidan ham o'chiriladi.${note} Davom etasizmi?`)) return;
  const r=await POST("/api/msg_delete_many",{mids:own}).catch(()=>null);
  if(!r||!r.ok){ alert2((r&&r.error)||"Xabarlar o'chirilmadi"); return; }
  (r.deleted||[]).forEach(mid=>{ const i=CH.order.indexOf(mid); if(i>=0) CH.order.splice(i,1); CH.msgs.delete(mid); });
  if(CH.pinned&&(r.deleted||[]).includes(CH.pinned.mid)){ CH.pinned=null; renderPinbar(); }
  endSelect(); renderTimeline({keep:true}); toast(r.info||"Xabarlar o'chirildi"); haptic("medium");
}

function jumpTo(mid){
  const n = $("m"+mid) || document.querySelector(`[data-view="${mid}"]`);
  const row = n && (n.classList.contains("mrow") ? n : n.closest(".mrow"));
  if(!row){ toast("Xabar eskiroq — yuqoriga aylantiring"); return; }
  row.scrollIntoView({ behavior:"smooth", block:"center" });
  row.classList.remove("hl"); void row.offsetWidth; row.classList.add("hl");
}
async function pinMsg(mid){
  const r = await POST("/api/pin", { order_id: CUR, mid }).catch(()=>null);
  if(!r || !r.ok){ toast((r&&r.error)||"Bajarilmadi"); return; }
  CH.pinned = mid ? CH.msgs.get(mid) : null; renderPinbar(); toast(mid ? "Xabar qadaldi" : "Qadash olib tashlandi");
}
function renderPinbar(){
  const p = CH.pinned; $("pinbar").classList.toggle("hide", !p);
  if(p) $("pin-text").textContent = msgPreview(p) || "Xabar";
}
function jumpPinned(){ if(CH.pinned) jumpTo(CH.pinned.mid); }
function unpin(e){ pinMsg(0); }
async function deleteMsg(mid){
  const m = CH.msgs.get(mid);
  if(!await confirm2(m && m.cmid ? "Xabar mijozda ham o'chiriladi. O'chirasizmi?"
                                  : "Bu xabar mijoz chatida topilmadi — faqat yozishmadan o'chiriladi. O'chirasizmi?")) return;
  const r = await POST("/api/msg_del", { mid }).catch(()=>null);
  if(!r || !r.ok){ alert2((r&&r.error)||"O'chirilmadi"); return; }
  toast(r.info || "O'chirildi"); haptic("medium");
  const i = CH.order.indexOf(mid); if(i>=0) CH.order.splice(i,1); CH.msgs.delete(mid);
  if(CH.pinned && CH.pinned.mid===mid){ CH.pinned=null; renderPinbar(); }
  const n = $("m"+mid); if(n){ n.style.transition="opacity .2s, transform .2s"; n.style.opacity=0; n.style.transform="scale(.9)"; setTimeout(()=>renderTimeline({keep:true}), 200); }
}

/* ---------- javob / tahrir paneli ---------- */
function setReply(mid){
  const m = CH.msgs.get(mid); if(!m || CH.status==="done" || CH.status==="canceled") return;
  if(CH.editMid) cancelEdit();
  CH.replyTo = mid;
  $("rb-title").textContent = "Javob: " + (m.own ? "Siz" : (CH.name||"Mijoz"));
  $("rb-text").textContent = msgPreview(m) || "Xabar";
  $("rb-ic").innerHTML = '<path d="M9 17l-5-5 5-5M4 12h12a4 4 0 0 1 4 4v4"/>';
  $("replybar").classList.remove("hide"); haptic("light"); CMP.focus();
}
function clearReply(silent){
  if(CH && CH.editMid){ cancelEdit(); return; }
  if(CH) CH.replyTo = null; $("replybar").classList.add("hide");
}
function startEdit(mid){
  const m = CH.msgs.get(mid); if(!m) return;
  CH.replyTo = null; CH.editMid = mid; CH._draftBeforeEdit = CMP.getHTML();
  $("rb-title").textContent = "Tahrirlash"; $("rb-text").textContent = m.text;
  $("rb-ic").innerHTML = '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.1 2.1 0 0 1 3 3L12 15l-4 1 1-4z"/>';
  $("replybar").classList.remove("hide");
  if(m.html) CMP.setHTML(m.html); else CMP.setText(m.text);
}
function cancelEdit(){
  CH.editMid = null; $("replybar").classList.add("hide");
  const d = CH._draftBeforeEdit || ""; d ? CMP.setHTML(d) : CMP.clear();
}

/* ---------- holat panellari ---------- */
let CURFF = "";
function applyFulfill(kind){ CURFF = kind||""; $("ff-delivery").classList.toggle("on", CURFF==="delivery"); $("ff-pickup").classList.toggle("on", CURFF==="pickup"); }
async function fulfill(el){
  const kind = el.dataset.k, prev = CURFF, next = CURFF===kind ? "" : kind;
  applyFulfill(next); haptic("sel");
  const r = await POST("/api/cmd", { order_id: CUR, cmd: "fulfillment", arg: next }).catch(()=>null);
  if(!r || !r.ok){ applyFulfill(prev); toast("Saqlanmadi, qaytadan urinib ko'ring"); return; }
  applyFulfill(r.fulfillment||"");
}
function applyChatStatus(st){
  const closed = st==="done" || st==="canceled";
  $("composer").classList.toggle("hide", closed);
  $("resumebar").classList.toggle("hide", !closed);
  $("fulfillbar").classList.toggle("hide", false);
  if(closed){ $("resume-lbl").textContent = st==="canceled" ? "Bu murojaat bekor qilingan" : "Bu murojaat yakunlangan"; hidePanels(); $("replybar").classList.add("hide"); if(recActive()) finishRec(false); }
}
async function resume(){
  const r = await POST("/api/reopen", { order_id: CUR }).catch(()=>null);
  if(!r || !r.ok){ alert2((r&&r.error)||"Ochilmadi"); return; }
  applyChatStatus("in_progress"); CH.status="in_progress"; updateSub(); kickSync(); CMP.focus();
}
function renderTagsbar(){
  const t = CH.tags||[]; $("tagsbar").classList.toggle("hide", !t.length);
  $("tagsbar").innerHTML = t.map(x=>`<span class="chip">#${esc(x)}</span>`).join("") + `<span class="chip" style="background:none;color:var(--hint)">✎</span>`;
}

/* ---------- yozuv maydoni (formatlash bilan) ---------- */
let _typT = 0, _draftT = null;
const CMP = TGF.Composer($("ed"), {
  placeholder: T("Xabar"),
  onEnter: ()=>{ if(cmdOpen() && cmdRunSelected()) return; send(); },
  touchEnterNewline: true,
  onInput: (c)=>{
    const has = !c.isEmpty();
    $("sendbtn").classList.toggle("hide", !has && !CH?.editMid);
    $("mic").classList.toggle("hide", has || !!CH?.editMid);
    updateCmd(c.getText());
    if(has && CUR && Date.now() - _typT > 4500 && !CH?.editMid){ _typT = Date.now(); POST("/api/typing", { order_id: CUR, shared:CH.shared?1:0 }).catch(()=>{}); }
    clearTimeout(_draftT); _draftT = setTimeout(saveDraftNow, 900);
  },
  onKey: (e, c)=>{
    if(cmdOpen() && (e.key==="ArrowUp" || e.key==="ArrowDown")){ e.preventDefault(); cmdMove(e.key==="ArrowUp" ? -1 : 1); return; }
    if(cmdOpen() && e.key==="Tab"){ e.preventDefault(); const x=CMDLIST[CMDSEL]; if(x){ if(x.kind==="br" || BRANCH_CMDS.includes(x.id)) pickCmdItem(x); else c.setText(x.c); } return; }
    if(e.key==="Escape" && BRMODE){ e.preventDefault(); e.stopPropagation(); BRMODE = null; c.clear(); hidePanels(); return; }
    if(e.key==="ArrowUp" && c.isEmpty() && CH && !CH.editMid){
      const last = [...CH.order].reverse().map(i=>CH.msgs.get(i)).find(m=>m.own && m.cmid && m.type==="text" && !String(m.text).startsWith("👨‍💼"));
      if(last){ e.preventDefault(); startEdit(last.mid); }
    }
    if(e.key==="Escape" && CH && (CH.replyTo || CH.editMid)){ e.preventDefault(); e.stopPropagation(); clearReply(); }
  },
  onPasteImage: async f=>{ if(!CUR) return; openMedia([await compressImage(f,1600,.8)]); },
  onDropFiles: files=>handleFiles(files),
});
let _lastDraft = {};
function saveDraftNow(){
  if(!CUR || !CH || CH.editMid || !CH.draftReady) return;
  const h = CMP.isEmpty() ? "" : CMP.getHTML();
  if(_lastDraft[CUR] === h) return; _lastDraft[CUR] = h;
  const c = ST.chatMap[CUR]; if(c) c.draft = h;
  POST("/api/chat_state", { order_id: CUR, draft: h, shared:CH.shared?1:0 }).catch(()=>{});
}
$("chat").addEventListener("dragover", e=>{ if(CUR) e.preventDefault(); });
$("chat").addEventListener("drop", e=>{ if(!CUR || !e.dataTransfer.files.length) return; e.preventDefault(); handleFiles(e.dataTransfer.files); });
async function handleFiles(files){
  const imgs = [...files].filter(f=>f.type.startsWith("image/")).slice(0,10);
  const rest = [...files].filter(f=>!f.type.startsWith("image/"));
  if(imgs.length){ const d=[]; for(const f of imgs) d.push(await compressImage(f,1600,.8)); openMedia(d); }
  for(const f of rest) await sendDocFile(f);
}

/* ---------- yuborish (navbat bilan, internet uzilsa — keyin yuboriladi) ---------- */
let pendingBill = false;
function exitBill(){ pendingBill=false; CMP.setPlaceholder(T("Xabar")); }
const QKEY = () => "pq_" + (ST.op.id||"");
function loadQueue(){ try{ return JSON.parse(LS.get(QKEY())||"[]"); }catch(e){ return []; } }
function saveQueue(q){ LS.set(QKEY(), JSON.stringify(q)); }
function loadPendingFromQueue(){ if(!CH) return; loadQueue().filter(p=>p.order_id===CUR).forEach(p=>{ if(!CH.pending.find(x=>x.lid===p.lid)) CH.pending.push(Object.assign({}, p, {state:"queued"})); }); }
async function send(){
  if(recActive() || !CUR) return;
  if(CMP.isEmpty()) return;
  const html = CMP.getHTML(), text = TGF.toPlain(html).trim();
  if(!text) return;
  // Filial buyrug'i matni hech qachon mijozga oddiy xabar bo'lib ketmasin
  const bc = brCmdOf(text);
  if(bc){
    await loadBranches();
    const cur = CMDLIST[CMDSEL], f = filterBranches(bc.q);
    const b = cur && cur.kind==="br" ? cur.b : f[0];
    BRMODE = null; CMP.clear(); hidePanels();
    if(b) runBranchCmd(bc.cm.id, b); else alert2("Filial topilmadi");
    return;
  }
  if(/^\/\S*$/.test(text)){
    const f = findCmds(text);
    CMP.clear(); hidePanels();
    if(f.length) runCmd(f[0].c); else alert2("Bunday buyruq yo'q. Ro'yxat uchun / yozing");
    return;
  }
  if(CH.editMid){
    const mid = CH.editMid; CH.editMid = null; CH._draftBeforeEdit = ""; $("replybar").classList.add("hide"); CMP.clear();
    const r = await POST("/api/msg_edit", { mid, html, text }).catch(()=>null);
    if(!r || !r.ok){ alert2((r&&r.error)||"Tahrirlanmadi"); return; }
    const m = CH.msgs.get(mid); if(m){ m.text = text; m.html = TGF.hasMarkup(html) ? html : ""; m.edited = true; const n=$("m"+mid); if(n) n.outerHTML = rowHtml(m, prevOf(mid), nextOf(mid), false); }
    return;
  }
  if(pendingBill){
    exitBill(); CMP.clear();
    const r = await POST("/api/cmd", { order_id: CUR, cmd: "bill", arg: text }).catch(()=>null);
    toast(r && r.ok ? r.info : ((r&&r.error)||"Xatolik")); kickSync(); return;
  }
  const p = { lid: Date.now().toString(36)+Math.random().toString(36).slice(2,6), order_id: CUR, shared:!!CH.shared, html, text,
              reply_mid: CH.replyTo || 0, time: new Date().toTimeString().slice(0,5), state: "sending" };
  CMP.clear(); clearReply(); hidePanels();
  _lastDraft[CUR] = ""; const c = ST.chatMap[CUR]; if(c) c.draft = "";
  CH.pending.push(p);
  MSGS.insertAdjacentHTML("beforeend", pendingHtml(p)); toBottom();
  haptic("light");
  await doSend(p);
}
async function doSend(p){
  let r;
  try{ r = await POST("/api/send", { order_id: p.order_id, shared:p.shared?1:0, html: p.html, text: p.text, reply_mid: p.reply_mid }); }
  catch(e){
    // internet yo'q — navbatda qoladi
    p.state = "queued"; const q = loadQueue(); if(!q.find(x=>x.lid===p.lid)){ q.push(p); saveQueue(q); }
    setConn(false); return;
  }
  const q = loadQueue().filter(x=>x.lid!==p.lid); saveQueue(q);
  if(!r.ok){
    p.state = "failed"; p.err = r.error;
    if(CH && CH.oid===p.order_id){ const n=$("p"+p.lid); if(n) n.outerHTML = pendingHtml(p); }
    toast(r.error || "Yuborilmadi"); return;
  }
  if(CH && CH.oid===p.order_id){
    CH.pending = CH.pending.filter(x=>x.lid!==p.lid);
    const n = $("p"+p.lid);
    if(r.message && !CH.msgs.has(r.message.mid)){
      addMsg(r.message);
      const pv = prevOf(r.message.mid);
      if(pv && pv.type==="photo"){ renderTimeline({ keep: true }); return; }
      if(n){ const prev = prevOf(r.message.mid); n.outerHTML = rowHtml(r.message, prev, null, false);
        if(prev){ const pn=$("m"+prev.mid); if(pn) pn.outerHTML = rowHtml(prev, prevOf(prev.mid), r.message, false); } }
    } else if(n) n.remove();
  }
}
let _flushing = false;
async function flushQueue(){
  if(_flushing) return; const q = loadQueue(); if(!q.length) return;
  _flushing = true;
  for(const p of q){
    if(CH && CH.oid===p.order_id){ const ex = CH.pending.find(x=>x.lid===p.lid); if(ex){ ex.state="sending"; await doSend(ex); continue; } }
    await doSend(p);
  }
  _flushing = false;
}
window.addEventListener("online", ()=>{ kickSync(); flushQueue(); });
function pendingMenu(lid, x, y){
  const p = CH.pending.find(z=>z.lid===lid); if(!p) return;
  TGF.menu(x, y, [
    {header: p.err || "Yuborilmadi"},
    {label:"Qayta yuborish", icon:"<svg viewBox='0 0 24 24'><path d='M21 12a9 9 0 1 1-2.6-6.4M21 4v5h-5'/></svg>", onClick:()=>{ p.state="sending"; const n=$("p"+lid); if(n) n.outerHTML=pendingHtml(p); doSend(p); }},
    {label:"O'chirish", danger:true, icon:"<svg viewBox='0 0 24 24'><path d='M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6'/></svg>", onClick:()=>{ CH.pending=CH.pending.filter(z=>z.lid!==lid); saveQueue(loadQueue().filter(z=>z.lid!==lid)); const n=$("p"+lid); if(n) n.remove(); }},
  ]);
}

/* ---------- buyruqlar ( / ) ---------- */
// Buyruqlar tanlangan tilda ko'rinadi; ikkala tildagi nomi ham ishlayveradi
const CMDS=[
  {id:"autoclose",  uz:"/10daqiqa",        ru:"/10минут",         d:"10 daqiqada avto-yakunlash"},
  {id:"askbranch",  uz:"/filialtanlatish", ru:"/выбор_филиала",   d:"Mijozga filial tanlatish"},
  {id:"sendbranch", uz:"/filialmalumoti",  ru:"/инфо_филиала",    d:"Filial ma'lumotini yuborish"},
  {id:"bill",       uz:"/hisoblash",       ru:"/счёт",            d:"Hisob-kitob yuborish"},
  {id:"changebranch", uz:"/filialalmashtirish", ru:"/сменить_филиал", d:"Filialni almashtirish (mijozga yuboriladi)"},
].map(x=>Object.assign(x, { c: LANG==="ru" ? x.ru : x.uz }));
function findCmds(v){ v = (v||"").toLowerCase(); return CMDS.filter(x=>x.c.startsWith(v) || x.uz.startsWith(v) || x.ru.startsWith(v)); }
let CMDSEL = -1, CMDLIST = [];
/* Filiallar (bir marta yuklanadi) + qidiruv: lotin/kirill, apostrof va so'z tartibi farq qilmaydi */
let BRANCHES = null;
async function loadBranches(force){
  if(BRANCHES && !force) return BRANCHES;
  const r = await GET("/api/branches").catch(()=>null); if(r && r.ok) BRANCHES = r.branches;
  return BRANCHES || [];
}
const _CYR = {"а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"yo","ж":"j","з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"x","ц":"ts","ч":"ch","ш":"sh","щ":"sh","ъ":"","ы":"i","ь":"","э":"e","ю":"yu","я":"ya","ў":"o","қ":"q","ғ":"g","ҳ":"h"};
function normQ(s){ return (s||"").toLowerCase().replace(/[\u0400-\u04ff]/g, c=>(c in _CYR ? _CYR[c] : c)).replace(/[ʻʼ'`’‘"]/g,"").replace(/\s+/g," ").trim(); }
function filterBranches(q){
  const list = BRANCHES || [], nq = normQ(q); if(!nq) return list.slice();
  const words = nq.split(" "), out = [];
  list.forEach(b=>{ const n = normQ(b.name), full = n + " " + normQ(b.address);
    if(!words.every(w=>full.includes(w))) return;
    out.push([n.startsWith(nq) ? 0 : n.includes(nq) ? 1 : words.every(w=>n.includes(w)) ? 2 : 3, b]); });
  return out.sort((a,b)=>a[0]-b[0]).map(x=>x[1]);
}
const BRANCH_CMDS = ["sendbranch","changebranch"];
let BRMODE = null;   // filial buyrug'i tanlangan: yozilgan matn filial qidiruvi bo'ladi
function cmdByName(n){ n = (n||"").toLowerCase(); return CMDS.find(x=>[x.c,x.uz,x.ru].some(c=>c.toLowerCase()===n)); }
function brCmdOf(v){   // "/filialmalumoti bosh ofis" -> { cm, q: "bosh ofis" }
  const m = /^(\/\S+)(?:\s+([\s\S]*))?$/.exec((v||"").trim()); if(!m) return null;
  const cm = cmdByName(m[1]); if(!cm || !BRANCH_CMDS.includes(cm.id)) return null;
  if(!m[2] && BRMODE !== cm) return null;   // faqat buyruq nomi — hali buyruqlar ro'yxati
  return { cm, q: m[2] || "" };
}
function cmdOpen(){ return !$("cmdpanel").classList.contains("hide") && CMDLIST.length > 0; }
function cmdHighlight(){
  $("cmdpanel").querySelectorAll("[data-ci]").forEach(el=>el.classList.toggle("sel", +el.dataset.ci===CMDSEL));
  const s = $("cmdpanel").querySelector(".qr.sel"); if(s && s.scrollIntoView) s.scrollIntoView({block:"nearest"});
}
function cmdMove(d){ if(!CMDLIST.length) return; CMDSEL = (CMDSEL + d + CMDLIST.length) % CMDLIST.length; cmdHighlight(); haptic("sel"); }
function cmdRunSelected(){ const x = CMDLIST[CMDSEL]; if(!x) return false; pickCmdItem(x); return true; }
function pickCmdItem(x){
  if(x.kind==="br"){ BRMODE = null; CMP.clear(); hidePanels(); runBranchCmd(x.cm.id, x.b); return; }
  if(BRANCH_CMDS.includes(x.id)){   // filial buyrug'i: ro'yxat chiqadi, yozib qidiriladi
    BRMODE = x; CMP.setText(x.c + " "); haptic("sel"); return;
  }
  BRMODE = null; CMP.clear(); hidePanels(); runCmd(x.c);
}
const PIN_IC = '<svg class="ic" viewBox="0 0 24 24"><path d="M12 21s-7-6-7-11a7 7 0 0 1 14 0c0 5-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>';
function branchRowsHtml(list, sel, attr){
  return list.map((b,i)=>`<div class="qr${i===sel?" sel":""}" ${attr}="${i}" data-ci="${i}">${PIN_IC}
    <div style="min-width:0;flex:1"><div class="cmd brn">${esc(b.name)}</div>${b.address?`<div class="d">${esc(b.address)}</div>`:""}</div>
    ${CH && b.id===CH.branchId ? `<span class="d">✓ ${esc(T("hozirgi"))}</span>` : ""}</div>`).join("");
}
function updateCmd(v){
  const p = $("cmdpanel"); v = v || "";
  const bc = brCmdOf(v);
  if(bc){
    BRMODE = bc.cm;
    if(!BRANCHES){ CMDLIST = []; p.innerHTML = '<div class="spinner"></div>'; p.classList.remove("hide");
      loadBranches().then(()=>{ if(BRMODE) updateCmd(CMP.getText()); }); return; }
    const f = filterBranches(bc.q);
    const prev = CMDLIST[CMDSEL] && CMDLIST[CMDSEL].b ? CMDLIST[CMDSEL].b.id : null;
    CMDLIST = f.map(b=>({ kind:"br", b, cm: bc.cm }));
    const pi = CMDLIST.findIndex(x=>x.b.id===prev); CMDSEL = CMDLIST.length ? (pi >= 0 ? pi : 0) : -1;
    p.innerHTML = `<div class="phint">${esc(T(bc.cm.d))} — ${esc(T("filial nomini yozing · ↑↓ tanlash · Enter"))}</div>` +
      (f.length ? branchRowsHtml(f, CMDSEL, "data-bri") : `<div class="empty" style="padding:16px">${esc(T("Filial topilmadi"))}</div>`);
    p.classList.remove("hide"); cmdHighlight(); return;
  }
  BRMODE = null;
  const lv = v.toLowerCase();
  if(/^\/\S*$/.test(lv)){
    const f = findCmds(lv);
    const prevC = CMDLIST[CMDSEL] && CMDLIST[CMDSEL].c;
    CMDLIST = f;
    // Telegramdek: boshida eng pastdagisi tanlangan
    CMDSEL = f.length ? Math.max(0, f.findIndex(x=>x.c===prevC) >= 0 ? f.findIndex(x=>x.c===prevC) : f.length - 1) : -1;
    if(f.length){ p.innerHTML = f.map((x,i)=>`<div class="qr${i===CMDSEL?" sel":""}" data-cmd="${esc(x.c)}" data-ci="${i}"><svg class="ic" viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h10"/></svg><div><div class="cmd">${esc(x.c)}</div><div class="d">${esc(T(x.d))}</div></div></div>`).join(""); p.classList.remove("hide"); return; }
  }
  p.classList.add("hide"); CMDLIST = []; CMDSEL = -1;
}
$("cmdpanel").addEventListener("mousemove", e=>{ const q=e.target.closest("[data-ci]"); if(q && +q.dataset.ci!==CMDSEL){ CMDSEL=+q.dataset.ci; cmdHighlight(); } });
$("cmdpanel").addEventListener("mousedown", e=>{ if(e.target.closest("[data-ci]")) e.preventDefault(); });   // klaviatura yopilmasin
$("cmdpanel").addEventListener("click", e=>{ const q=e.target.closest("[data-ci]"); if(q && CMDLIST[+q.dataset.ci]) pickCmdItem(CMDLIST[+q.dataset.ci]); });
async function runCmd(c){
  const cm = cmdByName(c); const id = cm ? cm.id : "";
  if(id==="autoclose"){ const r=await POST("/api/cmd",{order_id:CUR,cmd:"autoclose"}).catch(()=>null); toast(r&&r.ok?r.info:((r&&r.error)||"Xatolik")); }
  else if(id==="askbranch"){ const r=await POST("/api/cmd",{order_id:CUR,cmd:"askbranch"}).catch(()=>null); toast(r&&r.ok?r.info:((r&&r.error)||"Xatolik")); }
  else if(BRANCH_CMDS.includes(id)){ openBranchPicker(id); }
  else if(id==="bill"){ pendingBill=true; CMP.setPlaceholder(T("Hisob-kitob: matn yozing yoki rasm/ovoz/stiker yuboring")); CMP.focus(); toast("Hisob-kitob rejimi"); }
}
async function runBranchCmd(id, b){
  if(!CUR || !b) return;
  if(id==="changebranch" && !await confirm2(T("Filial «{n}» qilib almashtirilsinmi? Mijozga filial ma'lumoti yuboriladi.", {n: b.name}))) return;
  const r = await POST("/api/cmd", { order_id: CUR, cmd: id, arg: b.id }).catch(()=>null);
  toast(r && r.ok ? r.info : ((r && r.error) || "Xatolik"), 2600);
  if(r && r.ok && id==="changebranch" && CH){ CH.branch = r.branch; CH.branchId = r.branch_id; updateSub(); }
  if(r && r.ok) haptic("medium");
  kickSync();
}
/* Filial tanlash oynasi: qidiruv + ↑↓ + Enter (biriktirish/menyu orqali) */
async function openBranchPicker(id){
  if(!CUR) return;
  await loadBranches(true);
  openSheet(`<h3>${esc(T(id==="changebranch" ? "Filialni almashtirish" : "Filial ma'lumotini yuborish"))}</h3>
    ${id==="changebranch" ? `<div class="phint" style="margin:0 16px 8px">${esc(T("Tanlangan filial murojaat va mijoz profiliga yoziladi, mijozga filial kartasi yuboriladi."))}</div>` : ""}
    <div class="searchbox" style="padding:0 16px 8px"><div class="in"><svg class="ic" viewBox="0 0 24 24" style="width:19px;height:19px;color:var(--hint)"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
      <input id="br-q" placeholder="${esc(T("Filial nomi yoki manzili"))}" autocomplete="off"></div></div>
    <div id="br-list" class="brlist"></div>`,
    el=>{
      const inp = $("br-q"); let sel = 0, list = [];
      const draw = ()=>{
        list = filterBranches(inp.value); sel = Math.max(0, Math.min(sel, list.length - 1));
        $("br-list").innerHTML = list.length ? branchRowsHtml(list, sel, "data-bi")
          : `<div class="empty" style="padding:22px">${esc(T("Filial topilmadi"))}</div>`;
        const s = $("br-list").querySelector(".qr.sel"); if(s) s.scrollIntoView({ block: "nearest" });
      };
      const pick = i=>{ const b = list[i]; if(!b) return; closeSheet(); runBranchCmd(id, b); };
      inp.oninput = ()=>{ sel = 0; draw(); };
      inp.onkeydown = e=>{
        if(e.key==="ArrowDown" || e.key==="ArrowUp"){ e.preventDefault(); if(list.length){ sel = (sel + (e.key==="ArrowDown" ? 1 : -1) + list.length) % list.length; draw(); haptic("sel"); } }
        else if(e.key==="Enter"){ e.preventDefault(); pick(sel); }
      };
      el.addEventListener("mousemove", e=>{ const it = e.target.closest("[data-bi]"); if(it && +it.dataset.bi!==sel){ sel = +it.dataset.bi; $("br-list").querySelectorAll("[data-bi]").forEach(x=>x.classList.toggle("sel", +x.dataset.bi===sel)); } });
      el.addEventListener("click", e=>{ const it = e.target.closest("[data-bi]"); if(it) pick(+it.dataset.bi); });
      draw(); setTimeout(()=>{ if(!isTouch()) inp.focus(); }, 120);
    });
}

/* ---------- panellar: tayyor javoblar / stikerlar ---------- */
function hidePanels(){ ["cmdpanel","quickpanel","stickerpanel"].forEach(i=>$(i).classList.add("hide")); updateBackBtn(); }
let TPLS = null;
async function loadTpls(){ const r = await GET("/api/templates").catch(()=>null); TPLS = r && r.ok ? r.items : []; return TPLS; }
async function toggleQuick(){
  const p = $("quickpanel"); const was = !p.classList.contains("hide"); hidePanels(); if(was) return;
  await loadTpls();
  p.innerHTML = `<div class="phint">${esc(T("Bosing — maydonga qo'yiladi · ➤ — darhol yuboriladi ·"))} <b>{ism}</b> <b>{filial}</b> <b>{operator}</b> ${esc(T("o'zgaruvchilari ishlaydi"))}</div>` +
    TPLS.map(t=>`<div class="qr" data-tpl="${t.id}"><svg class="ic" viewBox="0 0 24 24"><path d="M13 2L3 14h7l-1 8 10-12h-7z"/></svg>
      <div class="tx">${t.own?'<span class="own">MENIKI</span>':""}${esc(t.text)}</div>
      ${t.own?`<button class="mini" data-tdel="${t.id}" title="O'chirish"><svg class="ic" viewBox="0 0 24 24" style="width:16px;height:16px"><path d="M18 6L6 18M6 6l12 12"/></svg></button>`:""}
      <button class="mini" data-tsend="${t.id}" title="Darhol yuborish"><svg class="ic" viewBox="0 0 24 24" style="width:17px;height:17px"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg></button></div>`).join("") +
    `<div class="qr" data-tadd="1" style="color:var(--accent)"><svg class="ic" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg><div class="tx" style="color:var(--accent);font-weight:600">Yangi shablon qo'shish</div></div>`;
  p.classList.remove("hide");
}
$("quickpanel").addEventListener("click", async e=>{
  const del = e.target.closest("[data-tdel]"), snd = e.target.closest("[data-tsend]"), add = e.target.closest("[data-tadd]"), row = e.target.closest("[data-tpl]");
  if(add) return addTpl(()=>toggleQuick().then(()=>toggleQuick()));
  if(del){ e.stopPropagation(); if(!await confirm2("Shablon o'chirilsinmi?")) return; await POST("/api/tpl_del",{id:+del.dataset.tdel}); hidePanels(); toggleQuick(); return; }
  const t = TPLS && TPLS.find(x=>x.id===+(snd||row||{}).dataset?.[snd?"tsend":"tpl"]);
  if(!t) return;
  hidePanels();
  if(snd){ CMP.setText(t.text); send(); }
  else { CMP.setText(t.text); CMP.focusEnd(); }
});
function addTpl(after){
  TGF.prompt("Yangi tayyor javob", [{ph:"Matn: Assalomu alaykum, {ism}!"}], async ([t])=>{
    if(!t) return; const r = await POST("/api/tpl_add",{text:t}).catch(()=>null);
    toast(r && r.ok ? "Shablon qo'shildi" : ((r&&r.error)||"Xatolik")); after && after();
  });
}
async function openMyTpls(){
  await loadTpls();
  const mine = TPLS.filter(t=>t.own);
  openSheet(`<h3>Tayyor javoblarim</h3><div class="phint" style="margin:0 0 6px">${esc(T("Chatda ⚡ tugmasi orqali ishlatiladi."))} <b>{ism}</b>, <b>{filial}</b>, <b>{operator}</b>, <b>{telefon}</b> ${esc(T("— avtomatik almashtiriladi."))}</div>` +
    (mine.map(t=>`<div class="item"><div class="lbl" style="white-space:pre-wrap">${esc(t.text)}</div><button class="iconbtn" data-mdel="${t.id}"><svg class="ic" viewBox="0 0 24 24" style="color:var(--red)"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/></svg></button></div>`).join("") || `<div class="empty" style="padding:24px">Hali shaxsiy shablon yo'q</div>`) +
    `<button class="sbtn" data-madd>+ Shablon qo'shish</button>`,
    el=>el.addEventListener("click", async e=>{
      if(e.target.closest("[data-madd]")) return addTpl(openMyTpls);
      const d = e.target.closest("[data-mdel]"); if(d){ await POST("/api/tpl_del",{id:+d.dataset.mdel}); openMyTpls(); }
    }));
}
async function toggleStickers(){
  const p = $("stickerpanel"); const was = !p.classList.contains("hide"); hidePanels(); if(was) return;
  const r = await GET("/api/stickers").catch(()=>null);
  if(!r || !r.ok || !r.items.length){ toast("Stiker yo'q. Admin panel → Tayyor javoblar → stiker qo'shing."); return; }
  p.innerHTML = r.items.map(s=>`<img class="stk" loading="lazy" data-stk="${s.id}" src="${esc(fileUrl(s.file_id,"sticker"))}">`).join("");
  p.classList.remove("hide");
}
$("stickerpanel").addEventListener("click", async e=>{
  const s = e.target.closest("[data-stk]"); if(!s) return; hidePanels(); const id = +s.dataset.stk;
  if(pendingBill){ exitBill(); const r=await POST("/api/cmd",{order_id:CUR,cmd:"bill",sticker_id:id}).catch(()=>null); toast(r&&r.ok?r.info:((r&&r.error)||"Xatolik")); kickSync(); return; }
  const r = await POST("/api/send_sticker",{order_id:CUR,sticker_id:id,shared:CH.shared?1:0}).catch(()=>null);
  if(!r || !r.ok){ toast((r&&r.error)||"Yuborilmadi"); return; } kickSync();
});

/* ---------- biriktirish ---------- */
function attach(){
  openSheet(`<h3>Biriktirish</h3>
    <div class="item" data-att="photo"><svg class="ic ic-blue" viewBox="0 0 24 24" style="width:34px;height:34px;padding:7px;border-radius:50%;color:#fff"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="9" cy="9" r="2"/><path d="M21 15l-5-5L5 21"/></svg><div class="lbl">Rasm<div class="sub">Bir nechta tanlash mumkin — har biri alohida yuboriladi</div></div></div>
    <div class="item" data-att="doc"><svg class="ic ic-violet" viewBox="0 0 24 24" style="width:34px;height:34px;padding:7px;border-radius:50%;color:#fff"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg><div class="lbl">Fayl / PDF<div class="sub">Hujjat, PDF, video (maks 15 MB)</div></div></div>
    <div class="item" data-att="tpl"><svg class="ic ic-orange" viewBox="0 0 24 24" style="width:34px;height:34px;padding:7px;border-radius:50%;color:#fff"><path d="M13 2L3 14h7l-1 8 10-12h-7z"/></svg><div class="lbl">Tayyor javob</div></div>
    <div class="item" data-att="branch"><svg class="ic ic-green" viewBox="0 0 24 24" style="width:34px;height:34px;padding:7px;border-radius:50%;color:#fff"><path d="M12 21s-7-6-7-11a7 7 0 0 1 14 0c0 5-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/></svg><div class="lbl">Filial ma'lumoti</div></div>
    <div class="item" data-att="chbranch"><svg class="ic ic-orange" viewBox="0 0 24 24" style="width:34px;height:34px;padding:7px;border-radius:50%;color:#fff"><path d="M17 1l4 4-4 4M3 11V9a4 4 0 0 1 4-4h14M7 23l-4-4 4-4M21 13v2a4 4 0 0 1-4 4H3"/></svg><div class="lbl">Filialni almashtirish<div class="sub">Operator tanlaydi — mijozga yuboriladi</div></div></div>
    <div class="item" data-att="cat"><svg class="ic ic-pink" viewBox="0 0 24 24" style="width:34px;height:34px;padding:7px;border-radius:50%;color:#fff"><path d="M10.5 20.5l10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7zM8.5 8.5l7 7"/></svg><div class="lbl">Dori katalogi<div class="sub">Narx va mavjudlik · kelganda xabar berish</div></div></div>
    <div class="item" data-att="bill"><svg class="ic ic-teal" viewBox="0 0 24 24" style="width:34px;height:34px;padding:7px;border-radius:50%;color:#fff"><path d="M6 2h12v20l-3-2-3 2-3-2-3 2zM9 7h6M9 11h6M9 15h4"/></svg><div class="lbl">Hisob-kitob<div class="sub">Ro'yxat × soni = jami, chiroyli karta</div></div></div>
    <div class="item" data-att="billtext"><svg class="ic ic-gray" viewBox="0 0 24 24" style="width:34px;height:34px;padding:7px;border-radius:50%;color:#fff"><path d="M4 6h16M4 12h16M4 18h10"/></svg><div class="lbl">Hisob-kitob (erkin matn / rasm / ovoz)</div></div>`,
    el=>el.addEventListener("click", e=>{ const a=e.target.closest("[data-att]"); if(!a) return; closeSheet();
      ({photo:()=>$("file-photo").click(), doc:()=>$("file-doc").click(), tpl:toggleQuick, branch:()=>openBranchPicker("sendbranch"), chbranch:()=>openBranchPicker("changebranch"), cat:()=>openCatalog(), bill:openBill, billtext:()=>runCmd(CMDS.find(x=>x.id==="bill").c)})[a.dataset.att](); }));
}
function compressImage(file, maxDim, quality){
  return new Promise(res=>{ const rd=new FileReader();
    rd.onload=()=>{ const img=new Image();
      img.onload=()=>{ let w=img.width,h=img.height; if(w>maxDim||h>maxDim){ if(w>=h){ h=Math.round(h*maxDim/w); w=maxDim; } else { w=Math.round(w*maxDim/h); h=maxDim; } }
        const c=document.createElement("canvas"); c.width=w; c.height=h; c.getContext("2d").drawImage(img,0,0,w,h);
        try{ res(c.toDataURL("image/jpeg",quality)); }catch(e){ res(rd.result); } };
      img.onerror=()=>res(rd.result); img.src=rd.result; };
    rd.readAsDataURL(file); });
}
$("file-photo").onchange = async function(){
  const files=[...this.files].slice(0,10); this.value=""; if(!files.length||!CUR) return;
  const d=[]; for(const f of files) d.push(await compressImage(f,1600,.8)); openMedia(d);
};
$("file-doc").onchange = function(){ const f=this.files[0]; this.value=""; if(f && CUR) sendDocFile(f); };
function sendDocFile(f){
  return new Promise(res=>{
    if(f.size > 15*1024*1024){ alert2("Fayl juda katta (maks 15 MB)"); return res(); }
    const rep = CH.replyTo || 0; clearReply();
    toast("Yuborilmoqda: " + f.name, 4000);
    const rd = new FileReader();
    rd.onload = async()=>{
      const r = await POST("/api/send", { order_id: CUR, shared:CH.shared?1:0, media_kind: "document", media_name: f.name, media_mime: f.type||"", media_data: rd.result, reply_mid: rep }).catch(()=>null);
      if(!r || !r.ok) alert2((r&&r.error)||"Yuborilmadi"); else { toast("Yuborildi ✓"); kickSync(); }
      res();
    };
    rd.readAsDataURL(f);
  });
}
/* rasm(lar) oldindan ko'rish + izoh (formatlash bilan) */
let pendingMedia = null;
const MMC = TGF.Composer($("mm-cap"), { placeholder: T("Izoh qo'shing..."), onEnter: ()=>sendMedia() });
function openMedia(datas){
  pendingMedia = datas; MMC.clear();
  $("mm-title").textContent = datas.length>1 ? datas.length+" ta rasm" : "Rasm yuborish";
  $("mm-stage").innerHTML = datas.map(d=>`<img src="${d}" style="max-width:${datas.length>1?"46%":"100%"};max-height:${datas.length>1?"40vh":"100%"};border-radius:12px;object-fit:contain">`).join("");
  $("mediamodal").classList.remove("hide"); updateBackBtn();
  if(!isTouch()) setTimeout(()=>MMC.focus(), 100);
}
function closeMedia(){ pendingMedia=null; $("mediamodal").classList.add("hide"); updateBackBtn(); }
async function sendMedia(){
  if(!pendingMedia || !CUR) return;
  const capH = MMC.isEmpty() ? "" : MMC.getHTML(), cap = TGF.toPlain(capH).trim(), datas = pendingMedia; closeMedia();
  if(pendingBill){ exitBill(); const r=await POST("/api/cmd",{order_id:CUR,cmd:"bill",arg:cap,media_kind:"photo",media_data:datas[0]}).catch(()=>null); toast(r&&r.ok?r.info:((r&&r.error)||"Xatolik")); kickSync(); return; }
  const rep = CH.replyTo||0; clearReply();
  toast(datas.length>1 ? `${datas.length} ta rasm yuborilmoqda...` : "Yuborilmoqda...", 6000);
  for(let i=0;i<datas.length;i++){
    const r = await POST("/api/send", { order_id: CUR, shared:CH.shared?1:0, html: i===0?capH:"", text: i===0?cap:"", media_kind: "photo", media_data: datas[i], reply_mid: i===0?rep:0 }).catch(()=>null);
    if(!r || !r.ok){ alert2(((r&&r.error)||"Yuborilmadi")+(datas.length>1?` (${i+1}-rasm)`:"")); break; }
  }
  $("toast").classList.add("hide"); kickSync();
}

/* ---------- media ko'ruvchi (rasm/video, chapga-o'ngga) ---------- */
let VW = { list: [], i: 0, zoom: 1, tx: 0, ty: 0, rot: 0, rots: {} };   // rots: har rasmning burilishi (sessiya davomida)
function mediaList(){ return CH.order.map(i=>CH.msgs.get(i)).filter(m=>m.file_id && (m.type==="photo"||m.type==="video"||m.type==="animation"||m.type==="video_note")); }
function openViewer(mid){
  VW.list = mediaList(); VW.i = Math.max(0, VW.list.findIndex(m=>m.mid===mid));
  $("viewer").classList.remove("hide"); renderViewer(); updateBackBtn();
}
function renderViewer(){
  const m = VW.list[VW.i]; if(!m) return closeViewer();
  VW.zoom = 1; VW.tx = 0; VW.ty = 0; VW.rot = VW.rots[m.mid] || 0;
  const st = $("v-stage");
  st.innerHTML = m.type==="photo" ? `<img src="${esc(fileUrl(m.file_id,"photo"))}" draggable="false">`
    : `<video src="${esc(fileUrl(m.file_id,"video"))}" controls autoplay playsinline ${m.type==="animation"?"loop muted":""}></video>`;
  $("v-cnt").textContent = (VW.list.length>1 ? `${VW.i+1} / ${VW.list.length} · ` : "") + (m.own?"Siz":(CH.name||"Mijoz")) + " · " + (m.ts||"").slice(0,16);
  $("v-cap").innerHTML = m.text ? TGF.render(m.html, m.text) : "";
  document.querySelector("#viewer .nav.l").classList.toggle("hide", VW.i<=0);
  document.querySelector("#viewer .nav.r").classList.toggle("hide", VW.i>=VW.list.length-1);
  const thumbs=$("v-thumbs");
  thumbs.classList.toggle("hide",VW.list.length<2);
  thumbs.innerHTML=VW.list.map((x,i)=>`<button class="vthumb ${i===VW.i?"on":""}" data-vi="${i}" title="${i+1} / ${VW.list.length}">${x.type==="photo"?`<img loading="lazy" src="${esc(fileUrl(x.file_id,"photo"))}">`:`<span>▶</span>`}</button>`).join("");
  requestAnimationFrame(()=>{ const on=thumbs.querySelector(".vthumb.on"); if(on)on.scrollIntoView({block:"nearest",inline:"center"}); });
  document.querySelectorAll("#viewer .vimg").forEach(b=>b.classList.toggle("hide", m.type!=="photo"));
  const el = st.firstElementChild;
  if(el){ el.addEventListener(el.tagName==="IMG" ? "load" : "loadedmetadata", vTransform, { once: true }); vTransform(); }
}
function closeViewer(){ $("viewer").classList.add("hide"); $("v-stage").innerHTML=""; updateBackBtn(); }
function vPrev(){ if(VW.i>0){ VW.i--; renderViewer(); } }
function vNext(){ if(VW.i<VW.list.length-1){ VW.i++; renderViewer(); } }
function viewerOpen(){ const m=VW.list[VW.i]; if(m) openExternal(fileUrl(m.file_id, m.type==="photo"?"photo":"video")); }
// Burilganda (90°/270°) rasm ekranga sig'ishi uchun masshtab
function vFit(el){
  if(!(VW.rot % 180)) return 1;
  const st = $("v-stage"), w = el.offsetWidth, h = el.offsetHeight; if(!w || !h) return 1;
  return Math.min(st.clientWidth / h, st.clientHeight / w);
}
function vTransform(){
  const el = $("v-stage").firstElementChild; if(!el) return;
  const z = el.tagName==="IMG" ? VW.zoom : 1;
  el.style.transform = `translate(${VW.tx}px,${VW.ty}px) rotate(${VW.rot}deg) scale(${z * vFit(el)})`;
  el.style.cursor = z > 1 ? "grab" : "";
}
function vZoom(f){ const m = VW.list[VW.i]; if(!m || m.type!=="photo") return;
  VW.zoom = Math.max(1, Math.min(6, VW.zoom * f)); if(VW.zoom===1){ VW.tx = VW.ty = 0; } vTransform(); haptic("sel"); }
function vZoomIn(){ vZoom(1.4); }
function vZoomOut(){ vZoom(1/1.4); }
function vRotate(){ const m = VW.list[VW.i]; if(!m) return;
  VW.rot = (VW.rot + 90) % 360; VW.rots[m.mid] = VW.rot; VW.tx = VW.ty = 0; vTransform(); haptic("sel"); }
(function(){
  const st = $("v-stage"); let x0=0,y0=0,t0=0,lastTap=0,moved=false;
  const thumbs=$("v-thumbs");
  thumbs.addEventListener("click",e=>{ const b=e.target.closest("[data-vi]"); if(!b)return; VW.i=+b.dataset.vi; renderViewer(); });
  thumbs.addEventListener("wheel",e=>{ e.preventDefault(); e.stopPropagation(); thumbs.scrollLeft+=(Math.abs(e.deltaX)>Math.abs(e.deltaY)?e.deltaX:e.deltaY); },{passive:false});
  let pinch = null;
  const dist = t=>Math.hypot(t[0].clientX-t[1].clientX, t[0].clientY-t[1].clientY);
  st.addEventListener("touchstart", e=>{
    if(e.touches.length===2){ pinch = { d: dist(e.touches), z: VW.zoom }; moved = true; return; }
    x0=e.touches[0].clientX; y0=e.touches[0].clientY; t0=Date.now(); moved=false; }, {passive:true});
  st.addEventListener("touchmove", e=>{
    if(pinch && e.touches.length===2){ VW.zoom = Math.max(1, Math.min(6, pinch.z * dist(e.touches) / pinch.d)); if(VW.zoom===1){ VW.tx=VW.ty=0; } vTransform(); return; }
    if(pinch) return;
    const dx=e.touches[0].clientX-x0, dy=e.touches[0].clientY-y0;
    if(Math.abs(dx)>6||Math.abs(dy)>6) moved=true;
    if(VW.zoom>1){ VW.tx+=dx; VW.ty+=dy; x0=e.touches[0].clientX; y0=e.touches[0].clientY; vTransform(); } }, {passive:true});
  st.addEventListener("touchend", e=>{
    if(pinch){ if(!e.touches.length) pinch = null; return; }
    const dx=e.changedTouches[0].clientX-x0, dy=e.changedTouches[0].clientY-y0;
    if(VW.zoom===1 && moved){ if(Math.abs(dx)>60 && Math.abs(dx)>Math.abs(dy)){ dx<0?vNext():vPrev(); } else if(dy>110) closeViewer(); return; }
    if(!moved){ const n=Date.now(); if(n-lastTap<300){ VW.zoom = VW.zoom>1?1:2.4; VW.tx=VW.ty=0; vTransform(); } lastTap=n; }
  });
  st.addEventListener("dblclick", ()=>{ VW.zoom = VW.zoom>1?1:2.2; VW.tx=VW.ty=0; vTransform(); });
  let drag = null;
  st.addEventListener("mousedown", e=>{ if(VW.zoom>1 && e.button===0){ e.preventDefault(); drag = { x: e.clientX, y: e.clientY }; } });
  window.addEventListener("mousemove", e=>{ if(!drag) return; VW.tx += e.clientX-drag.x; VW.ty += e.clientY-drag.y; drag = { x: e.clientX, y: e.clientY }; vTransform(); });
  window.addEventListener("mouseup", ()=>{ drag = null; });
  window.addEventListener("resize", ()=>{ if(!$("viewer").classList.contains("hide")) vTransform(); });
  let wheelAt=0;
  st.addEventListener("wheel", e=>{
    e.preventDefault();
    // Sichqoncha g'ildiragi galereyada oldingi/keyingi mediaga o'tadi.
    // Ctrl/⌘ bilan aylantirish esa kattalashtirishni saqlab qoladi.
    if(e.ctrlKey||e.metaKey){ vZoom(e.deltaY<0?1.15:.87); return; }
    const now=Date.now(); if(now-wheelAt<260)return; wheelAt=now;
    (Math.abs(e.deltaX)>Math.abs(e.deltaY)?e.deltaX:e.deltaY)>0 ? vNext() : vPrev();
  }, {passive:false});
  st.addEventListener("click", e=>{ if(e.target===st) closeViewer(); });
  document.addEventListener("keydown", e=>{ if($("viewer").classList.contains("hide")) return;
    if(e.key==="ArrowLeft") vPrev(); if(e.key==="ArrowRight") vNext();
    if(e.key==="r" || e.key==="R" || e.key==="к" || e.key==="К") vRotate();
    if(e.key==="+" || e.key==="=") vZoomIn(); if(e.key==="-") vZoomOut(); });
})();
function openExternal(u){ const a = absUrl(u); try{ tg.openLink(a); }catch(e){ window.open(a, "_blank"); } }
function openDoc(mid){
  const m = CH.msgs.get(mid); if(!m) return;
  openExternal(fileUrl(m.file_id, "document", m.file_name, m.mime_type));
}

/* ---------- chat menyusi ---------- */
function chatMenu(el){
  const r = el.getBoundingClientRect();
  const open = CH.status==="new" || CH.status==="in_progress";
  TGF.menu(r.right - 250, r.bottom + 4, [
    {label:"Mijoz kartasi", icon:"<svg viewBox='0 0 24 24'><circle cx='12' cy='8' r='4'/><path d='M4 21c0-4 4-6 8-6s8 2 8 6'/></svg>", onClick:clientCard},
    {label:"Yozishmadan qidirish", icon:"<svg viewBox='0 0 24 24'><circle cx='11' cy='11' r='7'/><path d='M21 21l-4.3-4.3'/></svg>", onClick:chatSearch},
    {label:"Teglar", icon:"<svg viewBox='0 0 24 24'><path d='M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L2 12V2h10l8.6 8.6a2 2 0 0 1 0 2.8z'/><circle cx='7' cy='7' r='1.5'/></svg>", onClick:openTags},
    {label:"Ichki izoh (mijoz ko'rmaydi)", icon:"<svg viewBox='0 0 24 24'><rect x='5' y='11' width='14' height='10' rx='2'/><path d='M8 11V7a4 4 0 0 1 8 0v4'/></svg>", onClick:addInote},
    {label:"Mijoz haqida izoh", icon:"<svg viewBox='0 0 24 24'><path d='M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7'/><path d='M18.5 2.5a2.1 2.1 0 0 1 3 3L12 15l-4 1 1-4z'/></svg>", onClick:openNote},
    {label:"Eslatma qo'yish", icon:"<svg viewBox='0 0 24 24'><path d='M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0'/></svg>", onClick:openRemind},
    open && !(CH.pause||{}).paused && {label:"Pauzaga qo'yish", icon:"⏸", onClick:openPause},
    open && (CH.pause||{}).paused && {label:"Pauzadan chiqarish", icon:"▶️", onClick:resumePause},
    open && {label:"Filialni almashtirish", icon:"📍", onClick:()=>openBranchPicker("changebranch")},
    open && {label:"Dori katalogi", icon:"💊", onClick:()=>openCatalog()},
    open && {label:"Hisob-kitob yaratish", icon:"🧾", onClick:openBill},
    open && {label:"Boshqa operatorga o'tkazish", icon:"<svg viewBox='0 0 24 24'><path d='M17 1l4 4-4 4M3 11V9a4 4 0 0 1 4-4h14M7 23l-4-4 4-4M21 13v2a4 4 0 0 1-4 4H3'/></svg>", onClick:openTransfer},
    "sep",
    open && {label:"Yakunlash", icon:"<svg viewBox='0 0 24 24'><path d='M20 6L9 17l-5-5'/></svg>", onClick:()=>closeOrder(CUR)},
    !CH.rejected && {label:"Otkaz (kanalga, chat ochiq qoladi)", icon:"🚫", onClick:rejectOrder},
    open && {label:"Bekor qilish", danger:true, icon:"<svg viewBox='0 0 24 24'><circle cx='12' cy='12' r='9'/><path d='M15 9l-6 6M9 9l6 6'/></svg>", onClick:()=>cancelOrder(CUR)},
  ]);
}
async function closeOrder(oid){
  if(!await confirm2("Murojaatni yakunlaysizmi? Mijozga baholash yuboriladi.")) return;
  const r = await POST("/api/close", { order_id: oid }).catch(()=>null);
  if(!r || !r.ok){ alert2((r&&r.error)||"Yakunlab bo'lmadi. Internetni tekshiring."); return; }
  toast("Murojaat yakunlandi ✓"); haptic("medium");
  if(oid===CUR) backToList(); kickSync();
}
async function cancelOrder(oid){
  if(!await confirm2("Murojaat bekor qilinsinmi? Mijozga «bekor qilindi» xabari boradi.")) return;
  const r = await POST("/api/cancel", { order_id: oid }).catch(()=>null);
  if(!r || !r.ok){ alert2((r&&r.error)||"Bajarilmadi"); return; }
  toast(r.info || "Bekor qilindi"); haptic("medium");
  if(oid===CUR) backToList(); kickSync();
}
async function rejectOrder(){
  if(!await confirm2("Отказ: murojaat Отказ kanaliga joylanadi. Chat ochiq qoladi — davom ettirishingiz mumkin. Davom etamizmi?")) return;
  const r = await POST("/api/reject", { order_id: CUR }).catch(()=>null);
  if(!r || !r.ok){ alert2((r&&r.error)||"Bajarilmadi"); return; }
  CH.rejected = true; updateSub(); toast(r.info || "Отказ"); haptic("medium");
}
async function hideOrder(oid){
  if(!await confirm2("Chat ro'yxatdan o'chirilsinmi?")) return;
  const r = await POST("/api/hide", { order_id: oid }).catch(()=>null);
  if(!r || !r.ok){ alert2((r&&r.error)||"O'chirilmadi"); return; }
  if(oid===CUR) backToList(); ST.chats = ST.chats.filter(c=>c.order_id!==oid); delete ST.chatMap[oid]; renderChatList(); updateBadges();
}
function backToList(){
  if(recActive()) finishRec(false);
  if(SELM) endSelect();
  saveDraftNow();
  const tab=(CH&&CH.returnTab)||"chats";
  CUR = null; CH = null; hidePanels();
  show("app", "fade"); showTab(tab); renderChatList(); renderGeneralChats(); kickSync();
}

/* ---------- chat ichida qidiruv ---------- */
async function chatSearch(){
  const box = $("csearch"); const open = box.classList.contains("hide");
  box.classList.toggle("hide", !open);
  if(!open){ CH.search = null; $("cs-q").value=""; MSGS.querySelectorAll("mark").forEach(m=>m.replaceWith(...m.childNodes)); MSGS.querySelectorAll(".found").forEach(n=>n.classList.remove("found")); return; }
  setTimeout(()=>$("cs-q").focus(), 50);
  if(CH.hasMore){ const r = await GET("/api/messages", { order_id: CUR, all: 1, shared:CH.shared?1:"" }).catch(()=>null);
    if(r && r.ok && CH){ r.messages.forEach(m=>addMsg(m)); CH.hasMore = false; renderTimeline({ keep: true }); } }
}
let _csT = null;
$("cs-q").addEventListener("input", ()=>{ clearTimeout(_csT); _csT = setTimeout(()=>{ CH.search = { q: $("cs-q").value.trim().toLowerCase(), hits: [], i: 0 }; applySearchMarks(true); }, 200); });
$("cs-q").addEventListener("keydown", e=>{ if(e.key==="Enter"){ e.preventDefault(); e.shiftKey?csPrev():csNext(); } });
function applySearchMarks(jump){
  const S = CH.search; if(!S) return;
  MSGS.querySelectorAll("mark").forEach(m=>m.replaceWith(...m.childNodes)); MSGS.querySelectorAll(".found").forEach(n=>n.classList.remove("found"));
  S.hits = [];
  if(!S.q){ $("cs-cnt").textContent=""; return; }
  CH.order.forEach(mid=>{ const m=CH.msgs.get(mid); if((m.text||"").toLowerCase().includes(S.q)) S.hits.push(mid); });
  S.hits.forEach(mid=>{ const n=$("m"+mid); if(!n) return; const t=n.querySelector(".txt"); if(t) markText(t, S.q); });
  S.i = S.hits.length - 1;
  $("cs-cnt").textContent = S.hits.length ? `${S.i+1}/${S.hits.length}` : "0";
  if(jump && S.hits.length) csGo();
}
function markText(el, q){
  const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); const nodes=[]; let n; while((n=w.nextNode())) nodes.push(n);
  nodes.forEach(tn=>{ const v=tn.nodeValue, i=v.toLowerCase().indexOf(q); if(i<0) return;
    const mk=document.createElement("mark"); const r=document.createRange(); r.setStart(tn,i); r.setEnd(tn,i+q.length); r.surroundContents(mk); });
}
function csGo(){ const S=CH.search; if(!S||!S.hits.length) return; MSGS.querySelectorAll(".found").forEach(n=>n.classList.remove("found"));
  const n=$("m"+S.hits[S.i]); if(n){ n.classList.add("found"); n.scrollIntoView({block:"center",behavior:"smooth"}); } $("cs-cnt").textContent=`${S.i+1}/${S.hits.length}`; }
function csPrev(){ const S=CH.search; if(!S||!S.hits.length) return; S.i=(S.i-1+S.hits.length)%S.hits.length; csGo(); }
function csNext(){ const S=CH.search; if(!S||!S.hits.length) return; S.i=(S.i+1)%S.hits.length; csGo(); }

/* ---------- teglar / ichki izoh / o'tkazish ---------- */
async function openTags(){
  const r = await GET("/api/tags").catch(()=>null); const preset = r && r.ok ? r.tags : [];
  const sel = new Set(CH.tags||[]); const all = [...new Set([...preset, ...sel])];
  openSheet(`<h3>Murojaat teglari</h3><div class="tagpick">${all.map(t=>`<button data-tag="${esc(t)}" class="${sel.has(t)?"on":""}">#${esc(t)}</button>`).join("")}<button data-newtag style="border-style:dashed;color:var(--accent)">+ Yangi</button></div><button class="sbtn" data-savetags>Saqlash</button>`,
    el=>el.addEventListener("click", async e=>{
      const b = e.target.closest("[data-tag]"); if(b){ b.classList.toggle("on"); haptic("sel"); return; }
      if(e.target.closest("[data-newtag]")){ TGF.prompt("Yangi teg", [{ph:"Masalan: Qayta qo'ng'iroq"}], ([t])=>{ if(!t) return; const nb=document.createElement("button"); nb.dataset.tag=t; nb.className="on"; nb.textContent="#"+t; el.querySelector("[data-newtag]").before(nb); }); return; }
      if(e.target.closest("[data-savetags]")){
        const tags = [...el.querySelectorAll("[data-tag].on")].map(x=>x.dataset.tag);
        const r2 = await POST("/api/order_tags", { order_id: CUR, tags }).catch(()=>null);
        if(r2 && r2.ok){ CH.tags = r2.tags; renderTagsbar(); closeSheet(); toast("Teglar saqlandi"); } else toast("Saqlanmadi");
      }
    }));
}
function addInote(){
  TGF.prompt("Ichki izoh (mijoz ko'rmaydi)", [{ph:"Masalan: mijoz ertaga qayta yozadi"}], async ([t])=>{
    if(!t) return; const r = await POST("/api/inote", { order_id: CUR, text: t }).catch(()=>null);
    if(r && r.ok){ toast("Izoh qo'shildi"); kickSync(); } else toast((r&&r.error)||"Xatolik");
  });
}
async function openTransfer(){
  const r = await GET("/api/ops_list").catch(()=>null);
  if(!r || !r.ok){ toast("Ro'yxat yuklanmadi"); return; }
  r.items=(r.items||[]).filter(o=>o.id!==CH.operatorId);
  const dot = s => s==="free" ? "var(--green)" : s==="busy" ? "var(--orange)" : "var(--hint)";
  const lbl = s => s==="free" ? "bo'sh" : s==="busy" ? "band" : "oflayn";
  openSheet(`<h3>Kimga o'tkazamiz?</h3>` + (r.items.map(o=>`<div class="item" data-to="${o.id}" data-tn="${esc(o.name)}">${avaHtml(o.name,42)}
      <div class="lbl">${esc(o.name)}<div class="sub"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${dot(o.state)};margin-right:5px"></span>${lbl(o.state)} · ${o.load} ta ochiq suhbat</div></div></div>`).join("") || `<div class="empty" style="padding:24px">Boshqa faol operator yo'q</div>`),
    el=>el.addEventListener("click", e=>{ const it=e.target.closest("[data-to]"); if(!it) return;
      TGF.prompt(`${it.dataset.tn} ga o'tkazish`, [{ph:"Izoh (ixtiyoriy): nima kelishildi"}], async ([note])=>{
        const r2 = await POST("/api/transfer", { order_id: CUR, to_id: +it.dataset.to, note }).catch(()=>null);
        if(r2 && r2.ok){ closeSheet(); toast(r2.info||"O'tkazildi"); backToList(); } else alert2((r2&&r2.error)||"Xatolik");
      }); }));
}

/* ---------- mijoz kartasi / izoh / eslatma ---------- */
async function clientCard(){
  if(!CUR) return;
  const r = await GET("/api/client_info", { order_id: CUR }).catch(()=>null);
  if(!r || !r.ok){ toast("Ma'lumot topilmadi"); return; }
  const c = r.client;
  const stl = s => s==="done"?"Yakunlangan":s==="canceled"?"Bekor":s==="new"?"Yangi":"Jarayonda";
  openSheet(`<div style="text-align:center;padding:8px 16px 10px">
      <div style="display:flex;justify-content:center;margin-bottom:8px">${avaHtml(c.name,84)}</div>
      <div style="font-size:20px;font-weight:700">${esc(c.name)}</div>
      ${c.username?`<div class="s-alt" data-prof="${esc(c.username)}">@${esc(c.username)}</div>`:""}
      <div style="color:var(--hint);font-size:13px;margin-top:4px"><span class="pz-keep">${esc(c.branch)||esc(T("Filial tanlanmagan"))}</span> · ${esc(T("ro'yxatdan"))}: ${esc(c.reg)||"—"}</div></div>
    <div class="list" style="background:var(--sec)">
      ${c.phone?`<a class="item" href="tel:${esc(c.phone)}" style="text-decoration:none;color:inherit"><svg class="ic ic-green" viewBox="0 0 24 24" style="width:30px;height:30px;padding:5px;border-radius:8px;color:#fff"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/></svg><div class="lbl">${esc(c.phone)}<div class="sub">Qo'ng'iroq qilish</div></div></a>`:""}
      ${c.note?`<div class="item" data-act="openNote"><svg class="ic ic-orange" viewBox="0 0 24 24" style="width:30px;height:30px;padding:5px;border-radius:8px;color:#fff"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/></svg><div class="lbl" style="white-space:pre-wrap">${esc(c.note)}<div class="sub">Izoh</div></div></div>`:""}
    </div>
    <h3 style="font-size:14px;color:var(--hint);margin:12px 16px 4px">Murojaatlari</h3>
    ${r.orders.map(o=>`<div class="item" ${o.can_open?`data-ord="${o.id}"`:'style="opacity:.72;cursor:default"'}><div class="lbl">#${o.id} <span style="color:var(--hint);font-size:12.5px">· ${esc(o.date)}</span>${o.can_open?"":`<div class="sub">${esc(T("Boshqa operator murojaati — faqat qisqa tarix"))}</div>`}</div><div class="val">${stl(o.status)}${o.rating?" · "+o.rating+"★":""}</div></div>`).join("") || '<div class="empty">Murojaat yo\'q</div>'}`,
    el=>el.addEventListener("click", e=>{
      const o = e.target.closest("[data-ord]"); if(o){ const shared=!!CH.shared; closeSheet(); openChat(+o.dataset.ord, c.name, shared); return; }
      const p = e.target.closest("[data-prof]"); if(p){ try{ tg.openTelegramLink("https://t.me/"+p.dataset.prof); }catch(err){} }
    }));
}
let curNote = "";
async function loadNote(){
  const oid = CUR; const r = await GET("/api/note", { order_id: oid }).catch(()=>null);
  if(oid!==CUR) return; curNote = (r && r.ok && r.note) ? r.note : "";
  $("notebanner").classList.toggle("hide", !curNote); $("note-text-b").textContent = curNote;
}
function openNote(){
  if(!CUR) return;
  openSheet(`<h3>Mijoz haqida izoh</h3><textarea class="inp" id="note-text" rows="5" placeholder="Masalan: doimiy mijoz, diabetik, faqat naqd to'laydi">${esc(curNote)}</textarea><button class="sbtn" data-savenote>Saqlash</button>`,
    el=>{ setTimeout(()=>{ const t=$("note-text"); t && t.focus(); },150); el.querySelector("[data-savenote]").onclick = async()=>{
      const note = $("note-text").value.trim(); const r = await POST("/api/note", { order_id: CUR, note }).catch(()=>null);
      if(!r || !r.ok){ toast("Saqlanmadi"); return; } curNote = note; closeSheet(); $("notebanner").classList.toggle("hide", !note); $("note-text-b").textContent = note; toast("Saqlandi"); }; });
}
function openRemind(){
  openSheet(`<h3>Eslatma qo'yish</h3><input class="inp" id="rm-note" placeholder="Izoh (ixtiyoriy): masalan, narxni aytish">
    <div class="item" data-min="15"><div class="lbl">15 daqiqadan keyin</div></div><div class="item" data-min="60"><div class="lbl">1 soatdan keyin</div></div>
    <div class="item" data-min="180"><div class="lbl">3 soatdan keyin</div></div><div class="item" data-min="tm"><div class="lbl">Ertaga 09:00 da</div></div>`,
    el=>el.addEventListener("click", async e=>{ const it=e.target.closest("[data-min]"); if(!it) return;
      let minutes = +it.dataset.min; if(it.dataset.min==="tm"){ const n=new Date(), t=new Date(n); t.setDate(t.getDate()+1); t.setHours(9,0,0,0); minutes=Math.max(1,Math.round((t-n)/60000)); }
      const note = $("rm-note").value.trim(); closeSheet();
      const r = await POST("/api/remind", { order_id: CUR, minutes, note }).catch(()=>null); toast(r&&r.ok?r.info:((r&&r.error)||"Xatolik"), 3000); }));
}

/* ============================================================
   OVOZ YOZISH (Telegramdek: bosib turish, chapga surib bekor qilish, tepaga — qulflash)
   ============================================================ */
const OPUS_ENC = "https://cdn.jsdelivr.net/npm/opus-recorder@8.0.5/dist/encoderWorker.min.js";
let audioCtx=null, analyser=null, recStream=null, recAnim=null, recStart=0, recBars=[], opusRec=null, rec=null, recChunks=[];
let recMode = null;   // null | 'starting' | 'hold' | 'locked'
let recReleased = false;
let recGen = 0;        // bekor qilinganda kutilayotgan startRec natijasini e'tiborsiz qoldirish uchun
function recActive(){ return !!recMode; }
function getAccent(){ return (getComputedStyle(document.documentElement).getPropertyValue("--accent")||"#3390ec").trim(); }
const MIC = $("mic"), COMP = $("composer");
let hold = null;
MIC.addEventListener("pointerdown", e=>{
  if(e.button>0 || !CUR) return;
  if(recMode==="locked"){ return; }
  e.preventDefault(); try{ MIC.setPointerCapture(e.pointerId); }catch(err){}
  hold = { x: e.clientX, y: e.clientY, t: Date.now(), id: e.pointerId };
  recReleased = false;
  hold.timer = setTimeout(()=>{ hold && startRec("hold"); }, 180);
});
MIC.addEventListener("pointermove", e=>{
  if(!hold || recMode!=="hold") return;
  const dx = e.clientX - hold.x, dy = e.clientY - hold.y;
  $("recslide").style.transform = `translateX(${Math.min(0,dx)}px)`; $("recslide").style.opacity = Math.max(.2, 1 + dx/150);
  if(dx < -110){ hold=null; finishRec(false); haptic("medium"); }
  else if(dy < -80){ lockRec(); }
});
MIC.addEventListener("pointerup", e=>{
  if(recMode==="locked" && !hold){ stopSendRec(); return; }
  if(!hold) return;
  clearTimeout(hold.timer);
  const short = Date.now() - hold.t < 180; hold = null; recReleased = true;
  if(short && !recMode){ startRec("locked"); return; }       // qisqa bosish — qulflangan yozish
  if(recMode==="hold") stopSendRec();
  else if(recMode==="starting") recMode = "starting-release";
});
MIC.addEventListener("pointercancel", ()=>{ if(hold){ clearTimeout(hold.timer); hold=null; } if(recMode==="hold") lockRec(); });
function lockRec(){ if(!recMode) return; recMode = "locked"; COMP.classList.add("locked"); hold = null; haptic("light");
  MIC.innerHTML = '<svg class="ic" viewBox="0 0 24 24" style="fill:currentColor;stroke:none;transform:rotate(45deg) translate(-2px,1px)"><path d="M3.4 20.4l17.4-7.5c.8-.4.8-1.5 0-1.8L3.4 3.6c-.7-.3-1.4.3-1.3 1l1.1 6.1 9.3 1.3-9.3 1.3-1.1 6.1c-.1.7.6 1.3 1.3 1z"/></svg>'; }
const MIC_HTML = MIC.innerHTML;
async function startRec(mode){
  if(recMode) return;
  recMode = "starting"; const gen = ++recGen;
  COMP.classList.add("rec"); $("rectime").textContent = "0:00";   // savat tugmasi darhol ko'rinsin
  if(!navigator.mediaDevices){ recMode=null; COMP.classList.remove("rec"); alert2("Mikrofon mavjud emas"); return; }
  let stream;
  try{ stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch(e){ if(gen===recGen){ recMode=null; COMP.classList.remove("rec","locked"); alert2("Mikrofonga ruxsat berilmadi"); } return; }
  if(gen !== recGen){ stream.getTracks().forEach(t=>t.stop()); return; }   // kutish paytida bekor qilindi
  recStream = stream;
  recChunks=[]; opusRec=null; rec=null;
  let srcNode=null;
  try{ audioCtx = new (window.AudioContext||window.webkitAudioContext)(); try{ audioCtx.resume(); }catch(e){}
    srcNode = audioCtx.createMediaStreamSource(recStream); analyser = audioCtx.createAnalyser(); analyser.fftSize=256; srcNode.connect(analyser); }catch(e){}
  if(window.Recorder && srcNode){
    try{ opusRec = new Recorder({ encoderPath: OPUS_ENC, numberOfChannels: 1, encoderSampleRate: 48000, streamPages: false, encoderApplication: 2048, sourceNode: srcNode });
      await opusRec.start(); }catch(e){ try{ opusRec && opusRec.close(); }catch(_){} opusRec=null; }
    if(gen !== recGen){ try{ opusRec && opusRec.close(); }catch(_){} opusRec=null; return; }
  }
  if(!opusRec){
    if(!window.MediaRecorder){ recStream.getTracks().forEach(t=>t.stop()); recMode=null; alert2("Bu qurilma ovoz yozishni qo'llamaydi"); return; }
    let mime=""; ["audio/ogg;codecs=opus","audio/webm;codecs=opus","audio/webm","audio/mp4"].forEach(m=>{ if(!mime && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m)) mime=m; });
    try{ rec = mime ? new MediaRecorder(recStream,{mimeType:mime}) : new MediaRecorder(recStream); }catch(e){ recStream.getTracks().forEach(t=>t.stop()); recMode=null; alert2("Ovoz yozib bo'lmadi"); return; }
    rec.ondataavailable = e=>{ if(e.data && e.data.size>0) recChunks.push(e.data); };
    rec.start(200);
  }
  const released = recMode==="starting-release";
  recMode = (mode==="hold" && !released && !recReleased) ? "hold" : "locked";
  COMP.classList.add("rec"); COMP.classList.toggle("locked", recMode==="locked");
  if(recMode==="locked") lockRec();
  $("recslide").style.transform=""; $("recslide").style.opacity=1;
  hidePanels(); haptic("medium");
  recStart = Date.now(); recBars = []; tickTime(); drawWave();
}
function tickTime(){ if(!recMode || recMode==="starting") return; const s=Math.floor((Date.now()-recStart)/1000); $("rectime").textContent = fmtDur(s); setTimeout(tickTime, 250); }
function drawWave(){
  const c = $("recwave"); if(!c || !analyser) return;
  const ctx = c.getContext("2d"), data = new Uint8Array(analyser.frequencyBinCount);
  (function frame(){ if(!analyser) return;
    c.width = c.offsetWidth; c.height = 30; analyser.getByteFrequencyData(data);
    let sum=0; for(let i=0;i<data.length;i++) sum+=data[i]; recBars.push(Math.min(1,(sum/data.length/255)*2.4));
    const max = Math.floor(c.width/4); if(recBars.length>max) recBars.shift();
    ctx.clearRect(0,0,c.width,c.height); ctx.fillStyle = getAccent();
    for(let i=0;i<recBars.length;i++){ const h=Math.max(3,recBars[i]*c.height); ctx.fillRect(i*4,(c.height-h)/2,2.4,h); }
    recAnim = requestAnimationFrame(frame); })();
}
function stopSendRec(){ finishRec(true); }
function cancelRec(){ if(!recActive()) return; finishRec(false); haptic("medium"); toast("Ovozli xabar o'chirildi", 1400); }
async function _sendVoiceBlob(blob, mime, oid){
  if(blob.size<300){ toast("Ovoz juda qisqa"); return; }
  const asBill = pendingBill; if(asBill) exitBill();
  const shared = !!(CH && CH.oid===oid && CH.shared);
  const rep = CH && CH.oid===oid ? (CH.replyTo||0) : 0; if(rep) clearReply();
  const rd = new FileReader();
  rd.onload = async()=>{ try{
    const r = asBill ? await POST("/api/cmd",{order_id:oid,cmd:"bill",media_kind:"voice",media_mime:mime,media_data:rd.result})
                     : await POST("/api/send",{order_id:oid,shared:shared?1:0,media_kind:"voice",media_mime:mime,media_data:rd.result,reply_mid:rep});
    if(!r.ok){ alert2(r.error||"Yuborilmadi"); return; }
    if(asBill) toast(r.info||"Hisob-kitob yuborildi");
    kickSync();
  }catch(err){ alert2("Ovoz yuborilmadi — internetni tekshiring"); } };
  rd.readAsDataURL(blob);
}
function finishRec(sendIt){
  const oid = CUR;
  recGen++;   // hali boshlanayotgan (mikrofon ruxsatini kutayotgan) yozuv ham bekor bo'ladi
  const doneUI = ()=>{ if(recAnim) cancelAnimationFrame(recAnim); recAnim=null;
    if(recStream){ recStream.getTracks().forEach(t=>t.stop()); recStream=null; }
    if(audioCtx){ try{audioCtx.close();}catch(e){} audioCtx=null; } analyser=null;
    COMP.classList.remove("rec","locked"); MIC.innerHTML = MIC_HTML; recMode = null; hold = null; };
  if(opusRec){ const orc=opusRec; opusRec=null;
    orc.ondataavailable = t=>{ try{ orc.close(); }catch(e){} if(sendIt) _sendVoiceBlob(new Blob([t],{type:"audio/ogg"}),"audio/ogg",oid); };
    try{ orc.stop(); }catch(e){ try{ orc.close(); }catch(_){} }
    doneUI(); return; }
  if(rec && rec.state==="recording"){ const mime=(rec&&rec.mimeType)||"audio/webm";
    rec.onstop = ()=>{ doneUI(); if(sendIt) _sendVoiceBlob(new Blob(recChunks,{type:mime}),mime,oid); };
    try{ rec.stop(); }catch(e){ doneUI(); } }
  else doneUI();
}

/* ---------- ovoz pleyeri (to'lqin + play/pause; iOS Ogg uchun WASM dekoder) ---------- */
const waveCache = {};
let _actx=null; function actx(){ if(!_actx) _actx=new (window.AudioContext||window.webkitAudioContext)(); return _actx; }
let _oggDecP=null;
function loadOggDecoder(){
  const has=()=>window.OggOpusDecoder||(window["ogg-opus-decoder"]||{}).OggOpusDecoder;
  if(has()) return Promise.resolve(has()); if(_oggDecP) return _oggDecP;
  _oggDecP=new Promise((res,rej)=>{ const s=document.createElement("script"); s.src="https://cdn.jsdelivr.net/npm/ogg-opus-decoder@1.6.9/dist/ogg-opus-decoder.min.js";
    s.onload=()=>{ const D=has(); D?res(D):rej(new Error("dekoder")); }; s.onerror=()=>rej(new Error("dekoder yuklanmadi")); document.head.appendChild(s); });
  return _oggDecP;
}
const _vbuf={};
async function decodeVoice(url){
  if(_vbuf[url]) return _vbuf[url];
  const ab = await (await fetch(url)).arrayBuffer(); const ctx = actx();
  try{ const b = await ctx.decodeAudioData(ab.slice(0)); _vbuf[url]=b; return b; }catch(e){}
  const Dec = await loadOggDecoder(); const dec = new Dec(); await dec.ready;
  const {channelData,samplesDecoded,sampleRate} = await dec.decodeFile(new Uint8Array(ab)); try{ dec.free(); }catch(e){}
  const chs = (channelData&&channelData.length)?channelData.length:1; const buf = ctx.createBuffer(chs, samplesDecoded||1, sampleRate||48000);
  for(let ch=0;ch<chs;ch++) buf.copyToChannel(channelData[ch], ch); _vbuf[url]=buf; return buf;
}
const ICON_PLAY='<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
const ICON_PAUSE='<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>';
let _playing = null;
function initVoicePlayers(root){
  (root||document).querySelectorAll(".vp").forEach(vp=>{
    if(vp.dataset.ready) return; vp.dataset.ready = "1";
    const url = vp.dataset.src, fid = vp.dataset.fid;
    const canvas = vp.querySelector("canvas"), btn = vp.querySelector(".pp"), tlab = vp.querySelector(".vt");
    let audio=null, bars=waveCache[fid]||null, dur=0;
    const out = vp.closest(".mrow.o");
    const draw = prog=>{ const ctx=canvas.getContext("2d"); canvas.width=canvas.offsetWidth||140; canvas.height=28;
      const b = bars || new Array(36).fill(.25), bw = canvas.width/b.length;
      const on = out ? getComputedStyle(document.documentElement).getPropertyValue("--meta-out").trim() : getAccent();
      for(let i=0;i<b.length;i++){ const h=Math.max(3,b[i]*canvas.height); ctx.fillStyle=(i/b.length<=prog)?on:"rgba(140,150,160,.45)";
        const x=i*bw, w=Math.max(2,bw-1.6), y=(canvas.height-h)/2; ctx.beginPath(); if(ctx.roundRect) ctx.roundRect(x,y,w,h,1.2); else ctx.rect(x,y,w,h); ctx.fill(); } };
    setTimeout(()=>draw(0), 0);
    if(!bars){ fetch(url).then(r=>r.arrayBuffer()).then(buf=>{ const ac=new (window.AudioContext||window.webkitAudioContext)();
      ac.decodeAudioData(buf).then(ab=>{ dur=ab.duration; const ch=ab.getChannelData(0), N=36, block=Math.max(1,Math.floor(ch.length/N)), o=[]; let mx=0;
        for(let i=0;i<N;i++){ let s=0; for(let j=0;j<block;j++) s+=Math.abs(ch[i*block+j]||0); o.push(s/block); mx=Math.max(mx,o[i]); }
        bars=o.map(v=>mx?Math.min(1,v/mx):.25); waveCache[fid]=bars; draw(0); tlab.textContent=fmtDur(dur); ac.close(); }).catch(()=>{}); }).catch(()=>{}); }
    const setIcon = p=>btn.innerHTML = p?ICON_PAUSE:ICON_PLAY; setIcon(false);
    let wa=null, switched=false;
    function waStop(){ if(wa&&wa.node){ try{ wa.node.onended=null; wa.node.stop(); }catch(e){} cancelAnimationFrame(wa.raf); wa.playing=false; } }
    async function waToggle(){
      const ctx=actx(); try{ ctx.resume(); }catch(e){}
      if(wa&&wa.playing){ wa.offset+=ctx.currentTime-wa.startAt; waStop(); setIcon(false); return; }
      if(!wa){ tlab.textContent="…"; let buf; try{ buf=await decodeVoice(url); }catch(e){ tlab.textContent="✖ ijro etilmadi"; return; }
        wa={buf,offset:0,playing:false,node:null,startAt:0,raf:0}; dur=buf.duration; draw(0); tlab.textContent=fmtDur(dur); }
      wa.node=ctx.createBufferSource(); wa.node.buffer=wa.buf; wa.node.connect(ctx.destination);
      wa.startAt=ctx.currentTime; wa.playing=true; setIcon(true);
      wa.node.onended=()=>{ if(wa.playing){ wa.offset=0; wa.playing=false; setIcon(false); draw(0); tlab.textContent=fmtDur(dur); } };
      const tick=()=>{ if(!wa.playing) return; const cur=wa.offset+(actx().currentTime-wa.startAt), d=dur||1; draw(Math.min(1,cur/d)); tlab.textContent=fmtDur(Math.max(0,d-cur)); wa.raf=requestAnimationFrame(tick); };
      wa.node.start(0, Math.min(wa.offset, Math.max(0,(dur||0)-.05))); wa.raf=requestAnimationFrame(tick);
    }
    function goWA(){ if(switched) return; switched=true; audio=null; setIcon(false); waToggle(); }
    btn.onclick = e=>{ e.stopPropagation();
      if(switched){ waToggle(); return; }
      if(!audio){ audio=new Audio(url);
        audio.onloadedmetadata=()=>{ if(!dur&&isFinite(audio.duration)){ dur=audio.duration; tlab.textContent=fmtDur(dur);} };
        audio.ontimeupdate=()=>{ const d=audio.duration||dur||1; draw(audio.currentTime/d); tlab.textContent=fmtDur(d-audio.currentTime); };
        audio.onended=()=>{ setIcon(false); draw(0); tlab.textContent=fmtDur(dur); };
        audio.onerror=goWA; }
      if(audio.paused){ if(_playing && _playing!==audio){ try{ _playing.pause(); }catch(err){} } _playing=audio; const p=audio.play(); setIcon(true); if(p&&p.catch) p.catch(goWA); }
      else { audio.pause(); setIcon(false); }
      audio.onpause = ()=>setIcon(false);
    };
    canvas.onclick = e=>{ e.stopPropagation(); const frac=e.offsetX/(canvas.offsetWidth||1);
      if(audio&&audio.duration){ audio.currentTime=frac*audio.duration; }
      else if(switched&&wa){ const wasP=wa.playing; waStop(); setIcon(false); wa.offset=Math.max(0,Math.min(dur||0,frac*(dur||0))); draw(frac); if(wasP) waToggle(); } };
  });
}

/* ============================================================
   KANAL (yangi murojaatlar)
   ============================================================ */
let chanTimer = null;
async function openChannel(){ show("channel","in"); await loadChannel(); if(chanTimer) clearInterval(chanTimer); chanTimer = setInterval(()=>{ if(!document.hidden && CURSCREEN==="channel") loadChannel(); }, 8000); }
function closeChannel(){ if(chanTimer){ clearInterval(chanTimer); chanTimer=null; } show("app","fade"); renderChatList(); }
async function loadChannel(){
  const r = await GET("/api/channel").catch(()=>null); if(!r || !r.ok) return;
  $("chan-count").textContent = r.count + " ta yangi";
  const box = $("chanfeed");
  if(!r.items.length){ box.innerHTML = `<div class="empty"><div class="big">📭</div>Hozircha yangi murojaat yo'q</div>`; return; }
  box.innerHTML = r.items.map(it=>{
    let media = "";
    const fid = it.file_id;
    if(fid && it.ftype==="photo") media = `<div class="ph" data-cimg="${esc(fileUrl(fid,"photo"))}" style="margin:6px 0"><img loading="lazy" src="${esc(fileUrl(fid,"photo"))}"></div>`;
    else if(fid && (it.ftype==="voice"||it.ftype==="audio")) media = `<div class="vp" data-src="${esc(fileUrl(fid,"voice"))}" data-fid="${esc(fid)}" style="margin:6px 0"><button class="pp" type="button"></button><div class="vw"><canvas></canvas><div class="vt">0:00</div></div></div>`;
    else if(fid && it.ftype==="video") media = `<div class="vid" style="margin:6px 0"><video controls playsinline preload="metadata" src="${esc(fileUrl(fid,"video"))}"></video></div>`;
    else if(fid && it.ftype==="sticker") media = `<img src="${esc(fileUrl(fid,"sticker"))}" style="width:120px;height:120px;object-fit:contain">`;
    else if(fid && it.ftype==="document"){ const [k,l]=docIcon(it.file_name,it.mime_type);
      media = `<div class="doc" data-cdoc="${esc(fileUrl(fid,"document",it.file_name||"",it.mime_type||""))}" style="margin:6px 0"><div class="di ${k}">${esc(l)}</div><div style="min-width:0"><div class="dn">${esc(it.file_name||"Hujjat")}</div><div class="ds">${esc(l)} · ochish</div></div></div>`; }
    else if(fid) media = `<div class="sub">${esc(CT_LBL[it.ftype]||"Fayl")}</div>`;
    const txt = it.text && it.ftype!=="document" ? `<div class="cbody">${TGF.linkify(it.text)}</div>` : "";
    return `<div class="ccard"><div class="ch">${avaHtml(it.name,44)}
        <div style="flex:1;min-width:0"><div class="nm" data-prof="${esc(it.uname||"")}">${esc(it.name)}</div><div class="sub">${esc(it.phone)}${it.branch?" · "+esc(it.branch):""}</div></div>
        <div class="sub" style="align-self:flex-start">${esc(it.time)}</div></div>${txt}${media}
      <button class="accept" data-acc="${it.order_id}" data-name="${esc(it.name)}">Qabul qilish</button></div>`;
  }).join("");
  initVoicePlayers(box);
}
$("chanfeed").addEventListener("click", async e=>{
  const a = e.target.closest("[data-acc]");
  if(a){ a.disabled = true; a.textContent = "Qabul qilinmoqda...";
    const r = await POST("/api/channel_accept", { order_id: +a.dataset.acc }).catch(()=>null);
    if(!r || !r.ok){ alert2((r&&r.error)||"Qabul qilinmadi"); loadChannel(); return; }
    haptic("medium"); if(chanTimer){ clearInterval(chanTimer); chanTimer=null; } openChat(r.order_id, a.dataset.name); return; }
  const im = e.target.closest("[data-cimg]"); if(im){ openExternal(im.dataset.cimg); return; }
  const d = e.target.closest("[data-cdoc]"); if(d){ openExternal(d.dataset.cdoc); return; }
  const p = e.target.closest("[data-prof]"); if(p){ if(p.dataset.prof){ try{ tg.openTelegramLink("https://t.me/"+p.dataset.prof); }catch(err){} } else toast("Mijoz Telegram username qo'ymagan"); }
});

/* ============================================================
   RO'YXATLAR (profil)
   ============================================================ */
let _lvKind=null, _lvT=null;
const LV_CFG={unfinished:{t:"Yakunlanmagan murojaatlar",u:"/api/unfinished",search:false},
              done:{t:"Suhbatlar tarixi",u:"/api/done",search:true},
              myratings:{t:"So'nggi baholarim",u:"/api/my_ratings",search:false},
              rating:{t:"Reyting",u:"/api/rating",search:false}};
$("lv-q").addEventListener("input", ()=>{ clearTimeout(_lvT); _lvT=setTimeout(loadList,300); });
async function openList(el){ const kind = el.dataset.k; _lvKind=kind; const c=LV_CFG[kind];
  $("lv-title").textContent=c.t; $("lv-search").classList.toggle("hide",!c.search); if(c.search) $("lv-q").value="";
  show("listview","in"); await loadList(); }
async function loadList(){
  const kind=_lvKind, c=LV_CFG[kind], box=$("lv-body"); box.innerHTML='<div class="spinner"></div>';
  const params={}; if(c.search){ const t=$("lv-q").value.trim(); if(t) params.q=t; }
  const r = await GET(c.u, params).catch(()=>null);
  if(!r || !r.ok){ box.innerHTML='<div class="empty">Xatolik</div>'; return; }
  if(kind==="rating"){
    box.innerHTML = r.items.map((it,i)=>`<div class="crow"><div class="cfront" style="cursor:default">
      <div class="ava" style="background:${i<3?["#f5b301","#a8b2bd","#cd7f32"][i]:avaBg(it.name)}">${i<3?["🥇","🥈","🥉"][i]:i+1}</div>
      <div class="mid"><div class="l1"><span class="nm">${esc(it.name)}${it.name===r.me?" (siz)":""}</span></div>
      <div class="l2"><span class="pv">${it.done} yakun · ${it.score} ball${it.rating?" · "+it.rating+"★":""}</span></div></div></div></div>`).join("") || '<div class="empty">Bo\'sh</div>'; return;
  }
  if(kind==="myratings"){
    box.innerHTML = r.items.map(it=>{ const stars="★".repeat(it.rating)+"☆".repeat(5-it.rating); const col=it.rating<=2?"var(--red)":it.rating===3?"var(--orange)":"var(--green)";
      return `<div class="crow" data-oid="${it.order_id}" data-name="${esc(it.name)}"><div class="cfront">${avaHtml(it.name)}
        <div class="mid"><div class="l1"><span class="nm">${esc(it.name)}</span><span class="tm">${esc(it.time||"")}</span></div>
        <div class="l2"><span class="pv"><span style="color:${col};font-weight:600">${stars}</span>${it.feedback?" · «"+esc(it.feedback)+"»":""}</span></div></div></div></div>`; }).join("") || '<div class="empty">Hali baho yo\'q</div>'; return;
  }
  if(!r.items.length){ box.innerHTML='<div class="empty">Bo\'sh</div>'; return; }
  box.innerHTML = r.items.map(it=>{
    const sub = kind==="unfinished" ? (it.status==="new"?"Yangi":"Jarayonda")+(it.operator?" · "+esc(it.operator):"")+(it.mine?" · siznikida":"")
                                    : (it.status==="canceled"?"🔴 Bekor · ":"🟢 Yakun · ")+esc(it.time||"")+(it.rating?" · "+it.rating+"★":"");
    return `<div class="crow" data-oid="${it.order_id}" data-name="${esc(it.name)}"><div class="cfront">${avaHtml(it.name)}
      <div class="mid"><div class="l1"><span class="nm">${esc(it.name)}</span></div><div class="l2"><span class="pv">${sub}</span></div></div></div></div>`; }).join("");
}
$("lv-body").addEventListener("click", e=>{ const r=e.target.closest(".crow[data-oid]"); if(r) openChat(+r.dataset.oid, r.dataset.name); });
function closeList(){ $("lv-search").classList.add("hide"); show("app","fade"); showTab("prof"); }

/* ============================================================
   PROFIL
   ============================================================ */
async function loadProfile(){
  const r = await GET("/api/profile").catch(()=>null); if(!r || !r.ok) return;
  if(r.token){ ST.op.token = r.token; saveSession(); }
  if(r.mk){ ST.mk = r.mk; LS.set("op_mk", r.mk); }
  ST.op.name = r.name;
  $("p-name").textContent = r.name; $("p-login").textContent = "@"+r.login + (r.ws?` · ish vaqti ${r.ws}–${r.we}`:"");
  const a = $("p-ava"); a.textContent = ini(r.name); a.style.background = avaBg(r.name);
  $("p-acc").textContent = r.stats.accepted; $("p-done").textContent = r.stats.done; $("p-today").textContent = r.stats.today_done; $("p-rate").textContent = r.stats.rating || "—";
  const free = r.availability==="free"; $("p-switch").classList.toggle("on", free); $("p-stlbl").textContent = free?"Bo'sh — yangi murojaatlar keladi":"Band — yangi murojaat kelmaydi";
  setSnd(LS.get("snd")||"on"); loadMyChart();
  renderGoal(r.goal);
}
async function toggleStatus(){
  const r = await POST("/api/status").catch(()=>null); if(!r || !r.ok) return;
  const free = r.availability==="free"; $("p-switch").classList.toggle("on", free); $("p-stlbl").textContent = free?"Bo'sh — yangi murojaatlar keladi":"Band — yangi murojaat kelmaydi"; haptic("sel");
}
async function loadMyChart(){
  const r = await GET("/api/mystats").catch(()=>null); if(!r || !r.ok) return;
  const mx = Math.max(...r.days.map(d=>d.c),1);
  if(!r.days.some(d=>d.c)){ $("mychart").innerHTML = `<div style="flex:1;align-self:center;text-align:center;color:var(--hint);font-size:13.5px">Bu hafta hali yakunlangan murojaat yo'q.<br>Birinchisini yakunlang 💪</div>`; return; }
  $("mychart").innerHTML = r.days.map((d,i)=>`<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;height:100%;justify-content:flex-end">
    <div style="font-size:10.5px;font-weight:600">${d.c||""}</div>
    <div style="width:100%;max-width:28px;height:${Math.max(4,(d.c/mx)*60)}px;border-radius:6px 6px 3px 3px;background:${d.c?(i===6?"var(--accent)":"color-mix(in srgb,var(--accent) 55%,transparent)"):"var(--sep)"};transition:height .4s"></div>
    <div style="font-size:10.5px;color:var(--hint)">${esc(d.label)}</div></div>`).join("");
}
document.querySelectorAll("#sndseg button").forEach(b=>b.onclick=()=>{ setSnd(b.dataset.v); haptic("sel"); });
document.querySelectorAll("#themeseg button").forEach(b=>b.onclick=()=>{ setTheme(b.dataset.th); haptic("sel"); });
document.querySelectorAll("#langseg button").forEach(b=>{ b.classList.toggle("on", b.dataset.l===LANG);
  b.onclick=()=>{ if(b.dataset.l!==LANG){ haptic("sel"); I18N.setLang(b.dataset.l); } }; });

/* ---------- chat foni sozlash ---------- */
function openWallpaper(){
  const tiles = WP_LIST.map(([k,l])=>`<div class="wpt wp-${k} ${!WP.custom&&WP.preset===k?"on":""}" data-wp="${k}" title="${esc(l)}"></div>`).join("");
  openSheet(`<h3>Chat foni</h3>
    <div class="wpprev" id="wp-prev"><div id="wp-pw" style="position:absolute;inset:-10px"></div><div id="wp-pd" style="position:absolute;inset:0;background:#000;opacity:${(WP.dim||0)/100}"></div>
      <div class="in"><div class="pb" style="background:var(--b-in);color:var(--b-in-t);align-self:flex-start">Assalomu alaykum! Dori bormi?</div>
      <div class="pb" style="background:var(--b-out);color:var(--b-out-t);align-self:flex-end">Ha, bor. Narxi 45 000 so'm 💊</div></div></div>
    <div class="wpgrid">${tiles}<div class="wpt up ${WP.custom?"on":""}" data-wpup><svg class="ic" viewBox="0 0 24 24"><path d="M12 16V4M7 9l5-5 5 5M4 20h16"/></svg>O'z rasmingiz</div></div>
    <div class="rng"><span>Xiralashtirish</span><input type="range" min="0" max="20" value="${WP.blur||0}" id="wp-blur"></div>
    <div class="rng"><span>Qorong'ilik</span><input type="range" min="0" max="70" value="${WP.dim||0}" id="wp-dim"></div>
    <button class="sbtn" data-wpsave>Saqlash</button>`,
    el=>{
      const prevWall = $("wp-pw"); applyWallpaper(prevWall);
      const sync = ()=>{ applyWallpaper(prevWall); $("wp-pd").style.opacity = (WP.dim||0)/100; };
      el.addEventListener("click", async e=>{
        const t = e.target.closest("[data-wp]");
        if(t){ WP.preset = t.dataset.wp; WP.custom = false; el.querySelectorAll(".wpt").forEach(x=>x.classList.toggle("on", x===t)); sync(); haptic("sel"); return; }
        if(e.target.closest("[data-wpup]")){ $("file-wp").click(); return; }
        if(e.target.closest("[data-wpsave]")){
          const r = await POST("/api/wallpaper", Object.assign({ dim: WP.dim, blur: WP.blur }, WP.custom ? {} : { preset: WP.preset })).catch(()=>null);
          if(r && r.ok){ LS.set("wp_preset", WP.preset); applyWallpaper(); closeSheet(); toast("Fon saqlandi"); } else toast("Saqlanmadi");
        }
      });
      $("wp-blur").oninput = e=>{ WP.blur = +e.target.value; sync(); };
      $("wp-dim").oninput = e=>{ WP.dim = +e.target.value; sync(); };
      $("file-wp").onchange = async function(){
        const f = this.files[0]; this.value = ""; if(!f) return;
        toast("Yuklanmoqda...");
        const data = await compressImage(f, 1600, .82);
        const r = await POST("/api/wallpaper", { data, dim: WP.dim, blur: WP.blur }).catch(()=>null);
        if(!r || !r.ok){ toast((r&&r.error)||"Yuklanmadi"); return; }
        Object.assign(WP, r); await fetchCustomWp(); sync(); applyWallpaper();
        el.querySelectorAll(".wpt").forEach(x=>x.classList.toggle("on", x.hasAttribute("data-wpup"))); toast("Rasm o'rnatildi");
      };
    });
}


/* ============================================================
   PAUZA — chat yopilmaydi, pauza vaqti statistikaga kirmaydi
   ============================================================ */
function renderPausebar(){
  const p = (CH && CH.pause) || {};
  const open = CH && (CH.status==="new" || CH.status==="in_progress");
  $("pausebar").classList.toggle("hide", !p.paused);
  $("pauseresume").classList.toggle("hide", !(p.paused && open));
  if(p.paused){
    const rl = m => m%1440===0 ? T("{n} kun", {n: m/1440}) : m%60===0 ? T("{n} soat", {n: m/60}) : T("{n} daq", {n: m});
    const txt = T(p.reason || "Pauza") + (p.until_label ? " · 🔔 " + T("{t} eslatma", {t: p.until_label}) : "")
              + (p.remind_min ? " · 🔔 " + T("har {t}", {t: rl(p.remind_min)}) : "");
    $("pause-text").textContent = txt; $("pr-text").textContent = txt;
  }
  const mi = $("pz-btn"); if(mi) mi.classList.toggle("hide", !!p.paused);
}
function fmtMin(m){ m = Math.round(m||0); if(m < 60) return T("{n} daq", {n: m}); const h = Math.floor(m/60); return T("{h} soat {m} daq", {h, m: m%60}); }
function pauseHtml(h){
  const st = (h.start||"").slice(11,16);
  const tail = h.end ? ` → ${esc(h.end.slice(11,16))} · ${esc(fmtMin(h.minutes))}` : ` · ${esc(T("davom etmoqda"))}`;
  const by = {client: T("mijoz yozdi"), operator: T("operator davom ettirdi"), time: T("vaqt tugadi"), close: T("yakunlandi")}[h.by] || "";
  return `<div class="sysm pz"><span>⏸ ${esc(T("Pauza"))}: ${esc(T(h.reason||""))} · ${esc(st)}${tail}${by?" · "+esc(by):""}</span></div>`;
}
const PAUSE_REASONS = ["Mijoz keyinroq yozadi","Mijoz ertaga yozadi","Dori kutilmoqda","Mijoz o'ylab ko'radi","To'lov kutilmoqda","Narx aniqlanmoqda"];
function openPause(){
  if(!CUR) return;
  const tm = ()=>{ const n=new Date(), t=new Date(n); t.setDate(t.getDate()+1); t.setHours(9,0,0,0); return Math.max(1, Math.round((t-n)/60000)); };
  openSheet(`<h3>⏸ ${esc(T("Suhbatni pauzaga qo'yish"))}</h3>
    <div class="phint" style="margin:0 0 8px">${esc(T("Chat yopilmaydi. Pauzadagi vaqt statistikaga kirmaydi. Belgilangan vaqt eslatma uchun; pauza operator davom ettirganda yoki mijoz yozganda tugaydi."))}</div>
    <div class="sublbl">${esc(T("Sabab"))}</div>
    <div class="tagpick" id="pz-reasons">${PAUSE_REASONS.map((r,i)=>`<button data-r="${esc(r)}" class="${i===1?"on":""}">${esc(T(r))}</button>`).join("")}<button data-custom style="border-style:dashed;color:var(--accent)">${esc(T("+ Boshqa"))}</button></div>
    <div class="sublbl">${esc(T("Qachon eslatilsin"))}</div>
    <div class="tagpick" id="pz-time"><button data-m="60">${esc(T("1 soat"))}</button><button data-m="180">${esc(T("3 soat"))}</button><button data-m="${tm()}" class="on">${esc(T("Ertaga 09:00"))}</button><button data-m="0">${esc(T("Muddatsiz"))}</button></div>
    <div class="sublbl">🔔 ${esc(T("Eslatma (faqat ish vaqtimda)"))}</div>
    <div class="tagpick" id="pz-rem"><button data-r2="30">${esc(T("har 30 daqiqa"))}</button><button data-r2="60" class="on">${esc(T("har 1 soat"))}</button><button data-r2="120">${esc(T("har 2 soat"))}</button><button data-r2="1440">${esc(T("har 1 kun"))}</button><button data-r2="0">${esc(T("kerak emas"))}</button></div>
    <div class="phint" style="margin:8px 0">${esc(T("Pauza ichki holat: mijozga bu haqda xabar yuborilmaydi."))}</div>
    <button class="sbtn" data-pzgo>⏸ ${esc(T("Pauzaga qo'yish"))}</button>`,
    el=>el.addEventListener("click", async e=>{
      const r = e.target.closest("#pz-reasons [data-r]"), t = e.target.closest("#pz-time [data-m]"), rm = e.target.closest("#pz-rem [data-r2]");
      if(rm){ el.querySelectorAll("#pz-rem button").forEach(b=>b.classList.toggle("on", b===rm)); haptic("sel"); return; }
      if(r){ el.querySelectorAll("#pz-reasons button").forEach(b=>b.classList.toggle("on", b===r)); haptic("sel"); return; }
      if(t){ el.querySelectorAll("#pz-time button").forEach(b=>b.classList.toggle("on", b===t)); haptic("sel"); return; }
      if(e.target.closest("[data-custom]")){ TGF.prompt(T("Pauza sababi"), [{ph: T("Masalan: shifokor bilan maslahatlashadi")}], ([v])=>{ if(!v) return;
        const b=document.createElement("button"); b.dataset.r=v; b.textContent=v; el.querySelector("[data-custom]").before(b);
        el.querySelectorAll("#pz-reasons button").forEach(x=>x.classList.toggle("on", x===b)); }); return; }
      if(e.target.closest("[data-pzgo]")){
        const reason = (el.querySelector("#pz-reasons .on")||{}).dataset?.r || "Pauza";
        const minutes = +((el.querySelector("#pz-time .on")||{}).dataset?.m || 0);
        const remind = +((el.querySelector("#pz-rem .on")||{}).dataset?.r2 || 0);
        const res = await POST("/api/pause", { order_id: CUR, reason, minutes, remind }).catch(()=>null);
        if(!res || !res.ok){ alert2((res&&res.error)||"Xatolik"); return; }
        closeSheet(); toast(res.info || "Pauza"); haptic("medium"); kickSync();
      }
    }));
}
async function resumePause(){
  const r = await POST("/api/pause", { order_id: CUR, resume: 1 }).catch(()=>null);
  if(!r || !r.ok){ alert2((r&&r.error)||"Xatolik"); return; }
  toast(r.info || "Suhbat davom ettirildi"); haptic("medium");
  if(CH && CH.pause){ CH.pause.paused = false; renderPausebar(); }
  kickSync(); if(!isTouch()) CMP.focus();
}

/* ============================================================
   DORI KATALOGI + «KELGANDA XABAR BERISH»
   ============================================================ */
const fmtMoney = n => String(Math.round(n||0)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
const SOM = () => T("so'm");
function prodRow(p, mode){
  const stock = p.in_stock ? `<span class="stk-on">${esc(T("bor"))}</span>` : `<span class="stk-off">${esc(T("yo'q"))}</span>`;
  return `<div class="prow" data-pid="${p.id}">
    <div class="pi">💊</div>
    <div class="pm"><div class="pn">${esc(p.name)}</div><div class="ps">${p.note?esc(p.note)+" · ":""}${p.unit?esc(p.unit)+" · ":""}${stock}${p.waits?` · 🔔 ${p.waits}`:""}</div></div>
    <div class="pp2">${p.price?fmtMoney(p.price)+" "+esc(SOM()):"—"}</div>
    <div class="pbtns">
      ${mode!=="bill"?`<button class="mini" data-pins="${p.id}" title="${esc(T("Matnga qo'shish"))}"><svg class="ic" viewBox="0 0 24 24" style="width:17px;height:17px"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg></button>`:""}
      <button class="mini acc" data-padd="${p.id}" title="${esc(T("Hisobga qo'shish"))}"><svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px"><path d="M12 5v14M5 12h14"/></svg></button>
      ${!p.in_stock?`<button class="mini" data-pwait="${p.id}" title="${esc(T("Kelganda xabar berish"))}">🔔</button>`:""}
    </div></div>`;
}
let _catT = null, _catItems = {};
function openCatalog(mode){
  openSheet(`<h3>💊 ${esc(T("Dori katalogi"))}</h3>
    <div class="searchbox" style="padding:0 16px 8px"><div class="in"><svg class="ic" viewBox="0 0 24 24" style="width:19px;height:19px;color:var(--hint)"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
      <input id="cat-q" placeholder="${esc(T("Dori nomi (lotin yoki kirill)"))}" autocomplete="off"></div></div>
    <div id="cat-list"><div class="spinner"></div></div>
    ${mode==="bill"?`<button class="sbtn ghost" data-backbill>← ${esc(T("Hisob-kitobga qaytish"))}</button>`:`<button class="sbtn ghost" data-openbill>🧾 ${esc(T("Hisob-kitob"))} <span id="cat-bn"></span></button>`}`,
    el=>{
      const inp = $("cat-q"); setTimeout(()=>{ if(!isTouch()) inp.focus(); }, 120);
      const load = async()=>{
        const r = await GET("/api/products", { q: inp.value.trim(), order_id: CUR || "" }).catch(()=>null);
        if(!r || !r.ok){ $("cat-list").innerHTML = `<div class="empty">${esc(T("Xatolik"))}</div>`; return; }
        const h = el.querySelector("h3"); if(h) h.textContent = "💊 " + T("Dori katalogi") + (r.branch ? " · 📍 " + r.branch : "");
        _catItems = {}; r.items.forEach(p=>_catItems[p.id]=p);
        $("cat-list").innerHTML = r.items.length ? r.items.map(p=>prodRow(p, mode)).join("")
          : `<div class="empty" style="padding:26px">${esc(r.total ? T("Topilmadi") : T("Katalog bo'sh. Admin panel → Sozlamalar → Dori katalogi orqali Excel yuklang."))}</div>`;
        updBillCount();
      };
      inp.oninput = ()=>{ clearTimeout(_catT); _catT = setTimeout(load, 220); };
      load();
      el.addEventListener("click", async e=>{
        const ins = e.target.closest("[data-pins]"), add = e.target.closest("[data-padd]"), wt = e.target.closest("[data-pwait]");
        if(e.target.closest("[data-backbill],[data-openbill]")) return openBill();
        if(ins){ const p=_catItems[+ins.dataset.pins]; closeSheet();
          CMP.focusEnd(); CMP.insertText(`${p.name} — ${p.price?fmtMoney(p.price)+" "+SOM():"?"} ${p.in_stock?"✅":"❌ "+T("hozircha yo'q")}\n`); return; }
        if(add){ const p=_catItems[+add.dataset.padd]; billAdd(p.name, p.price); add.classList.add("done"); haptic("light"); toast(T("Hisobga qo'shildi: {n}", {n: p.name}), 1400); updBillCount(); return; }
        if(wt){ const p=_catItems[+wt.dataset.pwait];
          if(!await confirm2(T("«{n}» kelganda mijozga avtomatik xabar yuborilsinmi?", {n: p.name}))) return;
          const r = await POST("/api/stock_wait", { order_id: CUR, product_id: p.id }).catch(()=>null);
          toast(r && r.ok ? (r.info||"OK") : ((r&&r.error)||"Xatolik")); if(r && r.ok){ wt.remove(); kickSync(); } }
      });
    });
}

/* ============================================================
   HISOB-KITOB YARATUVCHI
   ============================================================ */
function billKey(){ return "bill_" + (ST.op.id||"") + "_" + CUR; }
function getBill(){ try{ return JSON.parse(LS.get(billKey())||"null") || {items:[], delivery:0, note:""}; }catch(e){ return {items:[], delivery:0, note:""}; } }
function setBill(b){ LS.set(billKey(), JSON.stringify(b)); }
function billAdd(name, price){ const b = getBill(); const ex = b.items.find(i=>i.name===name); if(ex) ex.qty++; else b.items.push({name, qty:1, price: price||0}); setBill(b); }
function billTotal(b){ return b.items.reduce((s,i)=>s + (+i.qty||0)*(+i.price||0), 0) + (+b.delivery||0); }
function updBillCount(){ const e=$("cat-bn"); if(e){ const n=getBill().items.length; e.textContent = n ? "("+n+")" : ""; } }
function openBill(){
  if(!CUR) return;
  const b = getBill();
  const row = (it, i)=>`<div class="brow" data-i="${i}">
      <input class="bn" value="${esc(it.name)}" placeholder="${esc(T("Dori nomi"))}">
      <div class="bq"><button data-dec>−</button><span>${it.qty}</span><button data-inc>+</button></div>
      <input class="bp" inputmode="numeric" value="${it.price||""}" placeholder="${esc(T("narx"))}">
      <button class="bx" data-del>✕</button></div>`;
  openSheet(`<h3>🧾 ${esc(T("Hisob-kitob"))}</h3>
    <div id="bill-items">${b.items.map(row).join("") || `<div class="empty" style="padding:18px">${esc(T("Ro'yxat bo'sh — katalogdan qo'shing"))}</div>`}</div>
    <div style="display:flex;gap:8px;padding:4px 16px 8px"><button class="sbtn ghost" style="margin:0" data-fromcat>💊 ${esc(T("Katalogdan"))}</button><button class="sbtn ghost" style="margin:0" data-manual>✍️ ${esc(T("Qo'lda"))}</button></div>
    <div class="rng"><span>🚚 ${esc(T("Yetkazib berish"))}</span><input class="bp" id="bill-del" inputmode="numeric" value="${b.delivery||""}" placeholder="0" style="flex:1"></div>
    <input class="inp" id="bill-note" placeholder="${esc(T("Izoh (ixtiyoriy): masalan, 30 daqiqada tayyor"))}" value="${esc(b.note||"")}">
    <div class="btotal">${esc(T("Jami"))}: <b id="bill-sum">${fmtMoney(billTotal(b))} ${esc(SOM())}</b></div>
    <button class="sbtn" data-sendbill>${esc(T("Mijozga yuborish"))}</button>
    ${b.items.length?`<button class="sbtn ghost" data-clearbill style="color:var(--red)">${esc(T("Tozalash"))}</button>`:""}`,
    el=>{
      const sync = ()=>{ const bb = getBill();
        el.querySelectorAll(".brow").forEach(r=>{ const it = bb.items[+r.dataset.i]; if(!it) return;
          it.name = r.querySelector(".bn").value; it.price = +(r.querySelector(".bp").value.replace(/\D/g,"")) || 0; });
        bb.delivery = +($("bill-del").value.replace(/\D/g,"")) || 0; bb.note = $("bill-note").value;
        setBill(bb); $("bill-sum").textContent = fmtMoney(billTotal(bb)) + " " + SOM(); return bb; };
      el.addEventListener("input", sync);
      el.addEventListener("click", async e=>{
        const r = e.target.closest(".brow");
        if(r && e.target.closest("[data-inc],[data-dec],[data-del]")){
          const bb = sync(), i = +r.dataset.i;
          if(e.target.closest("[data-del]")) bb.items.splice(i,1);
          else bb.items[i].qty = Math.max(1, (+bb.items[i].qty||1) + (e.target.closest("[data-inc]")?1:-1));
          setBill(bb); haptic("sel"); return openBill();
        }
        if(e.target.closest("[data-fromcat]")){ sync(); return openCatalog("bill"); }
        if(e.target.closest("[data-manual]")){ const bb=sync(); bb.items.push({name:"", qty:1, price:0}); setBill(bb); openBill();
          setTimeout(()=>{ const ins=document.querySelectorAll(".brow .bn"); ins.length && ins[ins.length-1].focus(); }, 80); return; }
        if(e.target.closest("[data-clearbill]")){ if(!await confirm2(T("Hisob-kitob tozalansinmi?"))) return; LS.del(billKey()); return openBill(); }
        if(e.target.closest("[data-sendbill]")){
          const bb = sync(); bb.items = bb.items.filter(i=>i.name.trim());
          if(!bb.items.length){ toast(T("Ro'yxat bo'sh")); return; }
          if(!await confirm2(T("Mijozga {s} so'mlik hisob-kitob yuborilsinmi?", {s: fmtMoney(billTotal(bb))}))) return;
          const res = await POST("/api/cmd", { order_id: CUR, cmd: "billitems", items: bb.items, delivery: bb.delivery, note: bb.note }).catch(()=>null);
          if(!res || !res.ok){ alert2((res&&res.error)||"Xatolik"); return; }
          LS.del(billKey()); closeSheet(); toast(res.info||"Hisob-kitob yuborildi"); haptic("medium"); kickSync();
        }
      });
    });
}

/* ============================================================
   KUNLIK MAQSAD (profil)
   ============================================================ */
function renderGoal(g){
  const box = $("goalcard"); if(!box) return;
  if(!g || !g.goal){ box.innerHTML = ""; box.classList.add("hide"); return; }
  const pct = Math.min(100, Math.round(g.done / g.goal * 100)), C = 2*Math.PI*26;
  box.classList.remove("hide");
  box.innerHTML = `<svg width="64" height="64" viewBox="0 0 64 64"><circle cx="32" cy="32" r="26" fill="none" stroke="var(--sep)" stroke-width="7"/>
      <circle cx="32" cy="32" r="26" fill="none" stroke="${pct>=100?"var(--green)":"var(--accent)"}" stroke-width="7" stroke-linecap="round"
        stroke-dasharray="${(C*pct/100).toFixed(1)} ${C.toFixed(1)}" transform="rotate(-90 32 32)"/>
      <text x="32" y="37" text-anchor="middle" font-size="14" font-weight="700" fill="var(--text)">${pct}%</text></svg>
    <div><div style="font-weight:700;font-size:16px">${esc(T("Bugungi maqsad"))}: ${g.done} / ${g.goal}</div>
      <div class="sub">${esc(pct>=100 ? T("Barakalla! Maqsad bajarildi 🎉") : T("Yana {n} ta murojaat yakunlang", {n: g.goal - g.done}))}</div></div>`;
}

/* ============================================================
   BILDIRISHNOMALAR MARKAZI
   ============================================================ */
async function openNotifications(){
  const r=await GET("/api/notifications").catch(()=>null);
  if(!r||!r.ok){ toast("Bildirishnomalarni yuklab bo'lmadi"); return; }
  const icons={reminder:"⏰",unfinished:"⌛",new_orders:"📥",pause:"⏸",rating:"⭐",auto_close:"⏱",operator_message:"💬"};
  const unread=r.items.filter(n=>!n.read).length;
  const when=s=>{ if(!s)return ""; const d=s.slice(8,10)+"."+s.slice(5,7)+" · "+s.slice(11,16); return d; };
  const html=`<div class="shead notify-head"><div class="notify-head-icon">🔔</div><div><b>${esc(T("Bildirishnomalar"))}</b><div class="notify-summary">${unread?`${unread} ta yangi bildirishnoma`:"Hammasi o'qilgan"}</div></div><button data-close>✕</button></div>
    <div class="notify-tools"><button data-notify-all ${unread?"":"disabled"}>✓ Barchasini o'qilgan qilish</button><button data-notify-refresh>↻ Yangilash</button></div>
    <div class="notify-list">${r.items.length?r.items.map(n=>`
    <div class="notify-row ${n.read?"read":"unread"}" data-notify="${n.id}" data-kind="${esc(n.kind)}" ${n.order_id?`data-order="${n.order_id}"`:""}>
      <div class="notify-kind k-${esc(n.kind)}">${icons[n.kind]||"🔔"}</div><div class="notify-main"><div class="nt">${esc(n.title)}</div>
      ${n.body?`<div class="nb">${esc(n.body)}</div>`:""}<div class="ntime"><span class="notify-dot"></span>${esc(when(n.created_at))}${n.order_id?`<span> · #${n.order_id}</span>`:""}</div></div><span class="notify-chev">›</span></div>`).join(""):
      `<div class="empty"><div class="big">🔕</div>Bildirishnoma yo'q</div>`}</div>`;
  openSheet(html,el=>{
    el.querySelector("[data-close]").onclick=closeSheet;
    el.querySelector("[data-notify-refresh]").onclick=()=>openNotifications();
    el.querySelector("[data-notify-all]").onclick=async e=>{
      if(e.currentTarget.disabled)return;
      const rr=await POST("/api/notifications/read",{}).catch(()=>null); if(!rr||!rr.ok)return toast("Saqlanmadi");
      el.querySelectorAll(".notify-row.unread").forEach(x=>{x.classList.remove("unread");x.classList.add("read");});
      e.currentTarget.disabled=true; const s=el.querySelector(".notify-summary"); if(s)s.textContent="Hammasi o'qilgan";
      ST.notifyUnread=0; updateBadges();
    };
    el.addEventListener("click",async e=>{ const row=e.target.closest("[data-notify]"); if(!row)return;
      if(row.classList.contains("unread")){
        row.classList.remove("unread");row.classList.add("read"); ST.notifyUnread=Math.max(0,ST.notifyUnread-1);updateBadges();POST("/api/notifications/read",{id:+row.dataset.notify}).catch(()=>{});
        const left=el.querySelectorAll(".notify-row.unread").length, s=el.querySelector(".notify-summary"), all=el.querySelector("[data-notify-all]");
        if(s)s.textContent=left?`${left} ta yangi bildirishnoma`:"Hammasi o'qilgan"; if(all)all.disabled=!left;
      }
      const oid=+row.dataset.order||0; if(oid){ closeSheet(); openChat(oid,"Murojaat #"+oid,true); }
    });
  });
}

/* ============================================================
   OPERATORLARARO ICHKI CHAT
   ============================================================ */
let OPCHAT=null, opChatTimer=null;
async function openOperatorChat(id,name){
  if(!id)return; clearInterval(opChatTimer);
  OPCHAT={id,name:name||"Operator",messages:new Map(),order:[],max:0};
  $("opchat-name").textContent=OPCHAT.name; $("opchat-ava").textContent=ini(OPCHAT.name); $("opchat-ava").style.background=avaBg(OPCHAT.name);
  $("opmsgs").innerHTML='<div class="spinner"></div>'; $("opinput").value=""; show("opchat","in");
  await loadOperatorMessages(true); opChatTimer=setInterval(()=>loadOperatorMessages(false),3000);
  setTimeout(()=>$("opinput").focus(),80);
}
async function loadOperatorMessages(first){
  if(!OPCHAT)return; const id=OPCHAT.id;
  const r=await GET("/api/operator_messages",{peer_id:id,after:first?0:OPCHAT.max}).catch(()=>null);
  if(!r||!r.ok||!OPCHAT||OPCHAT.id!==id)return;
  (r.messages||[]).forEach(m=>{ if(!OPCHAT.messages.has(m.id))OPCHAT.order.push(m.id); OPCHAT.messages.set(m.id,m); OPCHAT.max=Math.max(OPCHAT.max,m.id); });
  if(first||r.messages.length)renderOperatorMessages();
  const peer=ST.operators.find(o=>o.id===id); if(peer)peer.unread=0;
  ST.operatorUnread=ST.operators.reduce((n,o)=>n+(+o.unread||0),0); updateBadges();
}
function renderOperatorMessages(){
  if(!OPCHAT)return; const box=$("opmsgs"), near=box.scrollHeight-box.scrollTop-box.clientHeight<90;
  box.innerHTML=OPCHAT.order.map(id=>OPCHAT.messages.get(id)).map(m=>`<div class="opmsg ${m.own?"own":""}">
    <div class="omt">${esc(m.text)}</div><div class="omm">${esc((m.created_at||"").slice(11,16))}${m.own&&m.read?" · ✓✓":""}</div></div>`).join("")||
    `<div class="empty"><div class="big">💬</div>${esc(OPCHAT.name)} bilan ichki yozishma.<br>Bu xabarlar mijozga ko'rinmaydi.</div>`;
  if(near||!box._drawn)box.scrollTop=box.scrollHeight; box._drawn=true;
}
function closeOperatorChat(){
  clearInterval(opChatTimer); opChatTimer=null; OPCHAT=null; show("app","fade");
  if(ST.folder==="operators")loadOperatorPeers();
}
async function sendOperator(){
  if(!OPCHAT)return; const input=$("opinput"), text=input.value.trim(); if(!text)return;
  const id=OPCHAT.id; input.value="";
  const r=await POST("/api/operator_send",{peer_id:id,text}).catch(()=>null);
  if(!r||!r.ok){ input.value=text; alert2((r&&r.error)||"Xabar yuborilmadi"); return; }
  await loadOperatorMessages(false); haptic("light");
}
$("opinput").addEventListener("keydown",e=>{ if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendOperator();} });

/* ============================================================
   KOMPYUTER: IKKI USTUNLI KO'RINISH (Telegram Desktop kabi)
   ============================================================ */
const WIDE_MQ = matchMedia("(min-width: 900px)");
function isWide(){ return WIDE_MQ.matches; }
WIDE_MQ.addEventListener && WIDE_MQ.addEventListener("change", ()=>{ if(CURSCREEN!=="login") show(CURSCREEN); });

/* ============================================================
   UMUMIY: data-act delegatsiyasi
   ============================================================ */
const ACTS = { toggleSearch, openChannel, quickEnter, showForm, forgetAcc, logout:()=>confirm2("Hisobdan chiqasizmi?").then(ok=>ok&&logout()),
  toggleStatus, openWallpaper, openMyTpls, openList, back: goBack, clientCard, chatSearch, chatMenu, fulfill, jumpPinned,
  unpin, openNote, openTags, toBottom: ()=>toBottom(), clearReply: ()=>clearReply(), attach, toggleQuick, toggleStickers,
  cancelRec, send, resume, csPrev, csNext, toggleFS, openPause, resumePause, openCatalog:()=>openCatalog(), openBill, closeMedia, sendMedia, closeViewer, viewerOpen, vPrev, vNext, vRotate, vZoomIn, vZoomOut, endSelect, copySel, deleteSelected, reopenChat,
  openNotifications, closeOperatorChat, sendOperator };
document.addEventListener("click", e=>{
  const t = e.target.closest("[data-act]"); if(!t) return;
  const f = ACTS[t.dataset.act]; if(!f) return;
  if(t.dataset.act==="unpin") e.stopPropagation();
  if(t.closest("#chatlist") && t.dataset.act==="openChannel") return;   // ro'yxat o'zi ishlaydi
  f(t, e);
});
document.querySelectorAll(".tabbar button").forEach(b=>b.onclick=()=>showTab(b.dataset.tab));
/* klaviatura yorliqlari */
document.addEventListener("keydown", e=>{
  if((e.ctrlKey||e.metaKey) && e.key.toLowerCase()==="c" && SELM && CURSCREEN==="chat" && !getSelection().toString()){ e.preventDefault(); copySel(); return; }
  if(e.key==="Escape" && SELM){ e.preventDefault(); endSelect(); return; }
  if((e.ctrlKey||e.metaKey) && e.key.toLowerCase()==="f" && CURSCREEN==="chat"){ e.preventDefault(); if($("csearch").classList.contains("hide")) chatSearch(); else $("cs-q").focus(); }
});

/* ---------- start ---------- */
setTheme(LS.get("theme")||"auto");
setPattern();
applyInsets();
(async ()=>{
  const s = await loadSession();
  if(s && s.id && s.token){ ST.op = s; enter(); }
  else { await renderSaved(); show("login","fade"); }
})();
