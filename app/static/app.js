/* Linger UI. Reads api/cached (or window.LINGER_CACHE when opened as a file),
   POSTs api/ask for a live run, and falls back to the recorded run if that fails. */
const NS = "http://www.w3.org/2000/svg";
const STAY = new Set(["stop", "stand", "sit", "linger"]);
const ZONES = ["TL","TC","TR","ML","C","MR","BL","BC","BR"];
const VERB = {walk:"walking", stop:"stopping", stand:"standing", sit:"sitting", linger:"lingering", path_change:"changing path",
  bus_arrive:"arriving", crosswalk_block:"blocking the crosswalk", vehicle_stop:"stopping"};
const isVeh = (e) => e.actor === "vehicle";
let light = "all";   // all | day | night
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

let D = null;          // current result
let sel = {kind:null, id:null};
let byEv = {}, bySeg = {};

const $ = (s) => document.querySelector(s);
const el = (tag, attrs = {}, parent) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
};
const html = (s) => s.replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const clock = (t) => `${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,"0")}`;
const who = (e) => isVeh(e) ? `a ${e.vehicle || "vehicle"}` : (e.count === 1 ? "1 person" : `${e.count} people`);
const say = (e) => `${who(e)} ${VERB[e.behavior]} at ${e.zone}${e.near ? " near the " + e.near : ""}`;

/* ---------- data loading ---------- */
async function load() {
  try {
    const r = await fetch("api/cached");
    if (!r.ok) throw 0;
    return await r.json();
  } catch { return window.LINGER_CACHE; }
}

function index(d) {
  byEv = Object.fromEntries(d.events.map(e => [e.id, e]));
  bySeg = Object.fromEntries(d.segments.map(s => [s.segment_id, s]));
}

/* ---------- camera view ---------- */
const VW = 640, VH = 360;
const zc = (z) => { const i = ZONES.indexOf(z); return [(i % 3 + .5) * VW / 3, (Math.floor(i / 3) + .5) * VH / 3]; };

function drawView(highlight = []) {
  const svg = $("#zones"); svg.innerHTML = "";
  const stats = {};
  D.events.filter(e => e.camera_id === D.camera_id && STAY.has(e.behavior) && (light === "all" || e.light === light))
    .forEach(e => stats[e.zone] = (stats[e.zone] || 0) + e.count);
  const max = Math.max(1, ...Object.values(stats));
  const nearBy = {};
  D.events.filter(e => e.camera_id === D.camera_id && e.near).forEach(e => {
    nearBy[e.zone] = nearBy[e.zone] || {}; nearBy[e.zone][e.near] = (nearBy[e.zone][e.near] || 0) + 1; });
  const hz = new Set(highlight.map(e => e.zone));
  ZONES.forEach((z, i) => {
    const x = (i % 3) * VW / 3, y = Math.floor(i / 3) * VH / 3;
    const v = (stats[z] || 0) / max;
    el("rect", {x, y, width: VW/3, height: VH/3, fill: "#F2C230", "fill-opacity": (.05 + .35 * v).toFixed(2)}, svg);
    if (hz.has(z)) el("rect", {x: x+2, y: y+2, width: VW/3-4, height: VH/3-4, fill: "none", stroke: "#F2C230", "stroke-width": 3}, svg);
    const t = el("text", {x: x + 10, y: y + 22, fill: "#E9E7E0", "font-size": 15, "font-weight": 800}, svg); t.textContent = z;
    const near = nearBy[z] && Object.entries(nearBy[z]).sort((a,b) => b[1]-a[1])[0][0];
    if (near) { const n = el("text", {x: x + 10, y: y + 40, fill: "#9BA2A6", "font-size": 12}, svg); n.textContent = near; }
    if (stats[z]) { const c = el("text", {x: x + VW/3 - 10, y: y + VH/3 - 10, fill: "#E9E7E0", "font-size": 12, "text-anchor": "end"}, svg);
      c.textContent = `${stats[z]} ${stats[z] === 1 ? "stay" : "stays"}`; }
  });
  for (let k = 1; k < 3; k++) {
    el("line", {x1: k*VW/3, y1: 0, x2: k*VW/3, y2: VH, stroke: "#E9E7E0", "stroke-width": 2, "stroke-dasharray": "14 10", opacity: .5}, svg);
    el("line", {x1: 0, y1: k*VH/3, x2: VW, y2: k*VH/3, stroke: "#E9E7E0", "stroke-width": 2, "stroke-dasharray": "14 10", opacity: .5}, svg);
  }
  highlight.forEach((e, j) => {
    const [cx, cy] = zc(e.zone);
    if (isVeh(e)) {
      el("rect", {x: cx - 22, y: cy - 34, width: 44, height: 24, rx: 3, fill: "none", stroke: "#E9E7E0", "stroke-width": 2.5}, svg);
      const t = el("text", {x: cx, y: cy - 17, fill: "#E9E7E0", "font-size": 11, "text-anchor": "middle"}, svg); t.textContent = e.vehicle || "vehicle";
      return;
    }
    for (let p = 0; p < Math.min(e.count, 6); p++) {
      const a = (p / Math.max(1, e.count)) * Math.PI * 2 + j;
      el("circle", {cx: cx + Math.cos(a) * 18 * (e.count > 1), cy: cy + 18 + Math.sin(a) * 12 * (e.count > 1), r: 6,
        fill: STAY.has(e.behavior) ? "#E9E7E0" : "none", stroke: e.behavior === "path_change" ? "#F2C230" : "#E9E7E0", "stroke-width": 2}, svg);
    }
  });
}

