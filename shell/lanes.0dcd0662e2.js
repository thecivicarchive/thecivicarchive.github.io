/* The Civic Archive: Reading & access, in lanes (John, 2026-10-29: "bucket them into ... lanes ... in the accessibility menu
   but containerized ... when you access one of them it pops out ... tab containers in it ... you can click on those and
   they get pinned ... open others and they open from right to left on the screen ... see multiple popped open at one
   time"; 2026-10-31, after trying it: "Lanes can go everywhere").
   Every page's Reading & access opens a rail of lanes (Language, How much, Text, Colour and contrast, Motion and calm,
   Ready-made sets). A lane opens as a panel to the left of the rail, each lane after it to the left of the last, so several
   stay open side by side; on a phone, where there is no room for that, each opens below the last in one sheet. Inside a
   lane each setting is a tab; a tab clicked is pinned open (as many as the reader likes) and stays pinned on this device
   until clicked again.
   Two kinds of page, one arrangement:
   - the shell's pages (start({kind: "shell"})): the panel the shell builds (#tca-access) is taken apart and its fieldsets,
     presets, the Meet me where I am chooser and "Put everything back" are moved into the lanes with the shell's own
     listeners still on them, so every choice is kept, combined, said aloud and carried to every page as before. On the
     Access page, where the settings are the page itself, nothing changes.
   - the pages that keep their own top bar (start({kind: "rider"})): the same lanes, holding only the settings those pages
     honour (the rider's own apply), drawn here from the shell's own words ([["scale","Text size",[["100","100%"],["115","115%"],["130","130%"],["150","150%"],["200","200%"]],""],["face","Typeface",[["standard","Standard"],["dyslexia","Lexend"],["hyperlegible","Atkinson Hyperlegible"]],"Lexend and Atkinson Hyperlegible were each designed to be easier to read."],["space","Spacing",[["standard","Standard"],["generous","Generous"]],""],["contrast","Contrast",[["standard","Standard"],["high","High"],["dark","Dark"]],""],["lang","Words",[["standard","Standard"],["plain","Plain"]],"Plain words where a plain version is written."],["depth","Detail",[["standard","Standard"],["detailed","More structure"],["focus","Focus"]],"More structure adds section labels, reading times and a progress line. Focus puts the extras away until you choose Show more or a higher level, which sets this back to Standard."],["motion","Motion",[["full","On"],["reduced","Reduced"]],""],["sheets","Sheet speed",[["full","Full (5 seconds)"],["quick","Quick (1 second)"],["instant","Instant"]],"How a member's page changes sheets. Any click, tap or key skips the move. Motion off makes every change instant."],["reveal","Scroll fade",[["full","Full"],["subtle","Subtle"],["off","Off"]],"How text fades in and out at the edges of the screen."],["calm","Calm",[["off","Off"],["on","On"]],"No countdowns and no motion. Chart bars get patterns."],["palette","Chart colours",[["standard","Standard"],["deut","Red-green (deuteranopia)"],["prot","Red-green (protanopia)"],["trit","Blue-yellow (tritanopia)"],["mono","Grey only"]],"Changes the colours of charts only, and adds patterns."],["companion","Companion",[["on","On"],["still","Still"],["off","Off"]],"Still draws it once. Off never loads it."]], written in by the build from
     build_shell.AXIS_UI); the ready-made sets and the rest are on the Access page, and the rail says so.
   This module adds only the arrangement. Nothing is sent anywhere; the pinned tabs are kept in this browser (tca.lanes.v1). */
import { t, tHTML, N_, tagLang, choices, setLanguage, L } from "./i18n.d705614426.js";
import { chooser } from "./levels.623c6c496a.js";

