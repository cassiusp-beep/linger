/* Linger UI: a four-step story in plain language. Data comes from api/cached (or cache.js offline). */
const NS = "http://www.w3.org/2000/svg";
const STAY = new Set(["stop", "stand", "sit", "linger"]);
const ZONES = ["TL","TC","TR","ML","C","MR","BL","BC","BR"];
const POS = {TL:"top left", TC:"top middle", TR:"top right", ML:"left middle", C:"center", MR:"right middle", BL:"bottom left", BC:"bottom middle", BR:"bottom right"};
const PAST = {walk:"walked by", stop:"stopped", stand:"stood", sit:"sat", linger:"lingered", path_change:"changed path",
  bus_arrive:"arrived", crosswalk_block:"blocked the crosswalk", vehicle_stop:"stopped"};
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const C = {ink:"#15201C", muted:"#5B6964", link:"#D2731A", future:"#2E62C9", night:"#ECEBF8", green:"#0E6B4F"};

let D, byEv = {}, bySeg = {}, ZNAME = {}, ZFEAT = {};
let sel = {kind: null, id: null}, light = "all", showAll = false;

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const el = (tag, attrs = {}, parent) => { const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); if (parent) parent.appendChild(n); return n; };
const cap = (s) => s ? s[0].toUpperCase() + s.slice(1) : s;
const clock = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
const isVeh = (e) => e.actor === "vehicle";
const camEvents = () => (D.events || []).filter(e => e.camera_id === D.camera_id);

/* ---------- plain-language naming ---------- */
function nameZones() {
  const counts = {};
  camEvents().forEach(e => { if (e.near) { counts[e.zone] = counts[e.zone] || {}; counts[e.zone][e.near] = (counts[e.zone][e.near] || 0) + 1; } });
  const claims = [];
  for (const [z, m] of Object.entries(counts)) for (const [f, n] of Object.entries(m)) claims.push([n, z, f]);
  claims.sort((a, b) => b[0] - a[0]);
  const usedF = new Set(); ZFEAT = {};
  for (const [, z, f] of claims) if (!ZFEAT[z] && !usedF.has(f)) { ZFEAT[z] = f; usedF.add(f); }
  ZONES.forEach(z => ZNAME[z] = ZFEAT[z] ? `the ${ZFEAT[z]}` : `the ${POS[z]} area`);
}
function plain(text) {
  if (!text) return "";
  let t = text;
  ZONES.filter(z => z !== "C").forEach(z => {
    const f = ZFEAT[z];
    const re = f ? new RegExp(`\\b${z}\\b(,)?( (beside|by|near) the ${f})?`, "g") : new RegExp(`\\b${z}\\b`, "g");
    t = t.replace(re, (m, comma) => ZNAME[z] + (comma || ""));
  });
  t = t.replace(/\b(at|over|by) C\b/g, (m, w) => `${w} ${ZNAME.C}`);
  return t.replace(/\bthe the\b/g, "the");
}
function who(e) { return isVeh(e) ? `A ${e.vehicle || "vehicle"}` : (e.count === 1 ? "1 person" : `${e.count} people`); }
function say(e) {
  const place = e.behavior === "crosswalk_block" ? "" : ` at ${ZNAME[e.zone]}`;
  return `${who(e)} ${PAST[e.behavior] || e.behavior}${place}`;
}
function gapText(dt) { const s = Math.round(dt); return s <= 1 ? "Right after" : `${s} seconds later`; }

/* ---------- data ---------- */
async function load() {
  try { const r = await fetch("api/cached"); if (!r.ok) throw 0; return await r.json(); }
  catch { return window.LINGER_CACHE; }
}
function index() {
  byEv = Object.fromEntries(D.events.map(e => [e.id, e]));
  bySeg = Object.fromEntries(D.segments.map(s => [s.segment_id, s]));
  nameZones();
}
function stays(filter = light) {
  const out = {};
  camEvents().filter(e => STAY.has(e.behavior) && (filter === "all" || e.light === filter))
    .forEach(e => out[e.zone] = (out[e.zone] || 0) + e.count);
  return out;
}

