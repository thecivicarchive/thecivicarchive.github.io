/* The Civic Archive: Congress as it moves (John, 2026-11-18): alerts for every bill and resolution, what the chambers have
   posted as coming up, and reminders, on every page.
   - The record is read into alerts by the Congress update every 90 minutes (and recorded votes sooner, from the
     chambers' own vote lists), so every reader sees the same events with the same times; this module only shows them. The
     files are this site's own, /night-live/congress/ (alerts.json, alerts-all.json, upcoming.json, mv/<roll>.json),
     looked at every five minutes while a page is visible; nothing comes from any other server and nothing is sent.
   - The banner, across the top of every page: the key alerts of the last twelve hours (a vote, a passage, a law, a veto,
     anything about a bill the reader follows) taking turns, and anything posted to start within the hour. "What's moving"
     opens the Congress page's full list; the close button hides the banner on this device until a newer key alert comes.
   - Follow a bill, My members (the state and district the Congress page keeps for "How did your members vote?"), Notify
     me, and reminders: all kept in this browser only (tca.congress.*), never sent anywhere. Notifications come through only
     while a page of the site or the app is open; the browser is asked for permission only from the reader's own press.
   - The words (John, 2026-11-18: lively, facts only): an emoji title and a sentence, each fact as the record states it.
     The emoji is decorative: what is read aloud is the words alone.
   - window.tcaCongress is the Congress page's way in (its "What's moving", "Coming up", ticker, follow stars and
     countdowns): the contract is the comment above API below. It dispatches "tca:congress-ready" once, then
     "tca:congress" with detail.what ("alerts", "items", "follows", "reminders") on every change.
   - Motion off, Calm and reduced motion: a plain swap, nothing slides. A new alert is announced once, politely; never a
     sound.
   The build copies it into shell/ under a hashed name and writes in where the live files are and its stylesheet's name. */
import {t, date, num, list as listWords, tagLang} from "./i18n.d705614426.js";

const LIVE = "night-live/congress/";      /* from the copy's root to the live files, written by the build */
const CSS = "./congress.4736b1e82f.css";
const D = document, H = D.documentElement, ROOT = new URL("../", import.meta.url);
const EVERY = 300000, TURN = 9000, FRESH = 12 * 3600e3, SOON = 3600e3, MAX_TURN = 5, NOTE_MAX = 4, SEEN_MAX = 2000, TICK = 30000;
const KEYK = ["pass", "fail", "agree", "amend", "conf", "disagree", "tabled", "pres", "law", "veto", "over"];
const ALLK = KEYK.concat(["vote", "cmte", "rept", "cal", "cos", "new", "sched", "clo", "chg"]);
const EMOJI = {pass: "✅", fail: "❌", agree: "\u{1F91D}", amend: "\u{1F501}", conf: "\u{1F91D}", disagree: "↔️", tabled: "\u{1F5C4}️",
  pres: "\u{1F4E8}", law: "\u{1F58B}️", veto: "⛔", over: "⚖️", vote: "\u{1F5F3}️", cmte: "\u{1F3DB}️", rept: "\u{1F4C4}", cal: "\u{1F4CB}",
  cos: "✍️", new: "\u{1F195}", sched: "\u{1F4C5}", clo: "⏳", chg: "\u{1F501}", soon: "⏰"};
const BELL = "\u{1F514}";
const K = {follow: "tca.congress.follow.v1", remind: "tca.congress.remind.v1", notify: "tca.congress.notify.v1", hid: "tca.congress.hid.v1",
  said: "tca.congress.said"};
const ls = {get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
  json(k, d) { try { const v = JSON.parse(localStorage.getItem(k) || "null"); return v == null ? d : v; } catch (e) { return d; } }};
const ss = {get(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { sessionStorage.setItem(k, v); } catch (e) {} }};
const reducedOS = (() => { try { return matchMedia("(prefers-reduced-motion: reduce)"); } catch (e) { return {matches: false}; } })();
const still = () => reducedOS.matches || H.getAttribute("data-motion") === "reduced" || H.getAttribute("data-calm") === "on" ||
  H.classList.contains("calm") || ls.get("motion") === "off";
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
const fileURL = name => new URL(LIVE + name, ROOT).href;
const getJSON = url => fetch(url, {cache: "no-store", credentials: "same-origin"}).then(r => (r.ok ? r.json() : null)).catch(() => null);
const CH = {H: "House", S: "Senate", P: "President"};
const chamber = c => (c === "H" ? t("House") : c === "S" ? t("Senate") : c === "P" ? t("President") : "");
const other = c => (c === "H" ? t("Senate") : t("House"));