const D = document, H = D.documentElement;
const $ = (s, el = D) => el.querySelector(s), $$ = (s, el = D) => [...el.querySelectorAll(s)];
const KEY = "tca.lanes.v1", REOPEN = "tca.lanes.reopen";
const store = {
  get() { try { const v = JSON.parse(localStorage.getItem(KEY) || "null"); return v && typeof v === "object" && v.pins && typeof v.pins === "object" ? v : {pins: {}}; } catch (e) { return {pins: {}}; } },
  set(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} }
};
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
const UI = Object.fromEntries([["scale","Text size",[["100","100%"],["115","115%"],["130","130%"],["150","150%"],["200","200%"]],""],["face","Typeface",[["standard","Standard"],["dyslexia","Lexend"],["hyperlegible","Atkinson Hyperlegible"]],"Lexend and Atkinson Hyperlegible were each designed to be easier to read."],["space","Spacing",[["standard","Standard"],["generous","Generous"]],""],["contrast","Contrast",[["standard","Standard"],["high","High"],["dark","Dark"]],""],["lang","Words",[["standard","Standard"],["plain","Plain"]],"Plain words where a plain version is written."],["depth","Detail",[["standard","Standard"],["detailed","More structure"],["focus","Focus"]],"More structure adds section labels, reading times and a progress line. Focus puts the extras away until you choose Show more or a higher level, which sets this back to Standard."],["motion","Motion",[["full","On"],["reduced","Reduced"]],""],["sheets","Sheet speed",[["full","Full (5 seconds)"],["quick","Quick (1 second)"],["instant","Instant"]],"How a member's page changes sheets. Any click, tap or key skips the move. Motion off makes every change instant."],["reveal","Scroll fade",[["full","Full"],["subtle","Subtle"],["off","Off"]],"How text fades in and out at the edges of the screen."],["calm","Calm",[["off","Off"],["on","On"]],"No countdowns and no motion. Chart bars get patterns."],["palette","Chart colours",[["standard","Standard"],["deut","Red-green (deuteranopia)"],["prot","Red-green (protanopia)"],["trit","Blue-yellow (tritanopia)"],["mono","Grey only"]],"Changes the colours of charts only, and adds patterns."],["companion","Companion",[["on","On"],["still","Still"],["off","Off"]],"Still draws it once. Off never loads it."]].map(a => [a[0], a]));      /* [axis, legend, [[value, words]...], help line] */
const narrow = () => { try { return matchMedia("(max-width: 700px)").matches; } catch (e) { return false; } };