/* ---------- step 1: where people stop ---------- */
function drawStreet() {
  const svg = $("#street"); svg.innerHTML = "";
  const playing = $(".street")?.classList.contains("playing");
  const st = stays(), max = Math.max(1, ...Object.values(st));
  const hz = highlightZones();
  ZONES.forEach((z, i) => {
    const x = (i % 3) * 640 / 3, y = Math.floor(i / 3) * 120, w = 640 / 3, h = 120, v = (st[z] || 0) / max;
    // When footage is on, keep zone tint light so the video shows through the 3x3 boxes.
    const tint = playing ? (0.04 + 0.14 * v) : (0.06 + 0.62 * v);
    el("rect", {class: "zonefill", x, y, width: w, height: h, fill: "#E58A2E", "fill-opacity": tint.toFixed(2)}, svg);
    el("rect", {x: x + .5, y: y + .5, width: w - 1, height: h - 1, fill: "none", stroke: "#FFFFFF", "stroke-opacity": playing ? .55 : .35}, svg);
    if (hz.zones.has(z)) el("rect", {x: x + 3, y: y + 3, width: w - 6, height: h - 6, rx: 6, fill: "none", stroke: "#FFFFFF", "stroke-width": 4}, svg);
    const label = ZFEAT[z] ? cap(ZFEAT[z]) : "";
    if (label) {
      const t = el("text", {x: x + 12, y: y + 24, fill: "#FFFFFF", "font-size": 15, "font-weight": 700,
        "paint-order": "stroke", stroke: "rgba(0,0,0,.55)", "stroke-width": 3}, svg); t.textContent = label;
    }
    if (st[z]) { const c = el("text", {x: x + w - 12, y: y + h - 12, fill: "#FFFFFF", "font-size": 14, "font-weight": 800, "text-anchor": "end",
      "paint-order": "stroke", stroke: "rgba(0,0,0,.55)", "stroke-width": 3}, svg);
      c.textContent = `${st[z]} ${st[z] === 1 ? "stop" : "stops"}`; }
  });
  hz.events.forEach((e, j) => {
    const i = ZONES.indexOf(e.zone), cx = (i % 3 + .5) * 640 / 3, cy = (Math.floor(i / 3) + .5) * 120;
    if (isVeh(e)) {
      el("rect", {x: cx - 26, y: cy - 30, width: 52, height: 24, rx: 6, fill: "#FFFFFF"}, svg);
      const t = el("text", {x: cx, y: cy - 13, fill: C.ink, "font-size": 12, "font-weight": 700, "text-anchor": "middle"}, svg); t.textContent = e.vehicle || "vehicle";
      return;
    }
    for (let p = 0; p < Math.min(e.count, 6); p++) {
      el("circle", {cx: cx - (Math.min(e.count, 6) - 1) * 9 + p * 18, cy: cy + 14 + j * 4, r: 7,
        fill: STAY.has(e.behavior) ? "#FFFFFF" : "none", stroke: "#FFFFFF", "stroke-width": 2.5}, svg);
    }
  });
}
function drawRank() {
  const st = stays(), nightSt = stays("night"), total = Object.values(st).reduce((a, b) => a + b, 0);
  const rows = Object.entries(st).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const max = Math.max(1, ...rows.map(r => r[1]));
  $("#rank").innerHTML = rows.map(([z, n]) => {
    const nn = nightSt[z] || 0;
    const sub = light === "all" ? `${POS[z]} of the view${nn ? `, ${nn} at night` : ""}` : `${POS[z]} of the view`;
    return `<li data-zone="${z}" class="${sel.kind === "zone" && sel.id === z ? "on" : ""}" tabindex="0">
      <span class="nm">${esc(cap(ZNAME[z]))}</span><span class="ct">${n}</span>
      <span class="bar2"><i style="width:${(n / max * 100).toFixed(0)}%"></i></span><span class="sub">${esc(sub)}</span></li>`;
  }).join("") || `<li>No stops ${light === "night" ? "at night" : "in the daytime"} on this camera.</li>`;
  document.querySelectorAll("#rank li[data-zone]").forEach(li => {
    li.onclick = () => select("zone", li.dataset.zone);
    li.onkeydown = (k) => { if (k.key === "Enter") select("zone", li.dataset.zone); };
  });
  if (rows.length) {
    const [z, n] = rows[0], nn = stays("night")[z] || 0, all = stays("all")[z] || 0;
    const when = light === "all" ? "" : light === "night" ? " at night" : " in the daytime";
    const nightPct = all ? Math.round(nn / all * 100) : 0;
    $("#s1lede").textContent = `Most stopping${when} happens at ${ZNAME[z]}: ${n} of ${total} stops.` +
      (light === "all" && nightPct > 0 ? ` ${nightPct}% of those are at night.` : "");
  } else {
    $("#s1lede").textContent = "No stops found on this camera yet.";
  }
}