function playSegment(segId, t = 0) {
  const s = bySeg[segId], v = $("#clip");
  if (s && s.clip_url) {
    if (v.getAttribute("src") !== s.clip_url) v.src = s.clip_url;
    v.currentTime = t; v.classList.add("on"); v.play().catch(() => {});
    $("#viewCaption").textContent = `Playing ${segId} from ${s.camera_id}.`;
  } else {
    v.classList.remove("on");
    $("#viewCaption").textContent = s ? `${segId} on ${s.camera_id}: ${s.caption}` : "";
  }
}

/* ---------- linkograph ---------- */
function drawLinkograph(animate = false) {
  const svg = $("#lg"); svg.innerHTML = "";
  const ev = D.events.filter(e => e.camera_id === D.camera_id);
  const idx = Object.fromEntries(ev.map((e, i) => [e.id, i]));
  const links = D.links.filter(l => l.from in idx && l.to in idx);
  const padX = 30, H = 250, base = H - 44;
  const avail = (svg.parentElement.clientWidth || 900) - padX * 2;
  const sp = Math.max(22, Math.min(40, avail / Math.max(1, ev.length - 1)));
  const W = padX * 2 + (ev.length - 1) * sp;
  const maxSpan = Math.max(1, ...links.map(l => idx[l.to] - idx[l.from]));
  const k = Math.min(1, (base - 16) / (maxSpan * sp / 2));
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.style.width = W + "px";
  const X = (i) => padX + i * sp;
  const crit = new Set(D.critical);

  // time ticks
  let lastLabel = -99;
  ev.forEach((e, i) => {
    if (e.t - lastLabel >= 20) { lastLabel = e.t;
      const t = el("text", {x: X(i), y: H - 8, fill: "#9BA2A6", "font-size": 11, "text-anchor": "middle"}, svg); t.textContent = clock(e.t); }
  });
  // shade runs of night events so day and night read at a glance
  let runStart = null;
  ev.forEach((e, i) => {
    const night = e.light === "night", end = i === ev.length - 1 || ev[i + 1].light !== "night";
    if (night && runStart === null) runStart = i;
    if (night && end) {
      const x1 = X(runStart) - sp / 2, x2 = X(i) + sp / 2;
      el("rect", {x: x1, y: 0, width: x2 - x1, height: H - 22, fill: "#3A5A8C", "fill-opacity": .18}, svg);
      const t = el("text", {x: x2 - 8, y: 16, fill: "#9BB4D6", "font-size": 11, "text-anchor": "end"}, svg); t.textContent = "night";
      runStart = null;
    }
  });
  el("line", {x1: padX - 12, y1: base, x2: W - padX + 12, y2: base, stroke: "#454B4F"}, svg);

  const gl = el("g", {}, svg);
  links.forEach((l, n) => {
    const i = idx[l.from], j = idx[l.to];
    const ax = (X(i) + X(j)) / 2, ay = base - (X(j) - X(i)) / 2 * k;
    const isSel = sel.kind === "link" && sel.id === l.id, isAgent = l.id === D.selected_link;
    const g = el("g", {class: "lk", tabindex: 0, role: "button", "aria-label": l.rationale}, gl);
    const p = el("polyline", {points: `${X(i)},${base} ${ax},${ay} ${X(j)},${base}`, fill: "none",
      stroke: "#F2C230", "stroke-width": isSel ? 2.6 : 1, "stroke-opacity": isSel ? 1 : (0.15 + 0.45 * (l.score - .5) / .5).toFixed(2)}, g);
    const d = 4 + (isSel || isAgent ? 2 : 0);
    el("path", {d: `M${ax},${ay-d} L${ax+d},${ay} L${ax},${ay+d} L${ax-d},${ay} Z`,
      fill: isSel ? "#F2C230" : isAgent ? "#5FB7C6" : "#24272A", stroke: isAgent && !isSel ? "#5FB7C6" : "#F2C230", "stroke-width": 1.2}, g);
    el("circle", {cx: ax, cy: ay, r: 10, fill: "transparent"}, g);
    if (animate && !reduced) {
      const len = (X(j) - X(i)) * 1.5 + 20;
      p.style.strokeDasharray = len; p.style.strokeDashoffset = len;
      p.style.transition = `stroke-dashoffset 500ms ease ${Math.min(n * 12, 900)}ms`;
      requestAnimationFrame(() => requestAnimationFrame(() => p.style.strokeDashoffset = 0));
    }
    g.addEventListener("click", () => select("link", l.id));
    g.addEventListener("keydown", (e) => { if (e.key === "Enter") select("link", l.id); });
    g.addEventListener("mouseenter", () => drawView([byEv[l.from], byEv[l.to]]));
  });

  ev.forEach((e, i) => {
    const r = 3.5 + Math.min(9, e.degree * 0.7);
    const isSel = (sel.kind === "event" && sel.id === e.id) ||
                  (sel.kind === "link" && D.links.some(l => l.id === sel.id && (l.from === e.id || l.to === e.id)));
    const g = el("g", {tabindex: 0, role: "button", "aria-label": say(e)}, svg);
    if (crit.has(e.id)) el("circle", {cx: X(i), cy: base, r: r + 5, fill: "none", stroke: "#F2C230", "stroke-width": 2}, g);
    if (isVeh(e)) {
      el("rect", {x: X(i) - r, y: base - r, width: 2 * r, height: 2 * r, fill: "#24272A", stroke: "#E9E7E0", "stroke-width": isSel ? 3 : 2}, g);
      el("line", {x1: X(i) - r + 2, y1: base, x2: X(i) + r - 2, y2: base, stroke: "#E9E7E0", "stroke-width": 1.5}, g);
    } else el("circle", {cx: X(i), cy: base, r,
      fill: STAY.has(e.behavior) ? "#E9E7E0" : "#24272A",
      stroke: e.behavior === "path_change" ? "#F2C230" : "#E9E7E0", "stroke-width": isSel ? 3 : 1.5}, g);
    const z = el("text", {x: X(i), y: base + 18 + (i % 2) * 0, fill: isSel ? "#F2C230" : "#9BA2A6", "font-size": 10, "text-anchor": "middle"}, g);
    z.textContent = e.zone;
    g.addEventListener("mouseenter", () => drawView([e]));
    g.addEventListener("click", () => select("event", e.id));
    g.addEventListener("keydown", (k2) => { if (k2.key === "Enter") select("event", e.id); });
  });
  svg.addEventListener("mouseleave", () => drawView(currentHighlight()));
}