/* the lanes, and the settings in each (an axis is one of the site's settings; presets are the shell's own buttons) */
const LANES = [
  /* first, so a reader who does not read English finds it before anything else: its line in the rail names every language
     in its own words */
  {id: "lang", name: N_("Language"), about: N_("Read the site in another language. Only languages with a finished translation are listed."),
   tabs: [{id: "pick", name: N_("Languages"), make: () => langList()}, {id: "how", name: N_("How translations work"), make: () => langHow()}]},
  {id: "much", name: N_("How much"), about: N_("How much each page shows at once, and what you came for. The facts are the same at every level."),
   tabs: [{id: "level", name: N_("Level and focus"), level: true}, {axis: "depth"}]},
  {id: "text", name: N_("Text"), about: N_("The size of the type, the typeface, the space around it, and plain words."),
   aboutRider: N_("The size of the type, the typeface and the space around it."),
   tabs: [{axis: "scale"}, {axis: "face"}, {axis: "space"}, {axis: "lang"}]},
  {id: "colour", name: N_("Colour and contrast"), about: N_("Light, dark or high contrast, and chart colours for colour blindness."),
   aboutRider: N_("Light, dark or high contrast."),
   tabs: [{axis: "contrast"}, {axis: "palette"}]},
  {id: "motion", name: N_("Motion and calm"), about: N_("Everything that moves: motion itself, Calm, the scroll fade, page changes and the companion."),
   aboutRider: N_("Everything that moves: motion itself, Calm, page changes and the companion."),
   tabs: [{axis: "motion"}, {axis: "calm"}, {axis: "reveal"}, {axis: "sheets"}, {axis: "companion"}]},
  {id: "sets", name: N_("Ready-made sets"), about: N_("Several settings at once. Turn on as many as help: they combine, and the gentler choice wins."),
   tabs: [{id: "reading", name: N_("Reading"), presets: ["dyslexia", "lowvision", "plain"]},
          {id: "attention", name: N_("Attention"), presets: ["adhd", "focus", "calm"]},
          {id: "tools", name: N_("Tools"), presets: ["screenreader", "colour"]}]}
];
const ICON = {
  lang: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.6 2.4 3.8 5.2 3.8 8.5s-1.2 6.1-3.8 8.5c-2.6-2.4-3.8-5.2-3.8-8.5s1.2-6.1 3.8-8.5z"/>',
  much: '<path d="M4 7h16M4 12h10M4 17h6"/><circle cx="17" cy="12" r="2"/><circle cx="13" cy="17" r="2"/>',
  text: '<path d="M3 18 8 6l5 12M5 14h6"/><path d="M15 12.5c1-1.4 4.6-1.6 5 .6V18m0-3.2c-2.6-.6-5.4 0-5.4 1.6 0 1.8 3.6 2 5.4-.4"/>',
  colour: '<circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor"/>',
  motion: '<path d="M3 12c2.5-5 5-5 7.5 0s5 5 7.5 0"/><path d="M3 17c2.5-3 5-3 7.5 0"/>',
  sets: '<rect x="4" y="9" width="12" height="11" rx="2"/><path d="M8 6h10a2 2 0 0 1 2 2v9"/>',
  count: '<path d="M5 19V11M10 19V6M15 19v-5M20 19V9"/>'
};
const svg = (p, cls = "") => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${p}</svg>`;
const X = svg('<path d="M6 6l12 12M18 6 6 18"/>');
const PIN = '<path d="M9 3h6l-1 6 3.5 3.5h-11L10 9z"/><path d="M12 12.5V21"/>';

let O = null;      /* the page's own: {kind, apply, axes, say, reset, has, trigger, bar, closeOthers} */
let lanes = [];    /* the lanes this page can show, each with only the tabs it holds */

/* ---------- the Language lane: the languages with a finished translation, each in its own words ---------- */
function langs() { return choices().map(l => ({code: l.code, name: l.name, html: l.html, status: l.status, label: l.label || ""})); }
function inReaders(html) {      // a language's name in the language the page is read in ("Spanish" on an English page, "inglés" on a Spanish one)
  try { return new Intl.DisplayNames([L.html || "en"], {type: "language"}).of(html) || ""; } catch (e) { return ""; }
}
function langList() {
  const box = D.createElement("div"); box.className = "ln-lang";
  box.innerHTML = `<ul class="ln-langs" role="list"></ul><p class="ln-note">${esc(t("Choosing a language shows this page again in it, where you were. Your choice is kept on this device only."))}</p>`;
  box.addEventListener("click", e => {
    const b = e.target.closest("[data-lang-pick]"); if (!b) return;
    const code = b.dataset.langPick;
    if (code === L.code) { say(t("{language} is the language this page is in now.", {language: b.querySelector("b").textContent})); return; }
    try { sessionStorage.setItem(REOPEN, "lang"); } catch (x) {}      // the lane opens again when the page comes back in the new language
    setLanguage(code);
  });
  return box;
}
function drawLang() {
  const p = panels.get("lang"), ul = p && $(".ln-langs", p); if (!ul) return;
  ul.innerHTML = langs().map(l => {
    const gloss = l.status === "test" ? "" : inReaders(l.html);
    const line = l.code === "en" ? t("The site as it is written") : l.label;
    return `<li><button type="button" class="ln-lng" data-lang-pick="${esc(l.code)}" aria-pressed="${l.code === L.code ? "true" : "false"}">
<span class="ln-lng-n"><b lang="${esc(l.html)}">${esc(l.name)}</b>${gloss && gloss.toLowerCase() !== l.name.toLowerCase() ? `<span>${esc(gloss)}</span>` : ""}</span>
${line ? `<span class="ln-lng-l"${l.code === "en" ? "" : ` lang="${esc(l.html)}"`}>${esc(line)}</span>` : ""}
${l.status === "draft" ? `<span class="ln-lng-t">${esc(t("On the draft site only, for now"))}</span>` : ""}</button></li>`;
  }).join("");
}
function langHow() {
  const box = D.createElement("div"); box.className = "ln-how";
  box.innerHTML = `<ul>