/* ---------- step 2: what tends to happen next ---------- */
function keyPairs() {
  const L = D.links || [], pick = [], usedZ = new Set();
  if (!L.length) return pick;
  const add = (l) => { if (l && byEv[l.from] && byEv[l.to] && !pick.includes(l)) { pick.push(l); usedZ.add(byEv[l.from].zone + byEv[l.to].zone); } };
  add(L.find(l => l.id === D.selected_link));
  add([...L].filter(l => byEv[l.from] && byEv[l.to] && isVeh(byEv[l.from]) && byEv[l.to].behavior === "path_change").sort((a, b) => b.score - a.score)[0]);
  add([...L].filter(l => byEv[l.from] && byEv[l.to] && STAY.has(byEv[l.from].behavior) && STAY.has(byEv[l.to].behavior) && !usedZ.has(byEv[l.from].zone + byEv[l.to].zone))
    .sort((a, b) => b.score - a.score)[0]);
  return pick.slice(0, 3);
}
function drawPairs() {
  if (!(D.links || []).length) {
    $("#s2lede").textContent = "Not enough connected moments here yet to show a pattern.";
    $("#pairs").innerHTML = "";
    return;
  }
  $("#s2lede").textContent = "Moments that happen close together, in the same spot. These are patterns, not proof that one thing caused the other.";
  $("#pairs").innerHTML = keyPairs().map(l => {
    const a = byEv[l.from], b = byEv[l.to];
    const where = l.zone_rel === "same" ? "Same spot" : "Next to each other";
    const when = a.light === "night" ? "at night" : a.light === "day" ? "in the daytime" : "";
    return `<button class="pair ${sel.kind === "link" && sel.id === l.id ? "on" : ""}" data-link="${l.id}">
      <span class="a">${esc(say(a))}</span><span class="gap">${gapText(l.dt)}</span><span class="b">${esc(say(b))}</span>
      <span class="tag">${where}${when ? ", " + when : ""}${l.id === D.selected_link ? ". Linger explores this one below." : ""}</span></button>`;
  }).join("");
  document.querySelectorAll(".pair").forEach(b => b.onclick = () => select("link", b.dataset.link));
}
function drawTimeline(animate = false) {
  const svg = $("#lg"); svg.innerHTML = "";
  const ev = camEvents(), idx = Object.fromEntries(ev.map((e, i) => [e.id, i]));
  if (!ev.length) { svg.setAttribute("viewBox", "0 0 400 220"); svg.style.width = "100%"; return; }
  const all = (D.links || []).filter(l => l.from in idx && l.to in idx);
  const keep = new Set([...all].sort((a, b) => b.score - a.score).slice(0, 16).map(l => l.id));
  keyPairs().forEach(l => keep.add(l.id)); if (sel.kind === "link") keep.add(sel.id);
  const links = showAll ? all : all.filter(l => keep.has(l.id));
  const padX = 26, H = 220, base = H - 40;
  const avail = (svg.parentElement.clientWidth || 800) - padX * 2;
  const sp = Math.max(20, Math.min(44, avail / Math.max(1, ev.length - 1)));
  const W = padX * 2 + (ev.length - 1) * sp, X = (i) => padX + i * sp;
  const maxSpan = Math.max(1, ...links.map(l => idx[l.to] - idx[l.from]));
  const k = Math.min(8, (base - 24) * 2 / Math.max(1, maxSpan * sp));  // tallest arc nearly fills the panel
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.style.width = W + "px";

  let run = null;
  ev.forEach((e, i) => {
    const n = e.light === "night", end = i === ev.length - 1 || ev[i + 1].light !== "night";
    if (n && run === null) run = i;
    if (n && end) { const x1 = X(run) - sp / 2, x2 = X(i) + sp / 2;
      el("rect", {x: x1, y: 0, width: x2 - x1, height: H, fill: C.night}, svg);
      const t = el("text", {x: x2 - 8, y: 16, fill: "#34307E", "font-size": 11, "font-weight": 700, "text-anchor": "end"}, svg); t.textContent = "Night";
      run = null; }
  });
  let last = -99;
  ev.forEach((e, i) => { if (e.t - last >= 20) { last = e.t;
    const t = el("text", {x: X(i), y: H - 6, fill: C.muted, "font-size": 11, "text-anchor": "middle"}, svg); t.textContent = clock(e.t); } });
  el("line", {x1: padX - 10, y1: base, x2: W - padX + 10, y2: base, stroke: "#C9D1CD"}, svg);

  links.forEach((l, n) => {
    const i = idx[l.from], j = idx[l.to];
    const on = sel.kind === "link" && sel.id === l.id, key = l.id === D.selected_link;
    const g = el("g", {tabindex: 0, role: "button", "aria-label": `${say(byEv[l.from])}, then ${say(byEv[l.to])}`, style: "cursor:pointer"}, svg);
    const p = el("path", {d: `M${X(i)},${base} Q${(X(i) + X(j)) / 2},${base - (X(j) - X(i)) * k} ${X(j)},${base}`,
      fill: "none", stroke: C.link, "stroke-width": on ? 3.5 : key ? 2.5 : 1.4, "stroke-opacity": on || key ? 1 : 0.45}, g);
    el("path", {d: p.getAttribute("d"), fill: "none", stroke: "transparent", "stroke-width": 10}, g);
    if (animate && !reduced) { const len = p.getTotalLength();
      p.style.strokeDasharray = len; p.style.strokeDashoffset = len;
      p.style.transition = `stroke-dashoffset 450ms ease ${Math.min(n * 15, 700)}ms`;
      requestAnimationFrame(() => requestAnimationFrame(() => p.style.strokeDashoffset = 0)); }
    g.onclick = () => select("link", l.id);
    g.onkeydown = (k2) => { if (k2.key === "Enter") select("link", l.id); };
  });
  ev.forEach((e, i) => {
    const r = 4 + Math.min(6, e.degree * 0.5);
    const on = (sel.kind === "event" && sel.id === e.id) || (sel.kind === "zone" && sel.id === e.zone) ||
      (sel.kind === "link" && D.links.some(l => l.id === sel.id && (l.from === e.id || l.to === e.id)));
    const g = el("g", {tabindex: 0, role: "button", "aria-label": say(e), style: "cursor:pointer"}, svg);
    if (on) el("circle", {cx: X(i), cy: base, r: r + 5, fill: C.link, "fill-opacity": .2}, g);
    if (isVeh(e)) el("rect", {x: X(i) - r, y: base - r, width: 2 * r, height: 2 * r, rx: 2, fill: "#fff", stroke: C.ink, "stroke-width": 2}, g);
    else el("circle", {cx: X(i), cy: base, r, fill: STAY.has(e.behavior) ? C.ink : "#fff",
      stroke: e.behavior === "path_change" ? C.link : C.ink, "stroke-width": e.behavior === "path_change" ? 2.5 : 1.5}, g);
    el("circle", {cx: X(i), cy: base, r: 12, fill: "transparent"}, g);
    g.onclick = () => select("event", e.id);
    g.onkeydown = (k2) => { if (k2.key === "Enter") select("event", e.id); };
  });
}