function currentHighlight() {
  if (sel.kind === "event") return [byEv[sel.id]];
  if (sel.kind === "link") { const l = D.links.find(x => x.id === sel.id); return l ? [byEv[l.from], byEv[l.to]] : []; }
  return [];
}

/* ---------- futures ---------- */
function drawBranches(animate = false) {
  const svg = $("#br"); svg.innerHTML = "";
  const l = D.links.find(x => x.id === D.selected_link);
  const a = byEv[l.from], b = byEv[l.to];
  $("#fsub").innerHTML = `Branched from the agent's selected link at ${clock(a.t)}: ${html(l.rationale)} ` +
    `<button class="linkbtn" id="showLink">Show this link</button>`;
  $("#showLink").onclick = () => select("link", l.id);

  const x0 = 60, y0 = 100, xs = [210, 390, 570];
  el("circle", {cx: x0, cy: y0, r: 8, fill: "#F2C230"}, svg);
  const t0 = el("text", {x: x0, y: y0 + 26, fill: "#9BA2A6", "font-size": 12, "text-anchor": "middle"}, svg); t0.textContent = "now";
  const offsets = {baseline: 0}; let up = -1;
  D.branches.forEach((br) => {
    const dy = br.kind === "baseline" ? 0 : (up *= -1, up) * -62;
    const isSel = sel.kind === "branch" && sel.id === br.id;
    const color = br.kind === "baseline" ? "#8B9196" : "#5FB7C6";
    const g = el("g", {class: "branch", tabindex: 0, role: "button", "aria-label": `${br.intervention}, ${br.label}`}, svg);
    const d = dy === 0 ? `M${x0},${y0} L${xs[2]},${y0}` :
      `M${x0},${y0} C${x0 + 90},${y0} ${xs[0] - 60},${y0 + dy} ${xs[0]},${y0 + dy} L${xs[2]},${y0 + dy}`;
    const p = el("path", {d, class: "bl", fill: "none", stroke: color, "stroke-width": isSel ? 4.5 : 2.5,
      "stroke-dasharray": br.kind === "baseline" ? "8 6" : "none"}, g);
    if (animate && !reduced && br.kind !== "baseline") {
      p.style.strokeDasharray = 900; p.style.strokeDashoffset = 900; p.style.transition = "stroke-dashoffset 600ms ease";
      requestAnimationFrame(() => requestAnimationFrame(() => p.style.strokeDashoffset = 0));
    }
    xs.forEach((x, i) => {
      el("circle", {cx: x, cy: y0 + dy, r: 5, fill: "#1C1F21", stroke: color, "stroke-width": 2}, g);
      const tl = el("text", {x, y: y0 + dy - 10, fill: "#9BA2A6", "font-size": 11, "text-anchor": "middle"}, g);
      tl.textContent = br.timeline[i] ? br.timeline[i].t : "";
    });
    const words = br.intervention.split(" "), lines = [""];
    words.forEach(w => { if ((lines[lines.length - 1] + " " + w).length > 52 && lines.length < 2) lines.push(w);
      else lines[lines.length - 1] = (lines[lines.length - 1] + " " + w).trim(); });
    const ty = y0 + dy - (lines.length > 1 ? 10 : 2);
    lines.forEach((ln, i) => { const t = el("text", {x: xs[2] + 22, y: ty + i * 17, fill: isSel ? "#F2C230" : "#E9E7E0", "font-size": 14, "font-weight": 600}, g); t.textContent = ln; });
    const lab = el("text", {x: xs[2] + 22, y: ty + (lines.length - 1) * 17 + 17, fill: color, "font-size": 12}, g);
    lab.textContent = br.label;
    el("rect", {x: x0, y: y0 + dy - 28, width: 1090 - x0, height: 50, fill: "transparent"}, g);
    g.addEventListener("click", () => select("branch", br.id));
    g.addEventListener("keydown", (e) => { if (e.key === "Enter") select("branch", br.id); });
  });
}