<li>${esc(t("Translated by Claude, an AI model, and checked by a second pass. Every translated page says so in a line under the top bar."))}</li>
<li>${esc(t("Names are never translated: candidates, members of Congress, bills and parties keep their own names."))}</li>
<li>${esc(t("A ballot question’s official wording uses the government’s own translation, word for word, where there is one. Where there is none, it stays in English, with a note."))}</li>
<li>${esc(t("Long records, such as bill summaries, stay in English for now. Your browser’s own translate button can help there."))}</li>
</ul>`;
  return box;
}

/* ---------- the settings themselves ---------- */
/* the controls once moved into a lane, kept by name: a closed lane is off the page, out of reach of a search */
const SEG = {}, PRE = {}, KEPT = {};
function made(axis) {      /* a setting drawn here, on a page that keeps its own top bar, in the shell's own words */
  const u = UI[axis]; if (!u) return null;
  /* marked data-ln-axis, never data-axis: the record pages' pop-out cards take every click on a data-axis (their rating bars) */
  const fs = D.createElement("fieldset"); fs.className = "tca-seg"; fs.dataset.lnAxis = axis;
  fs.innerHTML = `<legend>${esc(t(u[1]))}</legend><div class="opts">${u[2].map(([v, w]) =>
    `<label><input type="radio" name="ln-ax-${axis}" value="${esc(v)}"><span>${esc(t(w))}</span></label>`).join("")}</div>`
    + (u[3] ? `<span class="hint">${esc(t(u[3]))}</span>` : "");
  fs.addEventListener("change", e => { if (e.target.matches("input[type=radio]")) O.apply({[axis]: e.target.value}); });
  return fs;
}
function seg(axis) {
  if (SEG[axis]) return SEG[axis];
  if (O.kind === "shell") return $(`#tca-access .tca-seg[data-axis="${axis}"]`);
  return O.has.includes(axis) ? (SEG[axis] = made(axis)) : null;
}
function syncMade() {      /* the settings drawn here show the settings as they are (the shell's own sync keeps its own) */
  if (O.kind === "shell") return;
  const a = O.axes();
  for (const [axis, box] of Object.entries(SEG)) for (const r of $$("input[type=radio]", box)) r.checked = r.value === String(a[axis]);
}
function legend(axis) { const b = seg(axis), l = b && $("legend", b); return l ? l.textContent.trim() : axis; }
function picked(axis) {      // the words of the choice made, and whether it is the first (the default)
  const b = seg(axis); if (!b) return null;
  const all = $$("input[type=radio]", b), on = all.find(r => r.checked) || all[0];
  return on ? {words: $("span", on.closest("label")).firstChild.textContent.trim(), dflt: on === all[0]} : null;
}
function presetBtn(id) { return PRE[id] || $(`#tca-access [data-preset="${id}"]`); }
function tabName(tab) { return tab.name ? t(tab.name) : (tab.label || legend(tab.axis)); }
function tabKey(tab) { return tab.id || tab.axis; }
/* which tabs a lane holds on this page: the settings this page has, the presets where the shell is, Language where there is a choice */
function holds(tab) {
  if (tab.axis) return !!seg(tab.axis);
  if (tab.presets) return O.kind === "shell" && tab.presets.some(presetBtn);
  if (tab.level) return O.kind === "rider" || !!$("#tca-access [data-tca-meet]");
  if (tab.take) return !!tab.take();
  return true;
}

/* the line under each lane in the rail: what is set there now */
function summary(lane) {
  if (lane.id === "lang") {      // every language in its own words, the one in use first
    const all = langs().filter(l => l.status !== "test"), first = all.filter(l => l.code === L.code), rest = all.filter(l => l.code !== L.code);
    return {text: first.concat(rest).map(l => l.name).join(" · "), n: L.code === "en" ? 0 : 1};
  }
  if (lane.id === "much") {
    const box = KEPT.level, lv = box && $("[data-lv-set][aria-pressed=true]", box), fo = box && $("[data-focus-set][aria-pressed=true]", box);
    const bits = [lv ? lv.firstChild.textContent.trim() : "", fo ? fo.textContent.trim() : ""];
    const d = picked("depth"); if (d && !d.dflt) bits.push(d.words);
    return {text: bits.filter(Boolean).join(" · "), n: (lv && lv.dataset.lvSet !== "3" ? 1 : 0) + (fo && fo.dataset.focusSet !== "none" ? 1 : 0) + (d && !d.dflt ? 1 : 0)};
  }
  if (lane.id === "sets") {
    const on = lane.tabs.flatMap(x => x.presets).map(presetBtn).filter(b => b && b.getAttribute("aria-pressed") === "true").map(b => $("b", b).textContent.trim());
    return {text: on.length ? on.join(" · ") : t("None on"), n: on.length};
  }
  if (lane.id === "count") return {text: t("Your two switches"), n: 0};
  const ch = lane.tabs.map(x => picked(x.axis)).filter(p => p && !p.dflt).map(p => p.words);
  return {text: ch.length ? ch.join(" · ") : t("Standard"), n: ch.length};
}

