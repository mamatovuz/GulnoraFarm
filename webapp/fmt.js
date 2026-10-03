/* Gulnora Farm — Telegram uslubidagi matn formatlash (operator va admin panel uchun umumiy).
 *
 *  • Composer: contenteditable yozuv maydoni. Matnni belgilab sichqonchaning o'ng tugmasini bossangiz
 *    (yoki telefonda belgilasangiz) — Qalin, Kursiv, Tagiga chizilgan, Ustidan chizilgan, Monospace,
 *    Spoiler, Iqtibos, Havola menyusi chiqadi. Telegram Desktop'dagi tugmalar ham ishlaydi:
 *    Ctrl+B, Ctrl+I, Ctrl+U, Ctrl+Shift+X, Ctrl+Shift+M, Ctrl+Shift+P, Ctrl+Shift+., Ctrl+K, Ctrl+Shift+N.
 *  • Qo'lda yozilgan teglar ham ishlaydi: <b>Ozodbek</b>, hatto <b>Ozodbek<b> ham.
 *    Markdown ham: **qalin**, __kursiv__, ~~chizilgan~~, ||spoiler||, `kod`.
 *  • render(): serverdan kelgan Telegram-HTML'ni xavfsiz ko'rsatadi (faqat ruxsat etilgan teglar).
 */