/* ---------- the clock: every time on this device's own clock ---------- */
function asDate(s) {
  if (!s) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d, 12); }      /* a day: noon here, so no zone moves it */
  const d = new Date(s); return isNaN(d) ? null : d;
}
export function when(s, how = "full") {
  const d = asDate(s); if (!d) return "";
  if (how === "day" || /^\d{4}-\d{2}-\d{2}$/.test(s)) return date(d, {weekday: "short", month: "short", day: "numeric"});
  if (how === "time") return date(d, {hour: "numeric", minute: "2-digit", timeZoneName: "short"});
  return date(d, {weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short"});
}
const dayOf = s => when(s, "day");

/* ---------- the words (lively, every fact as the record states it) ---------- */
const isRes = a => /^(hres|sres)$/.test(a.bt || "");
const isCon = a => /^(hconres|sconres)$/.test(a.bt || "");
function splitWords(ps) {
  if (!ps) return "";
  const P = {D: t("Democrats"), R: t("Republicans"), I: t("independents")}, parts = [];
  String(ps).replace(/([DRI])\s+(\d+)-(\d+)/g, (m, p, y, n) => { parts.push(t("{party} {y} to {n}", {party: P[p], y: num(+y), n: num(+n)})); return m; });
  return parts.length ? parts.join(", ") + "." : "";
}
function tally(q) {
  if (!q) return "";
  const m = /^(\d+)\s*[–-]\s*(\d+)(.*)$/.exec(q);
  if (m) return t("{y} to {n}", {y: num(+m[1]), n: num(+m[2])}) + (/two-thirds/.test(m[3]) ? " " + t("(two-thirds needed)") : "");
  return {"by voice vote": t("by voice vote"), "by unanimous consent": t("by unanimous consent"), "voice vote": t("by voice vote"),
    "unanimous consent": t("by unanimous consent"), "by a rule, without a separate vote": t("by a rule, without a separate vote")}[q] || q;
}
/* a measure's name in a sentence: its short title ("the Safe Cloud Storage Act"), or its number when the record has only a
   long title ("To amend title 9 ...") */
const LONG = /^(To |A bill|A resolution|A joint resolution|A concurrent resolution|Expressing|Providing|Authorizing|Requesting|Recognizing|Supporting|Condemning|Directing|Designating|Disapproving|Calling|Honoring|Commending|Proposing|Making|Amending)/;
const title = a => a.ti && !LONG.test(a.ti) ? t("the {title}", {title: a.ti.replace(/^(The|A|An) /, s => s.toLowerCase())}) : (a.d || t("the measure"));
const Title = a => { const s = title(a); return s.charAt(0).toUpperCase() + s.slice(1); };
function nextWords(a) {
  switch (a.nx) {
    case "other": return t("Next stop: the {chamber}.", {chamber: other(a.ch)});
    case "pres": return t("Both chambers have passed it: next stop, the President's desk.");
    case "back": return t("It passed with changes, so it goes back to the {chamber}.", {chamber: other(a.ch)});
    case "done": return isRes(a) ? t("A resolution of the {chamber} alone, so that settles it.", {chamber: chamber(a.ch)}) : t("Both chambers have agreed to it, and it does not go to the President.");
    case "states": return t("Both chambers have passed it; three-fourths of the states would have to ratify it.");
  }
  return "";
}
const CAT = {"Cloture": "A vote to end debate", "Motion to table": "A motion to table it", "Motion to proceed": "A motion to take it up",
  "Amendment": "An amendment", "Motion to (re)commit": "A motion to send it back to committee", "Previous question": "A vote on the previous question",
  "Motion to refer": "A motion to refer it", "Point of order": "A point of order", "Motion to waive": "A motion to waive the rules",
  "Motion to reconsider": "A motion to reconsider", "Passage": "The vote to pass it", "Resolve differences": "A vote on the other chamber's changes",
  "Veto override": "A vote to override the veto"};
const carried = r => /^(agreed to|passed|invoked|sustained|adopted)/i.test(r || "") ? true : /^(failed|rejected|not )/i.test(r || "") ? false : null;
function itemWhen(w) {
  if (!w) return "";
  if (w.at) return when(w.at);
  if (w.day) return dayOf(w.day);
  if (w.w) return t("the week of {day}", {day: dayOf(w.w)});
  return "";
}
/* [title, sentence], without the emoji */
export function texts(a) {
  const v = {d: a.d || "", ch: chamber(a.ch), other: other(a.ch), date: a.dt ? dayOf(a.dt) : "", q: tally(a.q), title: title(a), Title: Title(a),
    cm: a.cm || t("the committee"), c: num(a.c || 0)};
  const sp = splitWords(a.ps), nx = nextWords(a), q = v.q ? " " + v.q : "";
  const join = (...s) => s.filter(Boolean).join(" ");
  switch (a.k) {
    case "pass": return [isRes(a) || isCon(a) ? t("The {ch} agrees to {d}", v) : t("The {ch} passes {d}", v),
      join(t("{Title} passed", v) + q + (v.date ? " " + t("on {date}", v) : "") + ".", sp, nx)];
    case "fail": return [t("{d} fails in the {ch}", v), join(t("{Title} fell short", v) + q + (v.date ? " " + t("on {date}", v) : "") + ".", sp)];
    case "agree": return [t("The {ch} agrees to the {other}'s changes to {d}", v), join(t("Agreed to", v) + q + (v.date ? " " + t("on {date}", v) : "") + ".", sp, nx)];
    case "amend": return [t("The {ch} sends {d} back with more changes", v), join(t("{Title} goes back to the {other}", v) + q + ".", sp)];
    case "conf": return [t("The {ch} adopts the final version of {d}", v), join(t("The conference report was agreed to", v) + q + (v.date ? " " + t("on {date}", v) : "") + ".", sp, nx)];
    case "disagree": return [t("The {ch} disagrees with the {other}'s changes to {d}", v), join(t("The two chambers still have to settle on one text of {title}.", v), sp)];
    case "tabled": return [t("The {ch} tables the {other}'s message on {d}", v), join(t("The {other}'s message on {title} was set aside", v) + q + ".", sp)];
    case "pres": return [t("{d} heads to the President's desk", v), t("{Title} was presented to the President on {date}. The President has ten days, Sundays not counted, to sign or veto it.", v)];
    case "law": return [t("{d} is now law!", v), (a.lk === "u" ? t("{Title} became law on {date} without the President's signature.", v) : t("{Title} was signed into law on {date}.", v))
      + (a.lw ? " " + t("It is Public Law {law}.", {law: a.lw}) : "")];
    case "veto": return [t("The President vetoes {d}", v), t("{Title} was vetoed on {date}. Congress can override with two-thirds of each chamber.", v)];
    case "over": return [t("The {ch} votes to override the veto of {d}", v), join((a.r === "Passed" ? t("The override carried", v) : t("The override fell short", v)) + q + ".", sp)];
    case "vote": {
      const what = t(CAT[a.cat] || "A vote") + (a.on === "amendment" ? " " + t("on an amendment") : ""), c = carried(a.r);
      return [t("{ch} vote on {d}", v), join(what + " " + (c === true ? t("carried") : c === false ? t("failed") : (a.r || "").toLowerCase()) + q + (v.date ? " " + t("on {date}", v) : "") + ".", sp)];
    }
    case "cmte": return [t("{cm} approves {d}", v), t("The committee voted to send {title} to the full {ch}", v) + (a.q ? " " + t("({q})", {q: tally(a.q)}) : "") + (v.date ? " " + t("on {date}", v) : "") + "."];
    case "rept": return [t("{cm} reports {d}", v), t("The committee's report on {title} was filed on {date}, so it can head to the floor.", v)];
    case "cal": return [t("{d} is on the {cal}", {d: v.d, cal: a.cm || t("calendar")}), t("{Title} can now be called up for a floor vote", v) + (a.q ? " " + t("(calendar number {q})", {q: a.q}) : "") + "."];
    case "cos": {
      const [ad, dr] = a.co || [0, 0];
      return [t("Cosponsors signing on: {n} on {c} measures", {n: num(ad), c: v.c}), t("Members added their names to {c} measures on {date}.", v) + (dr ? " " + t("{n} withdrew.", {n: num(dr)}) : "")];
    }
    case "new": return [t("{c} new bills and resolutions", v), t("Members introduced {c} new measures on {date}.", v)];
    case "sched": {
      const w = a.w || {};
      if (a.l) return [t("The House's lineup for the week of {date}", {date: dayOf(a.dt)}), t("{c} measures are on the House floor schedule. The House posts the week, not a day or time for each.", v)];
      if (a.add) return [t("{d} added to the House's week", v), t("{Title} joins the floor schedule for the week of {date}.", {Title: v.Title, date: dayOf(a.dt)})];
      return [t("{cm} meets on {d}", {cm: v.cm, d: v.d || t("its agenda")}), t("{ty} set for {when}.", {ty: w.ty || t("A meeting"), when: itemWhen(w)}) + (w.room ? " " + t("Room {room}.", {room: w.room}) : "") + " " + t("Times can change.")];
    }
    case "clo": {
      const w = a.w || {};
      if (w.late) return [t("Cloture filed on {d}", v), t("Under the Senate's rules the vote to end debate was due {when}; the record shows no vote on it yet.", {when: itemWhen(w)})];
      return [t("Cloture filed on {d}", v), (w.at ? t("Under the Senate's rules the vote to end debate comes around {when}.", {when: when(w.at)}) : t("Under the Senate's rules the vote to end debate comes on {when}.", {when: itemWhen(w)}))
        + " " + t("The Senate often agrees to another time.")];
    }
    case "chg": {
      const w = a.w || {};
      if (w.st === "gone") return [t("Off the schedule: {what}", {what: w.cm || v.d}), t("The {ty} set for {when} was taken off the calendar.", {ty: (w.ty || t("meeting")).toLowerCase(), when: itemWhen(w)})];
      return [t("New time: {what}", {what: w.cm || v.d}), t("Now {when}", {when: itemWhen(w)}) + (w.was ? ", " + t("moved from {was}", {was: /T/.test(w.was) ? when(w.was) : dayOf(w.was)}) : "") + "."];
    }
    case "soon": { const w = a.w || {}, cw = countdown(w).words; return [t("Starting soon: {what}", {what: w.cm || w.ti || t("Congress")}), (cw ? cw.charAt(0).toUpperCase() + cw.slice(1) + "." : "") + (w.d && w.d.length ? " " + t("On the agenda: {list}.", {list: listWords(w.d)}) : "")]; }
  }
  return ["", ""];
}
const joinTS = (a, b) => a + (/[.!?]$/.test(a) ? " " : ". ") + b;
export function words(a) { const [x, y] = texts(a); return x ? joinTS(x, y) : ""; }
export const emoji = a => EMOJI[a.k] || "";
export const isKey = a => KEYK.includes(a.k) || (a.k === "vote" && !!a.rc);
const usPage = h => new URL("us/" + h, ROOT).href;
export function link(a) {
  if (a.b) return usPage("#bill=" + encodeURIComponent(a.b));
  if (["sched", "clo", "chg", "soon"].includes(a.k)) return usPage("#coming");
  return usPage("#moving");
}
export function voteLink(a) {
  if (!a.rc || !a.b) return "";
  const [, ch, yr, roll] = /^([HS])(\d{4})-(\d+)$/.exec(a.rc) || [];
  if (!ch || !a.dt) return "";
  return usPage("#vote=" + encodeURIComponent(`${a.b}_${ch}_${a.dt}_${roll}`));
}

/* ---------- countdowns ---------- */
const span = ms => {
  const m = Math.round(ms / 60000), d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), mm = m % 60;
  if (d >= 2) return t("in {d} days", {d: num(d)});
  if (d === 1) return h ? t("in 1 day {h} h", {h: num(h)}) : t("in 1 day");
  if (h) return mm ? t("in {h} h {m} min", {h: num(h), m: num(mm)}) : t("in {h} h", {h: num(h)});
  return mm <= 1 ? t("in a minute") : t("in {m} min", {m: num(mm)});
};
const startOfDay = d => new Date(d.getFullYear(), d.getMonth(), d.getDate());
export function countdown(it, now = Date.now()) {
  if (!it) return {words: "", soon: false, past: false, exact: false};
  if (it.st === "gone") return {words: t("taken off the schedule"), soon: false, past: true, exact: false, gone: true};
  if (it.done) return {words: t("taken up on {day}", {day: dayOf(it.done)}), soon: false, past: true, exact: false, done: true};
  if (it.late) return {words: t("due {day} under the Senate's rules; the record shows no vote on it yet", {day: dayOf(it.day)}), soon: false, past: false, exact: false};
  if (it.at) {
    const ms = Date.parse(it.at) - now;
    const exp = it.ex === 0 ? " " + t("(expected)") : "";
    if (ms > 0) return {words: span(ms) + exp, soon: ms <= SOON, past: false, exact: true, ms};
    if (ms > -2 * 3600e3) return {words: t("under way") + exp, soon: true, past: false, exact: true, ms};
    return {words: t("over"), soon: false, past: true, exact: true, ms};
  }
  const today = startOfDay(new Date(now));
  if (it.day) {
    const d = startOfDay(asDate(it.day)), days = Math.round((d - today) / 864e5);
    const w = days === 0 ? t("today") : days === 1 ? t("tomorrow") : days < 0 ? t("over") : days < 7 ? date(d, {weekday: "long"}) : dayOf(it.day);
    return {words: w + (it.ex === 0 || it.k === "clo" ? " " + t("(expected)") : ""), soon: false, past: days < 0, exact: false};
  }
  if (it.w) {
    const mon = startOfDay(asDate(it.w)), days = Math.round((mon - today) / 864e5);
    return {words: days > 6 ? t("next week") : days > -7 ? t("this week") : t("over"), soon: false, past: days <= -7, exact: false};
  }
  return {words: "", soon: false, past: false, exact: false};
}

/* ---------- the reader's choices, kept in this browser ---------- */
const listeners = new Set();
const emit = what => { try { dispatchEvent(new CustomEvent("tca:congress", {detail: {what}})); } catch (e) {} };
addEventListener("storage", e => {      /* a choice made on another page of the site, in another tab */
  if (e.key === K.follow) emit("follows");
  if (e.key === K.remind) { emit("reminders"); tickSoon(); }
});
const follows = {
  list: () => { const v = ls.json(K.follow, []); return Array.isArray(v) ? v.filter(k => typeof k === "string" && /^[a-z]+\d+-\d+$/.test(k)).slice(0, 500) : []; },
  has: key => follows.list().includes(key),
  toggle(key, on) {
    if (!/^[a-z]+\d+-\d+$/.test(key || "")) return false;
    const l = follows.list(), had = l.includes(key), want = on == null ? !had : !!on;
    if (want && !had) l.push(key);
    const nl = want ? l : l.filter(k => k !== key);
    ls.set(K.follow, JSON.stringify(nl)); emit("follows");
    if (box) take();      /* the banner counts followed bills' alerts too */
    return want;
  },
};
const LEADS = [1440, 60, 15];
const reminders = {
  all: () => { const v = ls.json(K.remind, {}); return v && typeof v === "object" && !Array.isArray(v) ? v : {}; },
  get: id => { const r = reminders.all()[id]; return r && LEADS.includes(r.lead) ? r.lead : null; },
  async set(it, minutes) {
    if (!it || !it.id) return null;
    const lead = LEADS.includes(+minutes) ? +minutes : 60, all = reminders.all();
    all[it.id] = {lead, at: refTime(it), what: words({k: "soon", w: it}).slice(0, 300), ti: it.cm || it.ti || "", fired: false, set: Date.now()};
    ls.set(K.remind, JSON.stringify(all)); emit("reminders");
    if (canNotify() && perm() === "default") await ask();
    tickSoon();
    return lead;
  },
  clear(id) { const all = reminders.all(); delete all[id]; ls.set(K.remind, JSON.stringify(all)); emit("reminders"); },
  /* whether a reminder can still come: the item's moment (see refTime) is ahead, and, with minutes, still that far ahead */
  can(it, minutes = 0) { const r = it && refTime(it); return r != null && r - (+minutes || 0) * 60000 > Date.now(); },
};
/* the moment a reminder counts back from: the posted time; for a day alone, 9 a.m. in Washington that day; for a House
   week, 9 a.m. in Washington on its Monday */
function refTime(it) {
  if (it.at) return Date.parse(it.at);
  const day = it.day || it.w; if (!day) return null;
  const [y, m, d] = day.split("-").map(Number);
  const dst = (() => { const a = new Date(Date.UTC(y, 2, 8)), b = new Date(Date.UTC(y, 10, 1)); a.setUTCDate(8 + (7 - a.getUTCDay()) % 7); b.setUTCDate(1 + (7 - b.getUTCDay()) % 7); const x = Date.UTC(y, m - 1, d); return x >= a && x < b; })();
  return Date.UTC(y, m - 1, d, 9 + (dst ? 4 : 5));
}
function mine() {
  const st = ls.get("state");
  if (!st || !/^[A-Z]{2}$/.test(st)) return null;
  const d = ls.get("district");
  return {st, dist: d !== null && d !== "" && !isNaN(+d) ? String(+d) : null};
}
const sameSeat = (dist, my) => my.dist == null || String(+dist || 0) === String(+my.dist || 0);
const POS = {Y: "voted yes", N: "voted no", P: "voted present", X: "did not vote"};
const mvCache = new Map();
function mineIn(a) {
  const my = mine(); if (!my) return Promise.resolve([]);
  if (a.rc) {
    if (!mvCache.has(a.rc)) mvCache.set(a.rc, getJSON(fileURL("mv/" + a.rc + ".json")));
    return mvCache.get(a.rc).then(doc => {
      if (!doc || !doc.m) return [];
      const senate = a.rc[0] === "S", out = [];
      for (const [bg, row] of Object.entries(doc.m)) {
        const [pos, name, party, st, dist] = row;
        if (st === my.st && (senate || sameSeat(dist, my))) out.push({bg, name, party, chamber: senate ? "Senate" : "House", pos, words: t(POS[pos] || "did not vote")});
      }
      return out;
    });
  }
  const out = [];
  if (a.k === "new") for (const r of a.l || []) { if (r[5] === my.st && (r[6] === "" || sameSeat(r[6], my))) out.push({bg: r[7], name: r[3], party: r[4], chamber: r[6] === "" ? "Senate" : "House", role: "sponsor", b: r[1], d: r[0]}); }
  if (a.k === "cos") for (const r of a.l || []) for (const x of r[6] || []) { if (x[4] === my.st && (x[5] === "" || sameSeat(x[5], my))) out.push({bg: x[1], name: x[2], party: x[3], chamber: x[5] === "" ? "Senate" : "House", role: x[0] === "-" ? "withdrew" : "cosponsor", b: r[1], d: r[0]}); }
  return Promise.resolve(out);
}
/* the bills an alert is about: its own, or a roundup's rows */
const billsOf = a => a.b ? [a.b] : (a.l || []).map(r => r[1]).filter(Boolean);
const followed = a => { const f = follows.list(); return f.length > 0 && billsOf(a).some(k => f.includes(k)); };

/* ---------- calendars ---------- */
const CAL = [["all", "Everything coming up"], ["house-floor", "The House floor"], ["senate-floor", "The Senate floor"],
  ["house-committees", "House committee markups"], ["senate-committees", "Senate committee markups"]];
function calendars() {
  const out = CAL.map(([id, name]) => ({id, name: t(name)}));
  const seen = new Set();
  for (const it of items) if ((it.k === "hc" || it.k === "sc") && it.code && !seen.has(it.code)) { seen.add(it.code); out.push({id: "c-" + it.code.toLowerCase().replace(/[^a-z0-9]+/g, ""), name: it.cm || it.code}); }
  return out.map(c => { const url = usPage("cal/" + c.id + ".ics"); return {...c, url, webcal: url.replace(/^https?:/, "webcal:")}; });
}
const icsText = s => String(s || "").replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
const icsTime = ms => new Date(ms).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
const icsDay = s => s.replace(/-/g, "");
function fold(line) { const out = []; let s = line; while (s.length > 72) { out.push(s.slice(0, 72)); s = " " + s.slice(72); } out.push(s); return out.join("\r\n"); }
function icsFor(it) {
  const L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//The Civic Archive//Congress coming up//EN", "METHOD:PUBLISH", "BEGIN:VEVENT",
    `UID:${String(it.id).replace(/:/g, "-")}@thecivicarchive.org`, "DTSTAMP:" + icsTime(Date.now()), `SEQUENCE:${it.seq || 0}`];
  if (it.at) { const s = Date.parse(it.at); L.push("DTSTART:" + icsTime(s), "DTEND:" + icsTime(s + 3600e3)); }
  else if (it.day) { const d = asDate(it.day), n = new Date(d.getTime() + 864e5); L.push("DTSTART;VALUE=DATE:" + icsDay(it.day), "DTEND;VALUE=DATE:" + `${n.getFullYear()}${String(n.getMonth() + 1).padStart(2, "0")}${String(n.getDate()).padStart(2, "0")}`); }
  else if (it.w) { const d = asDate(it.w), n = new Date(d.getTime() + 5 * 864e5); L.push("DTSTART;VALUE=DATE:" + icsDay(it.w), "DTEND;VALUE=DATE:" + `${n.getFullYear()}${String(n.getMonth() + 1).padStart(2, "0")}${String(n.getDate()).padStart(2, "0")}`); }
  const what = {hf: t("On the House floor this week"), sf: t("The Senate meets"), clo: t("Senate cloture vote expected"), hc: t("House committee"), sc: t("Senate committee")}[it.k] || t("Congress");
  const head = [(it.d || []).join(", "), it.cm || ""].filter(Boolean).join(" ");
  L.push("SUMMARY:" + icsText((it.k === "hc" || it.k === "sc") ? `${it.cm || what} ${(it.ty || "").toLowerCase()}${it.d && it.d.length ? ": " + it.d.join(", ") : ""}` : head && it.k !== "sf" ? `${what}: ${head}` : what));
  L.push("DESCRIPTION:" + icsText([it.ti, it.k === "hf" ? t("The House posts its bills for the week, not a day or time for each.") : "",
    it.ex === 0 ? t("Expected under the Senate's rules; the Senate often agrees to another time.") : "", t("Times can change; the chamber's own schedule is the authority."),
    it.src ? t("Posted by the chamber:") + " " + it.src : "", "The Civic Archive: " + usPage("#coming")].filter(Boolean).join("\n")));
  if (it.room) L.push("LOCATION:" + icsText(it.room));
  if (it.src) L.push("URL:" + it.src);
  L.push("END:VEVENT", "END:VCALENDAR");
  return L.map(fold).join("\r\n") + "\r\n";
}
function addToCalendar(it) {
  try {
    const blob = new Blob([icsFor(it)], {type: "text/calendar;charset=utf-8"}), a = D.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = (String(it.id).replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "congress") + ".ics";
    D.body.append(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
  } catch (e) {}
}

/* ---------- the stylesheet, fetched only when something is shown (three seconds at most) ---------- */
let cssReady = null;
function css() {
  if (cssReady) return cssReady;
  cssReady = new Promise(done => {
    const l = D.createElement("link");
    l.rel = "stylesheet"; l.href = new URL(CSS, import.meta.url).href; l.setAttribute("data-tca-congress-css", "");
    l.onload = l.onerror = () => done(); setTimeout(done, 3000); D.head.append(l);
  });
  return cssReady;
}

/* ---------- notifications on this device ---------- */
const canNotify = () => { try { return "Notification" in window && window.isSecureContext !== false; } catch (e) { return false; } };
const apple = () => /iPhone|iPad|iPod/.test(navigator.userAgent || "") || (/Macintosh/.test(navigator.userAgent || "") && navigator.maxTouchPoints > 1);
const offerNotify = () => canNotify() || apple();
const perm = () => { try { return Notification.permission; } catch (e) { return "denied"; } };
const ask = () => new Promise(res => {
  let done = false; const fin = r => { if (!done) { done = true; res(r || perm()); } };
  try { const p = Notification.requestPermission(fin); if (p && p.then) p.then(fin, () => fin()); } catch (e) { fin(); }
});
function nget() {
  const s = ls.json(K.notify, {}) || {};
  return {on: s.on === true, send: ["key", "all", "mine"].includes(s.send) ? s.send : "key",
    seen: Array.isArray(s.seen) ? s.seen.filter(x => typeof x === "string").slice(-SEEN_MAX) : []};
}
const nput = s => ls.set(K.notify, JSON.stringify(s));
const noting = () => canNotify() && nget().on && perm() === "granted";
const aid = a => (typeof a.id === "string" && a.id ? a.id : "n:" + a.n);
function markSeen(s, list) { const have = new Set(s.seen); for (const a of list) if (!have.has(aid(a))) { have.add(aid(a)); s.seen.push(aid(a)); } s.seen = s.seen.slice(-SEEN_MAX); }
async function wants(s, a) {
  if (s.send === "all") return true;
  if (followed(a)) return true;
  if (s.send === "key") return isKey(a);
  return (await mineIn(a)).length > 0;      /* "mine": the bills I follow and my members */
}
async function notifyNew(list) {
  if (!canNotify()) return;
  const s = nget(); if (!s.on) return;
  const had = new Set(s.seen), fresh = list.filter(a => !had.has(aid(a)));
  if (!fresh.length) return;
  markSeen(s, fresh); nput(s);
  if (perm() !== "granted") return;
  const now = Date.now(), picked = [];
  for (const a of fresh.filter(a => now - Date.parse(a.t) <= FRESH).sort((x, y) => x.n - y.n)) if (await wants(s, a)) picked.push(a);
  for (const a of picked.slice(-NOTE_MAX)) note(emoji(a) + " " + texts(a)[0], await noteBody(a), link(a), "tca-congress-" + (a.b || a.k));
}
/* what a notification says under its title: the reader's own members on a recorded vote first (a lock screen shows only
   the first few lines), then the alert's sentence */
export async function noteBody(a) {
  const [, y] = texts(a);
  const m = a.rc ? await mineIn(a) : [];
  return m.length ? t("Your members: {list}.", {list: listWords(m.map(p => `${p.name} ${p.words}`))}) + " " + y : y;
}
/* a reminder's notification: [title, body], the start on this device's clock and what is on the agenda */
export function reminderNote(it, r) {
  const head = "⏰ " + t("Reminder: {what}", {what: (it && (it.cm ? `${it.cm}${it.ty ? " " + it.ty.toLowerCase() : ""}` : it.ti)) || (r && r.ti) || t("Congress")});
  if (!it) return [head, (r && r.what) || ""];
  const cd = countdown(it), words = cd.words ? cd.words.charAt(0).toUpperCase() + cd.words.slice(1) : "";
  const at = it.at ? (it.ex === 0 ? t("expected around {time}", {time: when(it.at, "time")}) : t("at {time}", {time: when(it.at, "time")})) : "";
  const agenda = it.d && it.d.length ? " " + t("On the agenda: {list}.", {list: listWords(it.d)}) : "";
  return [head, [words, at].filter(Boolean).join(", ") + "." + agenda + (it.room ? " " + t("Room {room}.", {room: it.room}) : "")];
}
async function note(head, body, url, tag) {
  const o = {body, icon: new URL("icon-192.png", ROOT).href, tag, renotify: true, timestamp: Date.now(), data: {url}};
  let reg = null;
  try { if ("serviceWorker" in navigator) reg = await navigator.serviceWorker.getRegistration(ROOT.href); } catch (err) {}
  if (reg && reg.showNotification) { try { await reg.showNotification(head, o); return true; } catch (err) {} }
  try { const n = new Notification(head, o); n.onclick = ev => { try { ev.preventDefault(); focus(); } catch (x) {} n.close(); location.assign(url); }; return true; } catch (err) {}
  return false;
}
function turnOn() { const s = nget(); s.on = true; markSeen(s, latest.concat(full || [])); nput(s); bell(); }

/* ---------- reminders, while a page is open ---------- */
let soonT = 0;
function tickSoon() {
  clearTimeout(soonT);
  const all = reminders.all(), now = Date.now();
  let changed = false;
  for (const [id, r] of Object.entries(all)) {
    if (!r || typeof r !== "object") { delete all[id]; changed = true; continue; }
    if (r.at && now > r.at + 6 * 3600e3) { delete all[id]; changed = true; continue; }      /* long over: let it go */
    if (!r.fired && r.at && now >= r.at - r.lead * 60000) {
      r.fired = true; changed = true;
      const it = items.find(i => i.id === id), [head, msg] = reminderNote(it, r);
      const go = () => css().then(() => notice(head, msg));
      if (perm() === "granted") note(head, msg, usPage("#coming"), "tca-congress-remind-" + id).then(ok => { if (!ok) go(); }); else go();
    }
  }
  if (changed) { ls.set(K.remind, JSON.stringify(all)); emit("reminders"); }
  if (Object.values(all).some(r => r && !r.fired)) soonT = setTimeout(tickSoon, TICK);
}
/* a reminder with no notifications allowed: a small notice on the page */
function notice(head, msg) {
  const n = D.createElement("div");
  n.className = "tca-cgnote"; n.setAttribute("role", "status");
  n.innerHTML = `<p><b>${esc(head)}</b> ${esc(msg)}</p><a href="${esc(usPage("#coming"))}">${esc(t("See what's coming up"))}</a><button type="button" aria-label="${esc(t("Close"))}">${X}</button>`;
  tagLang(n);
  n.querySelector("button").addEventListener("click", () => n.remove());
  D.body.append(n);
}

/* ---------- the banner ---------- */
let box = null, msg = null, pauseBtn = null, liveEl = null, dlg = null, dlgFrom = null;
let latest = [], full = null, fullAt = 0, items = [], turn = [], at = 0, paused = false, held = false, turnT = 0, pollT = 0, last = 0, top = 0;
const X = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 6l12 12M18 6L6 18"/></svg>';
const DOME = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 20h16M6 20v-6M10 20v-6M14 20v-6M18 20v-6M5 14h14M7 14a5 5 0 0 1 10 0M12 6V4"/></svg>';
function build() {
  box = D.createElement("div");
  box.className = "tca-cg"; box.setAttribute("role", "region"); box.setAttribute("aria-label", t("Congress alerts"));
  box.innerHTML = `<div class="tca-cg-in"><span class="tca-cg-tag">${DOME}<span>${esc(t("Congress"))}</span></span><p class="tca-cg-msg"></p>
<div class="tca-cg-tools"><button type="button" class="tca-cg-b" data-cg="pause" hidden></button>${offerNotify() ? `<button type="button" class="tca-cg-b" data-cg="notify" aria-haspopup="dialog"><span class="tca-cg-e" aria-hidden="true">${BELL}</span><span class="tca-cg-bt"></span></button>` : ""}<a class="tca-cg-b" data-cg="all" href="${esc(usPage("#moving"))}">${esc(t("What's moving"))}</a>
<button type="button" class="tca-cg-x" data-cg="close">${X}</button></div></div><div class="tca-cg-sr" role="status" aria-live="polite"></div>`;
  tagLang(box);
  msg = box.querySelector(".tca-cg-msg"); pauseBtn = box.querySelector('[data-cg="pause"]'); liveEl = box.querySelector(".tca-cg-sr");
  const x = box.querySelector('[data-cg="close"]');
  x.setAttribute("aria-label", t("Hide these alerts until a new one comes")); x.title = t("Hide these alerts until a new one comes");
  pauseBtn.addEventListener("click", () => { paused = !paused; pauseBtn.textContent = paused ? t("Resume") : t("Pause"); spin(); });
  const nb = box.querySelector('[data-cg="notify"]'); if (nb) nb.addEventListener("click", e => notifyPress(e.currentTarget));
  x.addEventListener("click", hide);
  box.addEventListener("pointerenter", () => { held = true; }); box.addEventListener("pointerleave", () => { held = false; spin(); });
  box.addEventListener("focusin", () => { held = true; }); box.addEventListener("focusout", e => { if (!box.contains(e.relatedTarget)) { held = false; spin(); } });
  bell();
  /* just above the page's own top bar (below Election Night's banner, if a shared one is up), else at the very top */
  const night = D.querySelector(".tca-al"), bar = D.querySelector("header.tca-top, header.top") || D.querySelector("body > header");
  if (night && night.parentNode) night.after(box);
  else if (bar && bar.parentNode) bar.parentNode.insertBefore(box, bar);
  else { const f = D.body.firstElementChild; if (f && f.matches('a[href^="#"]')) f.after(box); else D.body.prepend(box); }
  dispatchEvent(new Event("resize"));
}
function show(i, slide) {
  const a = turn[i]; if (!a || !box) return;
  at = i;
  const [x, y] = texts(a), u = link(a);
  msg.textContent = "";
  const tm = D.createElement("time");
  if (a.k === "soon") { tm.dateTime = (a.w && a.w.at) || ""; tm.textContent = a.w && a.w.at ? when(a.w.at, "time") : ""; }
  else { tm.dateTime = a.t; tm.textContent = Date.now() - Date.parse(a.t) < 20 * 3600e3 ? when(a.t, "time") : dayOf(a.t); }
  const w = D.createElement("a"); w.href = u;
  w.innerHTML = `<span class="tca-cg-e" aria-hidden="true">${emoji(a)}</span><b>${esc(x)}</b><span class="tca-cg-s"> ${esc(y)}</span>`;      /* a phone shows the headline alone */
  msg.append(tm, " ", w);
  box.dataset.kind = a.k; box.dataset.n = String(a.n || "");
  box.classList.toggle("law", a.k === "law");
  /* the reader's own members on this vote, when the page knows their state */
  if (a.rc && mine()) mineIn(a).then(m => {
    if (!m.length || !box || box.dataset.n !== String(a.n)) return;
    const s = D.createElement("span"); s.className = "tca-cg-mine";
    s.textContent = " " + t("Your members: {list}.", {list: listWords(m.map(p => `${p.name} ${p.words}`))});
    msg.append(s);
  });
  if (slide && !still()) { box.classList.remove("slide"); void box.offsetWidth; box.classList.add("slide"); } else box.classList.remove("slide");
}
function spin() {
  clearTimeout(turnT);
  if (!box || turn.length < 2 || paused) return;
  turnT = setTimeout(() => { if (!held && !paused && D.visibilityState !== "hidden" && !(dlg && dlg.open)) show((at + 1) % turn.length, true); spin(); }, TURN);
}
function remove() { clearTimeout(turnT); if (box) { box.remove(); box = null; dispatchEvent(new Event("resize")); } }
function hide() {
  const soonIds = turn.filter(a => a.k === "soon").map(a => a.w.id);
  ls.set(K.hid, JSON.stringify({n: top, soon: soonIds}));
  const next = D.querySelector("header.tca-top a, header.tca-top button, header.top a, header.top button");
  remove();
  if (next) { try { next.focus({preventScroll: true}); } catch (e) {} }
}
function say(text) { if (!liveEl || !text) return; liveEl.textContent = ""; setTimeout(() => { if (liveEl) liveEl.textContent = text; }, 80); }
function bell() {
  if (!box) return;
  const b = box.querySelector('[data-cg="notify"]'); if (!b) return;
  const on = nget().on && perm() === "granted";
  b.querySelector(".tca-cg-bt").textContent = on ? t("Notifications on") : t("Notify me");
  b.setAttribute("aria-label", on ? t("Notifications on: change them") : t("Notify me"));
}
async function notifyPress(from) {
  await css();
  if (canNotify() && perm() === "default" && (await ask()) === "granted") turnOn();
  openDlg(from);
}

/* ---------- Notify me ---------- */
function ensureDlg() {
  if (dlg) return;
  dlg = D.createElement("dialog"); dlg.className = "tca-cgdlg"; dlg.setAttribute("aria-labelledby", "tca-cgdlg-h"); tagLang(dlg);
  dlg.addEventListener("click", e => {
    if (e.target === dlg) { dlg.close(); return; }
    const b = e.target.closest("[data-cgd]"); if (!b || !dlg.contains(b)) return;
    if (b.getAttribute("data-cgd") === "close") dlg.close();
  });
  dlg.addEventListener("change", onChange);
  dlg.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); dlg.close(); } });
  dlg.addEventListener("close", () => { if (dlgFrom && dlgFrom.isConnected) { try { dlgFrom.focus({preventScroll: true}); } catch (e) {} } dlgFrom = null; spin(); });
  D.body.append(dlg);
}
function openDlg(from) {
  ensureDlg();
  if (!dlg.open) dlgFrom = from || D.activeElement;
  dlg.innerHTML = notifyHTML();
  if (!dlg.open) { if (typeof dlg.showModal === "function") { try { dlg.showModal(); } catch (e) { dlg.setAttribute("open", ""); } } else dlg.setAttribute("open", ""); }
  const h = dlg.querySelector("h2"); h.tabIndex = -1; try { h.focus({preventScroll: true}); } catch (e) {}
}
function notifyHTML() {
  const s = nget(), p = canNotify() ? perm() : "none", on = s.on && p === "granted", my = mine(), nf = follows.list().length;
  const r = (val, label, hint) => `<label class="tca-cgdlg-r"><input type="radio" name="tca-cgn-send" value="${val}" data-cgn="send"${val === s.send ? " checked" : ""}><span>${esc(label)}${hint ? `<small>${esc(hint)}</small>` : ""}</span></label>`;
  return `<div class="tca-cgdlg-in"><button type="button" class="tca-cgdlg-x" data-cgd="close" aria-label="${esc(t("Close"))}">${X}</button>
<h2 id="tca-cgdlg-h"><span class="tca-cgdlg-e" aria-hidden="true">${BELL}</span>${esc(t("Congress alerts on this device"))}</h2>
<p class="tca-cgdlg-note">${esc(t("Alerts come through while a page of this site or the app is open, even in the background on a computer or Android phone. Your choices stay on this device; nothing about you is sent anywhere."))}</p>
${p === "denied" ? `<p class="tca-cgdlg-warn">${esc(t("This browser is blocking notifications from this site, so the switch stays off. To allow them, open this site's settings in your browser (in most browsers, the icon just left of the address), set Notifications to Allow, then reload this page."))}</p>` : ""}
${p === "none" ? `<p class="tca-cgdlg-warn">${esc(t("This browser cannot show notifications from a web page. On an iPhone or iPad, add the site to your Home Screen first (Get the app), then open it from there."))}</p>` : ""}
<label class="tca-cgdlg-sw"><input type="checkbox" role="switch" data-cgn="on"${on ? " checked" : ""}${p === "denied" || p === "none" ? " disabled" : ""}><span>${esc(t("On for this device"))}</span></label>
<fieldset class="tca-cgdlg-fs"><legend>${esc(t("Send me"))}</legend>
${r("key", t("The big moments"), t("Floor votes, a bill passing or failing, laws signed, vetoes, and everything about bills I follow."))}
${r("all", t("Everything"), t("Also committee approvals, calendars, cosponsors, the daily new-bills roundup and schedule changes."))}
${r("mine", t("Only bills I follow and my members"), my ? t("Your members are those for {where}, from the Congress page.", {where: my.st + (my.dist ? "-" + my.dist : "")}) : t("Pick your state on the Congress page's \"How did your members vote?\" first."))}</fieldset>
<p class="tca-cgdlg-note">${esc(nf ? t("You follow {n} bills. Reminders you set on the Coming up page come through here too.", {n: num(nf)}) : t("Follow a bill with its star on the Congress page. Reminders you set on the Coming up page come through here too."))}</p>
<p class="tca-cgdlg-acts"><a class="tca-cgdlg-b" href="${esc(usPage("#moving"))}">${esc(t("What's moving"))}</a><a class="tca-cgdlg-b" href="${esc(usPage("#coming"))}">${esc(t("Coming up"))}</a><button type="button" class="tca-cgdlg-b" data-cgd="close">${esc(t("Done"))}</button></p></div>`;
}
async function onChange(ev) {
  const el = ev.target, n = el.getAttribute("data-cgn"); if (!n) return;
  const s = nget();
  if (n === "on") {
    if (!el.checked) { s.on = false; nput(s); bell(); return; }
    if (perm() === "default") await ask();
    if (perm() === "granted") turnOn(); else { s.on = false; nput(s); }
    bell(); const y = dlg.querySelector(".tca-cgdlg-in").scrollTop; dlg.innerHTML = notifyHTML(); dlg.querySelector(".tca-cgdlg-in").scrollTop = y;
    const f = dlg.querySelector('input[data-cgn="on"]'); if (f) try { f.focus({preventScroll: true}); } catch (e) {}
    return;
  }
  if (n === "send") { s.send = el.value; nput(s); }
}