/* ---------- said aloud: the page's own live region, so a pin is said like a setting ---------- */
function say(text) { if (O && O.say) O.say(text); }

/* ---------- the rail ---------- */
let root = null, rail = null, stack = null, opener = null;
const panels = new Map();      // lane id -> its panel, kept when closed (it holds the page's own controls)
const open = [];               // lane ids, in the order they were opened (the first sits next to the rail)
let saved = store.get();

function build() {
  if (root) return;
  const src = $("#tca-access");
  root = D.createElement("div"); root.className = "ln-root ln-" + O.kind;
  tagLang(root);
  const rider = O.kind === "rider";
  root.innerHTML = `<div class="ln-stack" aria-label="${esc(t("Open lanes"))}"></div><div class="ln-keep" hidden></div>
<section class="ln-rail" role="region" aria-labelledby="ln-h" hidden>
<header class="ln-rh"><h2 id="ln-h" tabindex="-1">${esc(t("Reading & access"))}</h2><button type="button" class="ln-x" data-ln-close aria-label="${esc(t("Close reading and access"))}">${X}</button></header>
<p class="ln-sub"><span class="ln-wide">${esc(t("Open a lane, or several: each opens to the left of the last. Inside a lane, click a tab to pin it."))}</span><span class="ln-narrow">${esc(t("Open a lane, or several: each opens below the last. Inside a lane, tap a tab to pin it."))}</span></p>
<div class="ln-shelf" hidden><p class="ln-lab">${esc(t("Pinned"))}</p><ul></ul></div>
<ul class="ln-lanes"></ul>
<div class="ln-foot"><span class="ln-reset"></span><button type="button" class="ln-btn ln-all" hidden>${esc(t("Close every lane"))}</button>
${rider ? `<p class="ln-kept ln-more">${tHTML("The ready-made sets, chart colours and a few more settings are on the <0>Access</0> page.", {0: w => `<a href="${esc(O.access)}">${w}</a>`})}</p>` : ""}
<p class="ln-kept">${esc(t("Kept on this device only. Nothing is sent anywhere. These are the site’s own settings, so they carry to every page."))}</p></div>
</section>`;
  D.body.append(root);
  rail = $(".ln-rail", root); stack = $(".ln-stack", root);
  /* "Put everything back": the shell's own button, with its own listener; on the other pages, the page's own reset */
  const reset = src && $("[data-tca-reset]", src);
  if (O.kind === "shell" && reset) { reset.classList.add("ln-btn"); $(".ln-reset", root).append(reset); }
  else if (O.reset) {
    const b = D.createElement("button"); b.type = "button"; b.className = "ln-btn"; b.textContent = t("Put everything back");
    b.addEventListener("click", () => O.reset()); $(".ln-reset", root).append(b);
  }
  /* the counting switches get a lane of their own where a counting service is set up (on the shell's pages; the other
     pages keep them in Help) */
  const countBox = () => src && $("[data-tca-count-switches]", src);
  const all = LANES.slice();
  if (O.kind === "shell" && countBox()) all.push({id: "count", name: N_("Counting visits"), about: N_("Whether this site counts your visits, and whether it may note your state."),
    tabs: [{id: "switches", name: N_("Your switches"), take: countBox}]});
  lanes = all.map(l => ({...l, tabs: l.tabs.filter(holds)})).filter(l => l.tabs.length && (l.id !== "lang" || langs().length > 1));      // Language only where there is a choice
  $(".ln-lanes", root).innerHTML = lanes.map(l => `<li><button type="button" class="ln-lane" data-lane="${l.id}" aria-expanded="false" aria-controls="ln-p-${l.id}">
<span class="ln-ic">${svg(ICON[l.id] || ICON.sets)}</span><span class="ln-t"><b>${esc(t(l.name))}</b><span class="ln-sum"></span></span><span class="ln-n" hidden></span><span class="ln-chev" aria-hidden="true">&lsaquo;</span></button></li>`).join("");
  /* a closed lane waits in a hidden holder, still on the page, so the page keeps its controls in step with every change */
  for (const l of lanes) { const p = makePanel(l); panels.set(l.id, p); $(".ln-keep", root).append(p); }
  rail.addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.hasAttribute("data-ln-close")) closeAll(true);
    else if (b.classList.contains("ln-all")) { closeLanes(); $("#ln-h").focus(); }
    else if (b.dataset.lane) openLane(b.dataset.lane, {from: b});
    else if (b.dataset.jump) { const [lane, tab] = b.dataset.jump.split(":"); openLane(lane, {from: b, tab}); }
  });
  H.addEventListener("tca:axes", () => { syncMade(); draw(); });
  for (const el of $$("[data-preset]", root)) el.addEventListener("click", () => setTimeout(draw, 0));
  syncMade(); drawLang();
}

