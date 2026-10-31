/* the top movers in the forecasts, as a ticker (movers.py writes this file and data/movers.json beside it; John, 2026-10-30).
   A page names a box for it: <div data-mvx></div>; the script fills every such box once the page has drawn it (window.MVX.mount
   for a page that draws later). Each item links to the race's chart. Motion off, Calm on or the device's reduced motion: no
   movement, the items in a row that scrolls by hand. */
(() => {
  const ME = document.currentScript, BASE = ME ? new URL(".", ME.src) : new URL("./", location.href);
  const SRC = new URL("data/movers.json" + (ME && ME.dataset.v ? "?v=" + ME.dataset.v : ""), BASE).href;
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const pct = t => t >= 995 ? "over 99%" : t < 5 ? "under 1%" : `${Math.round(t / 10)}%`;      /* never 0 or 100 */
  const pts = m => { const v = Math.abs(m) / 10; return v >= 9.5 ? String(Math.round(v)) : (Math.round(v * 10) / 10).toString(); };
  const dayW = iso => { const [y, m, d] = String(iso || "").split("-").map(Number); return y ? new Date(y, m - 1, d).toLocaleDateString("en-US", {weekday: "short", month: "short", day: "numeric"}) : ""; };
  const H = document.documentElement;
  const still = () => H.dataset.motion === "reduced" || H.dataset.calm === "on" || H.classList.contains("calm") || matchMedia("(prefers-reduced-motion: reduce)").matches;
  let DATA = null, ASK = null;
  const load = () => ASK || (ASK = fetch(SRC).then(r => r.ok ? r.json() : Promise.reject(new Error(String(r.status)))).then(d => (DATA = d)));
  const item = (i, hidden) => `<li><a href="${esc(new URL(i.u, BASE).href)}"${hidden ? ' tabindex="-1"' : ""}>`
    + `<span class="mvx-dot ${esc(i.p)}" aria-hidden="true"></span><span class="mvx-st">${esc(i.w)}</span> <span class="mvx-o">${esc(i.o)}</span>`
    + ` <span>${esc(i.n)}</span> <span class="mvx-c">${pct(i.c)}</span>`
    + ` <span class="mvx-d ${i.m > 0 ? "up" : "dn"}" title="${esc(`${i.m > 0 ? "Up" : "Down"} ${pts(i.m)} points since ${dayW(i.b)}`)}"><span class="sr">${i.m > 0 ? "up" : "down"} </span>${pts(i.m)}</span>`
    + (i.f ? ` <span class="mvx-f">now leads</span>` : "") + `</a></li>`;
  function fill(box){
    if (!box || box.dataset.mvxDone) return; box.dataset.mvxDone = "1";
    if (!document.getElementById("mvx-css")) { const s = document.createElement("style"); s.id = "mvx-css"; s.textContent = ".mvx{--mvD:var(--pD,#1238B8);--mvR:var(--pR,#A51E16);--mvO:var(--muted,#6b6b6b);position:relative;margin:14px 0 4px;border:1px solid var(--line,rgba(0,0,0,.14));border-radius:12px;background:var(--surface,#fff);display:flex;align-items:stretch;overflow:hidden;font-size:14px;line-height:1.3;min-height:44px}\n.mvx-lab{flex:none;display:flex;flex-direction:column;justify-content:center;gap:1px;padding:6px 12px;border-right:1px solid var(--line,rgba(0,0,0,.14));background:color-mix(in srgb,var(--ink,#111) 5%,var(--surface,#fff));max-width:42%}\n.mvx-lab b{font-size:12px;letter-spacing:.08em;text-transform:uppercase}\n.mvx-lab small{font-size:12px;color:var(--muted,#555);white-space:nowrap}\n.mvx-vp{flex:1;min-width:0;overflow:hidden;display:flex;align-items:center;-webkit-mask-image:linear-gradient(90deg,transparent,#000 18px,#000 calc(100% - 18px),transparent);mask-image:linear-gradient(90deg,transparent,#000 18px,#000 calc(100% - 18px),transparent)}\n.mvx-run{display:flex;width:max-content;animation:mvx-go var(--mvx-dur,60s) linear infinite}\n.mvx-trk{list-style:none;margin:0;padding:0 8px 0 0;display:flex;gap:6px}\n.mvx-trk li{flex:none}\n.mvx-trk a{display:inline-flex;align-items:center;gap:6px;padding:8px 10px;border-radius:8px;color:inherit;text-decoration:none;white-space:nowrap;min-height:28px}\n.mvx-trk a:hover{background:color-mix(in srgb,var(--ink,#111) 7%,transparent)}\n.mvx-trk a:focus-visible{outline:3px solid var(--accent,#2F6B5E);outline-offset:-2px}\n.mvx-dot{width:9px;height:9px;border-radius:50%;background:var(--mvO);flex:none}\n.mvx-dot.D{background:var(--mvD)}.mvx-dot.R{background:var(--mvR)}\n.mvx-st{font-weight:700}\n.mvx-o{color:var(--muted,#555)}\n.mvx-c{font-weight:700;font-variant-numeric:tabular-nums}\n.mvx-d{font-variant-numeric:tabular-nums;font-weight:600;padding:1px 6px;border-radius:999px;border:1px solid var(--line-strong,rgba(0,0,0,.3))}\n.mvx-d.up::before{content:\"\\25B2\\00A0\" / \"\"}.mvx-d.dn::before{content:\"\\25BC\\00A0\" / \"\"}\n.mvx .sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap}\n.mvx-f{font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--accent-ink,var(--accent,#2F6B5E))}\n.mvx-ctl{flex:none;display:flex;align-items:center;padding:0 6px;border-left:1px solid var(--line,rgba(0,0,0,.14))}\n.mvx-ctl button{all:unset;box-sizing:border-box;cursor:pointer;min-width:44px;min-height:44px;display:inline-flex;align-items:center;justify-content:center;border-radius:8px;font-size:13px;font-weight:600;padding:0 8px}\n.mvx-ctl button:hover{background:color-mix(in srgb,var(--ink,#111) 7%,transparent)}\n.mvx-ctl button:focus-visible{outline:3px solid var(--accent,#2F6B5E);outline-offset:-2px}\n.mvx.paused .mvx-run,.mvx:hover .mvx-run,.mvx:focus-within .mvx-run{animation-play-state:paused}\n.mvx-none{padding:10px 12px;color:var(--muted,#555)}\n@keyframes mvx-go{to{transform:translateX(-50%)}}\n.mvx.still .mvx-run{animation:none}\n.mvx.still .mvx-vp{overflow-x:auto;-webkit-mask-image:none;mask-image:none;scrollbar-width:thin}\n.mvx.still .mvx-trk[aria-hidden],.mvx.still .mvx-ctl{display:none}\n@media (prefers-reduced-motion:reduce){.mvx .mvx-run{animation:none}.mvx .mvx-vp{overflow-x:auto;-webkit-mask-image:none;mask-image:none}.mvx .mvx-trk[aria-hidden],.mvx .mvx-ctl{display:none}}\n@media (max-width:640px){.mvx{flex-wrap:wrap}.mvx-lab{max-width:none;flex:1 1 100%;flex-direction:row;flex-wrap:wrap;align-items:baseline;gap:2px 8px;border-right:0;border-bottom:1px solid var(--line,rgba(0,0,0,.14))}.mvx-lab b{white-space:nowrap}.mvx-vp{flex:1 1 180px}}"; document.head.appendChild(s); }
    load().then(d => {
      const L = d.items || [];
      box.classList.add("mvx"); box.setAttribute("role", "region"); box.setAttribute("aria-label", "Top movers in the forecasts");
      const lab = `<div class="mvx-lab"><b>Top movers</b><small>${d.since ? `since ${esc(dayW(d.since))}&rsquo;s forecast` : "in the forecasts"} &middot; <span class="tag analysis">Analysis</span></small></div>`;
      if (!L.length) { box.innerHTML = lab + `<p class="mvx-none">No race&rsquo;s forecast moved by a point or more since the previous day.</p>`; return; }
      box.innerHTML = lab + `<div class="mvx-vp"><div class="mvx-run"><ul class="mvx-trk">${L.map(i => item(i)).join("")}</ul><ul class="mvx-trk" aria-hidden="true">${L.map(i => item(i, true)).join("")}</ul></div></div>`
        + `<div class="mvx-ctl"><button type="button" aria-pressed="false" title="Pause the ticker">Pause</button></div>`;
      const run = box.querySelector(".mvx-run"), btn = box.querySelector(".mvx-ctl button");
      const pace = () => { const w = run.scrollWidth / 2; run.style.setProperty("--mvx-dur", `${Math.max(20, Math.round(w / 55))}s`); };
      const motion = () => box.classList.toggle("still", still());
      btn.addEventListener("click", () => { const on = !box.classList.contains("paused"); box.classList.toggle("paused", on); btn.setAttribute("aria-pressed", String(on)); btn.textContent = on ? "Play" : "Pause"; btn.title = on ? "Play the ticker" : "Pause the ticker"; });
      motion(); pace();
      new MutationObserver(motion).observe(H, {attributes: true, attributeFilter: ["data-motion", "data-calm", "class"]});
      let t = 0; addEventListener("resize", () => { clearTimeout(t); t = setTimeout(pace, 200); });
    }, () => { box.hidden = true; });
  }
  const mount = el => (el ? [el] : [...document.querySelectorAll("[data-mvx]")]).forEach(fill);
  window.MVX = {mount};
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => mount()); else mount();
})();