/* ---------- the files ---------- */
const valid = a => a && typeof a === "object" && ALLK.includes(a.k) && typeof a.t === "string" && !isNaN(Date.parse(a.t)) && Number.isFinite(a.n);
const sorted = doc => doc.a.filter(valid).sort((x, y) => (Date.parse(y.t) - Date.parse(x.t)) || (y.n - x.n));
const ok = doc => doc && doc.v === 1 && Array.isArray(doc.a);
let fullP = null;
function loadAll() {
  if (full && Date.now() - fullAt < 120000) return Promise.resolve(full);
  if (!fullP) fullP = getJSON(fileURL("alerts-all.json")).then(doc => { if (ok(doc)) { full = sorted(doc); fullAt = Date.now(); } fullP = null; return full || latest; });      /* one request at a time */
  return fullP;
}
function take() {
  const now = Date.now(), hid = ls.json(K.hid, {}) || {};
  const fresh = latest.filter(a => now - Date.parse(a.t) <= FRESH && (isKey(a) || followed(a)));
  const soon = items.filter(it => it.at && it.st !== "gone" && ["hc", "sc", "clo"].includes(it.k) && (() => { const c = countdown(it, now); return c.soon && !c.past; })())
    .map(it => ({k: "soon", n: 0, id: "soon:" + it.id, w: it, t: new Date(now).toISOString()}));
  const newTop = latest.reduce((m, a) => Math.max(m, a.n), 0);
  const wasTop = top; top = Math.max(top, newTop);
  const hiddenSoon = new Set(Array.isArray(hid.soon) ? hid.soon : []);
  /* the banner's turns: laws and vetoes first, then passage, then the other votes; each kind newest first */
  const RANK = {law: 0, veto: 1, over: 2, pass: 3, fail: 3, agree: 3, amend: 3, conf: 3, disagree: 4, tabled: 4, pres: 4, vote: 5};
  const shownFresh = fresh.filter(a => a.n > (+hid.n || 0))
    .sort((x, y) => ((RANK[x.k] ?? 9) - (RANK[y.k] ?? 9)) || (Date.parse(y.t) - Date.parse(x.t)) || (y.n - x.n));
  const shownSoon = soon.filter(a => !hiddenSoon.has(a.w.id));
  turn = shownSoon.concat(shownFresh).slice(0, MAX_TURN);
  if (!turn.length) { remove(); return; }
  const was = box ? turn.findIndex(a => box.dataset.n === String(a.n || "") && a.n) : -1;
  if (!box) build();
  pauseBtn.hidden = turn.length < 2; if (pauseBtn.hidden) paused = false;
  pauseBtn.textContent = paused ? t("Resume") : t("Pause");
  bell();
  const isNew = newTop > wasTop && wasTop > 0;
  const newest = turn.reduce((bi, a, i) => ((a.n || 0) > (turn[bi].n || 0) ? i : bi), 0);      /* a new alert shows first, wherever its kind sorts */
  show(isNew ? newest : was < 0 ? 0 : was, isNew);
  spin();
  const said = +(ss.get(K.said) || 0);
  if (said && newTop > said) { const nw = shownFresh.filter(a => a.n > said).sort((x, y) => y.n - x.n)[0]; if (nw) say(words(nw)); }
  if (newTop > said) ss.set(K.said, String(newTop));
}
let readyFired = false;
function look() {
  clearTimeout(pollT);
  if (D.visibilityState === "hidden" && !noting()) return;
  last = Date.now();
  Promise.all([getJSON(fileURL("alerts.json")), getJSON(fileURL("upcoming.json"))]).then(([doc, up]) => {
    const before = latest.length ? latest[0].n : 0, beforeItems = JSON.stringify(items.map(i => [i.id, i.at, i.st]));
    if (ok(doc)) latest = sorted(doc);
    if (up && up.v === 1 && Array.isArray(up.i)) items = up.i.filter(i => i && typeof i.id === "string");
    if (!readyFired) { readyFired = true; dispatchEvent(new Event("tca:congress-ready")); }
    else {
      if ((latest[0] || {}).n !== before) emit("alerts");
      if (JSON.stringify(items.map(i => [i.id, i.at, i.st])) !== beforeItems) emit("items");
    }
    notifyNew(latest);
    if (latest.some(a => Date.now() - Date.parse(a.t) <= FRESH && (isKey(a) || followed(a))) || items.some(i => i.at && countdown(i).soon)) css().then(take);
    else remove();
    tickSoon();
  });
  pollT = setTimeout(look, EVERY);
}
function seen() {
  if (D.visibilityState === "hidden") { if (!noting()) clearTimeout(pollT); return; }
  clearTimeout(pollT);
  pollT = setTimeout(look, Math.max(0, last + EVERY - Date.now()));
}