/* ---------- step 3: what could change ---------- */
const WHEN = {"+0m": "Right away", "+10m": "After 10 min", "+30m": "After 30 min"};
function drawOptions() {
  if (!(D.branches || []).length) {
    $("#s3lede").textContent = "Linger only suggests changes it can back with at least 2 clips. This place doesn't have enough yet.";
    $("#options").innerHTML = "";
    return;
  }
  const l = (D.links || []).find(x => x.id === D.selected_link);
  $("#s3lede").textContent = l ? `Starting from the pattern "${say(byEv[l.from])}, then ${say(byEv[l.to]).toLowerCase()}", Linger imagines what happens next under each option. Each one shows how many real clips back it up.` : "";
  $("#options").innerHTML = D.branches.map(br => `
    <button class="opt ${br.kind === "baseline" ? "base" : ""} ${sel.kind === "branch" && sel.id === br.id ? "on" : ""}" data-branch="${br.id}">
      <span class="kind">${br.kind === "baseline" ? "Keep as is" : "Change the street"}</span>
      <h3>${esc(plain(br.kind === "baseline" ? "Leave the street as it is" : br.intervention))}</h3>
      <p class="pred">${esc(cap(plain(br.prediction)))}</p>
      <dl class="steps">${br.timeline.map(t => `<dt><b>${WHEN[t.t] || t.t}</b></dt><dd>${esc(cap(plain(t.state)))}</dd>`).join("")}</dl>
      <p class="risk"><b>Watch out:</b> ${esc(cap(plain(br.risk)))}</p>
      <span class="badge">Based on ${br.plausibility_n} clips</span>
    </button>`).join("");
  document.querySelectorAll(".opt").forEach(b => b.onclick = () => select("branch", b.dataset.branch));
}

