/* ---------- the Coverage tab's body (John, 2026-11-08): how others reported a race, as links only. One script for every ballot page (the
   Congress page and each state's), loaded the first time a reader opens a race's Coverage tab; each race's figures are a small file of their
   own (CVX.base on the page: data/coverage/<race>.json). It uses the page's language layer (T, TH, RAW, I18) and the page's CVX (where the
   files are; the race's state and candidates). Nothing loads from another server: each link opens the outlet's or the account's own page in a
   new tab; no player, no picture. No headline is shown beside a call or a statement (an outlet's headline carries its own words); headlines
   appear under News coverage only, each under its outlet's name. Nothing is said about a candidate with no statement listed. ---------- */
(() => {
  if (window.COVX) return;
  const css = document.createElement("style"); css.textContent = ".cv h3{font:700 18px/1.3 var(--sans);margin:24px 0 2px}\n.cv h4{font:700 14.5px/1.3 var(--sans);margin:14px 0 4px}\n.cv ul{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:8px}\n.cv li{min-width:0;border:1px solid var(--line);border-radius:12px;padding:9px 12px;background:var(--bg);font-size:14.5px;line-height:1.45;overflow-wrap:anywhere}\n.cv li small{display:block;color:var(--muted);font-size:12.5px;margin-top:3px}\n.cv a{color:var(--accent-ink,var(--accent));text-underline-offset:2px}\n.cv a:focus-visible,.cv summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}\n.cv .cvfix{color:var(--muted);font-size:13.5px;line-height:1.5;margin:6px 0 0;max-width:75ch}\n.cv .cvwho{border-left:4px solid var(--pc,var(--line-strong));padding:2px 0 2px 12px;margin-top:14px}\n.cv .cvwho h4{margin:0 0 2px}\n.cv details>summary{cursor:pointer;font:600 13.5px var(--sans);padding:6px 0;color:var(--accent-ink,var(--accent))}\n.cv .cvmore{margin-top:6px}\n.cv .cvafter{margin:18px 0 0;border:1px solid var(--line);border-radius:14px;padding:4px 14px 8px;background:var(--bg)}\n.cv .cvafter>summary{color:var(--ink);font-size:14.5px}\n.cv .cvafter p,.cv .cvafter li{font-size:14px;line-height:1.55;max-width:75ch}\n.cv .cvafter ul.cvplain{display:block;list-style:disc;padding-left:22px}.cv .cvafter ul.cvplain li{border:0;background:none;padding:2px 0}\n.cv .cvref a{text-decoration:none;font-size:11px;padding:0 1px}\n.cv ol.cvsrc{margin:6px 0 0;padding-left:24px;display:grid;gap:4px;font-size:12.5px;color:var(--muted)}\n.cv ol.cvsrc li{border:0;background:none;padding:0;font-size:12.5px}\n.cv .cv-vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap}\n.cv .cvfoot{margin-top:18px}"; document.head.appendChild(css);
  const E = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const NO = s => RAW(`<span translate="no">${E(s)}</span>`);      /* a name, an outlet: data, never translated */
  const B = s => `<b>${s}</b>`;
  const safe = u => /^https?:\/\//i.test(String(u || "")) ? String(u) : "";
  const ext = (u, label, ctx) => { const h = safe(u); return h ? `<a href="${E(h)}" target="_blank" rel="noopener noreferrer">${label}${ctx ? `<span class="cv-vh">: ${E(ctx)}</span>` : ""}</a>` : ""; };
  const SHOW = 3;      /* a group shows its newest three; the rest of the file's are under "N more" */
  /* a time with its zone, the reader's way ("Nov 4, 10:41 p.m. CST"); a day alone where the record gives only the day */
  const tm = s => { if (!s) return ""; if (!s.includes("T")) return I18.date(s, {month: "long", day: "numeric"});
    const d = new Date(s); if (isNaN(d)) return "";
    if (I18.en) return d.toLocaleDateString("en-US", {month: "short", day: "numeric"}) + ", " + d.toLocaleTimeString("en-US", {hour: "numeric", minute: "2-digit", timeZoneName: "short"}).replace(/\s?AM\b/, " a.m.").replace(/\s?PM\b/, " p.m.");
    return I18.date(d, {month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short"}); };
  const day = s => !s ? "" : s.includes("T") ? I18.date(new Date(s), {month: "long", day: "numeric"}) : I18.date(s, {month: "long", day: "numeric"});
  const PF = {bluesky: "Bluesky", mastodon: "Mastodon", youtube: "YouTube", x: "X", facebook: "Facebook", instagram: "Instagram", threads: "Threads", tiktok: "TikTok"};
  const files = {};
  const need = id => files[id] || (files[id] = fetch(`${CVX.base}${encodeURIComponent(id)}.json?v=${encodeURIComponent(CVX.v || "")}`)
    .then(x => x.ok ? x.json() : Promise.reject(x.status)).catch(e => { delete files[id]; return Promise.reject(e); }));
  /* a group of links: the newest three, then "N more" folded, then a count of the older ones the file does not carry */
  function group(list, more, item, title, older){
    const L = (list || []).filter(x => safe(x.u)); if (!L.length) return "";
    const top = L.slice(0, SHOW), rest = L.slice(SHOW);
    return `<div class="cvgrp">${title ? `<h4>${title}</h4>` : ""}<ul>${top.map(item).join("")}</ul>
      ${rest.length ? `<details class="cvmore"><summary>${TH("{n, plural, one {# more} other {# more}}", {n: rest.length})}</summary><ul>${rest.map(item).join("")}</ul></details>` : ""}
      ${more ? `<p class="fnote">${older(more)}</p>` : ""}</div>`;
  }
  /* 1. who has called it: the outlet, for whom, when (the report's time where the file says the time is a report's), by way of whom, linked */
  function callsHTML(D){
    const L = (D.calls || []).filter(c => safe(c.u)); if (!L.length) return "";
    return `<section class="cvs"><h3>${TH("Who has called it")}</h3><ul>${L.map(c => `<li>${TH("<0>{outlet}</0> called it for {name}", {0: B, outlet: NO(c.o), name: NO(c.n)})}
      <small>${[c.t ? (c.r ? TH("reported {time}", {time: tm(c.t)}) : c.q ? TH("by {time}", {time: tm(c.t)}) : E(tm(c.t))) : "", c.by ? TH("by way of {outlet}", {outlet: NO(c.by)}) : "",
        ext(c.u, E(T("Read")), c.o)].filter(Boolean).join(" &middot; ")}</small></li>`).join("")}</ul>
      <p class="cvfix">${TH("News organizations call races from their own counts. The Civic Archive does not call races; the result is final when the state certifies it.")}</p></section>`;
  }
  /* 2. what the candidates said after the election: each candidate in ballot order, each statement's kind, medium, who posted or reported
     it, its day and its link. A candidate with none listed is not named here at all */
  const KIND = k => k === "v" ? T("Declared victory") : k === "c" ? T("Conceded") : T("Statement");
  const MED = m => m === "v" ? T("Video") : m === "p" ? T("Post") : T("Text");
  const GO = m => m === "v" ? T("Watch") : m === "p" ? T("See the post") : T("Read");
  function saidHTML(D, R){
    const G = (D.said || []).filter(g => (g.s || []).some(s => safe(s.u))); if (!G.length) return "";
    const pc = n => { const c = ((R && R.cands) || []).find(x => x.n === n); return c ? `var(--p${c.pc || "O"})` : "var(--line-strong)"; };
    return `<section class="cvs"><h3>${TH("What the candidates said after the election")}</h3>
      <p class="cvfix">${TH("Links to what the candidates said after the election, where they posted it or where a news organization reported it. We do not rate them.")}</p>
      ${G.map(g => `<div class="cvwho" style="--pc:${pc(g.n)}"><h4 translate="no">${E(g.n)}</h4><ul>${g.s.filter(s => safe(s.u)).map(s => `<li>${B(E(KIND(s.k)))} &middot; ${E(MED(s.m))}
        <small>${[s.bk === "c" ? TH("posted by {name}", {name: NO(s.by)}) : TH("reported by {outlet}", {outlet: NO(s.by)}), E(day(s.d)), ext(s.u, E(GO(s.m)), `${g.n}, ${KIND(s.k)}`)].filter(Boolean).join(" &middot; ")}</small></li>`).join("")}</ul></div>`).join("")}</section>`;
  }
  /* the explainer: the short version, and under "More" the full one with its numbered sources, each opened on November 8, 2026. It names
     no candidate of this election */
  const SRC = [
    ["Election Results, Canvass, and Certification", "U.S. Election Assistance Commission", "https://www.eac.gov/election-officials/election-results-canvass-and-certification"],
    ["Canvass, Certification and Contested Election Deadlines and Voter Intent Laws", "National Conference of State Legislatures", "https://www.ncsl.org/elections-and-campaigns/canvass-certification-and-contested-election-deadlines-and-voter-intent-laws"],
    ["Election Certification Deadlines", "National Conference of State Legislatures", "https://www.ncsl.org/elections-and-campaigns/election-certification-deadlines"],
    ["Election Recounts", "National Conference of State Legislatures", "https://www.ncsl.org/elections-and-campaigns/election-recounts"],
    ["Contested Election Deadlines", "National Conference of State Legislatures", "https://www.ncsl.org/elections-and-campaigns/contested-election-deadlines"],
    ["The Constitution of the United States: A Transcription", "National Archives", "https://www.archives.gov/founding-docs/constitution-transcript"],
    ["Contested Senate Elections", "U.S. Senate Historical Office", "https://www.senate.gov/about/origins-foundations/electing-appointing-senators/contested-senate-elections/"],
    ["Other Officers of the House", "History, Art & Archives, U.S. House of Representatives", "https://history.house.gov/Institution/Origins-Development/Other-Officers-of-the-House/"],
    ["2 U.S.C. 26, Roll of Representatives-elect", "U.S. Government Publishing Office (GovInfo)", "https://www.govinfo.gov/content/pkg/USCODE-2023-title2/html/USCODE-2023-title2-chap2-sec26.htm"],
    ["2 U.S.C. 1a, Election to be certified by governor", "U.S. Government Publishing Office (GovInfo)", "https://www.govinfo.gov/content/pkg/USCODE-2023-title2/html/USCODE-2023-title2-chap1-sec1a.htm"],
    ["When a New Congress Begins", "U.S. Senate Historical Office", "https://www.senate.gov/artandhistory/senate-stories/when-a-new-congress-begins.htm"],
    ["The Constitution: Amendments 11-27", "National Archives", "https://www.archives.gov/founding-docs/amendments-11-27"],
    ["Presidential Election Concession Speeches and Messages", "The American Presidency Project, University of California, Santa Barbara", "https://www.presidency.ucsb.edu/documents/presidential-documents-archive-guidebook/presidential-campaigns-debates-and-endorsements-2"],
    ["Telegram to William McKinley Conceding the Presidential Election (November 5, 1896)", "The American Presidency Project, University of California, Santa Barbara", "https://www.presidency.ucsb.edu/documents/telegram-william-mckinley-conceding-the-presidential-election"],
    ["Remarks Conceding the Presidential Election in Los Angeles, California (November 9, 1960)", "The American Presidency Project, University of California, Santa Barbara", "https://www.presidency.ucsb.edu/documents/remarks-conceding-the-presidential-election-los-angeles-california"],
    ["5 U.S.C. 3331, Oath of office", "U.S. Government Publishing Office (GovInfo)", "https://www.govinfo.gov/content/pkg/USCODE-2023-title5/html/USCODE-2023-title5-partIII-subpartB-chap33-subchapII-sec3331.htm"],
    ["Oath of Office", "History, Art & Archives, U.S. House of Representatives", "https://history.house.gov/Institution/Origins-Development/Oath-of-Office/"],
    ["Oath of Office", "U.S. Senate Historical Office", "https://www.senate.gov/about/origins-foundations/senate-and-constitution/oath-of-office.htm"],
    ["Constitution of the State of Minnesota", "Office of the Revisor of Statutes, Minnesota Legislature", "https://www.revisor.mn.gov/constitution/"],
    ["The House Explained", "U.S. House of Representatives", "https://www.house.gov/the-house-explained"]];
  const cite = (...n) => "\u2060" + n.map(k => `<sup class="cvref">${ext(SRC[k - 1][2], `[${k}]`, SRC[k - 1][0])}</sup>`).join("\u2060");      /* a word joiner: a number never starts a line */
  function afterHTML(){
    return `<details class="cvafter"><summary>${TH("After the votes are counted: what to expect")}</summary>
      <p>${TH("After Election Day, officials keep counting. In a review called the canvass, they make sure every valid vote is in. Then the results are certified, on a date set by each state. Until then, results are not official. A very close race may get a recount, by law or because someone asks, and a candidate may challenge the result in court. A concession is a custom, not a legal step, and does not change the count. The winner swears an oath and serves the whole district or state.")}</p>
      <details class="cvmorex"><summary>${TH("More")}</summary>
        <p>${TH("<0>Counting goes on after election night.</0> Election-night results are unofficial, even when they say every precinct has reported. New totals keep coming until every ballot is counted.<1/>", {0: B, 1: cite(1)})}</p>
        <p>${TH("<0>The canvass and certification.</0> Next comes the canvass. Officials check that every valid vote is in the final results.<1/> Then a state official or board certifies the results.<2/> Each state sets its own deadline, from days to weeks after the election.<3/> Certification is what allows the winner to be sworn in.<4/>", {0: B, 1: cite(1), 2: cite(2), 3: cite(3), 4: cite(2)})}</p>
        <p>${TH("<0>Recounts and court challenges.</0> In 26 states and Washington, D.C., a very close race is recounted automatically. In 41 states and D.C., someone can ask for a recount, usually the losing candidate or their party.<1/> A candidate who believes an election was run wrongly can contest it, often in court, under state law.<2/> Both are lawful steps with their own rules.", {0: B, 1: cite(4), 2: cite(5)})}</p>
        <p>${TH("<0>For Congress,</0> each chamber judges its own members’ elections.<1/> The House Clerk collects each new member’s proof of election and makes the list of members-elect.<2/> For a senator, the governor certifies the election under the state seal.<3/> The new Congress meets at noon on January 3.<4/>", {0: B, 1: cite(6, 7), 2: cite(8, 9), 3: cite(10, 11), 4: cite(12)})}</p>
        <p>${TH("<0>The concession.</0> Conceding is a custom, not a step in the law.<1/> Concession messages usually congratulate the winner, accept that the voters decided, and offer to work together on the problems ahead.<2/> In 1896, William Jennings Bryan sent the winner a telegram of congratulations two days after the election.<3/> In 1960, Richard Nixon spoke while votes were still coming in and thanked his supporters. He conceded by telegram later that morning.<4/>", {0: B, 1: cite(13, 2), 2: cite(13), 3: cite(14), 4: cite(15)})}</p>
        <p>${TH("<0>The winner’s role.</0> The winner swears an oath before taking office. Members of Congress swear to support and defend the Constitution and to “well and faithfully discharge the duties” of the office.<1/> State offices have oaths of their own. Minnesota’s officers, for example, swear to support both constitutions and do the job faithfully.<2/> A U.S. Representative serves the people of a whole district.<3/> When the old term ends on the day set by law, the office passes to the winner.<4/>", {0: B, 1: cite(16, 17, 18), 2: cite(6, 19), 3: cite(20), 4: cite(12)})}</p>
        <p>${TH("<0>What it does not mean.</0>", {0: B})}</p>
        <ul class="cvplain"><li>${TH("<0>No statement yet</0> is not a verdict. A candidate may wait while ballots are still being counted.<1/>", {0: B, 1: cite(1)})}</li>
          <li>${TH("<0>Asking for a recount</0> is not refusing the result. It is a step the law allows.<1/>", {0: B, 1: cite(4)})}</li>
          <li>${TH("<0>A concession does not change the count.</0> The official result comes from the canvass and certification.<1/>", {0: B, 1: cite(1, 2)})}</li></ul>
        <h4>${TH("Sources")}</h4>
        <ol class="cvsrc">${SRC.map(([t, p, u]) => `<li>${ext(u, `<span translate="no">${E(t)}</span>`)}, <span translate="no">${E(p)}</span></li>`).join("")}</ol>
        <p class="fnote">${TH("Each source was opened on November 8, 2026.")}</p>
      </details></details>`;
  }
  /* 3. news coverage: national, the state's and local outlets, each headline the outlet's own title under the outlet's name */
  function newsHTML(D, R){
    const N = D.news || {};
    const item = x => `<li><a href="${E(safe(x.u))}" target="_blank" rel="noopener noreferrer" translate="no">${E(x.h)}</a><small><span translate="no">${E(x.o)}</span>${x.t ? " &middot; " + E(tm(x.t)) : ""}</small></li>`;
    const g = (k, title) => N[k] ? group(N[k].i, N[k].more, item, title, n => TH("{n, plural, one {One older story from these outlets is not listed here.} other {# older stories from these outlets are not listed here.}}", {n})) : "";
    const body = g("national", TH("National outlets")) + g("state", TH("{state} outlets", {state: (R && R.stName) || ""})) + g("local", TH("Local outlets"));
    return body ? `<section class="cvs"><h3>${TH("News coverage")}</h3><p class="cvfix">${TH("Each headline is the outlet’s own title, linked to its page. Newest first.")}</p>${body}</section>` : "";
  }
  /* 4. official posts: the election office's and the candidates' own accounts */
  function postsHTML(D){
    const P = D.posts; if (!P) return "";
    const item = p => `<li>${p.x ? `<span translate="no">${E(p.x)}</span>` : ""}<small><b translate="no">${E(p.w)}</b> &middot; ${E(PF[p.pf] || T("Website"))}${p.t ? " &middot; " + E(tm(p.t)) : ""} &middot; ${ext(p.u, E(T("See the post")), p.w)}</small></li>`;
    const body = group(P.i, P.more, item, "", n => TH("{n, plural, one {One older post is not listed here.} other {# older posts are not listed here.}}", {n}));
    return body ? `<section class="cvs"><h3>${TH("Official posts")}</h3><p class="cvfix">${TH("Posts about the race from the state’s election office and the candidates’ own accounts. Newest first.")}</p>${body}</section>` : "";
  }
  function html(D, R){
    const foot = D.ck ? TH("<0>Where this comes from.</0> The stories are from the news outlets our Election Night feed reads (national outlets and each state’s own) and from a search of the web; the calls and statements are from that search. A second reader opened each link found on the web again on {date}. Official posts are from accounts that the election office’s or the candidate’s own website links to, or that the second reader confirmed. Nothing here is copied: each link opens the original in a new tab.", {0: B, date: I18.date(D.ck, {month: "long", day: "numeric", year: "numeric"})})
      : TH("<0>Where this comes from.</0> The stories are from the news outlets our Election Night feed reads (national outlets and each state’s own). Official posts are from accounts that the election office’s or the candidate’s own website links to. Nothing here is copied: each link opens the original in a new tab.", {0: B});
    return `<section class="bsec cv" id="coverage"><h2>${TH("Coverage")}</h2><p class="sub">${TH("How news organizations reported this race, who called it, and what the candidates said after the election. Links only: each opens on its own site.")}</p>
      ${callsHTML(D)}${saidHTML(D, R)}${afterHTML()}${newsHTML(D, R)}${postsHTML(D)}<p class="fnote cvfoot">${foot}</p></section>`;
  }
  function fill(box, id){ return need(id).then(D => { box.innerHTML = html(D, CVX.race(id) || {}); }); }
  window.COVX = {fill};
})();