(function(){
"use strict";
const TG = (window.Telegram && window.Telegram.WebApp) || null;

/* ---------------- yordamchilar ---------------- */
const ESC = {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"};
function esc(s){ return (s==null?"":String(s)).replace(/[&<>"']/g, c=>ESC[c]); }
function escT(s){ return (s==null?"":String(s)).replace(/[&<>]/g, c=>ESC[c]); }
const SAFE_HREF = /^(https?:\/\/|tg:\/\/|mailto:|tel:)/i;
const isTouch = () => matchMedia("(pointer:coarse)").matches;

/* ---------------- CSS ---------------- */
const css = `
.tgf-ed{outline:none;white-space:pre-wrap;word-break:break-word;overflow-y:auto;cursor:text}
.tgf-ed:empty::before{content:attr(data-ph);color:var(--hint);pointer-events:none}
.tgf-ed b,.tgf-ed strong{font-weight:700}
.tgf-ed code,.tgf-code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.92em;
  background:color-mix(in srgb,var(--accent) 12%,transparent);color:inherit;padding:1px 4px;border-radius:5px}
.tgf-ed blockquote,.tgf-q{margin:3px 0;padding:3px 8px 3px 10px;border-left:3px solid var(--accent);
  background:color-mix(in srgb,var(--accent) 9%,transparent);border-radius:4px 8px 8px 4px}
.tgf-pre{margin:4px 0;padding:8px 10px;border-radius:8px;overflow-x:auto;white-space:pre;
  background:color-mix(in srgb,var(--text) 7%,transparent);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.9em}
.tgf-ed .tgf-spoiler{background:color-mix(in srgb,var(--hint) 35%,transparent);border-radius:4px}
.tgf-sp{border-radius:4px;cursor:pointer;color:transparent;transition:color .25s,filter .25s;
  background-image:radial-gradient(circle,currentColor 0 .6px,transparent 1px);background-size:4px 4px;
  -webkit-text-fill-color:transparent;filter:blur(.4px);
  background-color:color-mix(in srgb,var(--hint) 35%,transparent)}
.tgf-sp.open{color:inherit;-webkit-text-fill-color:currentColor;background:color-mix(in srgb,var(--hint) 14%,transparent);filter:none;cursor:text}
.tgf-a{color:var(--link,#3390ec);text-decoration:none;word-break:break-all}
.tgf-a:hover{text-decoration:underline}
.tgf-menu{position:fixed;z-index:9999;min-width:220px;max-width:300px;padding:6px 0;border-radius:12px;
  background:var(--bg);color:var(--text);box-shadow:0 10px 38px rgba(0,0,0,.28),0 0 0 1px var(--sep);
  animation:tgfIn .14s ease-out;transform-origin:top left;user-select:none;-webkit-user-select:none;
  max-height:80vh;overflow-y:auto}
@keyframes tgfIn{from{opacity:0;transform:scale(.94)}to{opacity:1;transform:none}}
.tgf-mi{display:flex;align-items:center;gap:12px;padding:9px 16px;cursor:pointer;font-size:14.5px;line-height:1.2}
.tgf-mi:hover,.tgf-mi:active{background:color-mix(in srgb,var(--text) 7%,transparent)}
.tgf-mi.dis{opacity:.4;pointer-events:none}
.tgf-mi.danger{color:#e5484d}
.tgf-mi .k{margin-left:auto;color:var(--hint);font-size:12px;padding-left:18px}
.tgf-mi svg{width:20px;height:20px;flex-shrink:0;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round;opacity:.85}
.tgf-ms{height:1px;background:var(--sep);margin:5px 0}
.tgf-mh{padding:6px 16px 3px;font-size:12px;color:var(--hint);font-weight:600}
.tgf-bar{position:fixed;z-index:9998;display:flex;gap:2px;padding:4px;border-radius:12px;background:#1f2937;
  box-shadow:0 8px 24px rgba(0,0,0,.3);animation:tgfIn .12s ease-out}
.tgf-bar button{min-width:36px;height:34px;border:none;border-radius:8px;background:transparent;color:#fff;
  font-size:15px;cursor:pointer;padding:0 8px;font-family:inherit}
.tgf-bar button:active{background:rgba(255,255,255,.15)}
.tgf-dlg{position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;padding:16px;animation:tgfFade .15s}
@keyframes tgfFade{from{opacity:0}}
.tgf-dlg .box{width:100%;max-width:360px;background:var(--bg);color:var(--text);border-radius:16px;padding:18px;box-shadow:0 18px 50px rgba(0,0,0,.35)}
.tgf-dlg h4{margin:0 0 12px;font-size:17px}
.tgf-dlg input{width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid var(--sep);border-radius:10px;background:var(--sec);color:var(--text);font-size:15px;outline:none;margin-bottom:10px}
.tgf-dlg input:focus{border-color:var(--accent)}
.tgf-dlg .row{display:flex;justify-content:flex-end;gap:8px;margin-top:4px}
.tgf-dlg button{border:none;background:none;color:var(--accent);font-weight:600;font-size:15px;padding:9px 14px;border-radius:9px;cursor:pointer}
.tgf-dlg button.p{background:var(--accent);color:var(--accent-text,#fff)}
.tgf-lp{display:flex;gap:10px;margin:6px 0 2px;padding:6px 10px 6px 9px;border-left:3px solid var(--accent);
  border-radius:4px 8px 8px 4px;background:color-mix(in srgb,var(--accent) 8%,transparent);text-decoration:none;color:inherit;cursor:pointer;max-width:290px}
.tgf-lp .ico{width:34px;height:34px;border-radius:8px;flex-shrink:0;display:flex;align-items:center;justify-content:center;
  background:color-mix(in srgb,var(--accent) 18%,transparent);color:var(--accent);font-weight:700;font-size:15px;overflow:hidden}
.tgf-lp .ico img{width:22px;height:22px}
.tgf-lp .t1{font-weight:600;color:var(--accent);font-size:13.5px}
.tgf-lp .t2{font-size:12.5px;opacity:.75;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:220px}
`;
const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);

/* ---------------- ikonalar ---------------- */
const IC = {
  bold:'<path d="M7 5h6a3.5 3.5 0 0 1 0 7H7zM7 12h7a3.5 3.5 0 0 1 0 7H7z"/>',
  italic:'<path d="M14 5h-4M14 19h-4M15 5l-6 14"/>',
  underline:'<path d="M7 4v6a5 5 0 0 0 10 0V4M5 20h14"/>',
  strike:'<path d="M5 12h14M16 6.5C15 5 13.5 4.5 12 4.5c-2.5 0-4 1.3-4 3.2 0 1.5 1 2.4 3 3M8 17c1 1.6 2.6 2.5 4.3 2.5 2.4 0 4.2-1.3 4.2-3.4"/>',
  mono:'<path d="M8 8l-4 4 4 4M16 8l4 4-4 4"/>',
  spoiler:'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><path d="M3 3l18 18"/>',
  quote:'<path d="M7 7h4v4c0 3-2 5-4 5M14 7h4v4c0 3-2 5-4 5"/>',
  link:'<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
  clear:'<path d="M4 7V5h16v2M9 19h6M12 5v14M3 3l18 18"/>',
  cut:'<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4L8.1 15.9M14.5 14.5L20 20M8.1 8.1L12 12"/>',
  copy:'<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  paste:'<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/>',
  all:'<path d="M3 5h18M3 12h18M3 19h18"/>',
};
function icon(n){ return n && IC[n] ? `<svg viewBox="0 0 24 24">${IC[n]}</svg>` : (n||""); }

/* ---------------- kontekst menyu (umumiy) ---------------- */
let _menu = null;
function closeMenu(){ if(_menu){ _menu.remove(); _menu=null; } }
function menu(x, y, items){
  closeMenu();
  const m = document.createElement("div"); m.className = "tgf-menu";
  items.forEach(it=>{
    if(!it) return;
    if(it === "sep"){ m.insertAdjacentHTML("beforeend", '<div class="tgf-ms"></div>'); return; }
    if(it.header){ m.insertAdjacentHTML("beforeend", `<div class="tgf-mh">${escT(it.header)}</div>`); return; }
    const d = document.createElement("div");
    d.className = "tgf-mi" + (it.disabled?" dis":"") + (it.danger?" danger":"");
    d.innerHTML = icon(it.icon) + `<span>${escT(it.label)}</span>` + (it.key?`<span class="k">${escT(it.key)}</span>`:"");
    d.addEventListener("mousedown", e=>e.preventDefault());      // tanlov (selection) yo'qolmasin
    d.addEventListener("click", e=>{ e.stopPropagation(); closeMenu(); try{ it.onClick && it.onClick(); }catch(err){ console.error(err); } });
    m.appendChild(d);
  });
  if(window.I18N) window.I18N.translate(m);
  document.body.appendChild(m); _menu = m;
  const r = m.getBoundingClientRect(), W = innerWidth, H = innerHeight;
  let L = x, T = y;
  if(L + r.width > W - 8){ L = W - r.width - 8; }
  L = Math.max(8, L);
  if(T + r.height > H - 8){ T = Math.max(8, y - r.height); m.style.transformOrigin = "bottom left"; }
  m.style.left = L + "px"; m.style.top = T + "px";
  try{ TG && TG.HapticFeedback && TG.HapticFeedback.impactOccurred("light"); }catch(e){}
  return m;
}
["mousedown","touchstart"].forEach(ev=>document.addEventListener(ev, e=>{ if(_menu && !_menu.contains(e.target)) closeMenu(); }, {passive:true}));
document.addEventListener("keydown", e=>{ if(e.key==="Escape") closeMenu(); });
window.addEventListener("resize", closeMenu);
document.addEventListener("scroll", closeMenu, true);

/* ---------------- kichik dialog (havola) ---------------- */
function prompt2(title, fields, onOk){
  const d = document.createElement("div"); d.className = "tgf-dlg";
  d.innerHTML = `<div class="box"><h4>${escT(title)}</h4>${fields.map((f,i)=>
      `<input data-i="${i}" placeholder="${esc(f.ph||"")}" value="${esc(f.value||"")}">`).join("")}
    <div class="row"><button data-x>Bekor</button><button class="p" data-ok>Tayyor</button></div></div>`;
  if(window.I18N) window.I18N.translate(d);
  document.body.appendChild(d);
  const ins = [...d.querySelectorAll("input")];
  const done = ok=>{ d.remove(); if(ok) onOk(ins.map(i=>i.value.trim())); };
  d.querySelector("[data-x]").onclick = ()=>done(false);
  d.querySelector("[data-ok]").onclick = ()=>done(true);
  d.addEventListener("click", e=>{ if(e.target===d) done(false); });
  ins.forEach(i=>i.addEventListener("keydown", e=>{ if(e.key==="Enter"){ e.preventDefault(); done(true); } if(e.key==="Escape") done(false); }));
  setTimeout(()=>{ const f = ins.find(i=>!i.value) || ins[0]; f && f.focus(); }, 60);
}

/* ---------------- sanitize (Telegram-HTML) ---------------- */
const MAP = {b:"b",strong:"b",i:"i",em:"i",u:"u",ins:"u",s:"s",strike:"s",del:"s",code:"code",pre:"pre",
             "tg-spoiler":"tg-spoiler",spoiler:"tg-spoiler",blockquote:"blockquote",a:"a"};
/* Kirish: bizning teglarimiz + ekranlangan matn. Teglarni muvozanatlaydi, bir xil teg qayta ochilsa — yopadi. */
function balance(s){
  const out = [], stack = [];
  const re = /<(\/?)([a-zA-Z-]+)((?:\s+href="[^"<>]*")?)\s*>/g;
  let last = 0, m;
  const inCode = ()=>stack.includes("code")||stack.includes("pre");
  const close = t=>{ if(!stack.includes(t)) return; while(stack.length){ const x=stack.pop(); out.push(`</${x}>`); if(x===t) break; } };
  while((m = re.exec(s))){
    out.push(s.slice(last, m.index)); last = re.lastIndex;
    const isClose = !!m[1], tag = MAP[m[2].toLowerCase()];
    if(!tag || (inCode() && !(isClose && (tag==="code"||tag==="pre")))){ out.push(escT(m[0])); continue; }
    if(isClose){ close(tag); continue; }
    if(stack.includes(tag) && tag!=="a"){ close(tag); continue; }   // <b>Ozodbek<b>
    if(tag==="a"){
      const h = (m[3].match(/href="([^"]*)"/)||[])[1]||"";
      const hd = h.replace(/&amp;/g,"&");
      if(!SAFE_HREF.test(hd)){ out.push(escT(m[0])); continue; }
      stack.push("a"); out.push(`<a href="${esc(hd)}">`); continue;
    }
    stack.push(tag); out.push(`<${tag}>`);
  }
  out.push(s.slice(last));
  while(stack.length) out.push(`</${stack.pop()}>`);
  let r = out.join(""), prev;
  do{ prev = r; r = r.replace(/<(b|i|u|s|code|pre|tg-spoiler|blockquote)><\/\1>/g, ""); }while(prev !== r);
  return r;
}
function toPlain(h){ const t=document.createElement("textarea"); t.innerHTML=(h||"").replace(/<[^>]+>/g,""); return t.value; }
function hasMarkup(h){ return /<(b|i|u|s|code|pre|tg-spoiler|blockquote|a)\b/.test(h||""); }

/* matn bo'lagi: qo'lda yozilgan teglar saqlanadi, qolgani ekranlanadi + markdown */
const TYPED = /<\/?(?:b|strong|i|em|u|ins|s|strike|del|code|pre|tg-spoiler|spoiler|blockquote)>|<a\s+href="[^"<>]*">|<\/a>/gi;
function md(t){
  return t.replace(/\*\*([^*\n]+?)\*\*/g,"<b>$1</b>")
          .replace(/(^|[^_\w])__([^_\n]+?)__(?![_\w])/g,"$1<i>$2</i>")
          .replace(/~~([^~\n]+?)~~/g,"<s>$1</s>")
          .replace(/\|\|([^|\n]+?)\|\|/g,"<tg-spoiler>$1</tg-spoiler>")
          .replace(/`([^`\n]+?)`/g,"<code>$1</code>");
}
function textChunk(t, inCode){
  if(inCode) return escT(t);
  let out="", last=0, m; TYPED.lastIndex=0;
  while((m = TYPED.exec(t))){ out += md(escT(t.slice(last, m.index))) + m[0]; last = TYPED.lastIndex; }
  return out + md(escT(t.slice(last)));
}

/* contenteditable DOM -> Telegram-HTML */
function serialize(root){
  function walk(node, inCode){
    let out = "";
    node.childNodes.forEach((c, idx)=>{
      if(c.nodeType === 3){ out += textChunk(c.nodeValue.replace(/​/g,""), inCode); return; }
      if(c.nodeType !== 1) return;
      const tn = c.tagName.toLowerCase();
      if(tn === "br"){ if(!(idx === node.childNodes.length-1 && /^(div|p)$/i.test(node.tagName))) out += "\n"; return; }
      if(tn === "div" || tn === "p"){ if(out && !out.endsWith("\n")) out += "\n"; out += walk(c, inCode); return; }
      let tag = MAP[tn];
      if(tn === "span" && c.classList.contains("tgf-spoiler")) tag = "tg-spoiler";
      if(!tag && tn === "span"){
        const fw = c.style.fontWeight, fs = c.style.fontStyle, td = c.style.textDecoration||c.style.textDecorationLine||"";
        if(fw === "bold" || +fw >= 600) tag = "b"; else if(fs === "italic") tag = "i";
        else if(td.includes("line-through")) tag = "s"; else if(td.includes("underline")) tag = "u";
      }
      if(!tag){ out += walk(c, inCode); return; }
      const inner = walk(c, inCode || tag==="code" || tag==="pre");
      if(tag === "a"){
        const h = c.getAttribute("href")||"";
        out += SAFE_HREF.test(h) ? `<a href="${esc(h)}">${inner}</a>` : inner; return;
      }
      out += `<${tag}>${inner}</${tag}>`;
    });
    return out;
  }
  return balance(walk(root, false)).replace(/^\n+|\n+$/g, "");
}

/* ---------------- render: Telegram-HTML -> xavfsiz HTML ---------------- */
const URL_RE = /((?:https?:\/\/|www\.)[^\s<>"']+[^\s<>"'.,;:!?)\]}])|(\+?998[\s-]?\(?\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2})/gi;
function linkify(text){
  // text — ekranlanMAGAN oddiy matn
  let out = "", last = 0, m; URL_RE.lastIndex = 0; const s = String(text||"");
  while((m = URL_RE.exec(s))){
    out += escT(s.slice(last, m.index)); last = URL_RE.lastIndex;
    if(m[1]){ const href = /^www\./i.test(m[1]) ? "https://"+m[1] : m[1];
      out += `<a class="tgf-a" href="${esc(href)}" target="_blank" rel="noopener noreferrer">${escT(m[1])}</a>`; }
    else { const tel = m[2].replace(/[^\d+]/g,"");
      out += `<a class="tgf-a" href="tel:${esc(tel.startsWith("+")?tel:"+"+tel)}">${escT(m[2])}</a>`; }
  }
  return out + escT(s.slice(last));
}
function render(html, plain){
  if(!html) return linkify(plain||"");
  const t = document.createElement("template"); t.innerHTML = html;
  function walk(node, inLink){
    let out = "";
    node.childNodes.forEach(c=>{
      if(c.nodeType === 3){ out += inLink ? escT(c.nodeValue) : linkify(c.nodeValue); return; }
      if(c.nodeType !== 1) return;
      const tn = c.tagName.toLowerCase();
      if(tn === "br"){ out += "\n"; return; }
      const sp = tn === "tg-spoiler" || (tn === "span" && c.classList.contains("tg-spoiler"));
      const tag = sp ? "sp" : MAP[tn];
      if(tag === "a"){
        const h = c.getAttribute("href")||"";
        out += SAFE_HREF.test(h) ? `<a class="tgf-a" href="${esc(h)}" target="_blank" rel="noopener noreferrer">${walk(c,true)}</a>` : walk(c, inLink);
      } else if(tag === "sp") out += `<span class="tgf-sp" onclick="event.stopPropagation();this.classList.add('open')">${walk(c,inLink)}</span>`;
      else if(tag === "pre") out += `<pre class="tgf-pre">${escT(c.textContent)}</pre>`;
      else if(tag === "code") out += `<code class="tgf-code">${escT(c.textContent)}</code>`;
      else if(tag === "blockquote") out += `<blockquote class="tgf-q">${walk(c,inLink)}</blockquote>`;
      else if(tag) out += `<${tag}>${walk(c,inLink)}</${tag}>`;
      else out += walk(c, inLink);
    });
    return out;
  }
  return walk(t.content, false);
}
function firstUrl(text){ const m = String(text||"").match(/(?:https?:\/\/|www\.)[^\s<>"']+[^\s<>"'.,;:!?)\]}]/i); return m ? (/^www\./i.test(m[0])?"https://"+m[0]:m[0]) : ""; }
/* Havola kartasi (Telegram link preview uslubida) */
function linkCard(url){
  let u; try{ u = new URL(url); }catch(e){ return ""; }
  const host = u.hostname.replace(/^www\./,"");
  const known = {"t.me":"Telegram","telegram.me":"Telegram","youtube.com":"YouTube","youtu.be":"YouTube",
    "instagram.com":"Instagram","google.com":"Google","maps.google.com":"Google Maps","yandex.uz":"Yandex","yandex.ru":"Yandex"};
  const title = known[host] || (host.charAt(0).toUpperCase()+host.slice(1));
  const path = decodeURIComponent((u.pathname+u.search).replace(/\/$/,"")) || "/";
  return `<a class="tgf-lp" href="${esc(url)}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">
    <div class="ico">${escT(title.charAt(0))}</div>
    <div style="min-width:0"><div class="t1">${escT(title)}</div><div class="t2">${escT(host+(path!=="/"?path:""))}</div></div></a>`;
}
/* Telegram ichida havolalarni to'g'ri ochish */
document.addEventListener("click", e=>{
  const a = e.target.closest && e.target.closest("a.tgf-a, a.tgf-lp");
  if(!a || !TG) return;
  const h = a.getAttribute("href")||"";
  if(/^https?:/i.test(h)){
    e.preventDefault();
    try{ /^https?:\/\/(t|telegram)\.me\//i.test(h) ? TG.openTelegramLink(h) : TG.openLink(h); }catch(err){ window.open(h, "_blank"); }
  }
}, true);

/* ---------------- Composer ---------------- */
const KINDS = {
  bold:{tag:"B", m:el=>/^(B|STRONG)$/.test(el.tagName)},
  italic:{tag:"I", m:el=>/^(I|EM)$/.test(el.tagName)},
  underline:{tag:"U", m:el=>/^(U|INS)$/.test(el.tagName)},
  strike:{tag:"S", m:el=>/^(S|STRIKE|DEL)$/.test(el.tagName)},
  mono:{tag:"CODE", m:el=>el.tagName==="CODE"},
  spoiler:{tag:"SPAN", cls:"tgf-spoiler", m:el=>el.tagName==="SPAN"&&el.classList.contains("tgf-spoiler")},
  quote:{tag:"BLOCKQUOTE", m:el=>el.tagName==="BLOCKQUOTE"},
  link:{tag:"A", m:el=>el.tagName==="A"},
};
const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform||"");
const MOD = IS_MAC ? "⌘" : "Ctrl+";
const FMT_ITEMS = [
  ["bold","Qalin",MOD+"B"],["italic","Kursiv",MOD+"I"],["underline","Tagiga chizilgan",MOD+"U"],
  ["strike","Ustidan chizilgan",MOD+"Shift+X"],["mono","Monospace",MOD+"Shift+M"],
  ["spoiler","Spoiler (yashirin)",MOD+"Shift+P"],["quote","Iqtibos",MOD+"Shift+."],
  ["link","Havola qo'shish",MOD+"K"],["clear","Oddiy matn",MOD+"Shift+N"],
];

function Composer(el, opts){
  opts = opts || {};
  el.setAttribute("contenteditable","true");
  el.classList.add("tgf-ed");
  el.setAttribute("role","textbox"); el.setAttribute("aria-multiline","true");
  if(opts.placeholder) el.dataset.ph = opts.placeholder;
  const api = {};
  const fire = ()=>{
    // bo'sh qolsa (<br> qoldig'i) — placeholder ko'rinsin
    if(!el.textContent.replace(/​/g,"").length && el.innerHTML !== "") el.innerHTML = "";
    normalize(); opts.onInput && opts.onInput(api); };

  function selRange(){
    const s = getSelection(); if(!s.rangeCount) return null;
    const r = s.getRangeAt(0);
    return el.contains(r.commonAncestorContainer) ? r : null;
  }
  function hasSel(){ const r = selRange(); return !!(r && !r.collapsed && r.toString().length); }
  function closestKind(node, kind){
    while(node && node !== el){ if(node.nodeType===1 && KINDS[kind].m(node)) return node; node = node.parentNode; }
    return null;
  }
  function unwrap(n){ const p = n.parentNode; while(n.firstChild) p.insertBefore(n.firstChild, n); p.removeChild(n); p.normalize(); }
  function selectNode(n){ const r = document.createRange(); r.selectNodeContents(n); const s=getSelection(); s.removeAllRanges(); s.addRange(r); }

  function apply(kind, href){
    el.focus();
    const r = selRange(); if(!r) return;
    if(kind === "clear"){
      if(r.collapsed) return;
      const txt = r.toString(); r.deleteContents();
      const tn = document.createTextNode(txt); r.insertNode(tn);
      // atrofdagi barcha format teglaridan tashqariga chiqaramiz
      let guard = 0;
      while(tn.parentNode && tn.parentNode !== el && guard++ < 20){
        const par = tn.parentNode;
        if(/^(DIV|P)$/.test(par.tagName)) break;
        splitOut(tn, par);
      }
      selectNode(tn); fire(); return;
    }
    if(kind === "link" && !href){
      const pre = r.toString(); const saved = r.cloneRange();
      const ex = closestKind(r.commonAncestorContainer, "link");
      prompt2("Havola", [{ph:"Matn", value: ex ? ex.textContent : pre}, {ph:"https://...", value: ex ? ex.getAttribute("href") : (/^(https?:|www\.)/i.test(pre)?pre:"")}], vals=>{
        let [t, u] = vals; if(!u) { if(ex) { unwrap(ex); fire(); } return; }
        if(!/^(https?:\/\/|tg:\/\/|mailto:|tel:)/i.test(u)) u = "https://" + u.replace(/^\/+/,"");
        el.focus(); const s=getSelection(); s.removeAllRanges(); s.addRange(saved);
        if(ex){ ex.setAttribute("href", u); if(t) ex.textContent = t; fire(); return; }
        const a = document.createElement("a"); a.href = u; a.textContent = t || u;
        saved.deleteContents(); saved.insertNode(a);
        const after = document.createTextNode("​"); a.after(after);
        const r2 = document.createRange(); r2.setStartAfter(after); r2.collapse(true); s.removeAllRanges(); s.addRange(r2);
        fire();
      });
      return;
    }
    if(r.collapsed) return;
    const ex = closestKind(r.commonAncestorContainer, kind);
    if(ex){ unwrap(ex); fire(); return; }       // qayta bosilsa — formatni olib tashlaydi
    const K = KINDS[kind];
    const frag = r.extractContents();
    frag.querySelectorAll && [...frag.querySelectorAll("*")].forEach(n=>{ if(K.m(n)) unwrap(n); });
    const w = document.createElement(K.tag); if(K.cls) w.className = K.cls; if(href) w.href = href;
    w.appendChild(frag); r.insertNode(w);
    selectNode(w); fire();
  }
  function splitOut(node, parent){
    // node'ni parent elementidan tashqariga chiqaradi (parent ikkiga bo'linadi)
    if(!parent || parent === el || !parent.parentNode) return;
    const right = parent.cloneNode(false);
    while(node.nextSibling) right.appendChild(node.nextSibling);
    parent.after(node); node.after(right);
    if(!right.textContent) right.remove();
    if(!parent.textContent) parent.remove();
  }

  /* Qo'lda yozilgan <b>matn</b> (yoki <b>matn<b>) darhol formatga aylanadi */
  const LIVE = /<(b|i|u|s|code|spoiler|tg-spoiler)>([^<>]+?)<\/?\1>/i;
  function normalize(){
    const s = getSelection();
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let n, hit = null;
    while((n = walker.nextNode())){ if(LIVE.test(n.nodeValue) && !closestKind(n,"mono")){ hit = n; break; } }
    if(!hit) return;
    const m = hit.nodeValue.match(LIVE);
    const before = hit.nodeValue.slice(0, m.index), after = hit.nodeValue.slice(m.index + m[0].length);
    const t = m[1].toLowerCase();
    const map = {b:"B",i:"I",u:"U",s:"S",code:"CODE",spoiler:"SPAN","tg-spoiler":"SPAN"};
    const w = document.createElement(map[t]); if(map[t]==="SPAN") w.className = "tgf-spoiler";
    w.textContent = m[2];
    const tail = document.createTextNode(after || "​");
    const p = hit.parentNode;
    p.insertBefore(document.createTextNode(before), hit); p.insertBefore(w, hit); p.insertBefore(tail, hit); p.removeChild(hit);
    const r = document.createRange(); r.setStart(tail, after ? 0 : 1); r.collapse(true); s.removeAllRanges(); s.addRange(r);
    normalize();
  }

  /* klaviatura */
  el.addEventListener("keydown", e=>{
    const mod = e.ctrlKey || e.metaKey;
    if(mod){
      const k = e.key.toLowerCase(); let kind = null;
      if(!e.shiftKey && k==="b") kind="bold";
      else if(!e.shiftKey && k==="i") kind="italic";
      else if(!e.shiftKey && k==="u") kind="underline";
      else if(!e.shiftKey && k==="k") kind="link";
      else if(e.shiftKey && (k==="x"||e.code==="KeyX")) kind="strike";
      else if(e.shiftKey && (k==="m"||e.code==="KeyM")) kind="mono";
      else if(e.shiftKey && (k==="p"||e.code==="KeyP")) kind="spoiler";
      else if(e.shiftKey && (k==="n"||e.code==="KeyN")) kind="clear";
      else if(e.shiftKey && (e.code==="Period"||k===">"||k===".")) kind="quote";
      if(kind){ e.preventDefault(); apply(kind); return; }
    }
    if(e.key === "Enter" && !e.shiftKey && !e.isComposing && opts.onEnter && !(isTouch() && opts.touchEnterNewline)){
      e.preventDefault(); opts.onEnter(api); return;
    }
    if(e.key === "Enter" && (e.shiftKey || (isTouch() && opts.touchEnterNewline))){
      e.preventDefault(); insertText("\n");
    }
    if(opts.onKey) opts.onKey(e, api);
  });
  function insertText(t){
    const r = selRange(); if(!r){ el.focus(); }
    const rr = selRange(); if(!rr) return;
    rr.deleteContents();
    const tn = document.createTextNode(t); rr.insertNode(tn);
    // oxirida yangi qator bo'lsa, ko'rinishi uchun qo'shimcha belgi
    if(t === "\n" && !tn.nextSibling){ tn.after(document.createTextNode("​")); }
    const r2 = document.createRange(); r2.setStartAfter(tn); r2.collapse(true);
    const s=getSelection(); s.removeAllRanges(); s.addRange(r2);
    fire();
  }
  el.addEventListener("input", fire);
  /* qo'yish: faqat matn (rasm bo'lsa — tashqi handler) */
  el.addEventListener("paste", e=>{
    const items = (e.clipboardData && e.clipboardData.items) || [];
    for(const it of items){ if(it.type && it.type.indexOf("image")===0){ if(opts.onPasteImage){ e.preventDefault(); opts.onPasteImage(it.getAsFile()); } return; } }
    const t = e.clipboardData && e.clipboardData.getData("text/plain");
    if(t != null){ e.preventDefault(); insertText(t); }
  });
  el.addEventListener("drop", e=>{ if(e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length && opts.onDropFiles){ e.preventDefault(); opts.onDropFiles(e.dataTransfer.files); } });

  /* o'ng tugma — formatlash menyusi */
  el.addEventListener("contextmenu", e=>{
    e.preventDefault();
    const sel = hasSel();
    const items = [{header: sel ? "Formatlash" : "Formatlash uchun matnni belgilang"}];
    FMT_ITEMS.forEach(([k,l,key])=>items.push({icon:k, label:l, key, disabled: !sel && k!=="link", onClick:()=>apply(k)}));
    items.push("sep");
    items.push({icon:"cut", label:"Kesish", key:MOD+"X", disabled:!sel, onClick:()=>{ document.execCommand("cut"); fire(); }});
    items.push({icon:"copy", label:"Nusxa olish", key:MOD+"C", disabled:!sel, onClick:()=>document.execCommand("copy")});
    items.push({icon:"paste", label:"Qo'yish", key:MOD+"V", onClick:async()=>{
      try{ const t = await navigator.clipboard.readText(); if(t) insertText(t); }catch(err){ TG && TG.showAlert ? TG.showAlert("Qo'yish uchun "+MOD+"V bosing") : 0; } }});
    items.push({icon:"all", label:"Hammasini belgilash", key:MOD+"A", onClick:()=>{ el.focus(); selectNode(el); }});
    menu(e.clientX, e.clientY, items);
  });

  /* telefon: matn belgilansa — tepada suzuvchi formatlash paneli */
  let bar = null;
  function hideBar(){ if(bar){ bar.remove(); bar=null; } }
  document.addEventListener("selectionchange", ()=>{
    if(!isTouch()){ return; }
    clearTimeout(api._st);
    api._st = setTimeout(()=>{
      if(!hasSel()){ hideBar(); return; }
      const rect = selRange().getBoundingClientRect();
      if(!bar){
        bar = document.createElement("div"); bar.className = "tgf-bar";
        [["bold","<b>B</b>"],["italic","<i>I</i>"],["underline","<u>U</u>"],["strike","<s>S</s>"],
         ["mono","<code style='font-size:13px'>&lt;/&gt;</code>"],["spoiler","▒"],["quote","❝"],["link","🔗"],["clear","✕"]]
          .forEach(([k,h])=>{ const b=document.createElement("button"); b.innerHTML=h; b.type="button";
            b.addEventListener("mousedown", e=>e.preventDefault()); b.addEventListener("touchstart", e=>e.preventDefault(), {passive:false});
            b.addEventListener("touchend", e=>{ e.preventDefault(); apply(k); hideBar(); });
            b.addEventListener("click", ()=>{ apply(k); hideBar(); }); bar.appendChild(b); });
        document.body.appendChild(bar);
      }
      const bw = bar.offsetWidth, bh = bar.offsetHeight;
      let L = Math.min(Math.max(8, rect.left + rect.width/2 - bw/2), innerWidth - bw - 8);
      let T = rect.top - bh - 12; if(T < 8) T = rect.bottom + 12;
      bar.style.left = L+"px"; bar.style.top = T+"px";
    }, 250);
  });
  el.addEventListener("blur", ()=>setTimeout(()=>{ if(!hasSel()) hideBar(); }, 150));

  api.el = el;
  api.apply = apply;
  api.insertText = insertText;
  api.getHTML = ()=>serialize(el);
  api.getText = ()=>toPlain(serialize(el)).trim();
  api.isEmpty = ()=>!el.textContent.replace(/[​\s]/g,"").length;
  api.clear = ()=>{ el.innerHTML = ""; hideBar(); opts.onInput && opts.onInput(api); };
  api.setHTML = (h)=>{
    el.innerHTML = "";
    if(h){
      const t = document.createElement("template"); t.innerHTML = h;
      t.content.querySelectorAll("tg-spoiler").forEach(sp=>{ const s=document.createElement("span"); s.className="tgf-spoiler"; s.innerHTML=sp.innerHTML; sp.replaceWith(s); });
      t.content.querySelectorAll("*").forEach(n=>{ if(!/^(B|I|U|S|CODE|PRE|SPAN|BLOCKQUOTE|A|BR)$/.test(n.tagName)) n.replaceWith(...n.childNodes); else [...n.attributes].forEach(a=>{ if(!(a.name==="href"&&n.tagName==="A") && !(a.name==="class"&&n.tagName==="SPAN")) n.removeAttribute(a.name); }); });
      el.appendChild(t.content);
    }
    api.focusEnd(); opts.onInput && opts.onInput(api);
  };
  api.setText = (t)=>{ el.textContent = t||""; api.focusEnd(); opts.onInput && opts.onInput(api); };
  api.focus = ()=>el.focus();
  api.focusEnd = ()=>{ el.focus(); const r=document.createRange(); r.selectNodeContents(el); r.collapse(false); const s=getSelection(); s.removeAllRanges(); s.addRange(r); };
  api.setPlaceholder = p=>{ el.dataset.ph = p; };
  return api;
}

window.TGF = { esc, escT, render, linkify, firstUrl, linkCard, sanitize: balance, serialize, toPlain, hasMarkup,
               Composer, menu, closeMenu, prompt: prompt2, icon };
})();