/* ---------- step 4: recommendation ---------- */
function drawRec() {
  const r = D.recommendation;
  $("#recbody").innerHTML = r ? `<p class="recwhat">${esc(plain(r.action))}</p><p class="recwhy">${esc(cap(plain(r.why)))}</p>
    <div class="recrow"><span class="badge">Based on ${r.n} clips</span><button class="btn" id="recEv">See the evidence</button></div>` :
    `<p class="empty">No option had at least 2 supporting clips, so Linger is not recommending a change yet.</p>`;
  if (r) $("#recEv").onclick = () => select("rec", "rec");
}

/* ---------- details panel ---------- */
function clipHref(url) {
  if (!url) return null;
  if (/^https?:\/\//i.test(url) || url.startsWith("/")) return url;
  return "/app/" + url.replace(/^\.\//, "");
}
function clipList(items) {
  return items.map(c => {
    const s = bySeg[c.segment_id] || {};
    const href = clipHref(s.clip_url);
    const lines = (s.caption || "").match(/\[t=\d+(?:\.\d+)?s\][^\[]+/g) || [];
    const same = c.match !== "similar_space";
    return `<div class="clip" data-seg="${esc(c.segment_id)}"><div class="ch"><strong>Clip ${esc(c.segment_id)}</strong>
      <span class="where ${same ? "same" : "similar"}">${same ? "This camera" : "Similar street"}</span></div>
      <ul>${clipLines(c.segment_id, lines)}</ul>
      <button type="button" data-play="${esc(c.segment_id)}">${href ? "Play clip" : "Show on the street view"}</button>
      ${href ? `<video class="clipvid" controls playsinline muted loop preload="none"></video>` : ""}</div>`;
  }).join("");
}
function clipLines(id, raw) {
  const evs = D.events.filter(e => e.segment_id === id);
  const off = (bySeg[id] || {}).offset || 0;
  if (evs.length) return evs.slice(0, 4).map(e => `<li>${clock(e.t - off)} ${esc(say(e))}</li>`).join("");
  return raw.slice(0, 4).map(x => `<li>${esc(plain(x.replace(/\[t=(\d+(?:\.\d+)?)s\]\s*/, (m, t) => clock(+t) + " ").trim()))}</li>`).join("");
}
function drawDetail() {
  const box = $("#detail");
  if (sel.kind === "link") {
    const l = D.links.find(x => x.id === sel.id), a = byEv[l.from], b = byEv[l.to];
    box.innerHTML = `<p class="dtitle">${esc(say(a))}, then ${esc(say(b).toLowerCase())}.</p>
      <span class="note">A pattern, not proof of cause</span>
      <dl class="facts"><dt>Time apart</dt><dd>${Math.round(l.dt)} seconds</dd><dt>Where</dt><dd>${l.zone_rel === "same" ? "Same spot" : "Next to each other"}</dd>
      <dt>When</dt><dd>${clock(a.t)} on the camera's timeline${a.light !== "unknown" ? `, ${a.light === "night" ? "night" : "daytime"}` : ""}</dd>
      <dt>Strength</dt><dd>${l.score >= .85 ? "Strong" : l.score >= .65 ? "Medium" : "Weak"}</dd></dl>
      ${clipList([...new Set([a.segment_id, b.segment_id])].map(id => ({segment_id: id, match: "same_space"})))}`;
  } else if (sel.kind === "event") {
    const e = byEv[sel.id], n = D.links.filter(l => l.from === e.id || l.to === e.id).length;
    box.innerHTML = `<p class="dtitle">${esc(say(e))}</p>
      <dl class="facts"><dt>When</dt><dd>${clock(e.t)}${e.light !== "unknown" ? `, ${e.light === "night" ? "night" : "daytime"}` : ""}</dd>
      <dt>Connected to</dt><dd>${n} other ${n === 1 ? "moment" : "moments"}</dd></dl>
      ${clipList([{segment_id: e.segment_id, match: "same_space"}])}`;
  } else if (sel.kind === "zone") {
    const z = sel.id, ev = camEvents().filter(e => e.zone === z && !(e.behavior === "walk"));
    box.innerHTML = `<p class="dtitle">${esc(cap(ZNAME[z]))}</p><span class="note">${POS[z]} of the camera view</span>
      <dl class="facts"><dt>Stops</dt><dd>${stays("all")[z] || 0} (${stays("night")[z] || 0} at night)</dd>
      <dt>Moments here</dt><dd>${ev.length}</dd></dl>
      ${clipList([...new Set(ev.map(e => e.segment_id))].slice(0, 4).map(id => ({segment_id: id, match: "same_space"})))}`;
  } else if (sel.kind === "branch") {
    const br = D.branches.find(x => x.id === sel.id);
    box.innerHTML = `<p class="dtitle">${esc(plain(br.kind === "baseline" ? "Leave the street as it is" : br.intervention))}</p>
      <span class="note">The clips behind this option</span>${clipList(br.evidence)}`;
  } else if (sel.kind === "rec") {
    const r = D.recommendation;
    box.innerHTML = `<p class="dtitle">Why Linger recommends this</p><span class="note">Based on ${r.n} clips</span>
      ${clipList(r.segment_ids.map(id => D.evidence.find(x => x.segment_id === id) || {segment_id: id, match: "same_space"}))}`;
  } else {
    box.innerHTML = `<h3>Details</h3><p class="empty">Click any area, pattern, moment or option to see the details and the video behind it.</p>`;
  }
  box.querySelectorAll("[data-play]").forEach(b => b.onclick = () => play(b.dataset.play));
  document.querySelectorAll(".clipvid").forEach(v => { v.style.display = "none"; });
}
function play(id) {
  const s = bySeg[id] || {};
  const href = clipHref(s.clip_url);
  const streetV = $("#clip");
  const street = $(".street");
  const wrap = $(".streetwrap");

  document.querySelectorAll(".clip button[data-play]").forEach(b => b.classList.toggle("on", b.dataset.play === id));
  document.querySelectorAll(".clipvid").forEach(v => {
    if (v.closest(".clip")?.dataset.seg !== id) {
      v.pause();
      v.removeAttribute("src");
      v.load();
      v.style.display = "none";
    }
  });

  const card = document.querySelector(`.clip[data-seg="${CSS.escape(id)}"]`);
  const inline = card && card.querySelector(".clipvid");

  sel = {kind: sel.kind, id: sel.id, seg: id};

  if (href && streetV) {
    street.classList.add("playing");
    wrap?.classList.add("playing");
    streetV.classList.add("on");
    streetV.muted = true;
    streetV.loop = true;
    streetV.playsInline = true;
    const start = () => {
      streetV.play().catch((e) => console.warn("street clip play failed", id, e));
    };
    if (streetV.getAttribute("src") !== href) {
      streetV.src = href;
      streetV.load();
      streetV.addEventListener("loadeddata", start, { once: true });
    } else {
      start();
    }
    drawStreet();
    $("#s1").scrollIntoView({behavior: reduced ? "auto" : "smooth", block: "start"});
    if (inline) {
      inline.style.display = "block";
      if (inline.getAttribute("src") !== href) { inline.src = href; inline.load(); }
      inline.muted = true;
      inline.loop = true;
      inline.play().catch(() => {});
    }
  } else {
    streetV?.classList.remove("on");
    street?.classList.remove("playing");
    wrap?.classList.remove("playing");
    if (streetV) { streetV.removeAttribute("src"); streetV.load(); }
    drawStreet();
  }
}
function highlightZones() {
  let evs = [];
  if (sel.seg) evs = camEvents().filter(e => e.segment_id === sel.seg);
  else if (sel.kind === "event") evs = [byEv[sel.id]];
  else if (sel.kind === "link") { const l = D.links.find(x => x.id === sel.id); evs = [byEv[l.from], byEv[l.to]]; }
  const zones = new Set(evs.map(e => e.zone));
  if (sel.kind === "zone") zones.add(sel.id);
  return {zones, events: evs};
}

/* ---------- agent steps ---------- */
function traceHTML(steps, shown = steps.length) {
  return steps.map((s, i) => `<li class="${i >= shown ? "wait" : ""}"><span class="dot">${i + 1}</span><span class="t">${esc(s.step)}</span>
    <span class="s">${i < shown ? esc(cap(plain(s.summary))) : ""}${i < shown && s.mode !== "ok" ? ` <span class="fb">(used backup rules)</span>` : ""}</span></li>`).join("");
}
async function replay(steps) {
  for (let i = 0; i <= steps.length; i++) {
    $("#trace").innerHTML = traceHTML(steps, i);
    if (i < steps.length) await new Promise(r => setTimeout(r, reduced ? 0 : Math.min(800, Math.max(240, steps[i].ms))));
  }
  if (D.fallback) $("#trace").insertAdjacentHTML("afterend", `<p class="banner">The live run took too long, so this shows the last saved run.</p>`);
}
function setHow(open) { $("#how").hidden = !open; $("#howBtn").setAttribute("aria-expanded", open); }
$("#howBtn").onclick = () => setHow($("#how").hidden);

/* ---------- wiring ---------- */
function select(kind, id) {
  sel = {kind, id};
  drawStreet(); drawRank(); drawPairs(); drawTimeline(); drawOptions(); drawDetail();
}
document.querySelectorAll(".seg button").forEach(b => b.onclick = () => {
  light = b.dataset.light;
  document.querySelectorAll(".seg button").forEach(x => x.setAttribute("aria-pressed", x === b));
  drawStreet(); drawRank();
});
$("#allLinks").onchange = (e) => { showAll = e.target.checked; drawTimeline(); };
addEventListener("resize", () => D && $("#placeView") && !$("#placeView").hidden && drawTimeline());

let LIB = null, PLACE_META = {};

function miniHeat(zones) {
  const max = Math.max(1, ...ZONES.map(z => zones[z] || 0));
  return `<svg class="miniheat" viewBox="0 0 90 90" aria-hidden="true">${ZONES.map((z, i) => {
    const x = (i % 3) * 30, y = Math.floor(i / 3) * 30, v = (zones[z] || 0) / max;
    return `<rect x="${x+1}" y="${y+1}" width="28" height="28" rx="3" fill="#E58A2E" fill-opacity="${(0.08 + 0.7 * v).toFixed(2)}"/>`;
  }).join("")}</svg>`;
}
function placeLabel(c) { return `${c.place}, camera ${c.camera_n}`; }
function cardHeadline(c) {
  const feat = c.top_feature ? `the ${c.top_feature}` : (c.top_zone ? POS[c.top_zone] : "the view");
  let t = `${c.stops} stop${c.stops === 1 ? "" : "s"}, most at ${feat}.`;
  if ((c.night_share || 0) >= 0.3) t += ` ${Math.round(c.night_share * 100)}% of it at night.`;
  return t;
}
function renderLibrary() {
  $("#libraryView").hidden = false;
  $("#placeView").hidden = true;
  $("#askForm").hidden = true;
  $("#howBtn").hidden = true;
  const mock = (LIB.source || "").startsWith("mock");
  $("#libSub").textContent = "Linger read every clip in the VAST library and ranked the places where people stop and wait. Pick a place to see what happens there and what could change."
    + (mock ? " (Showing practice data.)" : "");
  const stops = (LIB.cameras || []).reduce((a, c) => a + (c.stops || 0), 0);
  $("#libStats").innerHTML = [
    ["Clips scanned", LIB.total_clips],
    ["Cameras in the library", LIB.total_cameras],
    ["Places analyzed", LIB.analyzed_cameras],
    ["Stops found", stops],
  ].map(([k, v]) => `<div class="stat"><span class="sv">${esc(v)}</span><span class="sk">${esc(k)}</span></div>`).join("");
  const ranked = (LIB.cameras || []).filter(c => c.analyzed);
  const other = (LIB.cameras || []).filter(c => !c.analyzed);
  $("#libCards").innerHTML = ranked.map(c => {
    const tags = [];
    if (c.groups) tags.push(`${c.groups} group${c.groups === 1 ? "" : "s"}`);
    if (c.buses) tags.push(c.buses === 1 ? "1 bus arrival" : `${c.buses} bus arrivals`);
    if ((c.night_share || 0) >= 0.3) tags.push(`${Math.round(c.night_share * 100)}% at night`);
    return `<a class="place-card ${c.rank === 1 ? "top" : ""}" href="#/place/${encodeURIComponent(c.camera_id)}">
      <div class="pc-top"><span class="rankpill">#${c.rank}</span>${c.rank === 1 ? `<span class="opp">Biggest opportunity</span>` : ""}</div>
      <h3>${esc(placeLabel(c))}</h3>
      <p class="pc-meta">${esc(c.camera_id)} · ${c.clips} clip${c.clips === 1 ? "" : "s"}</p>
      <p class="pc-head">${esc(cardHeadline(c))}</p>
      ${miniHeat(c.zones || {})}
      <div class="tags">${tags.map(t => `<span>${esc(t)}</span>`).join("")}</div>
      <span class="explore">Explore this place</span>
    </a>`;
  }).join("") || `<p class="empty">No places are analyzed yet. Re-ingest with the Linger prompt to rank stops.</p>`;
  $("#libAlso").innerHTML = other.map(c =>
    `<li><strong>${esc(placeLabel(c))}</strong> <span class="pc-meta">${c.clips} clips</span><br><span class="why">${esc(c.reason || "")}</span></li>`
  ).join("") || `<li class="empty">Every camera in the library was analyzed.</li>`;
}

async function loadLibrary() {
  try {
    const r = await fetch("api/library");
    if (!r.ok) throw 0;
    LIB = await r.json();
  } catch {
    LIB = (window.LINGER_LIBRARY && window.LINGER_LIBRARY.library) || window.LINGER_LIBRARY || {
      cameras: [], total_clips: 0, total_cameras: 0, analyzed_cameras: 0, source: "mock_segments.json"
    };
    if (window.LINGER_LIBRARY && window.LINGER_LIBRARY.library) LIB = { ...window.LINGER_LIBRARY.library };
  }
  PLACE_META = Object.fromEntries((LIB.cameras || []).map(c => [c.camera_id, c]));
}

async function loadCamera(cameraId) {
  try {
    const r = await fetch("api/camera/" + encodeURIComponent(cameraId));
    if (!r.ok) throw 0;
    return await r.json();
  } catch {
    const runs = (window.LINGER_LIBRARY && window.LINGER_LIBRARY.runs) || {};
    return runs[cameraId] || window.LINGER_CACHE;
  }
}

function render(animate) {
  index();
  D.events = D.events || [];
  D.links = D.links || [];
  D.branches = D.branches || [];
  D.segments = D.segments || [];
  D.trace = D.trace || [];
  const n = camEvents().length, mock = (D.source || "").startsWith("mock");
  $("#meta").textContent = `Camera ${D.camera_id}, ${n} moments, ${D.links.length} connections${mock ? ", practice data" : ""}`;
  const meta = PLACE_META[D.camera_id];
  $("#crumb").innerHTML = `<a href="#/">All places</a> / <span>${esc(meta ? placeLabel(meta) : D.camera_id)}</span>`;
  drawStreet(); drawRank(); drawPairs(); drawTimeline(animate); drawOptions(); drawRec(); drawDetail();
  $("#trace").innerHTML = traceHTML(D.trace);
}

async function showPlace(cameraId) {
  $("#libraryView").hidden = true;
  $("#placeView").hidden = false;
  $("#askForm").hidden = false;
  $("#howBtn").hidden = false;
  D = await loadCamera(cameraId);
  if (!D) { $("#detail").innerHTML = `<p class="empty">No results for this camera yet.</p>`; return; }
  sel = {kind: null, id: null}; light = "all"; showAll = false;
  render(false);
}

$("#askForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if ($("#placeView").hidden) return;
  const btn = $("#askBtn"); btn.disabled = true; btn.textContent = "Working...";
  setHow(true); $("#trace").innerHTML = `<li><span class="dot">1</span><span class="t">Planning searches</span></li>`;
  document.querySelectorAll(".banner").forEach(b => b.remove());
  let res;
  try {
    const r = await fetch("api/ask", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question: $("#q").value, camera_id: D && D.camera_id})});
    if (!r.ok) throw 0; res = await r.json();
  } catch { res = Object.assign({}, D || window.LINGER_CACHE, {fallback: true}); }
  D = res; sel = {kind: null, id: null}; index();
  await replay(D.trace || []);
  render(true);
  btn.disabled = false; btn.textContent = "Ask Linger";
});
document.querySelectorAll("#chips button").forEach(b => b.onclick = () => {
  $("#q").value = b.dataset.q;
  $("#askForm").requestSubmit();
});

async function route() {
  const h = location.hash || "#/";
  const m = h.match(/^#\/place\/(.+)$/);
  if (m) await showPlace(decodeURIComponent(m[1]));
  else {
    if (!LIB) await loadLibrary();
    renderLibrary();
  }
}
addEventListener("hashchange", () => route());
(async () => {
  await loadLibrary();
  await route();
})();