/* ---------- details panel ---------- */
function evidenceList(items) {
  return items.map(c => {
    const s = bySeg[c.segment_id] || {};
    return `<div class="ev"><strong>${html(c.segment_id)}</strong><span class="tag ${c.match}">${c.match === "same_space" ? "same camera" : "similar space"}</span>
      <div class="cap">${html(s.caption || "")}</div>
      <button data-play="${html(c.segment_id)}">${s.clip_url ? "Play clip" : "Show in view"}</button></div>`;
  }).join("");
}

function details() {
  const box = $("#details");
  if (sel.kind === "link") {
    const l = D.links.find(x => x.id === sel.id), a = byEv[l.from], b = byEv[l.to];
    box.innerHTML = `<h3>${html(l.rationale)}</h3><span class="assoc">Association, not cause</span>
      <dl class="facts"><dt>Link</dt><dd>${l.id}, ${l.type}</dd><dt>Time apart</dt><dd>${l.dt}s</dd>
      <dt>Zones</dt><dd>${a.zone} to ${b.zone} (${l.zone_rel})</dd><dt>Score</dt><dd>${l.score}</dd></dl>
      <div class="ev"><strong>${clock(a.t)}</strong> ${html(say(a))}<br><button data-play="${a.segment_id}">Show moment</button></div>
      <div class="ev"><strong>${clock(b.t)}</strong> ${html(say(b))}<br><button data-play="${b.segment_id}">Show moment</button></div>
      ${l.id === D.selected_link ? "" : `<p class="hint" style="margin-top:12px">The agent branched link ${D.selected_link}. Ask again to explore a different moment.</p>`}`;
  } else if (sel.kind === "event") {
    const e = byEv[sel.id];
    const n = D.links.filter(l => l.from === e.id || l.to === e.id);
    box.innerHTML = `<h3>${html(say(e))}</h3>
      <dl class="facts"><dt>Time</dt><dd>${clock(e.t)}</dd><dt>Segment</dt><dd>${e.segment_id}</dd><dt>Light</dt><dd>${e.light || "unknown"}</dd>
      <dt>Links</dt><dd>${n.length}${D.critical.includes(e.id) ? ", critical move" : ""}</dd></dl>
      ${n.slice(0, 6).map(l => `<div class="ev"><button class="linkbtn" data-link="${l.id}">${html(l.rationale)}</button></div>`).join("")}
      <div class="ev"><button data-play="${e.segment_id}">Show moment</button></div>`;
  } else if (sel.kind === "branch") {
    const br = D.branches.find(x => x.id === sel.id);
    box.innerHTML = `<h3>${html(br.intervention)}</h3><span class="assoc">${html(br.label)}</span>
      <p>${html(br.prediction)}</p>
      <dl class="facts" style="margin-top:12px">${br.timeline.map(t => `<dt>${t.t}</dt><dd>${html(t.state)}</dd>`).join("")}
      <dt>Risk</dt><dd>${html(br.risk)}</dd></dl>${evidenceList(br.evidence)}`;
  } else if (sel.kind === "rec") {
    const r = D.recommendation;
    box.innerHTML = `<h3>Evidence for the recommendation</h3><span class="assoc">${html(r.label)}</span>
      ${evidenceList(r.segment_ids.map(id => D.evidence.find(x => x.segment_id === id) || {segment_id: id, match: "same_space"}))}`;
  } else {
    box.innerHTML = `<p class="hint">Hover dots in the linkograph to see where each behavior happened. Select a yellow peak to read a link, or a future to see the clips behind it.</p>`;
  }
  box.querySelectorAll("[data-play]").forEach(b => b.onclick = () => {
    const id = b.dataset.play; const e = D.events.find(x => x.segment_id === id);
    playSegment(id); drawView(D.events.filter(x => x.segment_id === id));
  });
  box.querySelectorAll("[data-link]").forEach(b => b.onclick = () => select("link", b.dataset.link));
}