function makePanel(lane) {
  const p = D.createElement("section");
  p.className = "ln-panel"; p.id = "ln-p-" + lane.id; p.dataset.lane = lane.id;
  p.setAttribute("role", "region"); p.setAttribute("aria-labelledby", p.id + "-h");
  const name = t(lane.name);
  const tabs = lane.tabs.map(x => `<button type="button" class="ln-tab" data-tab="${tabKey(x)}" aria-expanded="false" aria-controls="ln-b-${lane.id}-${tabKey(x)}"><span>${esc(tabName(x))}</span>${svg(PIN, "ln-pin")}</button>`).join("");
  p.innerHTML = `<header class="ln-ph"><span class="ln-ic">${svg(ICON[lane.id] || ICON.sets)}</span><h3 id="${p.id}-h" tabindex="-1">${esc(name)}</h3><button type="button" class="ln-x" data-ln-shut aria-label="${esc(t("Close {lane}", {lane: name}))}">${X}</button></header>
<p class="ln-about">${esc(t(O.kind === "rider" && lane.aboutRider ? lane.aboutRider : lane.about))}</p>
<div class="ln-tabs" role="group" aria-label="${esc(t("{lane}: click a tab to pin it open, click again to unpin", {lane: name}))}">${tabs}</div>
<div class="ln-boxes"></div>
<p class="ln-empty" hidden>${esc(t("Nothing pinned in this lane. Click a tab above to pin it here."))}</p>`;
  const boxes = $(".ln-boxes", p);
  for (const x of lane.tabs) {
    if (x.axis) x.label = legend(x.axis);      // read while the fieldset is still where the page put it
    const k = tabKey(x), box = D.createElement("div"), tn = tabName(x);
    box.className = "ln-box"; box.id = `ln-b-${lane.id}-${k}`; box.dataset.tab = k; box.hidden = true;
    box.setAttribute("role", "group"); box.setAttribute("aria-label", tn);
    box.innerHTML = `<div class="ln-bh"><b>${esc(tn)}</b><button type="button" class="ln-unpin" data-unpin="${k}" aria-label="${esc(t("Unpin {tab}", {tab: tn}))}" title="${esc(t("Unpin"))}">${svg(PIN)}</button></div>`;
    if (x.axis) { const s = seg(x.axis); if (s) { SEG[x.axis] = s; box.append(s); } }
    else if (x.level) {      /* Meet me where I am: the shell's own chooser, or one drawn here with the page's own settings */
      let el = O.kind === "shell" ? $("#tca-access [data-tca-meet]") : null;
      if (!el) { el = D.createElement("div"); chooser(el, {apply: O.apply, axes: O.axes}); }
      KEPT[k] = el; box.append(el);
    }
    else if (x.take) { const el = x.take(); if (el) { KEPT[k] = el; box.append(el); } }
    else if (x.make) box.append(x.make());
    else if (x.presets) {
      const ul = D.createElement("ul"); ul.className = "tca-presets";
      for (const id of x.presets) { const b = presetBtn(id); if (b) { PRE[id] = b; ul.append(b.closest("li") || b); } }
      box.append(ul);
    }
    boxes.append(box);
  }
  p.addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b || !p.contains(b)) return;
    if (b.hasAttribute("data-ln-shut")) closeLane(lane.id, true);
    else if (b.classList.contains("ln-tab")) togglePin(lane.id, b.dataset.tab, b);
    else if (b.dataset.unpin) togglePin(lane.id, b.dataset.unpin, $(`.ln-tab[data-tab="${b.dataset.unpin}"]`, p));
  });
  return p;
}

