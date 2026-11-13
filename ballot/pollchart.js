/* ---------- the chart pop-out (John, 2026-10-24): a race's polls, our average and the model's forecast on one chart, the forecast's
   worked steps, and the feed's attention counts beside it, never inside it. One script for the Congress pages and every state's ballot
   page, loaded after the page: the page says what it knows about a race through window.PCX, and each race's figures come in a file of
   their own (data/chart/<race>.json) the first time its pop-out opens. Its style rides inside it ---------- */
(() => {
  const PX = window.PCX; if (!PX || window.PC) return;
  const DAY = 864e5, files = {};
  const $ = (s, el) => (el || document).querySelector(s), $$ = (s, el) => [...(el || document).querySelectorAll(s)];
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const keepH = s => RAW(`<span translate="no">${esc(s)}</span>`);
  const LEVEL = () => +document.documentElement.dataset.level || 3;
  const fmtDate = iso => iso ? I18.date(String(iso), {month: "long", day: "numeric", year: "numeric"}) : "";
  const PV = {D: "var(--pD)", R: "var(--pR)", L: "var(--pL)", G: "var(--pG)", I: "var(--pI)", W: "var(--pW)", O: "var(--pO)"};
  const pcVar = c => PV[(c || {}).pc] || PV.O;
  const surname = n => String(n).replace(/,?\s+(Jr\.?|Sr\.?|II|III|IV)$/i, "").trim().split(/\s+/).pop().toLowerCase();
  /* a poll's dates, its sample and who paid for it, written as a race's Polls tab writes them */
  const dayRange = (a, b) => { const u = s => new Date(Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)));
    try { return new Intl.DateTimeFormat(I18.loc, {month: "long", day: "numeric", year: "numeric", timeZone: "UTC"}).formatRange(u(a), u(b)); } catch (e) { return `${fmtDate(a)} – ${fmtDate(b)}`; } };
  const pollRange = p => !p.start || p.start === p.end ? esc(fmtDate(p.end)) : !I18.en ? esc(dayRange(p.start, p.end))
    : p.start.slice(0, 7) === p.end.slice(0, 7) ? esc(fmtDate(p.end)).replace(/ (\d+),/, (_m, d) => ` ${+p.start.slice(8)}&ndash;${d},`) : `${esc(fmtDate(p.start).replace(/, \d{4}$/, ""))}&ndash;${esc(fmtDate(p.end))}`;
  const pollSample = p => p.sample ? esc(p.sample) : p.n ? `${I18.num(Number(p.n))} ${esc(p.pop || "")}${p.moe != null ? `, &plusmn;${p.moe}` : ""}` : "";
  const paidWords = p => p.cp ? `<b>${p.cp === "party" ? TH("Paid for by a party") : TH("Paid for by a campaign")}${p.sponsor ? `: ${esc(p.sponsor)}` : ""}</b>`
    : p.sponsor && !String(p.pollster).includes(p.sponsor) ? TH("for {sponsor}", {sponsor: keepH(p.sponsor)}) : "";
  if (!document.getElementById("pcd-style")) { const st = document.createElement("style"); st.id = "pcd-style"; st.textContent = "/* the chart pop-out (John, 2026-10-24): the button, the dialog over a blurred and greyed page, the chart */\n.pcopen{display:flex;gap:6px 12px;align-items:center;flex-wrap:wrap;margin:14px 0 2px}.pcopen>span{font-size:13px;color:var(--muted)}\n.pcbtn{all:unset;box-sizing:border-box;cursor:pointer;display:inline-flex;align-items:center;gap:8px;min-height:40px;padding:6px 16px;border-radius:999px;background:var(--ink);color:var(--bg);font:700 14px var(--sans)}\n.pcbtn svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}\n.pcbtn:hover{opacity:.9}.pcbtn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}\n.pcinline{display:flex;gap:8px 10px;align-items:center;flex-wrap:wrap;margin:16px 0 4px}.pcinline .pcbtn{min-height:44px;padding:8px 18px;font-size:15px}\n.pcpin{position:fixed;z-index:25;top:72px;right:max(12px,env(safe-area-inset-right),calc((100vw - 1180px) / 2 + 20px))}\n.pcpin[hidden]{display:none}\n.pcpinbtn{min-height:44px;padding:8px 16px;box-shadow:0 12px 26px -12px rgba(0,0,0,.6),0 0 0 1px color-mix(in srgb,var(--bg) 35%,transparent)}\n:root:not(.calm) .pcpin:not([hidden]){animation:pcpinin .2s var(--ease,ease-out) both}\n@keyframes pcpinin{from{opacity:0;transform:translateY(-6px)}}\n@media (prefers-reduced-motion:reduce){.pcpin:not([hidden]){animation:none!important}}\n/* how the forecast is worked out: six steps, each a card with an arrow to the next (a column on a phone, rows of two or three wider) */\n.pcd-ix{margin:24px 0 0;border-top:1px solid var(--line);padding-top:16px}\n.pcd-ix>h3{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-family:var(--serif);font-weight:400;font-size:clamp(22px,2.8vw,28px);line-height:1.15;margin:0}\n.ix-lead{font-size:13.5px;color:var(--muted);margin:6px 0 0;max-width:80ch;line-height:1.5}\n.ix-flow{list-style:none;margin:16px 0 0;padding:0;display:grid;grid-template-columns:minmax(0,1fr);gap:32px}\n.ix-step{position:relative;min-width:0;border:1px solid var(--line);border-radius:16px;background:var(--bg);padding:12px 14px 14px}\n.ix-step:not(:last-child)::after{content:\"\\2193\";position:absolute;left:50%;bottom:-28px;transform:translateX(-50%);font:700 20px/1 var(--sans);color:var(--accent)}\n.ix-h{display:flex;gap:10px;align-items:center}.ix-h h4{margin:0;font-size:15.5px;line-height:1.25}\n.ix-n{flex:none;width:28px;height:28px;border-radius:50%;display:grid;place-items:center;background:var(--ink);color:var(--bg);font:700 14px var(--sans)}\n.ix-big{font-family:var(--serif);font-size:34px;line-height:1.05;margin:10px 0 0;font-variant-numeric:tabular-nums}\n.ix-cap{font-size:12.5px;color:var(--muted);margin:3px 0 0;line-height:1.4}\n.ix-vz{margin:10px 0 0}.ix-viz{display:block;width:100%;max-width:340px;height:auto;overflow:visible}.ix-viz.ix-dots{max-width:250px}\n.ix-viz text{font:12px var(--sans);fill:var(--muted)}.ix-viz .ix-strong{fill:var(--ink);font-weight:700}\n.ix-bar{fill:color-mix(in srgb,var(--ink) 55%,transparent)}.ix-zero,.ix-axis{stroke:var(--line-strong);stroke-width:1}.ix-even{stroke:var(--ink);stroke-dasharray:3 3}\n.ix-plain{font-size:14px;line-height:1.5;margin:10px 0 0}\n.ix-figs{margin:8px 0 0}.ix-figs p,.ix-figs li{font-size:13.5px;line-height:1.5}.ix-figs p{margin:6px 0 0}.ix-figs ul{margin:6px 0 0;padding-left:18px}\n.ix-form{font-size:12.5px;line-height:1.55;margin:8px 0 0;padding:8px 10px;border-radius:10px;background:color-mix(in srgb,var(--ink) 6%,transparent);font-variant-numeric:tabular-nums;overflow-wrap:anywhere}\n.ix-run{margin-top:14px}.ix-run a{color:var(--accent-ink,var(--accent))}\n@media (min-width:700px){.ix-flow{grid-template-columns:repeat(2,minmax(0,1fr));gap:24px 38px}\n  .ix-step:not(:last-child)::after{content:\"\\2192\";left:auto;right:-30px;top:50%;bottom:auto;transform:translateY(-50%)}\n  .ix-step:nth-child(2n):not(:last-child)::after{content:\"\\2199\";right:auto;left:-8px;top:auto;bottom:-25px;transform:none}}\n@media (min-width:1000px){.ix-flow{grid-template-columns:repeat(3,minmax(0,1fr))}\n  .ix-step:nth-child(n):not(:last-child)::after{content:\"\\2192\";left:auto;right:-30px;top:50%;bottom:auto;transform:translateY(-50%)}\n  .ix-step:nth-child(3n):not(:last-child)::after{content:\"\\2199\";right:auto;left:-8px;top:auto;bottom:-25px;transform:none}}\n:root.pcd-lock,:root.pcd-lock body{overflow:hidden}\n.pcd{box-sizing:border-box;width:min(1080px,calc(100% - 40px));max-width:none;max-height:calc(100dvh - 40px);margin:auto;padding:0;border:1px solid var(--line-strong);border-radius:24px;background:var(--surface);color:var(--ink);box-shadow:0 40px 90px -40px rgba(0,0,0,.7);overflow:hidden}\n.pcd::backdrop{background:rgba(14,16,22,.62)}\n@supports ((-webkit-backdrop-filter:blur(2px)) or (backdrop-filter:blur(2px))){.pcd::backdrop{background:rgba(60,62,68,.4);-webkit-backdrop-filter:blur(8px) grayscale(.85);backdrop-filter:blur(8px) grayscale(.85)}}\n.pcd-in{box-sizing:border-box;max-height:calc(100dvh - 42px);overflow:auto;overscroll-behavior:contain;padding:0 24px 22px}\n.pcd-top{position:sticky;top:0;z-index:4;display:flex;justify-content:space-between;align-items:flex-start;gap:12px;padding:18px 0 12px;background:var(--surface);border-bottom:1px solid var(--line)}\n.pcd-kick{font-size:11.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}\n.pcd-top h2{font-family:var(--serif);font-weight:400;font-size:clamp(24px,3.2vw,36px);line-height:1.05;margin:4px 0 0;outline:none}\n.pcd-x{all:unset;box-sizing:border-box;cursor:pointer;flex:none;width:44px;height:44px;display:grid;place-items:center;border-radius:50%;border:1px solid var(--line-strong);font:400 28px/1 var(--sans);color:var(--ink);background:var(--surface)}\n.pcd-x:hover{border-color:var(--ink)}.pcd-x:focus-visible{outline:2px solid var(--accent);outline-offset:2px}\n.pcd-acts{flex:none;display:flex;gap:8px;align-items:center}.pcd-acts .tca-share{margin:0}\n@media (max-width:520px){.pcd-acts .tca-share span{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}}\n.pcd .lvplain{margin:14px 0 0}\n.pcd-ctl{display:flex;gap:10px 14px;flex-wrap:wrap;align-items:center;margin:16px 0 0}\n.pcd-chk{display:inline-flex;gap:7px;align-items:center;font:600 13.5px var(--sans);cursor:pointer;min-height:36px}\n.pcd-chk input{width:18px;height:18px;margin:0;accent-color:var(--accent)}\n.pcd-pick{margin:12px 0 0}.pcd-pick:empty{display:none}\n.pcd-sel{display:inline-flex;gap:8px;align-items:center;flex-wrap:wrap;font:600 13.5px var(--sans)}\n.pcd-sel select{height:40px;max-width:100%;border-radius:999px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);padding:0 12px;font:600 14px var(--sans)}\n.pcd-sel select:focus-visible{outline:2px solid var(--accent);outline-offset:2px}\n.pcd-ticks{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:0 16px;max-height:212px;overflow-y:auto;overscroll-behavior:contain;border:1px solid var(--line);border-radius:14px;padding:0 12px 8px;background:var(--bg)}\n.pcd-ticks p{grid-column:1/-1;position:sticky;top:0;z-index:1;margin:0;padding:8px 0 4px;background:var(--bg);font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}\n.pcd-ticks:focus-visible{outline:2px solid var(--accent);outline-offset:2px}\n.pcd-ticks label{display:flex;gap:8px;align-items:flex-start;font-size:13.5px;padding:5px 0;cursor:pointer;line-height:1.35}\n.pcd-ticks input{width:17px;height:17px;margin:1px 0 0;flex:none;accent-color:var(--accent)}.pcd-ticks small{display:block;color:var(--muted);font-size:12px}\n.pcd-tickbtns{margin:6px 0 0;display:flex;gap:12px;flex-wrap:wrap}\n.pcd-lnk{all:unset;cursor:pointer;font:600 13px var(--sans);color:var(--accent-ink,var(--accent));text-decoration:underline;text-underline-offset:3px;padding:4px 0}\n.pcd-lnk:focus-visible{outline:2px solid var(--accent);outline-offset:2px}\n.pcd-fig{position:relative;margin:14px 0 0}\n.pcd-svg svg{display:block;width:100%;height:auto;overflow:visible;user-select:none;-webkit-user-select:none;touch-action:manipulation}\n.pcd-svg text{font:12px var(--sans);fill:var(--muted)}\n.pcd-svg .lab{font-weight:700;fill:var(--ink);paint-order:stroke;stroke:var(--surface);stroke-width:4px;stroke-linejoin:round}\n.pcd-svg .ana{fill:var(--muted);font-weight:700;letter-spacing:.04em}\n.pcd-svg .end{font-weight:700;paint-order:stroke;stroke:var(--surface);stroke-width:4px;stroke-linejoin:round}\n.pcd-svg .gl{stroke:var(--line);stroke-width:1}.pcd-svg .axl{stroke:var(--line-strong);stroke-width:1}\n.pcd-svg .vl{stroke:var(--muted);stroke-width:1;stroke-dasharray:3 4}.pcd-svg .ed{stroke:var(--ink);stroke-width:1.4}\n.pcd-svg .md{stroke-width:2;stroke-dasharray:6 4}\n.pcd-svg .b95{fill-opacity:.13}.pcd-svg .b80{fill-opacity:.26;stroke-opacity:.55;stroke-width:1}\n:root[data-theme=\"dark\"] .pcd-svg .b95{fill-opacity:.2}:root[data-theme=\"dark\"] .pcd-svg .b80{fill-opacity:.36;stroke-opacity:.9}\n:root[data-theme=\"dark\"] .pcd-svg .band{mix-blend-mode:screen}\n.pcd-svg .avg{fill:none;stroke-width:2.6;stroke-linejoin:round}\n.pcd-svg .pt circle{stroke-width:2;fill:var(--surface)}.pcd-svg .pt.mem circle{stroke:var(--surface)}\n.pcd-svg .pt,.pcd-svg .band,.pcd-svg .hist,.pcd-svg .avgpt{cursor:pointer;outline:none}\n.pcd-svg .pt:focus-visible circle,.pcd-svg .pt.on circle{stroke:var(--ink);stroke-width:3}\n.pcd-svg .band:focus-visible polygon{stroke:var(--ink);stroke-width:1.5}\n.pcd-svg .hist line{stroke-width:2;opacity:.75}.pcd-svg .hist path{stroke:var(--surface);stroke-width:1.5}\n.pcd-svg .hist:focus-visible path,.pcd-svg .avgpt:focus-visible circle{stroke:var(--ink);stroke-width:2.5}\n.pcd-tip{position:absolute;z-index:3;left:0;top:0;width:max-content;max-width:min(330px,calc(100% - 8px));pointer-events:none;background:var(--surface);color:var(--ink);border:1px solid var(--line-strong);border-radius:12px;padding:9px 12px;font-size:13px;line-height:1.45;box-shadow:0 16px 34px -18px rgba(0,0,0,.6)}\n.pcd-tip[hidden]{display:none}.pcd-tip small{color:var(--muted);font-size:12px}\n.pcd-tip .tl{display:grid;gap:2px;margin:4px 0}.pcd-tip .tl i,.pcd-leg i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:-1px}\n.pcd-leg{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12.5px;color:var(--muted);margin:8px 0 0}.pcd-leg>span{display:inline-flex;align-items:center;gap:2px}\n.pcd-leg i.lg-grey{background:var(--muted)}.pcd-leg i.lg-hollow{border:2px solid var(--muted);box-sizing:border-box;background:var(--surface)}\n.pcd-leg i.lg-line{width:18px;height:3px;border-radius:2px;background:var(--ink)}\n.pcd-leg i.lg-band{width:18px;height:11px;border-radius:2px;background:color-mix(in srgb,var(--muted) 34%,transparent)}\n.pcd-leg i.lg-dia{width:9px;height:9px;border-radius:1px;background:var(--muted);transform:rotate(45deg);margin-right:8px}\n.pcd-leg .tag{height:18px;font-size:10px;margin-left:4px}\n.pcd-early,.pcd-avgnote{max-width:80ch}.pcd-avgnote{font-size:13.5px;margin:10px 0 0;line-height:1.5}.pcd-avgnote a,.pcd-box a{color:var(--accent-ink,var(--accent))}\n.pcd-onecard{margin:12px 0 0;border:1px solid var(--line);border-left:4px solid var(--gold,var(--line-strong));border-radius:14px;padding:12px 14px;background:var(--bg);font-size:14px}\n.pcd-onecard[hidden]{display:none}.pcd-onecard p{margin:6px 0 0}.pcd-onecard ul{margin:6px 0 0;padding-left:18px}.pcd-onecard .tag{vertical-align:2px;margin-left:6px}\n.pcd-grid{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);gap:14px;margin:18px 0 0;align-items:start}\n.pcd-box{border:1px solid var(--line);border-radius:18px;padding:12px 16px 14px;background:var(--bg)}\n.pcd-box h3{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-family:var(--serif);font-weight:400;font-size:23px;line-height:1.1;margin:2px 0 4px}\n.pcd-box p{font-size:13.5px;line-height:1.5;margin:8px 0 0}.pcd-box .fnote{font-size:12.5px}\n.pcd-fcl{list-style:none;margin:10px 0 0;padding:0;display:grid;gap:6px}.pcd-fcl li{border-left:4px solid var(--pc);padding:3px 0 3px 10px;font-size:14px;line-height:1.4}\n.pcd-how{margin:10px 0 0;border-top:1px solid var(--line);padding-top:6px}.pcd-how summary{cursor:pointer;font:600 13px var(--sans);padding:4px 0}.pcd-how p{color:var(--muted)}\n.pcd-bars{list-style:none;margin:10px 0 0;padding:0;display:grid;gap:6px}\n.pcd-bars li{display:grid;grid-template-columns:minmax(90px,auto) 1fr auto;gap:8px;align-items:center;font-size:13px}\n.pcd-bars .b{height:10px;border-radius:5px;background:var(--line);overflow:hidden}.pcd-bars .b i{display:block;height:100%;background:var(--pc)}\n.pcd-foot{max-width:90ch}\n@media (max-width:760px){.pcd-grid{grid-template-columns:1fr}}\n@media (max-width:640px){      /* on a phone the pop-out is a sheet that fills the screen */\n  .pcd{width:100%;height:100%;max-height:none;margin:0;inset:0;border:0;border-radius:0}\n  .pcd-in{height:100%;max-height:none;padding:0 16px 28px}.pcd-top{padding:12px 0 10px}}\n:root:not(.calm) .pcd[open]{animation:pcdin .22s var(--ease,ease-out) backwards}      /* backwards: no transform stays on the dialog after it opens, so a Share menu inside it is placed against the window */\n@keyframes pcdin{from{opacity:0;transform:translateY(16px) scale(.985)}}\n@media (prefers-reduced-motion:reduce){.pcd[open]{animation:none!important}}"; document.head.appendChild(st); }
  const tDay = iso => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));
  const isoOf = t => new Date(t).toISOString().slice(0, 10);
  const todayIso = () => { const n = new Date(); return isoOf(Date.UTC(n.getFullYear(), n.getMonth(), n.getDate())); };
  const sd = iso => I18.date(iso, {month: "short", day: "numeric"});
  /* a run of the model: its date and time on the reader's own clock, and its place on the time line (by its time of day) */
  const sdt = h => h.at ? I18.date(new Date(h.at), {month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short"}) : sd(h.d);
  const tRun = h => tDay(h.d) + (h.f || 0) * DAY;
  const pc = (v, d = 0) => I18.num(v / 100, {style: "percent", minimumFractionDigits: d, maximumFractionDigits: d});
  const chanceW = c => c < 0.01 ? T("under 1%") : c > 0.99 ? T("over 99%") : pc(Math.round(c * 100));      /* never 0 or 100 */
  const nmH = n => `<span translate="no">${esc(n)}</span>`, f1 = v => v.toFixed(1), B = s => `<b>${s}</b>`;
  const ANA = () => `<span class="tag analysis">${TH("Analysis")}</span>`;
  const TI = s => `<a href="https://aapor.org/standards-and-ethics/transparency-initiative/" target="_blank" rel="noopener">${s}</a>`;
  const ICON = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 20h18"/><path d="M4 16l5-6 4 3 7-8"/><circle cx="9" cy="10" r=".6"/><circle cx="13" cy="13" r=".6"/></svg>`;
  const SHARE_SVG = `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>`;
  let S = null, rt = 0;
  /* the chart's own address (John, 2026-10-25): #race=<id>&chart=open opens a race's chart as the page loads (the Forecasts page's
     buttons and Share use it), and a chart opened by its button adds &chart=open to the address as a step of the browser's history,
     so Back closes it; the page's own routing passes over &chart=open, so the race page under the chart stays as it was */
  const CH = /&chart=open(?=&|$)/;
  const hashNow = () => { try { return decodeURIComponent(location.hash.slice(1)); } catch (e) { return location.hash.slice(1); } };
  const raceOf = h => h.startsWith("race=") ? h.slice(5).split("&")[0] : "";
  const wanted = () => { const h = hashNow(); return CH.test(h) ? raceOf(h) : ""; };
  const plainHash = () => location.hash.replace(CH, "");
  const setHash = (h, push, st) => { try { const u = location.pathname + location.search + h; if (push) history.pushState(st, "", u); else history.replaceState(st, "", u); } catch (e) {} };

  /* the race's polls: the members' (counted) and the others' (shown for reference), newest first */
  function pollsOf(r){
    const P0 = PX.polls(r.id) || {};
    return [...(P0.polls || []).map((p, i) => ({...p, id: "m" + i, m: true})), ...(P0.news || []).map((p, i) => ({...p, id: "n" + i, m: false}))]
      .filter(p => p.end && p.shares).sort((a, b) => b.end.localeCompare(a.end) || (b.m - a.m));
  }
  /* the two candidates the chart follows: the model's two leading candidates, else the two the polls ask about most */
  function whoOf(r, polls, F){
    let names = F ? F.top.map(c => c.n) : [];
    if (names.length < 2) { const k = {}; polls.forEach(p => Object.keys(p.shares).forEach(n => { k[n] = (k[n] || 0) + 1; }));
      names = Object.keys(k).sort((a, b) => k[b] - k[a]).slice(0, 2); }
    const g = r.cands || [];
    return names.map(n => { const c = g.find(x => x.n === n) || g.find(x => samePerson(x.n, n)) || {n, pc: "O"};
      return {n, col: pcVar(c), sur: n.trim().split(/\s+/).pop()}; });
  }
  /* a ticket ("A / B", "A and B") is named in a poll by its first name alone: a poll's figures are filed under the name the chart uses */
  const firstOf = n => String(n).split(/\s*\/\s*|\s+(?:and|&)\s+/i)[0];
  const samePerson = (a, b) => surname(firstOf(a)) === surname(firstOf(b));
  const remap = (polls, who) => polls.map(p => { const sh = {};
    Object.entries(p.shares).forEach(([k, v]) => { const w = who.find(x => x.n === k) || who.find(x => samePerson(x.n, k)); sh[w ? w.n : k] = v; });
    return {...p, shares: sh}; });
  /* our average through time: on each day a member's poll ended, the ten most recent members' polls then on record (two or more) */
  function averages(polls, who){
    const ms = polls.filter(p => p.m).sort((a, b) => a.end.localeCompare(b.end)), out = [];
    [...new Set(ms.map(p => p.end))].forEach(d => {
      const ten = ms.filter(p => p.end <= d).sort((a, b) => b.end.localeCompare(a.end)).slice(0, 10); if (ten.length < 2) return;
      const v = {}; who.forEach(w => { const x = ten.filter(p => p.shares[w.n] != null).map(p => p.shares[w.n]); if (x.length) v[w.n] = {x, a: x.reduce((s, y) => s + y, 0) / x.length}; });
      if (Object.keys(v).length) out.push({d, ten, v}); });
    return out;
  }

  /* ---- what a point, a line or the band says when pointed to, tapped or reached by the keyboard ---- */
  const pollTip = p => `<b>${esc(p.pollster)}</b>${paidWords(p) ? ` <small>${paidWords(p)}</small>` : ""}<br><small>${pollRange(p)}${pollSample(p) ? ` &middot; ${pollSample(p)}` : ""}</small>
    <span class="tl">${S.who.filter(w => p.shares[w.n] != null).map(w => `<span><i style="background:${w.col}"></i>${nmH(w.n)} <b>${pc(p.shares[w.n])}</b></span>`).join("")}</span>
    ${p.rest != null ? `<small>${TH("Someone else or undecided: {v}", {v: pc(p.rest)})}</small><br>` : ""}<small>${p.m ? TH("By a member of the Transparency Initiative: counted in our average.") : TH("Not averaged: the pollster is not a member of the Transparency Initiative.")}</small>`;
  const pollLabel = p => `${p.pollster}, ${T("ended {date}", {date: fmtDate(p.end)})}: ${S.who.filter(w => p.shares[w.n] != null).map(w => `${w.n} ${pc(p.shares[w.n])}`).join(", ")}. ${p.m ? T("Counted in our average.") : T("Not averaged.")}`;
  const avgTip = s => `<b>${TH("Our average on {date}", {date: sd(s.d)})}</b>${S.who.filter(w => s.v[w.n]).map(w => { const v = s.v[w.n];
      return `<br>${nmH(w.n)}: (${v.x.map(y => I18.num(y)).join(" + ")}) &divide; ${I18.num(v.x.length)} = <b>${pc(v.a, 1)}</b>`; }).join("")}
    <br><small>${TH("The {n, plural, one {# most recent poll} other {# most recent polls}} by members ending by then: {list}.", {n: s.ten.length, list: RAW(s.ten.map(p => `${esc(p.pollster)} (${esc(sd(p.end))})`).join(", "))})}</small>`;
  const bandTip = c => `<b>${nmH(c.n)}</b> ${ANA()}<br>${TH("The model’s estimate for Election Day: {md}; likely {lo} to {hi} of the vote (80 in 100 of its simulated outcomes), and {lo95} to {hi95} (95 in 100). {chance} chance of winning.",
      {md: pc(c.md, 1), lo: pc(c.l80, 1), hi: pc(c.h80, 1), lo95: pc(c.l95, 1), hi95: pc(c.h95, 1), chance: chanceW(c.ch)})}<br><small>${TH("Not a result: the official count decides.")}</small>`;
  const histTip = h => `<b>${TH("The model’s run of {date}", {date: sdt(h)})}</b> ${ANA()}${S.who.filter(w => h.c[w.n]).map(w => { const v = h.c[w.n];
      return `<br>${nmH(w.n)}: ${TH("{md}; likely {lo} to {hi}; {chance} chance", {md: pc(v[0], 1), lo: pc(v[1], 1), hi: pc(v[2], 1), chance: chanceW(v[3])})}`; }).join("")}
    <br><small>${TH("Its estimate for Election Day as it stood then; method {m}.", {m: keepH(h.m)})}</small>`;

  /* ---- the chart ---- */
  function draw(){
    const box = $(".pcd-svg", S.d); if (!box) return;
    const simple = LEVEL() <= 2, F = S.F, who = S.who;
    const view = simple ? "all" : S.view, range = simple ? "short" : S.range;
    const showAvg = (simple || S.showAvg) && S.avg.length > 0, showFc = !!F && (simple || S.showFc);
    const shown = S.polls.filter(p => view === "all" || (view === "sel" ? S.sel.has(p.id) : p.id === S.one));
    const today = tDay(todayIso()), ED = tDay(PX.election), end = ED + 4 * DAY;
    let start = range === "short" ? today - 60 * DAY
      : Math.min(today, ...shown.map(p => tDay(p.end)), ...(showFc ? F.hist.map(h => tDay(h.d)) : []), ...(showAvg ? [tDay(S.avg[0].d)] : [])) - 10 * DAY;
    if (view === "one" && shown[0] && tDay(shown[0].end) < start + 2 * DAY) {      /* a chosen poll is always in view, and the switch says so */
      start = tDay(shown[0].end) - 10 * DAY;
      if (S.range !== "long") { S.range = "long"; $$(".pcd-ctl [data-r]", S.d).forEach(b => b.setAttribute("aria-pressed", String(b.dataset.r === "long"))); } }
    const vis = shown.filter(p => tDay(p.end) >= start && tDay(p.end) <= end);
    S.early = shown.filter(p => tDay(p.end) < start);
    const W = Math.max(300, Math.round(box.clientWidth || 640)), narrow = W < 560, H = narrow ? 300 : 360;
    const M = {l: 44, r: narrow ? 62 : 108, t: 30, b: 32};
    const ys = [];
    vis.forEach(p => who.forEach(w => { if (p.shares[w.n] != null) ys.push(p.shares[w.n]); }));
    if (showAvg) S.avg.forEach(s => who.forEach(w => { if (s.v[w.n] && tDay(s.d) >= start) ys.push(s.v[w.n].a); }));
    if (showFc) { F.top.forEach(c => c.band.forEach(b => ys.push(b[1], b[4]))); F.hist.forEach(h => who.forEach(w => { const x = h.c[w.n]; if (x && tDay(h.d) >= start) ys.push(x[1], x[2]); })); }
    if (!ys.length) ys.push(40, 50);
    let y0 = Math.max(0, Math.floor((Math.min(...ys) - 2) / 5) * 5), y1 = Math.min(100, Math.ceil((Math.max(...ys) + 2) / 5) * 5);
    if (y1 - y0 < 10) y1 = Math.min(100, y0 + 10);
    const X = t => M.l + (t - start) / (end - start) * (W - M.l - M.r), Y = v => M.t + (y1 - v) / (y1 - y0) * (H - M.t - M.b);
    const tAt = px => start + (px - M.l) / (W - M.l - M.r) * (end - start);
    const o = [], TG = [], tg = (x, y, r, html) => (TG.push({x, y, r, html}), TG.length - 1);
    for (let v = y0; v <= y1; v += 5) o.push(`<line class="gl" x1="${M.l}" x2="${W - M.r}" y1="${f1(Y(v))}" y2="${f1(Y(v))}"/><text x="${M.l - 6}" y="${f1(Y(v) + 4)}" text-anchor="end">${esc(pc(v))}</text>`);
    /* days along the bottom: the first of each month over a long view, the 1st and the 15th over a short one */
    const span = (end - start) / DAY, ticks = [];
    for (let y = new Date(start).getUTCFullYear(), m = new Date(start).getUTCMonth(), k = 0; k < 40; k++) {
      const a = Date.UTC(y, m, 1), b = Date.UTC(y, m, 15); if (a > end) break;
      if (a >= start) ticks.push([a, span > 150]);
      if (span <= 150 && b >= start && b <= end) ticks.push([b, false]);
      if (++m > 11) { m = 0; y++; } }
    const every = narrow && ticks.length > 5 ? 2 : 1;
    o.push(`<line class="axl" x1="${M.l}" x2="${W - M.r}" y1="${H - M.b}" y2="${H - M.b}"/>`);
    ticks.forEach(([t, month], i) => { if (i % every) return; const x = f1(X(t));
      o.push(`<line class="axl" x1="${x}" x2="${x}" y1="${H - M.b}" y2="${H - M.b + 4}"/><text x="${x}" y="${H - M.b + 18}" text-anchor="middle">${esc(month ? I18.date(isoOf(t), {month: "short"}) : sd(isoOf(t)))}</text>`); });
    /* Election Day and today */
    const lab = (x, y, anchor, text) => `<text class="lab" x="${f1(x)}" y="${f1(y)}" text-anchor="${anchor}">${esc(text)}</text>`;
    const xE = X(ED), edW = T("Election Day").length * 6.8, edR = Math.min(W - 2, xE + edW / 2), edL = edR - edW;
    o.push(`<line class="ed" x1="${f1(xE)}" x2="${f1(xE)}" y1="${M.t - 4}" y2="${H - M.b}"/>`, lab(edR, M.t - 10, "end", T("Election Day")));
    if (today >= start && today < ED) { const xT = X(today), tW = T("Today").length * 6.8;
      o.push(`<line class="vl" x1="${f1(xT)}" x2="${f1(xT)}" y1="${M.t - 4}" y2="${H - M.b}"/>`,
        xT + tW / 2 + 6 < edL ? lab(xT, M.t - 10, "middle", T("Today")) : xT - 4 < edL - 6 ? lab(xT - 4, M.t - 10, "end", T("Today")) : lab(xT - 4, H - M.b - 8, "end", T("Today"))); }
    /* the model's band, from the run's day to Election Day: 95 in 100 light, 80 in 100 darker, the median dashed */
    S.bandHit = () => null;
    if (showFc) { const t0 = tDay(F.d0);
      F.top.forEach((c, i) => { const col = who[i].col, P = c.band.map(b => [X(t0 + b[0] * DAY), b]);
        const poly = (u, l) => P.map(([x, b]) => `${f1(x)},${f1(Y(b[u]))}`).concat(P.slice().reverse().map(([x, b]) => `${f1(x)},${f1(Y(b[l]))}`)).join(" ");
        const k = tg(xE, Y(c.md), 0, bandTip(c));
        o.push(`<g class="band" tabindex="0" role="img" data-t="${k}" aria-label="${esc(T("{name}: the model’s estimate for Election Day, {md}; likely {lo} to {hi} of the vote. Analysis.", {name: c.n, md: pc(c.md, 1), lo: pc(c.l80, 1), hi: pc(c.h80, 1)}))}"><polygon class="b95" points="${poly(4, 1)}" style="fill:${col}"/><polygon class="b80" points="${poly(3, 2)}" style="fill:${col};stroke:${col}"/><line class="md" x1="${f1(P[0][0])}" x2="${f1(xE)}" y1="${f1(Y(c.md))}" y2="${f1(Y(c.md))}" style="stroke:${col}"/></g>`); });
      S.bandHit = (px, py) => { const s = Math.round((tAt(px) - t0) / DAY); if (s < 0 || s > F.days) return null;
        const hit = F.top.filter(c => py >= Y(c.band[s][4]) - 2 && py <= Y(c.band[s][1]) + 2).sort((a, b) => Math.abs(Y(a.md) - py) - Math.abs(Y(b.md) - py))[0];
        return hit ? {x: px, y: py, html: bandTip(hit)} : null; };
      /* the runs before, each with its date and time: where the model's estimate for Election Day stood then */
      F.hist.filter(h => h.at !== F.at && tDay(h.d) >= start).forEach(h => { const x = X(tRun(h)), k0 = TG.length;
        who.forEach(w => { if (h.c[w.n]) tg(x, Y(h.c[w.n][0]), 12, histTip(h)); });
        o.push(`<g class="hist" tabindex="0" role="img" data-t="${k0}" aria-label="${esc(T("The model’s run of {date}", {date: sdt(h)}))}">${who.map(w => { const v = h.c[w.n]; if (!v) return ""; const y = Y(v[0]);
          return `<line x1="${f1(x)}" x2="${f1(x)}" y1="${f1(Y(v[2]))}" y2="${f1(Y(v[1]))}" style="stroke:${w.col}"/><path d="M${f1(x)},${f1(y - 6)}l6,6l-6,6l-6,-6z" style="fill:${w.col}"/>`; }).join("")}</g>`); }); }
    /* our average: a step at each day a member's poll ended */
    S.avgHit = () => null;
    if (showAvg) { const upto = Math.min(today, end);
      who.forEach(w => { const steps = S.avg.filter(s => s.v[w.n]); let d = "";
        steps.forEach((s, j) => { const a = Math.max(tDay(s.d), start), b = j + 1 < steps.length ? tDay(steps[j + 1].d) : upto; if (b < start) return;
          const y = f1(Y(s.v[w.n].a)); d += `${d ? "L" : "M"}${f1(X(a))},${y}L${f1(X(b))},${y}`; });
        if (d) o.push(`<path class="avg" d="${d}" style="stroke:${w.col}"/>`); });
      S.avg.filter(s => tDay(s.d) >= start).forEach(s => { const k0 = TG.length;
        who.forEach(w => { if (s.v[w.n]) tg(X(tDay(s.d)), Y(s.v[w.n].a), 10, avgTip(s)); });
        if (TG.length > k0) o.push(`<g class="avgpt" tabindex="0" role="img" data-t="${k0}" aria-label="${esc(T("Our average on {date}", {date: sd(s.d)}))}">${who.map(w => s.v[w.n] ? `<circle cx="${f1(X(tDay(s.d)))}" cy="${f1(Y(s.v[w.n].a))}" r="3.5" style="fill:${w.col}"/>` : "").join("")}</g>`); });
      S.avgHit = (px, py) => { const t = tAt(px); if (t > upto) return null; const s = [...S.avg].reverse().find(x => tDay(x.d) <= t);
        return s && who.some(w => s.v[w.n] && Math.abs(Y(s.v[w.n].a) - py) < 9) ? {x: px, y: py, html: avgTip(s)} : null; }; }
    /* the polls: members' filled (counted), the others' hollow (not averaged), by the day each ended */
    const same = {};
    [...vis].sort((a, b) => a.m - b.m).forEach(p => { const parts = who.filter(w => p.shares[w.n] != null); if (!parts.length) return;
      const j = same[p.end] = (same[p.end] || 0) + 1, x = X(tDay(p.end)) + (j % 2 ? 1 : -1) * Math.floor(j / 2) * 4, k0 = TG.length;
      parts.forEach(w => tg(x, Y(p.shares[w.n]), 12, pollTip(p)));
      o.push(`<g class="pt${p.m ? " mem" : ""}${view === "one" ? " on" : ""}" tabindex="0" role="${simple ? "img" : "button"}" data-t="${k0}" data-p="${p.id}" aria-label="${esc(pollLabel(p))}">${parts.map(w => `<circle cx="${f1(x)}" cy="${f1(Y(p.shares[w.n]))}" r="${p.m ? 6.5 : 5}" style="${p.m ? `fill:${w.col}` : `stroke:${w.col}`}"/>`).join("")}</g>`); });
    /* the model's medians on Election Day, named in the margin, and the word Analysis under them */
    if (showFc) { const ls = F.top.map((c, i) => ({y: Y(c.md), c, w: who[i]})).sort((a, b) => a.y - b.y);
      for (let i = 1; i < ls.length; i++) if (ls[i].y - ls[i - 1].y < 16) ls[i].y = ls[i - 1].y + 16;
      ls.forEach(L => o.push(`<text class="end" x="${f1(xE + 7)}" y="${f1(L.y + 4)}" style="fill:${L.w.col}">${esc(narrow ? pc(L.c.md, 1) : `${L.w.sur} ${pc(L.c.md, 1)}`)}</text>`));
      o.push(`<text class="ana" x="${f1(xE + 7)}" y="${f1(ls[ls.length - 1].y + 20)}">${esc(T("Analysis"))}</text>`); }
    S.T = TG; S.W = W;
    box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="group" aria-label="${esc(T("The polls of this race by the day each ended, in percent of the vote, with our average and the model’s estimate for Election Day"))}">${o.join("")}</svg>`;
    $(".pcd-leg", S.d).innerHTML = legend(showAvg, showFc);
    hideTip(true);
  }
  function legend(showAvg, showFc){
    const it = S.who.map(w => `<span><i style="background:${w.col}"></i>${nmH(w.n)}</span>`);
    if (S.polls.length) it.push(`<span><i class="lg-grey"></i>${TH("Poll by a member: counted in our average")}</span>`, `<span><i class="lg-hollow"></i>${TH("Not averaged")}</span>`);
    if (showAvg) it.push(`<span><i class="lg-line"></i>${TH("Our average")}</span>`);
    if (showFc) it.push(`<span><i class="lg-band"></i>${TH("The model’s range for Election Day")} ${ANA()}</span>`);
    if (showFc && S.F.hist.some(h => h.at !== S.F.at)) it.push(`<span><i class="lg-dia"></i>${TH("An earlier run of the model")}</span>`);
    return it.join("");
  }
  /* ---- the tooltip ---- */
  function hideTip(force){ if (!S || (S.pin && !force)) return; const t = $(".pcd-tip", S.d); if (t) t.hidden = true; S.pin = false; }
  function tipAt(t){
    const svg = $(".pcd-svg svg", S.d), fig = $(".pcd-fig", S.d), tip = $(".pcd-tip", S.d); if (!svg || !t) return;
    const b = svg.getBoundingClientRect(), f = fig.getBoundingClientRect(), k = b.width / S.W, x = b.left - f.left + t.x * k, y = b.top - f.top + t.y * k;
    tip.innerHTML = t.html; tip.hidden = false;
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    let left = x + 14; if (left + tw > f.width - 4) left = Math.max(4, x - 14 - tw);
    let top = y + 14; if (top + th > b.bottom - f.top) top = Math.max(0, y - 14 - th);
    tip.style.left = left + "px"; tip.style.top = top + "px";
  }
  function at(e){
    const svg = $(".pcd-svg svg", S.d); if (!svg) return null;
    const b = svg.getBoundingClientRect(), k = S.W / b.width, px = (e.clientX - b.left) * k, py = (e.clientY - b.top) * k;
    let best = null, bd = 1e9;
    S.T.forEach(t => { if (!t.r) return; const d = Math.hypot(t.x - px, t.y - py); if (d < t.r && d < bd) { bd = d; best = t; } });
    return best || S.bandHit(px, py) || S.avgHit(px, py);
  }
  /* ---- the words around the chart ---- */
  function oneCard(p){
    const L = s => `<a href="${esc(p.url)}" target="_blank" rel="noopener">${s}</a>`;
    return `<b>${L(esc(p.pollster))}</b>${paidWords(p) ? ` <small>${paidWords(p)}</small>` : ""} ${p.m ? `<span class="tag fact">${TH("Counted in our average")}</span>` : `<span class="tag note">${TH("Not averaged")}</span>`}
      <p>${pollRange(p)}${pollSample(p) ? ` &middot; ${pollSample(p)}` : ""}</p>
      <ul>${Object.entries(p.shares).map(([n, v]) => `<li>${nmH(n)}: <b>${pc(v)}</b></li>`).join("")}${p.rest != null ? `<li>${TH("Someone else or undecided")}: <b>${pc(p.rest)}</b></li>` : ""}</ul>
      ${p.note ? `<p class="fnote" lang="en">${esc(p.note)}</p>` : ""}
      <p class="fnote">${p.checked ? TH("<0>Read the pollster’s own release</0>; we checked these figures against it on {date}.", {0: L, date: fmtDate(p.checked)}) : TH("<0>Read the pollster’s own release</0>.", {0: L})}</p>`;
  }
  const optText = p => `${p.pollster}, ${T("ended {date}", {date: sd(p.end)})}${p.m ? "" : ` (${T("not averaged")})`}`;
  function pick(){
    const box = $(".pcd-pick", S.d), card = $(".pcd-onecard", S.d), P = S.polls; card.hidden = true; card.innerHTML = "";
    if (S.view === "one") { const p = P.find(x => x.id === S.one) || P[0];
      box.innerHTML = P.length ? `<label class="pcd-sel">${TH("Poll")} <select>${P.map(x => `<option value="${x.id}"${p && x.id === p.id ? " selected" : ""}>${esc(optText(x))}</option>`).join("")}</select></label>` : "";
      if (p) { S.one = p.id; card.innerHTML = oneCard(p); card.hidden = false; } }
    else if (S.view === "sel") { const grp = (m, title) => { const L = P.filter(x => x.m === m);
        return L.length ? `<p>${title}</p>` + L.map(x => `<label><input type="checkbox" value="${x.id}"${S.sel.has(x.id) ? " checked" : ""}><span>${esc(x.pollster)}<small>${pollRange(x)}</small></span></label>`).join("") : ""; };
      box.innerHTML = `<div class="pcd-ticks">${grp(true, TH("Polls by members: counted in our average"))}${grp(false, TH("Other published polls: not averaged"))}</div>
        <p class="pcd-tickbtns"><button type="button" class="pcd-lnk" data-all="1">${TH("Tick them all")}</button><button type="button" class="pcd-lnk" data-all="0">${TH("Clear the ticks")}</button></p>`; }
    else box.innerHTML = "";
  }
  function notes(){
    const d = S.d, E = $(".pcd-early", d), early = S.early || [];
    const none = LEVEL() > 2 && S.view === "sel" && !S.sel.size;
    E.hidden = !early.length && !none;
    E.innerHTML = none ? TH("No poll is ticked: tick one above to show it.") : early.length ? TH("{n, plural, one {# earlier poll is} other {# earlier polls are}} left of this view; the earliest ended {date}.", {n: early.length, date: fmtDate(early[early.length - 1].end)})
      + (LEVEL() > 2 ? ` <button type="button" class="pcd-lnk" data-r="long">${TH("Show them: since the first poll")}</button>` : "") : "";
    const mem = S.polls.filter(p => p.m);
    $(".pcd-avgnote", d).innerHTML = !S.polls.length ? TH("<0>No poll shown.</0> No published poll of this race is on our list yet, so the chart shows the model’s estimate alone.", {0: B}) : S.avg.length ? TH("<0>Our average</0> (the solid line) takes, on each day, the ten most recent polls by members of the <1>Transparency Initiative</1>; point to the line or tap it for its arithmetic. It counts every member’s poll, whichever polls the chart is showing.", {0: B, 1: TI})
      : mem.length ? TH("<0>No average line yet.</0> Our average needs at least two polls by members of the <1>Transparency Initiative</1>; this race has one so far, by {pollster}, ending {date}.", {0: B, 1: TI, pollster: keepH(mem[0].pollster), date: fmtDate(mem[0].end)})
      : TH("<0>No average line yet.</0> Our average needs at least two polls by members of the <1>Transparency Initiative</1>, and this race has none so far.", {0: B, 1: TI});
  }
  const trackWords = (t, st) => TH("<0>Its track record.</0> Tested on {what, select, mnstatewide {{state}’s statewide races of 2022 and 2024} mnusrep {{state}’s U.S. House races of 2022 and 2024} ussen {the U.S. Senate races of 2022 and 2024 in every state but Minnesota} usrep {the 2024 U.S. House races of the states whose lines did not change in 2024} governor {the governors’ races of 2022 and 2024} other {the other statewide offices of 2022 and 2024}} ({races, plural, one {# race} other {# races}}), the candidate it favoured won {fav} of {races}; the actual {unit, select, cand {vote fell inside its 80 percent range for {h80} of {n} candidates and inside its 95 percent range for {h95}} other {Democratic share fell inside its 80 percent range in {h80} of {n} races and inside its 95 percent range in {h95}}}; its vote shares were off by {mae} points on average.{thin, select, y { That is a thin record.} other {}}",
    {0: B, what: t.what, state: st, races: t.races, fav: t.fav, unit: t.unit, h80: t.h80, h95: t.h95, n: t.n, mae: I18.num(t.mae), thin: t.thin ? "y" : "n"});
  function fcHTML(){
    const F = S.F, st = S.r.stName;
    if (!F) return `<h3 id="pcd-fch">${TH("The model’s forecast")}</h3><p>${TH("The model has no forecast for this race.")}</p>`;
    const t = F.track, mp = F.polls || [];      /* (the polls the run counted are listed by Minnesota's model only) */
    const rows = F.top.map((c, i) => `<li style="--pc:${S.who[i].col}">${TH("<0>{name}</0>: {chance} chance; likely {lo} to {hi} of the vote", {0: B, name: keepH(c.n), chance: chanceW(c.ch), lo: pc(c.l80, 1), hi: pc(c.h80, 1)})}</li>`).join("");
    const rest = F.rest.length ? `<p>${TH("Also on the ballot: {list}.", {list: RAW(I18.and(F.rest.map(c => TH("{name}, likely {lo} to {hi}", {name: keepH(c.n), lo: pc(c.l80, 1), hi: pc(c.h80, 1)}))))})}</p>` : "";
    const polls = F.how === "mnhouse" ? TH("It adds up how each precinct of the district has voted before against the state, moved by the statewide mood from members’ polls of other states’ Senate races; a sitting member’s edge and the district’s own error are sized on the 2022 and 2024 results.")
      : F.how === "usstate" ? TH("It starts from how {state} voted for President in 2024, moved by members’ polls of other states’ Senate races and by members’ polls of this race where both names polled are November’s; the race’s own pull is sized on the 2022 and 2024 races.", {state: st})
      : F.how === "ushouse" ? TH("It starts from how the district’s precincts voted for President in 2024 against {state} (the MIT Election Data and Science Lab’s copy of the official returns, a secondary source) and how its 2024 House race went, moved with the state’s mood; a sitting member’s edge and the district’s own error are sized on the 2024 House races.", {state: st})
      : mp.length === 1 ? TH("The only poll of this race it counts is {pollster}’s, which ended {date}; it is blended with how {state} has voted before and members’ polls of other states’ Senate races, as the steps below show.", {pollster: keepH(mp[0].p), date: fmtDate(mp[0].e), state: st})
      : mp.length ? TH("It counts {n, plural, one {# poll} other {# polls}} of this race by members, blended with how {state} has voted before and members’ polls of other states’ Senate races, as the steps below show.", {n: mp.length, state: st})
      : TH("It counts no poll of this race; its estimate comes from how {state} has voted before and from members’ polls of other states’ Senate races.", {state: st});
    const moved = F.hist.length > 1 ? `<p>${TH("How its estimate has moved, run by run (the diamonds on the chart): {list}.", {list: RAW(F.hist.map(h => `${esc(sdt(h))}, ${S.who.map(w => h.c[w.n] ? `${nmH(w.sur)} ${pc(h.c[w.n][0], 1)}` : "").filter(Boolean).join(" / ")}`).join("; "))})}</p>` : "";
    return `<h3 id="pcd-fch">${TH("The model’s forecast")} ${ANA()}</h3>
      <p>${TH("A computer model’s estimate from past election results and polls by members of AAPOR’s Transparency Initiative. Not a result: the official count decides.")}</p>
      <ul class="pcd-fcl">${rows}</ul>${rest}
      <p>${F.drift ? TH("The darker band holds 80 in every 100 of the model’s simulated outcomes for Election Day, the lighter band 95 in 100. It widens toward November 3 by the model’s own allowance for opinion moving in the days still to come; with {n, plural, one {# day} other {# days}} left that adds little, so most of its width is what the model cannot know even now.", {n: F.days})
        : TH("The darker band holds 80 in every 100 of the model’s simulated outcomes for Election Day, the lighter band 95 in 100.")}</p>
      <p>${trackWords(t, st)}</p>
      <p>${polls}${F.env ? " " + TH("In the model’s own words: {note}", {note: RAW(`<span lang="en">${esc(F.env)}</span>`)}) : ""}</p>
      ${moved}
      <p class="fnote">${TH("Run {when}, method {m}, {draws} simulated elections.", {when: I18.date(new Date(F.at), {month: "long", day: "numeric", hour: "numeric", minute: "2-digit"}), m: keepH(F.m), draws: F.draws})}</p>
      <details class="pcd-how"${LEVEL() >= 5 ? " open" : ""}><summary>${TH("How the band is drawn")}</summary><p>${TH("On November 3 the band is the model’s own 80 and 95 percent ranges. On each day before it, the part of that width which the model’s rule for opinion drift gives to the days still to come is taken away: {k} points of the vote for each square root of a day here ({drift} on the log-odds scale the model works in). The middle line is the model’s median for Election Day; it stays level because the model does not guess which way opinion will move. Run {id}.",
        {k: I18.num(F.top[0].k, {maximumFractionDigits: 2}), drift: I18.num(F.drift, {maximumFractionDigits: 4}), id: keepH(F.run)})}</p></details>`;
  }
  function attHTML(){
    const A = S.A, head = `<h3 id="pcd-ath">${TH("Attention")} ${ANA()}</h3><p>${TH("How much news and social attention each candidate gets. <0>This does not predict votes</0>, and it is kept out of the forecast.", {0: B})}</p>`;
    const rule = `<p class="fnote">${TH("Counted from public headlines and posts. Not a measure of importance or of support.")}</p>`;
    if (!A) return head + `<p>${TH("The Election Night feed has counted nothing for this race yet.")}</p>` + rule;
    const named = S.who.map(w => A.named[w.n] || 0), total = named.reduce((a, b) => a + b, 0);
    const namedW = RAW(I18.and(S.who.map((w, i) => TH("{n, plural, one {# headline names {name}} other {# headlines name {name}}}", {n: named[i], name: keepH(w.n)}))));
    const when = RAW(!A.from ? "" : A.from === A.to ? esc(fmtDate(A.from)) : TH("{a} to {b}", {a: A.from.slice(0, 4) === A.to.slice(0, 4) ? I18.date(A.from, {month: "long", day: "numeric"}) : fmtDate(A.from), b: fmtDate(A.to)}));
    if (!A.news) return head + `<p>${A.social ? TH("<0>Too little to show yet.</0> The feed has found no headline about this race so far; {p, plural, one {# person} other {# people}} posted about it on the social networks it reads (it counts people by race, not by candidate).", {0: B, p: A.social})
      : TH("<0>Too little to show yet.</0> The Election Night feed has found no headline or post about this race so far{t, select, y {; it has run only as a trial, and runs for real from the evening of November 2} other {}}.", {0: B, t: A.trial ? "y" : "n"})}</p>` + rule;
    if (total < 10) return head + `<p>${A.trial
      ? TH("<0>Too little to show yet.</0> The feed has run only as a trial, on {ran}. It found {n, plural, one {# headline} other {# headlines}} about this race from {k, plural, one {# news outlet} other {# news outlets}}, published {when}: {named}. {p, plural, one {# person} other {# people}} posted about the race on the social networks it reads (it counts people by race, not by candidate). It runs for real from the evening of November 2.",
          {0: B, ran: I18.and((A.ran || []).map(fmtDate)), n: A.news, k: A.outlets, when, named: namedW, p: A.social})
      : TH("<0>Too little to show yet.</0> The feed has found {n, plural, one {# headline} other {# headlines}} about this race from {k, plural, one {# news outlet} other {# news outlets}}, published {when}: {named}. {p, plural, one {# person} other {# people}} posted about the race on the social networks it reads (it counts people by race, not by candidate).",
          {0: B, n: A.news, k: A.outlets, when, named: namedW, p: A.social})}</p>` + rule;
    const max = Math.max(1, ...named);
    return head + `<ul class="pcd-bars">${S.who.map((w, i) => `<li style="--pc:${w.col}"><span>${nmH(w.n)}</span><span class="b"><i style="width:${(named[i] / max * 100).toFixed(1)}%"></i></span><b>${I18.num(named[i])}</b></li>`).join("")}</ul>
      <p>${TH("Headlines naming each candidate, published {when}, from {k, plural, one {# news outlet} other {# news outlets}}; {p, plural, one {# person} other {# people}} posted about the race on the social networks the feed reads (it counts people by race, not by candidate).", {when, k: A.outlets, p: A.social})}</p>` + rule;
  }
  function fill(){
    if (!S) return;
    const d = S.d, F = S.F;
    const n10 = F ? Math.round(F.track.h80 / F.track.n * 10) : 0;
    $(".pcd-plain", d).innerHTML = F && S.polls.length ? TH("Each dot is a poll, and the shaded band is a computer model’s estimate for Election Day (<0>Analysis</0>, not a result): in the model’s tests on past elections, the real result landed inside its darker band about {n} times in 10.", {0: B, n: n10})
      : F ? TH("No poll of this race is on our list yet. The shaded band is a computer model’s estimate for Election Day (<0>Analysis</0>, not a result): in the model’s tests on past elections, the real result landed inside its darker band about {n} times in 10.", {0: B, n: n10})
      : TH("Each dot is a poll: filled dots are the polls we count, hollow ones are shown for reference only.");
    $$(".pcd-ctl [data-v]", d).forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === S.view)));
    $$(".pcd-ctl [data-r]", d).forEach(b => b.setAttribute("aria-pressed", String(b.dataset.r === S.range)));
    $$(".pcd-ctl [data-l]", d).forEach(x => { x.checked = !!S[x.dataset.l]; });
    pick(); draw(); notes();
    $(".pcd-fc", d).innerHTML = fcHTML(); $(".pcd-att", d).innerHTML = attHTML(); $(".pcd-ixbox", d).innerHTML = ixHTML() || (F ? `<p class="fnote" data-lv="3">${TH("The worked steps of a forecast are shown where this page can redo the model’s arithmetic from the run’s stored inputs and get back its result; for this race it cannot yet, so only the run’s results are shown.")}</p>` : "");
  }
  /* ---- how this forecast is worked out (John, 2026-10-24: "an infograph ... with the math"; 2026-10-25: "everywhere"): six steps, every
     figure the latest run's own, redone at build time from the steps its frame keeps (election/model/steps.py), for every race with a
     forecast: statewide races and districts, Minnesota's model and the other states'. Plain words for Beginner and Easy, the figures
     from Medium, the formulas from Hard, the run's name and the method from Advanced ---- */
  const mn = t => t.replace(/^-/, "−"), n3 = v => mn(I18.num(v, {minimumFractionDigits: 3, maximumFractionDigits: 3})), n4 = v => mn(I18.num(v, {minimumFractionDigits: 4, maximumFractionDigits: 4}));
  const o3 = v => (v < 0 ? `(${n3(v)})` : n3(v)), o4 = v => (v < 0 ? `(${n4(v)})` : n4(v));      /* a number after an operator: + (−0.012), never + -0.012 */
  const sgn = v => (v >= 0 ? "+" : "−") + I18.num(Math.abs(v), {minimumFractionDigits: 1, maximumFractionDigits: 1});
  const p1 = v => I18.num(Math.abs(v), {minimumFractionDigits: 1, maximumFractionDigits: 1});
  const chance1 = v => v > 0.99 ? T("over 99%") : v < 0.01 ? T("under 1%") : pc(v * 100, 1);
  function ixStates(M){      /* each state's shift against 2024, a bar from zero, in neutral ink (not party data) */
    const rows = M.states, mx = Math.max(1, ...rows.map(s => Math.abs(s[2]))), W = 300, rh = 18, H = rows.length * rh + 4, x0 = 150, half = 96;
    return `<svg class="ix-viz" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(T("Each state’s shift, in points: {list}", {list: rows.map(s => `${s[0]} ${sgn(s[2])}`).join(", ")}))}">${rows.map((s, i) => { const y = 2 + i * rh, w = Math.max(1, Math.abs(s[2]) / mx * half);
      return `<text x="4" y="${y + 13}">${esc(s[0])}</text><rect class="ix-bar" x="${f1(s[2] >= 0 ? x0 : x0 - w)}" y="${y + 4}" width="${f1(w)}" height="11" rx="2"/><text x="${W - 2}" y="${y + 13}" text-anchor="end">${esc(sgn(s[2]))}</text>`; }).join("")}<line class="ix-zero" x1="${x0}" x2="${x0}" y1="0" y2="${H}"/></svg>`;
  }
  function ixLine(pts, col){      /* the blend on one line: [share, label, g(rey) | o(pen) | d(rawn in the party's colour)] */
    const vs = pts.map(p => p[0]), lo = Math.floor(Math.min(...vs) - 1), hi = Math.ceil(Math.max(...vs) + 1), W = 300, H = 104, X = v => 16 + (v - lo) / (hi - lo) * (W - 32);
    const step = hi - lo > 16 ? 4 : hi - lo > 8 ? 2 : 1, ticks = []; for (let v = lo; v <= hi; v += step) ticks.push(v);
    const order = pts.map((p, i) => [p[0], i]).sort((a, b) => a[0] - b[0]).map(x => x[1]), side = {}; order.forEach((i, j) => { side[i] = j % 2; });
    return `<svg class="ix-viz" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(pts.map(p => `${p[1]} ${pc(p[0], 1)}`).join(", "))}"><line class="ix-axis" x1="10" x2="${W - 10}" y1="52" y2="52"/>${ticks.map(v => `<line class="ix-axis" x1="${f1(X(v))}" x2="${f1(X(v))}" y1="52" y2="57"/><text x="${f1(X(v))}" y="${H - 4}" text-anchor="middle">${esc(pc(v))}</text>`).join("")}
      ${pts.map((p, i) => `<circle cx="${f1(X(p[0]))}" cy="52" r="${p[2] === "d" ? 7 : 5.5}" style="${p[2] === "d" ? `fill:${col}` : p[2] === "o" ? "fill:var(--surface);stroke:var(--ink);stroke-width:2" : "fill:var(--muted)"}"/><text class="${p[2] === "d" ? "ix-strong" : ""}" x="${f1(X(p[0]))}" y="${side[i] ? 80 : 32}" text-anchor="middle">${esc(p[1])}</text>`).join("")}</svg>`;
  }
  function ixRange(P, col){      /* a likely range of the two-party share, {lo80, hi80, p}, against an even split */
    const lo = Math.min(45, Math.floor(P.lo80 - 2)), hi = Math.max(55, Math.ceil(P.hi80 + 2)), W = 300, H = 66, X = v => 12 + (v - lo) / (hi - lo) * (W - 24);
    return `<svg class="ix-viz" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(T("Likely {lo} to {hi}; 50% is a tie", {lo: pc(P.lo80, 1), hi: pc(P.hi80, 1)}))}"><line class="ix-axis" x1="8" x2="${W - 8}" y1="34" y2="34"/>
      <rect x="${f1(X(P.lo80))}" y="25" width="${f1(X(P.hi80) - X(P.lo80))}" height="18" rx="4" style="fill:${col};fill-opacity:.35;stroke:${col}"/><line x1="${f1(X(P.p))}" x2="${f1(X(P.p))}" y1="21" y2="47" style="stroke:${col};stroke-width:3"/>
      <line class="ix-even" x1="${f1(X(50))}" x2="${f1(X(50))}" y1="12" y2="52"/><text x="${f1(X(50))}" y="9" text-anchor="middle">${esc(T("50%: a tie"))}</text>
      <text x="${f1(X(P.lo80))}" y="${H - 2}" text-anchor="middle">${esc(pc(P.lo80, 1))}</text><text class="ix-strong" x="${f1(X(P.p))}" y="${H - 2}" text-anchor="middle">${esc(pc(P.p, 1))}</text><text x="${f1(X(P.hi80))}" y="${H - 2}" text-anchor="middle">${esc(pc(P.hi80, 1))}</text></svg>`;
  }
  function ixDots(W, F){      /* every simulated election as a square, in the colour of the candidate who came first in it */
    const cols = 50, c = 6, d = F.draws, rows = Math.ceil(d / cols), runs = [];
    let at = 0; S.who.forEach((w, i) => { const k = W[F.top[i] ? F.top[i].n : w.n] || 0; runs.push([at, at + k, w.col]); at += k; });
    if (at < d) runs.push([at, d, "var(--muted)"]);
    const rects = (a, b) => { if (b <= a) return []; const r0 = Math.floor(a / cols), c0 = a % cols, r1 = Math.floor((b - 1) / cols), c1 = (b - 1) % cols, out = [];
      if (r0 === r1) return [[c0, r0, c1 - c0 + 1, 1]];
      out.push([c0, r0, cols - c0, 1]); if (r1 > r0 + 1) out.push([0, r0 + 1, cols, r1 - r0 - 1]); out.push([0, r1, c1 + 1, 1]); return out; };
    const defs = runs.map((x, i) => `<pattern id="pcdot${i}" width="${c}" height="${c}" patternUnits="userSpaceOnUse"><rect width="${c - 1.4}" height="${c - 1.4}" rx="1" style="fill:${x[2]}"/></pattern>`).join("");
    const body = runs.map((x, i) => rects(x[0], x[1]).map(([cx, cy, w, h]) => `<rect x="${cx * c}" y="${cy * c}" width="${w * c}" height="${h * c}" fill="url(#pcdot${i})"/>`).join("")).join("");
    return `<svg class="ix-viz ix-dots" viewBox="0 0 ${cols * c} ${rows * c}" role="img" aria-label="${esc(S.who.map((w, i) => `${w.n} ${I18.num(W[F.top[i] ? F.top[i].n : w.n] || 0)}`).join(", ") + " / " + I18.num(d))}"><defs>${defs}</defs>${body}</svg>`;
  }
  function ixTrack(t){      /* each tested candidate or race: inside the 80 percent range (filled) or not (hollow); a bar where there are many */
    const per = 14, s = 20, rows = Math.ceil(t.n / per), lab = esc(T("{h} of {n}", {h: t.h80, n: t.n}));
    if (t.n > 70) return `<svg class="ix-viz" viewBox="0 0 280 26" role="img" aria-label="${lab}"><rect x="0" y="6" width="280" height="14" rx="7" style="fill:none;stroke:var(--muted);stroke-width:1.5"/><rect x="0" y="6" width="${f1(280 * t.h80 / t.n)}" height="14" rx="7" style="fill:var(--accent)"/></svg>`;
    return `<svg class="ix-viz" viewBox="0 0 ${per * s} ${rows * s}" role="img" aria-label="${lab}">${Array.from({length: t.n}, (_, i) => `<circle cx="${(i % per) * s + s / 2}" cy="${Math.floor(i / per) * s + s / 2}" r="6.5" style="${i < t.h80 ? "fill:var(--accent)" : "fill:none;stroke:var(--muted);stroke-width:2"}"/>`).join("")}</svg>`;
  }
  const ixStep = (i, title, big, cap, viz, plain, figs, form) => `<li class="ix-step"><div class="ix-h"><span class="ix-n" aria-hidden="true">${i}</span><h4>${title}</h4></div>
    <p class="ix-big">${big}</p><p class="ix-cap">${cap}</p>${viz ? `<div class="ix-vz">${viz}</div>` : ""}${plain ? `<p class="ix-plain" data-lv-max="2">${plain}</p>` : ""}${figs ? `<div class="ix-figs" data-lv="3">${figs}</div>` : ""}${form ? `<p class="ix-form" data-lv="4">${form}</p>` : ""}</li>`;
  function ixHTML(){
    const F = S.F, M = F && F.math; if (!M || M.v !== 2 || !F.track || F.top.length < 2) return "";
    const st = S.r.stName, p = S.r.st === "MN" ? "dfl" : "dem", g = S.r.cands || [], dc = g.find(c => c.pc === "D"), dName = dc ? dc.n : F.top[0].n;
    const dCol = (S.who.find(w => samePerson(w.n, dName)) || {}).col || PV.D, t = F.track, a = F.top[0], b = F.top[1], d1 = F.draws + 1;
    const W = (M.sim && M.sim.wins) || {}, wa = W[a.n] || 0, wb = W[b.n] || 0;
    const ups = M.ups || [], mine = ups.find(u => u.race === "this"), dist = M.kind === "district", D = M.dist || {}, P = M.post;
    const when = I18.date(new Date(F.at), {month: "long", day: "numeric", hour: "numeric", minute: "2-digit"});
    const office = ["ussen", "ussse"].includes(M.cls) ? "ussen" : ["mngov", "governor"].includes(M.cls) ? "governor" : "other";
    const offH = (u, start) => u.race === "this" ? esc(start ? T("This race") : T("this race")) : `<span translate="no">${esc(u.office || u.race)}</span>`;
    const shifted = M.shift.n >= 3, us = M.model === "us", first = mine || ups[0], fp = first && first.polls[0];
    /* the mood's spread, part by part (steps.py: start.g.parts) */
    const PART = {shift: T("how much the states’ polls disagree"), systematic: T("other states’ polls standing in for this one"), no_polls: T("no national shift could be read"),
      state: T("this state’s own departure from a uniform swing")};
    const gParts = I18.and(M.g.parts.map(([nm, v]) => `${PART[nm] || nm} ${n4(v)}`));
    const steps = [
      ixStep(1, TH("Where it starts"), esc(pc(M.base.p, 1)), TH("{p, select, dfl {the DFL’s} other {the Democrats’}} share of the two-party vote in {state}’s 2024 race for President, from the official count", {p, state: st}), "",
        TH("It starts from how {state} voted for President in 2024: {s} of the votes for the two big parties went to {p, select, dfl {the DFL} other {the Democrat}}.", {state: st, s: pc(M.base.p, 1), p}),
        `<p>${M.base.d != null && M.base.r != null ? TH("{d} votes for {p, select, dfl {the DFL ticket} other {the Democratic ticket}} and {r} for the Republican ticket, from the official statistics of the 2024 election published by the Clerk of the House.", {d: I18.num(M.base.d), r: I18.num(M.base.r), p}) : TH("The source is the official statistics of the 2024 election from the Clerk of the House.")}${M.census_unused ? " " + TH("Census figures and campaign money are not used before Election Day: neither has been tested on past races yet.") : ""}</p>`,
        TH("On the log-odds scale the model works in: x₀ = ln(p ÷ (1 − p)) = ln({p} ÷ {q}) = {x}.", {p: n4(M.base.p / 100), q: n4(1 - M.base.p / 100), x: n3(M.base.x)})),
      ixStep(2, TH("The polls"), esc(shifted ? T("{v} points", {v: sgn(M.shift.pts)}) : T("No national shift")),
        shifted ? TH("Democrats’ gain over Kamala Harris’s 2024 share, in members’ polls of {n} other states’ Senate races", {n: M.shift.n})
          : TH("fewer than three other states had Senate polls by members ending within {days} days of the run, so the model adds no national shift and gives the starting point a wider spread instead", {days: M.shift.days}),
        shifted && M.states.length ? ixStates(M) : "",
        (shifted ? TH("Polls by pollsters who publish their methods, in {n} other states, have Democrats doing about {pts} points {up, select, yes {better} other {worse}} than in 2024.", {n: M.shift.n, pts: I18.num(Math.abs(M.shift.pts)), up: M.shift.pts >= 0 ? "yes" : "no"}) : "")
          + " " + (!ups.length ? TH("No poll of {state}’s races by such a pollster was counted, so the forecast rests on the starting point and its spreads.", {state: st})
            : mine && !us ? TH("{state}’s own poll of this race is from {date}.", {state: st, date: I18.date(mine.polls[0][1], {month: "long", year: "numeric"})})
            : mine ? TH("{state}’s own polls of this race: {n, plural, one {one pollster’s latest poll} other {the latest polls of # pollsters, averaged}}.", {state: st, n: mine.polls.length})
            : TH("{state} has no counted poll of this race, but polls of its other races move it too.", {state: st})),
        (shifted ? `<p>${TH("In each of the {n} states, the latest poll of each member pollster that ended within {days} days of the run, up to five, is averaged, and each state counts the same.", {n: M.shift.n, days: M.shift.days})}</p>` : "")
          + (!ups.length ? `<p>${TH("No member’s poll of any of {state}’s races was counted in this run.", {state: st})}</p>`
            : us ? `<p>${TH("{state}’s own polls by members: for each race, the latest poll of each of up to five pollsters, averaged into one reading, with a shared error of {bias} on the log-odds scale for polls that miss together.", {state: st, bias: n3(ups[0].bias || 0)})}</p><ul>${ups.map(u => `<li>${TH("<0>{office}</0>: {list}; reading {y} for {p, select, dfl {the DFL} other {the Democratic side}} of the two-party vote.", {0: B, office: RAW(offH(u, 1)), list: RAW(u.polls.map(q => `${esc(q[0])} (${esc(sd(q[1]))}, ${pc(q[3], 1)})`).join(", ")), y: pc(u.y, 1), p})}</li>`).join("")}</ul>`
            : `<p>${TH("{state}’s own polls by members, one at a time:", {state: st})}</p><ul>${ups.flatMap(u => u.polls.map(q => `<li>${TH("<0>{pollster}</0>, {office}, ended {date}: {tp} for {p, select, dfl {the DFL} other {the Democratic side}} of the two-party vote. Its error comes from a sample of {n} people, the pollster’s own error, and the {days} days from its last day to Election Day.", {0: B, pollster: keepH(q[0]), office: RAW(offH(u)), date: fmtDate(q[1]), tp: pc(q[3], 1), n: q[2], days: q[4], p})}</li>`)).join("")}</ul>`)
          + (ups.some(u => u.race !== "this") ? `<p>${TH("A poll of another of {state}’s races moves this one too: every race starts from the same statewide mood, so a poll that finds that mood higher or lower than expected moves all of them.", {state: st})}</p>` : "")
          + (M.skip.length ? `<p data-lv="5">${TH("Polls by members left out of this run: {list}.", {list: RAW(M.skip.map(s => `${esc(s[0])}, ${esc(fmtDate(s[1]))} (<span lang="en">${esc(s[2])}</span>)`).join("; "))})}</p>` : ""),
        (shifted ? TH("Shift = the average over the states of logit(poll) − logit(Harris 2024) = {shift} on the log-odds scale (spread between the states {sd}).", {shift: n3(M.shift.x), sd: n3(M.shift.sd)}) : "")
          + (fp ? " " + TH("A poll’s error s = √(sampling² + pollster² + drift²) = √({a}² + {b}² + ({c} × √{days})²) = {s}.", {a: n3(fp[5]), b: n3(M.house), c: n4(M.drift), days: fp[4], s: n3(fp[6])}) : "")
          + (us && first ? " " + TH("A race’s reading averages its polls on the log-odds scale, with error s = √(the sum of each poll’s s² ÷ n² + bias²) = {s} for {office}.", {s: n3(first.s), office: RAW(offH(first))}) : "")),
      ixStep(3, TH("The blend"), esc(pc(P.p, 1)),
        dist ? TH("the mood of a typical race in {state} this year after the blend: {p, select, dfl {the DFL’s} other {the Democrats’}} share of the two-party vote", {state: st, p})
          : TH("{name}’s expected share of the two-party vote after the blend", {name: keepH(dName)}),
        ixLine([[M.base.p, T("2024"), "g"], [M.prior.p, T("Start"), "g"], ...(mine ? [[mine.y, us ? T("This race’s polls") : T("{race, select, this {This race’s poll} governor {Governor’s poll} us_senate {Senate poll} other {Another poll}}", {race: "this"}), "o"]] : []), [P.p, T("Blend"), dist ? "g" : "d"]], dCol),
        !ups.length ? TH("With no poll of {state}’s races counted, the blend is the starting point itself: {s}.", {state: st, s: pc(P.p, 1)})
          : dist ? TH("The model blends the starting point ({start}) with the polls of {state}’s races, weighing each by how sure it is, and lands at {s} for {p, select, dfl {the DFL} other {the Democratic side}} in a typical race this year.", {start: pc(M.prior.p, 1), state: st, s: pc(P.p, 1), p})
          : TH("The model blends the starting point moved by the national polls ({start}) with {state}’s own polls, weighing each by how sure it is. It lands at {p} for {name}.", {start: pc(M.prior.p, 1), state: st, p: pc(P.p, 1), name: keepH(dName)}),
        `<p>${ups.length ? TH("<0>Before {state}’s own polls:</0> {start}, the 2024 result moved by the national shift, give or take {g} on the log-odds scale ({parts}).", {0: B, state: st, start: pc(M.g.p, 1), g: n3(M.g.sd), parts: gParts})
            : TH("<0>The starting point:</0> {start}, the 2024 result moved by the national shift, give or take {g} on the log-odds scale ({parts}).", {0: B, start: pc(M.g.p, 1), g: n3(M.g.sd), parts: gParts})}</p>`
          + (!dist && M.own ? `<p>${TH("This race’s own pull from that mood: {o} (about {pts} points), measured by the model’s backtest on past {office, select, ussen {U.S. Senate} governor {governors’} other {statewide}} races.", {o: n3(M.own.sd), pts: I18.num(M.own.pts), office})}</p>`
            + (M.own.inc && M.own.dir ? `<p>${TH("A sitting U.S. senator’s edge: about {pts} points toward {who, select, d {the Democrat} other {the Republican}}, give or take {sd} on the log-odds scale, which puts this race’s starting point at {start}.", {pts: p1(M.own.inc[0] * 25), who: M.own.dir > 0 ? "d" : "r", sd: n3(M.own.inc[1]), start: pc(M.prior.p, 1)})}</p>` : "") : "")
          + (ups.length ? `<ul>${ups.map(u => `<li>${TH("{office}: the reading {y}, where the model expected {exp}, moved {kind, select, district {the state’s mood} other {this race}} from {before} to {after}, a weight of {w} on the difference.", {office: RAW(offH(u, 1)), y: pc(u.y, 1), exp: pc(u.exp, 1), kind: dist ? "district" : "statewide", before: pc(u.b, 1), after: pc(u.af, 1), w: pc(u.w * 100)})}</li>`).join("")}</ul>` : ""),
        first ? TH("Weight w = (how unsure the model was) ÷ (that, plus the reading’s error squared); for {office} w = {a} ÷ {S} = {w}. New estimate = old + w × (reading − expected), on the log-odds scale: {x} here, which is {p}.", {office: RAW(offH(first)), a: n4(first.a), S: n4(first.S), w: n3(first.w), x: n3(P.x), p: pc(P.p, 2)}) : ""),
      dist ? ixStep(4, TH("The district"), esc(pc(D.c.p, 1)), TH("{name}’s share of the two-party vote in this district at the state’s expected mood, with every error at zero", {name: keepH(dName)}),
          ixRange({lo80: D.lo80, hi80: D.hi80, p: D.c.p}, dCol),
          (Math.abs(D.lean_pts) < 0.5 ? TH("This district votes about like {state} as a whole, so at the state’s expected mood it comes to about {c} for {name}.", {state: st, c: pc(D.c.p, 1), name: keepH(dName)})
            : TH("This district usually votes about {pts} points {dir, select, more {more} other {less}} {p, select, dfl {DFL} other {Democratic}} than {state} as a whole, so at the state’s expected mood it comes to about {c} for {name}.", {pts: p1(D.lean_pts), dir: D.lean_pts >= 0 ? "more" : "less", p, state: st, c: pc(D.c.p, 1), name: keepH(dName)})),
          `<p>${D.how === "mn" ? TH("Its lean adds up its {n} precincts, each by how it has voted in past elections, weighted by the votes expected there: {lean} on the log-odds scale at the state’s expected mood.", {n: D.units || 0, lean: n3(D.lean)})
            : D.at ? TH("An at-large seat: the district is the whole state, so it has no lean of its own.")
            : D.pres && D.hse ? TH("Its lean blends how the district voted for President in 2024 ({dp}, against {sp} statewide), weighted {w}, with how its 2024 House race went ({hp}, against {hs} for President statewide{e, select, y {, less a sitting member’s edge} other {}}), weighted {w2}: {lean} on the log-odds scale.", {dp: pc(D.pres[0], 1), sp: pc(D.pres[1], 1), w: pc(D.w * 100), hp: pc(D.hse[0], 1), hs: pc(D.hse[1], 1), e: D.hse[2] ? "y" : "n", w2: pc((1 - D.w) * 100), lean: n3(D.lean)})
            : D.pres ? TH("Its lean is how the district voted for President in 2024 ({dp}, against {sp} statewide): {lean} on the log-odds scale. Its 2024 House race was not between the two big parties.", {dp: pc(D.pres[0], 1), sp: pc(D.pres[1], 1), lean: n3(D.lean)})
            : TH("Its lean is how its 2024 House race went ({hp}, against {hs} for President statewide{e, select, y {, less a sitting member’s edge} other {}}): {lean} on the log-odds scale. The presidential vote could not be placed in districts.", {hp: pc((D.hse || [])[0] || 0, 1), hs: pc((D.hse || [])[1] || 0, 1), e: D.hse && D.hse[2] ? "y" : "n", lean: n3(D.lean)})}</p>`
            + `<p>${TH("U.S. House races run on average about {pts} points {dir, select, ahead {ahead of} other {behind}} the top of the ticket, give or take {sd} on the log-odds scale, measured on past races.", {pts: p1(D.gap[0] * 25), dir: D.gap[0] >= 0 ? "ahead" : "behind", sd: n3(D.gap[1])})}${D.dir ? " " + TH("A sitting member’s edge: about {pts} points toward {who, select, d {the Democrat} other {the Republican}}.", {pts: p1(D.inc[0] * 25), who: D.dir > 0 ? "d" : "r"}) : ""}</p>`
            + `<p>${TH("Its spread adds five parts on the log-odds scale: the state’s mood {a}, the class gap {b}, the member’s edge {c}, a regional swing {d} and the district’s own error {e}, about {pts} points either way.", {a: n4(D.sd[0][1]), b: n4(D.sd[1][1]), c: n4(D.sd[2][1]), d: n4(D.sd[3][1]), e: n4(D.sd[4][1]), pts: p1(D.sdx * D.c.p * (100 - D.c.p) / 100)})}</p>`
            + `<p>${TH("Read as a straight line, that spread gives {lo} to {hi} for 8 in 10 outcomes. This is an approximation: the run’s own ranges, {rlo} to {rhi} of the vote for {name}, come from its simulated elections.", {lo: pc(D.lo80, 1), hi: pc(D.hi80, 1), rlo: pc((F.top.find(c => samePerson(c.n, dName)) || a).l80, 1), rhi: pc((F.top.find(c => samePerson(c.n, dName)) || a).h80, 1), name: keepH(dName)})}</p>`,
          (D.how === "mn" ? TH("x = μ + gap + edge × {dir} = {mu} + {gap} + {inc} × {dir} = {x}, where μ is the shift that, added to every precinct in the state, gives the blend statewide; the share is the district’s precincts added up at x: {s}.", {dir: D.dir < 0 ? "(−1)" : String(D.dir), mu: n3(D.c.mu ?? D.c.g), gap: o3(D.gap[0]), inc: o3(D.inc[0]), x: n3(D.c.x), s: pc(D.c.p, 2)})
            : TH("x = μ + gap + edge × {dir} = {mu} + {gap} + {inc} × {dir} = {x}; share = expit(x + lean) = expit({x} + {lean}) = {s}.", {dir: D.dir < 0 ? "(−1)" : String(D.dir), mu: n3(D.c.mu ?? D.c.g), gap: o3(D.gap[0]), inc: o3(D.inc[0]), x: n3(D.c.x), lean: o3(D.lean), s: pc(D.c.p, 2)}))
            + " " + TH("σ = √(slope² × Var G + gap² + edge² + region² + own²) = {s}, with slope {k}.", {s: n3(D.sdx), k: I18.num(D.slope)}))
      : ixStep(4, TH("How sure it is"), esc(T("± {pts} points", {pts: I18.num(P.pts, {minimumFractionDigits: 1, maximumFractionDigits: 1})})),
          TH("how far {name}’s two-party share may move either way (one standard deviation); 8 in 10 of the model’s outcomes fall between {lo} and {hi}", {name: keepH(dName), lo: pc(P.lo80, 1), hi: pc(P.hi80, 1)}), ixRange(P, dCol),
          TH("Polls and past results can be wrong, so the model keeps a margin: {name}’s share of the two-party vote likely lands between {lo} and {hi}. 50% is a tie.", {name: keepH(dName), lo: pc(P.lo80, 1), hi: pc(P.hi80, 1)}),
          `<p>${ups.length ? TH("The margin comes from the statewide mood’s spread ({g}), this race’s own pull ({o}) and each poll’s own error, which grows by {d} for each square root of a day between the poll’s last day and Election Day; the polls narrow it as they are blended in.", {g: n3(M.g.sd), o: n3((M.own || {}).sd || 0), d: n4(M.drift)})
            : TH("The margin comes from the statewide mood’s spread ({g}) and this race’s own pull ({o}); no poll narrowed it.", {g: n3(M.g.sd), o: n3((M.own || {}).sd || 0)})} ${fp && mine ? TH("For {pollster}’s poll of this race that is {days} days, adding {dr}.", {pollster: keepH(fp[0]), days: fp[4], dr: n3((M.drift || 0) * Math.sqrt(fp[4]))}) : ""} ${TH("This run was made with {n, plural, one {# day} other {# days}} to go.", {n: F.days})}</p>`,
          P.var ? TH("With G the statewide mood and κ this race’s own pull from it: σ = √(Var G + Var κ + 2 Cov(G, κ)) = √({a} + {b} + 2 × {c}) = {s} on the log-odds scale, about {pts} points of the two-party vote here.", {a: n4(P.var[0]), b: n4(P.var[1]), c: o4(P.var[2]), s: n3(P.sd), pts: I18.num(P.pts)}) : ""),
      ixStep(5, TH("{d} simulated elections", {d: I18.num(F.draws)}), esc(T("{w} of {d}", {w: I18.num(wa), d: I18.num(F.draws)})), TH("simulated elections that {name} came first in", {name: keepH(a.n)}), ixDots(W, F),
        TH("The computer runs the election {d} times with that margin. {a} came first in {wa} and {b} in {wb}, so their chances are {ca} and {cb}.", {d: I18.num(F.draws), a: keepH(a.n), b: keepH(b.n), wa: I18.num(wa), wb: I18.num(wb), ca: chanceW(a.ch), cb: chanceW(b.ch)}),
        `<p>${TH("Each run draws this race’s two-party split from steps 3 and 4.")}${M.sim.two === false ? " " + TH("Where a big party has more than one candidate, the model splits that side’s share equally among them.") : ""}${M.sim.minor ? " " + TH("The other candidates’ shares are drawn from what such candidates have won statewide: most often about {med} each, never above {cap}.", {med: pc(M.sim.minor.med, 2), cap: pc(M.sim.minor.cap, 1)}) : ""} ${TH("Write-ins take about {wi}.", {wi: pc(M.sim.wi, 2)})}${M.sim.pos != null && M.sim.rot != null ? " " + TH("The first line on the ballot gets an edge of 0 to {pos, plural, one {# point} other {# points}}; {state} rotates the names, so each is first for about {share} of voters and the edges nearly cancel.", {pos: M.sim.pos, state: st, share: pc(M.sim.rot)}) : ""}${M.sim.votes ? " " + TH("It expects about {v} votes in this race.", {v: I18.num(M.sim.votes)}) : ""} ${TH("The ranges are the middle 80 and the middle 95 of every 100 runs.")}</p>`
          + `<ul>${F.top.map(c => `<li>${TH("<0>{name}</0>: first in {w} runs, {chance} chance; likely {lo} to {hi} (80 in 100), {lo95} to {hi95} (95 in 100)", {0: B, name: keepH(c.n), w: I18.num(W[c.n] || 0), chance: chanceW(c.ch), lo: pc(c.l80, 1), hi: pc(c.h80, 1), lo95: pc(c.l95, 1), hi95: pc(c.h95, 1)})}</li>`).join("")}${F.rest.map(c => { const w = W[c.n] || 0;
            return `<li>${TH("<0>{name}</0>: first in {w} runs, {chance} chance; likely {lo} to {hi} (80 in 100)", {0: B, name: keepH(c.n), w: I18.num(w), chance: chanceW((w + 0.5) / d1), lo: pc(c.l80, 1), hi: pc(c.h80, 1)})}</li>`; }).join("")}</ul>`,
        TH("Chance = (wins + ½) ÷ (runs + 1), so it is never 0 or 100 percent: ({w} + ½) ÷ {d1} = {c}.", {w: I18.num(wa), d1: I18.num(d1), c: chance1((wa + 0.5) / d1)})),
      ixStep(6, TH("Its track record"), esc(T("{h} of {n}", {h: t.h80, n: t.n})), TH("{unit, select, cand {candidates whose actual vote fell inside the model’s 80 percent range in its tests} other {races where the Democrat’s actual share fell inside the model’s 80 percent range in its tests}}", {unit: t.unit}), ixTrack(t),
        TH("Tested on {races} past races, the candidate it favoured won {fav} of them.{thin, select, y { That is a short record.} other {}}", {races: t.races, fav: t.fav, thin: t.thin ? "y" : "n"}),
        `<p>${trackWords(t, st)}</p>`, "")];
    return `<section class="pcd-ix" aria-labelledby="pcd-ixh"><h3 id="pcd-ixh">${TH("How this forecast is worked out, as of {when}", {when})} ${ANA()}</h3>
      <p class="ix-lead" data-lv-max="2">${TH("Six steps, with the numbers from the model’s latest run.")}</p>
      <p class="ix-lead" data-lv="3">${TH("Six steps, each with the figures of the model’s latest run. The picture changes each time the model runs again and the site is rebuilt; every step was redone from the run’s stored inputs and gives back its stored result.")}</p>
      <ol class="ix-flow">${steps.join("")}</ol>
      <p class="fnote ix-run" data-lv="5">${TH("Run {id}, method {m}. Its {d} simulated elections are drawn from a seed made from the run’s name, so the run can be redone exactly from its stored inputs. <0>How forecasts are made</0>.", {id: keepH(F.run), m: keepH(F.m), d: I18.num(F.draws), 0: s => `<a href="../../method/#night-forecasts">${s}</a>`})}${M.steps_run && M.steps_run !== F.run ? " " + TH("Its steps are read from run {s}, which holds the same inputs for this race.", {s: keepH(M.steps_run)}) : ""}</p></section>`;
  }
  /* ---- opening and closing ---- */
  function frame(){
    const F = S.F, x = esc(T("Close the chart"));
    const su = PX.share ? PX.share(S.r.id) : "";
    const share = su ? `<button type="button" class="tca-share pcd-share" data-share data-share-url="${esc(su)}" data-share-title="${esc(T("{race}: polls and forecast", {race: S.r.title}))}" data-share-text="${esc(T("{race}: the polls, our average and the model’s forecast with its likely range, labelled Analysis.", {race: S.r.title}) + " The Civic Archive")}">${SHARE_SVG}<span>${TH("Share")}</span></button>` : "";
    return `<header class="pcd-top"><div><span class="pcd-kick">${TH("Polls and our model")}</span><h2 id="pcd-h" tabindex="-1">${esc(S.r.title)}</h2></div><div class="pcd-acts">${share}<button type="button" class="pcd-x" aria-label="${x}" title="${x}">&times;</button></div></header>
      <p class="lvplain pcd-plain" data-lv-max="2"></p>
      <div class="pcd-ctl" data-lv="3">
        ${S.polls.length ? `<div class="seg" role="group" aria-label="${esc(T("Which polls the chart shows"))}"><button type="button" data-v="one">${TH("One poll")}</button><button type="button" data-v="sel">${TH("Selected polls")}</button><button type="button" data-v="all">${TH("All polls")}</button></div>` : ""}
        ${S.polls.length ? `<div class="seg" role="group" aria-label="${esc(T("How far back the chart goes"))}"><button type="button" data-r="short">${TH("The last 60 days")}</button><button type="button" data-r="long">${TH("Since the first poll")}</button></div>` : ""}
        ${S.avg.length ? `<label class="pcd-chk"><input type="checkbox" data-l="showAvg">${TH("Our average")}</label>` : ""}${F ? `<label class="pcd-chk"><input type="checkbox" data-l="showFc">${TH("The model’s forecast")}</label>` : ""}
      </div>
      <div class="pcd-pick" data-lv="3"></div>
      <figure class="pcd-fig"><div class="pcd-svg"></div><div class="pcd-tip" hidden></div><figcaption class="pcd-leg"></figcaption></figure>
      <p class="fnote pcd-early" hidden></p>
      <div class="pcd-onecard" data-lv="3" hidden></div>
      <p class="pcd-avgnote" data-lv="3"></p>
      <div class="pcd-grid" data-lv="3"><section class="pcd-box pcd-fc" aria-labelledby="pcd-fch"></section><section class="pcd-box pcd-att" aria-labelledby="pcd-ath"></section></div>
      <div class="pcd-ixbox"></div>
      <p class="fnote pcd-foot">${S.polls.length ? TH("A poll measures opinion when it was taken, with a margin of error; it is not a forecast. Hollow dots are polls by pollsters outside the Initiative, each checked against its own release: shown for reference, never averaged.") : TH("A forecast is not a result: the official count decides.")}</p>`;
  }
  const onResize = () => { clearTimeout(rt); rt = setTimeout(() => { if (S) draw(); }, 90); };
  const need = id => files[id] || (files[id] = fetch(`${PX.base}${encodeURIComponent(id)}.json?v=${encodeURIComponent(PX.v || "")}`)
    .then(x => x.ok ? x.json() : Promise.reject(x.status)).catch(() => { delete files[id]; return {fc: null, att: null}; }));
  /* how: "load" (the address asked for the chart as the page opened), "history" (Back, Forward or a link changed the address to
     it), or nothing (a button: the chart adds its step to the history when the page shows that race) */
  function open(id, opener, how){
    const r = PX.race(id); if (!r || !PX.has(id)) return Promise.resolve(false);
    if (opener) opener.setAttribute("aria-busy", "true");
    return need(id).then(C => { if (opener) opener.removeAttribute("aria-busy"); show(r, C || {}, opener);
      if (!S) { if (how && CH.test(location.hash)) setHash(plainHash(), false, history.state); return false; }
      if (how === "load") { setHash(plainHash(), false, null); setHash(plainHash() + "&chart=open", true, {pcd: id}); S.pushed = true; }
      else if (how === "history") S.pushed = !!(history.state && history.state.pcd === id);
      else if (raceOf(hashNow()) === id && !CH.test(location.hash)) { setHash(location.hash + "&chart=open", true, {pcd: id}); S.pushed = true; }
      return true; });
  }
  /* a chart asked for by the address waits for the page to know the race (a state's page reads its races from a file of its own) */
  function whenReady(id, how, tries = 0){
    const r = PX.race(id);
    if (!r) { if (tries < 150) setTimeout(() => whenReady(id, how, tries + 1), 100); else if (CH.test(location.hash)) setHash(plainHash(), false, history.state); return; }
    if (!PX.has(id)) { if (CH.test(location.hash)) setHash(plainHash(), false, history.state); return; }
    const go = () => { if (wanted() !== id || (S && S.r.id === id)) return; open(id, $("#app .pcinline .pcbtn"), how); };
    (window.I18 && I18.ready ? I18.ready : Promise.resolve()).then(go, go);
  }
  function show(r, C, opener){
    if (S) close(true);
    const F = C.fc || null, raw = pollsOf(r), who = whoOf(r, raw, F), polls = remap(raw, who);
    if (!polls.length && !F) return;
    S = {r, opener: opener || document.activeElement, polls, F, A: C.att || null, who, avg: averages(polls, who), view: "all", range: "short",
         showAvg: true, showFc: true, sel: new Set(polls.map(p => p.id)), one: (polls.find(p => p.m) || polls[0] || {}).id, pin: false, T: [], W: 640,
         bandHit: () => null, avgHit: () => null};
    const d = S.d = document.createElement("dialog");
    d.className = "pcd"; d.setAttribute("aria-labelledby", "pcd-h");
    d.innerHTML = `<div class="pcd-in">${frame()}</div>`;
    document.body.appendChild(d);
    d.addEventListener("cancel", e => { e.preventDefault(); close(); });
    d.addEventListener("click", e => {
      if (e.target === d) { close(); return; }      /* a click on the blurred page behind */
      const x = e.target.closest(".pcd-x"), v = e.target.closest(".pcd-ctl [data-v]"), rg = e.target.closest("[data-r]"), all = e.target.closest("[data-all]");
      if (x) close();
      else if (v) { S.view = v.dataset.v; fill(); }
      else if (rg) { S.range = rg.dataset.r; const ctl = rg.closest(".pcd-ctl"); fill(); if (!ctl) { const b = $(`.pcd-ctl [data-r="${S.range}"]`, d); if (b && b.getClientRects().length) b.focus(); } }
      else if (all) { const k = all.dataset.all; S.sel = k === "1" ? new Set(S.polls.map(p => p.id)) : new Set(); pick(); draw(); notes(); const b = $(`[data-all="${k}"]`, d); if (b) b.focus(); } });
    d.addEventListener("change", e => { const x = e.target;
      if (x.matches(".pcd-ctl [data-l]")) { S[x.dataset.l] = x.checked; draw(); }
      else if (x.matches(".pcd-pick select")) { S.one = x.value; const p = S.polls.find(q => q.id === S.one), card = $(".pcd-onecard", d); card.innerHTML = p ? oneCard(p) : ""; card.hidden = !p; draw(); notes(); }
      else if (x.matches(".pcd-ticks input")) { if (x.checked) S.sel.add(x.value); else S.sel.delete(x.value); draw(); notes(); } });
    d.addEventListener("keydown", e => {      /* the keyboard stays inside the pop-out */
      if (e.key !== "Tab") return;
      const f = $$('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),summary,[tabindex]:not([tabindex="-1"])', d).filter(el => el.getClientRects().length);
      if (!f.length) return; const a = f[0], z = f[f.length - 1];
      if (e.shiftKey && (document.activeElement === a || !d.contains(document.activeElement))) { e.preventDefault(); z.focus(); }
      else if (!e.shiftKey && (document.activeElement === z || !d.contains(document.activeElement))) { e.preventDefault(); a.focus(); } });
    const sv = $(".pcd-svg", d);
    sv.addEventListener("pointermove", e => { if (e.pointerType === "touch" || S.pin) return; const t = at(e); if (t) tipAt(t); else hideTip(); });
    sv.addEventListener("pointerleave", () => hideTip());
    sv.addEventListener("click", e => { const g = e.target.closest(".pt");
      if (g && LEVEL() > 2) { S.view = "one"; S.one = g.dataset.p; fill(); const n = $(`.pt[data-p="${g.dataset.p}"]`, d); if (n) n.focus(); return; }
      const t = e.detail === 0 && g ? S.T[+g.dataset.t] : at(e); if (t) { tipAt(t); S.pin = true; } else hideTip(true); });
    sv.addEventListener("keydown", e => { const g = e.target.closest(".pt"); if (g && LEVEL() > 2 && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); g.dispatchEvent(new MouseEvent("click", {bubbles: true})); } });
    sv.addEventListener("focusin", e => { const g = e.target.closest("[data-t]"); if (g && S.T[+g.dataset.t]) tipAt(S.T[+g.dataset.t]); });
    sv.addEventListener("focusout", () => hideTip(true));
    document.documentElement.classList.add("pcd-lock");
    addEventListener("resize", onResize);
    d.showModal();
    fill();
    $(".pcd-x", d).focus();
  }
  /* fromHistory: the address has already moved on (Back, or a link), so the history is left as it is */
  function close(fromHistory){
    if (!S) return; const {d, opener, pushed, r} = S; S = null;
    removeEventListener("resize", onResize);
    try { d.close(); } catch (e) {} d.remove();
    document.documentElement.classList.remove("pcd-lock");
    const back = opener && opener.isConnected && opener !== document.body ? opener : $("#app .pcinline .pcbtn");
    if (back) back.focus({preventScroll: true});
    if (fromHistory === true || !CH.test(location.hash)) return;
    if (pushed && history.state && history.state.pcd === r.id) history.back();
    else setHash(plainHash(), false, history.state);
  }
  try { new MutationObserver(() => { if (S) fill(); }).observe(document.documentElement, {attributes: true, attributeFilter: ["data-level"]}); } catch (e) {}
  addEventListener("hashchange", () => { const want = wanted();
    if (want) { if (!S || S.r.id !== want) whenReady(want, "history"); return; }
    if (S) close(true); });
  document.addEventListener("click", e => { const b = e.target.closest(".pcbtn"); if (b) open(b.dataset.pc, b); });
  /* the way in (John, 2026-10-24: "more prominent ... pinned to the top"): a button under the race's heading, at every reading level,
     and the same button pinned just below the site's top bar once that one has scrolled away; a second way in at the top of the Polls tab */
  const btnH = (id, label, cls) => `<button type="button" class="pcbtn${cls || ""}" data-pc="${esc(id)}" aria-haspopup="dialog">${ICON}<span>${label}</span></button>`;
  function mount(id){
    if (!id || !PX.has(id)) return;
    const h1 = $("#app .bhero h1");
    if (h1 && !$("#app .pcinline")) h1.insertAdjacentHTML("afterend", `<p class="pcinline">${btnH(id, TH("Polls & forecast chart"))}</p>`);
    const hero = $("#app > section.bhero");
    if (hero && !$("#pcpin")) hero.insertAdjacentHTML("afterend", `<div class="pcpin" id="pcpin" hidden>${btnH(id, TH("Polls & forecast chart"), " pcpinbtn")}</div>`);
    const panel = $("#panel-polls");
    if (panel && !$(".pcbtn", panel)) panel.insertAdjacentHTML("afterbegin", `<div class="pcopen">${btnH(id, TH("Open the chart"))}<span>${TH("The polls, our average and our model’s forecast on one chart.")}</span></div>`);
    pin();
  }
  /* the pinned button shows only while the one under the heading is hidden under the site's top bar, and sits just below that bar */
  const barBottom = () => { let b = 0; $$("header.top, #insbar").forEach(el => { const p = getComputedStyle(el).position; if (p === "sticky" || p === "fixed") b = Math.max(b, el.getBoundingClientRect().bottom); }); return b; };
  function pin(){
    const p = $("#pcpin"), a = $("#app .pcinline"); if (!p || !a) return;
    const b = barBottom(), off = a.getBoundingClientRect().bottom < b + 2;
    if (off) p.style.top = Math.round(b + 8) + "px";
    if (p.hidden === off) p.hidden = !off;
  }
  addEventListener("scroll", pin, {passive: true});
  addEventListener("resize", pin);
  window.PC = {mount, open, close};
  /* every race page drawn from now on gets its button, and the one on screen now (the script comes after the page has drawn it) */
  if (typeof window.racePage === "function") { const rp = window.racePage; window.racePage = function (){ const out = rp.apply(this, arguments); try { mount(arguments[0]); } catch (e) {} return out; }; }
  const h0 = raceOf(hashNow());
  if (h0) mount(h0);
  if (wanted()) whenReady(wanted(), "load");
})();