/* ---------- the Congress page's way in ----------
   api.alerts("new" | "all") -> Promise<alert[]> newest first; api.items() -> Promise<item[]> soonest first; api.texts(a) ->
   [title, sentence]; api.words(a); api.emoji(a); api.link(a); api.voteLink(a); api.key(a); api.mine(); api.mineIn(a) ->
   Promise<[{name, party, chamber, pos?, words?, role?}]>; api.countdown(item, now?) -> {words, soon, past, exact};
   api.when(isoOrDay, "time" | "day" | "full"); api.follows.{list, has, toggle}; api.reminders.{get, set, clear};
   api.addToCalendar(item); api.calendars -> [{id, name, url, webcal}]; api.notify(fromElement). */
const firstLook = new Promise(res => { if (readyFired) res(); else addEventListener("tca:congress-ready", () => res(), {once: true}); });
const API = {
  alerts: which => firstLook.then(() => (which === "all" ? loadAll() : latest)),
  items: () => firstLook.then(() => items.slice().sort((x, y) => (Date.parse(x.at || "") || refTime(x) || 0) - (Date.parse(y.at || "") || refTime(y) || 0))),
  texts, words, emoji, link, voteLink, key: isKey, mine, mineIn, countdown, when, follows, noteBody, reminderNote,
  reminders: {get: reminders.get, set: reminders.set, clear: reminders.clear, can: reminders.can},
  addToCalendar, get calendars() { return calendars(); },
  notify: from => notifyPress(from),
};
window.tcaCongress = API;

/* "Notify me" anywhere on a page: an element with data-tca-notify="congress" (Election Night's own buttons, with any other
   value, stay Election Night's) */
D.addEventListener("click", e => {
  const b = e.target.closest && e.target.closest('[data-tca-notify="congress"]'); if (!b) return;
  e.preventDefault(); e.stopImmediatePropagation(); notifyPress(b);
}, true);
function boot() { D.addEventListener("visibilitychange", seen); look(); }
if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", boot, {once: true}); else boot();