/* ---------- pins: a tab clicked is pinned open in its lane, in the order pinned, and kept on this device ---------- */
function pins(laneId) { const v = saved.pins[laneId]; return Array.isArray(v) ? v : null; }
function setPins(laneId, list) { saved = store.get(); saved.pins[laneId] = list; store.set(saved); }
function laneOf(id) { return lanes.find(l => l.id === id); }
function showPins(laneId) {
  const p = panels.get(laneId), lane = laneOf(laneId), boxes = $(".ln-boxes", p);
  const list = (pins(laneId) || []).filter(k => lane.tabs.some(x => tabKey(x) === k));      // a tab this page does not hold stays pinned for pages that do
  for (const k of list) { const b = $(`.ln-box[data-tab="${k}"]`, p); if (b) boxes.append(b); }      // pinned order
  for (const b of $$(".ln-box", p)) b.hidden = !list.includes(b.dataset.tab);
  for (const x of $$(".ln-tab", p)) x.setAttribute("aria-expanded", list.includes(x.dataset.tab) ? "true" : "false");
  $(".ln-empty", p).hidden = list.length > 0;
  drawShelf();
}
function togglePin(laneId, k, tabBtn) {
  const lane = laneOf(laneId), x = lane.tabs.find(y => tabKey(y) === k), name = tabName(x);
  const list = (pins(laneId) || []).slice(), at = list.indexOf(k);
  if (at >= 0) list.splice(at, 1); else list.push(k);
  setPins(laneId, list); showPins(laneId);
  if (at >= 0) { say(t("{tab} unpinned.", {tab: name})); if (tabBtn) tabBtn.focus(); }
  else {
    say(t("{tab} pinned.", {tab: name}));
    const box = $(`#ln-b-${laneId}-${k}`);
    if (box) { box.scrollIntoView({block: "nearest", behavior: quiet() ? "auto" : "smooth"}); flash(box); }
  }
}
function flash(el) { if (quiet()) return; el.classList.remove("ln-flash"); void el.offsetWidth; el.classList.add("ln-flash"); }
function quiet() {
  let os = false; try { os = matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) {}
  return os || H.getAttribute("data-motion") === "reduced" || H.getAttribute("data-calm") === "on" || H.classList.contains("calm");
}

/* ---------- lanes open right to left: the first next to the rail, each one after it to the left of the last ---------- */
function openLane(id, {tab} = {}) {
  const p = panels.get(id), lane = laneOf(id); if (!p || !lane) return;
  const keys = lane.tabs.map(tabKey);
  if (!(pins(id) || []).some(k => keys.includes(k))) setPins(id, [...(pins(id) || []), keys[0]]);      // a lane opened for the first time here shows its first tab
  if (tab && !(pins(id) || []).includes(tab)) setPins(id, [...pins(id), tab]);
  showPins(id);
  const fresh = !open.includes(id);
  if (fresh) { open.push(id); stack.append(p); p.classList.remove("ln-new"); void p.offsetWidth; if (!quiet()) p.classList.add("ln-new"); }
  /* on a phone the lanes run down one sheet: bring the lane's heading to the top of it, so the lane just opened is what shows */
  p.scrollIntoView({inline: "nearest", block: narrow() ? "start" : "nearest", behavior: quiet() || fresh ? "auto" : "smooth"});
  const box = tab && $(`#ln-b-${id}-${tab}`);
  if (box) { box.scrollIntoView({block: "nearest"}); flash(box); }
  else if (!fresh) flash(p);
  $(`#${p.id}-h`).focus({preventScroll: true});
  draw();
}
function closeLane(id, restore) {
  const p = panels.get(id), i = open.indexOf(id); if (!p || i < 0) return;
  open.splice(i, 1); $(".ln-keep", root).append(p); p.classList.remove("ln-new");
  draw();
  if (restore) { const b = $(`.ln-lane[data-lane="${id}"]`, rail); if (b) b.focus(); }
}
function closeLanes() { for (const id of open.slice()) closeLane(id, false); }
function triggers() { return $$(`[aria-controls="${O.trigger}"]`); }
function openRail(from) {
  build();
  if (O.closeOthers) O.closeOthers();
  opener = from || D.activeElement;
  if (O.bar) {      /* where the page's own top bar ends, so the rail sits just under it */
    const bar = $(O.bar);
    root.style.setProperty("--bar-bottom", (bar ? Math.max(0, Math.round(bar.getBoundingClientRect().bottom)) : 0) + "px");
  }
  rail.hidden = false; root.classList.add("on");
  for (const b of triggers()) b.setAttribute("aria-expanded", "true");
  syncMade(); draw();
  $("#ln-h").focus({preventScroll: true});
}
function closeAll(restore) {
  if (!root || rail.hidden) return;
  closeLanes(); rail.hidden = true; root.classList.remove("on");
  for (const b of triggers()) b.setAttribute("aria-expanded", "false");
  if (restore && opener && D.contains(opener)) { try { opener.focus({preventScroll: true}); } catch (e) {} }
  opener = null;
}
const isOpen = () => !!root && !rail.hidden;