function select(kind, id) {
  sel = {kind, id};
  tab("details");
  drawLinkograph(); drawBranches(); details(); drawView(currentHighlight());
}

/* ---------- agent steps ---------- */
function stepsHTML(steps, shown = steps.length) {
  return steps.map((s, i) => `<div class="step ${s.mode !== "ok" ? "fb" : ""} ${i >= shown ? "pending" : ""}">
    <span class="n">${i + 1}</span><span class="t">${html(s.step)}</span><span class="ms">${i < shown ? s.ms + " ms" : ""}</span>
    <span class="tool">${html(s.tool)}${s.mode !== "ok" ? ", " + html(s.mode) : ""}</span>
    <span class="s">${i < shown ? html(s.summary) : ""}</span></div>`).join("") +
    (D && D.fallback ? `<p class="hint" style="margin-top:10px">The live run did not finish in time, so this is the last recorded run.</p>` : "");
}

async function replaySteps(steps) {
  const box = $("#steps");
  for (let i = 0; i <= steps.length; i++) {
    box.innerHTML = stepsHTML(steps, i);
    if (i < steps.length) await new Promise(r => setTimeout(r, reduced ? 0 : Math.min(900, Math.max(260, steps[i].ms))));
  }
}

function tab(name) {
  document.querySelectorAll(".tabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.tab === name));
  $("#details").hidden = name !== "details"; $("#steps").hidden = name !== "steps";
}
document.querySelectorAll(".tabs button").forEach(b => b.onclick = () => tab(b.dataset.tab));

document.querySelectorAll(".lightchips button").forEach(b => b.onclick = () => {
  light = b.dataset.light;
  document.querySelectorAll(".lightchips button").forEach(x => x.setAttribute("aria-pressed", x === b));
  const n = D.events.filter(e => e.camera_id === D.camera_id && STAY.has(e.behavior) && (light === "all" || e.light === light))
    .reduce((s, e) => s + e.count, 0);
  $("#viewCaption").textContent = `Zones shaded by ${light === "all" ? "all" : light} stays: ${n} person-stops.`;
  drawView(currentHighlight());
});

/* ---------- recommendation ---------- */
function drawRec() {
  const r = D.recommendation;
  $("#rec").innerHTML = r ? `<div><p class="what">${html(r.action)}</p><p class="why">${html(r.why)}</p></div>
    <div style="text-align:right"><p class="lab">${html(r.label)}</p><button id="recEv" style="margin-top:8px">Show evidence</button></div>` :
    `<p class="hint">No recommendation met the evidence bar (at least 2 clips).</p>`;
  if (r) $("#recEv").onclick = () => select("rec", "rec");
}

/* ---------- run ---------- */
function render(animate) {
  index(D);
  $("#camLabel").textContent = `${D.camera_id}, ${D.events.length} events, ${D.links.length} links${D.mode === "rules" ? ", rules mode" : ""}`;
  drawView(); drawLinkograph(animate); drawBranches(animate); details(); drawRec();
}

$("#askForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const btn = $("#askBtn"); btn.disabled = true; btn.textContent = "Working";
  tab("steps"); $("#steps").innerHTML = `<p class="hint">Planning searches...</p>`;
  let res;
  try {
    const r = await fetch("api/ask", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question: $("#q").value, camera_id: D && D.camera_id})});
    if (!r.ok) throw 0; res = await r.json();
  } catch { res = Object.assign({}, window.LINGER_CACHE, {fallback: true}); }
  D = res; sel = {kind: null, id: null}; index(D);
  await replaySteps(D.trace);
  render(true);
  btn.disabled = false; btn.textContent = "Ask";
});

(async () => {
  D = await load();
  if (!D) { $("#details").innerHTML = `<p class="hint">No results yet. Run scripts/build_cache.py, then reload.</p>`; return; }
  render(false);
  addEventListener("resize", () => drawLinkograph());
  $("#steps").innerHTML = stepsHTML(D.trace);
  tab("steps");
})();