/* ---------- the rail shows what is set in each lane, which lanes are open, and every pinned tab ---------- */
function draw() {
  if (!root) return;
  for (const l of lanes) {
    const b = $(`.ln-lane[data-lane="${l.id}"]`, rail); if (!b) continue;
    const s = summary(l), n = $(".ln-n", b);
    $(".ln-sum", b).textContent = s.text;
    n.hidden = !s.n; n.textContent = s.n ? t("{n, plural, one {# changed} other {# changed}}", {n: s.n}) : "";
    b.setAttribute("aria-expanded", open.includes(l.id) ? "true" : "false");
  }
  $(".ln-all", rail).hidden = open.length < 2;
  drawShelf();
}
function drawShelf() {
  if (!rail) return;
  const shelf = $(".ln-shelf", rail), ul = $("ul", shelf), items = [];
  for (const l of lanes) for (const k of pins(l.id) || []) {
    const x = l.tabs.find(y => tabKey(y) === k); if (!x) continue;
    items.push(`<li><button type="button" data-jump="${l.id}:${k}"><span class="ln-ic">${svg(ICON[l.id] || ICON.sets)}</span>${esc(tabName(x))}</button></li>`);
  }
  ul.innerHTML = items.join(""); shelf.hidden = !items.length;
}

/* ---------- start: the page hands over its own settings; Reading & access then opens the lanes ---------- */
export function start(opts) {
  if (O) return api;
  if (opts.kind === "shell") {
    const src = D.getElementById("tca-access");
    if (!src || src.classList.contains("inline")) return null;      // the Access page: the settings are the page itself
  }
  O = {has: [], ...opts};
  D.addEventListener("keydown", e => {
    if (e.key !== "Escape" || !isOpen()) return;
    const inPanel = e.target.closest && e.target.closest(".ln-panel");
    if (inPanel) closeLane(inPanel.dataset.lane, true);
    else if (rail.contains(e.target) || !open.length) closeAll(true);
    else closeLane(open[open.length - 1], true);
    e.preventDefault(); e.stopPropagation();
  }, true);
  for (const b of $$("[data-ln-open]")) b.addEventListener("click", () => openRail(b));
  if (opts.hash) addEventListener("hashchange", fromHash);
  setTimeout(() => { if (!reopen() && opts.hash) fromHash(); }, 300);      // after the page has wired its controls
  return api;
}
/* a lane named in the address opens on arrival (#lanes, #lanes=text,colour), so a link can show one (the shell's pages) */
function fromHash() {
  const m = /^#lanes(?:=([a-z]+(?:,[a-z]+)*))?$/.exec(location.hash); if (!m) return;
  openRail(null);
  for (const id of (m[1] || "").split(",").filter(Boolean)) if (panels.has(id)) openLane(id, {});
}
/* back from choosing a language: the Language lane opens again, once the page has drawn its controls */
function reopen() {
  let want = null; try { want = sessionStorage.getItem(REOPEN); sessionStorage.removeItem(REOPEN); } catch (e) {}
  if (!want) return false;
  openRail(null); if (panels.has(want)) openLane(want, {});
  return true;
}
const api = {
  toggle(from) { if (isOpen()) closeAll(true); else openRail(from); },
  open: openRail, close: closeAll, isOpen, lane: id => { openRail(null); openLane(id, {}); }
};
