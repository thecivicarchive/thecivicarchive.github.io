/*
 The night crossing: the way into Election Night (John, 2026-10-10: "sitting outside for 10 seconds looking up at a
 cloudless night sky, moon and stars going and having a meteor shower go on ... feel like a person would see this in real
 life with the imagery and scenery too"), and, from the same scene, the deck to sit on as long as you like (John,
 2026-10-11: "as if you are literally there").

 You sit in a chair at the railing of the cabin's deck in the Rockies at night: the planks and the log railing in the warm
 light from the window behind you, the mountains black against the sky. The page fades to the dark deck; the stars come
 out as your eyes adjust; your eyes settle on the ridge line and then lift to the sky: the real stars, the planets and the
 Milky Way for your own place and time, with their own colours and brightness, twinkling a little and dimmer near the
 horizon; a crescent moon with earthshine on its dark part, and its light on the deck; and a meteor shower from the radiant
 of the shower active on your date (or the nearest major one): thin streaks at the right speed and length, mostly white,
 with yellow and orange in a slow shower and more green in a fast one, whose brightest leave a glowing train; and one bright
 fireball near the end. The snow on the peaks is lit by the sky alone, a grey just below it. Then the night fades into
 Election Night's home.

 The deck (Election Night's own page for it). A reader starts seated where they chose: the chair at the railing, the top of
 the steps down to the yard, or the bench by the cabin's wall; looks around by dragging, by touch or with the arrow keys;
 gets up and walks the deck, down the steps and about the yard (W A S D or the arrows; on a phone a thumb control), never
 through the railing, the furniture, a tree or the cabin's wall; and sits again with a tap. The sky turns as the real one
 does, in real time; a meteor falls every few seconds, now and then a brighter one. Behind them the cabin is the great room
 itself seen from its deck, with the room's own measurements: the gable end of glass rising to the ridge, lit from inside
 by the lamps, the chandelier and the fire on the right-hand wall (the sofa, the loft and the stair show through it), the
 glazed door at the glass's right, a lantern beside it, the stone chimney up the right-hand end, smoke drifting across the
 stars; the room's light comes out through the glass and lies in bars across the boards. The
 sound of the place is off until they turn it on: wind in the pines, a creek far down the slope, an owl, now and then an elk
 bugling across the valley in its season (September and October) and coyotes far off, the fire crackling behind the glass,
 their own steps on the boards. The wind, the owl, the fire and the steps are made on the device; the elk, the coyotes and
 the creek are the National Park Service's own public-domain recordings, fetched only when the sound is turned on.

 Where and when come from this device alone: the place this site already keeps here when you used "Use my location"
 (rounded), or the state you chose, or else your time zone; the time from your device's clock (after dark tonight, when
 it is day). Nothing about you is sent anywhere, and no request this makes carries a place or a time.

 The screen gets it all through a lens: a high-range picture with depth, a soft bloom off the moon, the window and a
 fireball, depth of field that racks between the railing and the sky, a quiet shoulder on the brightest things, the lens's
 fall-off at the edges and a very fine grain. The moon is placed for the scene: tonight's crescent where tonight has one,
 otherwise a young crescent, always in view, drawn about two and a half times its true size so its crescent and earthshine
 show on a screen, and it is the moon whose light lies across the deck. A real shower shows a meteor or two a minute at
 best; ten seconds here hold a night's worth, and the deck shows one every few seconds.

 What it is drawn from (every work credited on Election Night's home and on the deck's page): stars from the Bright Star
 Catalogue, 5th revised edition (D. Hoffleit and W. H. Warren Jr.), as NASA's HEASARC keeps it; the planets from JPL's
 Keplerian elements for their approximate positions (E. M. Standish); the Milky Way from NASA's Deep Star Maps 2020
 (Goddard Space Flight Center Scientific Visualization Studio; Gaia DR2: ESA/Gaia/DPAC); the Moon from NASA's CGI Moon Kit
 (Scientific Visualization Studio, from the Lunar Reconnaissance Orbiter); the mountains from a public-domain National
 Park Service photograph of Longs Peak and Mount Meeker; the deck, the yard, the rocks, the bark and the cabin from CC0
 materials (Poly Haven); the showers' dates, radiants and speeds from the International Meteor Organization's working list.

 Uses three.js (MIT licence), kept with the site.
   prepare(opts)           fetch the crossing's files (on the first hover, focus or tap of a way into Election Night);
                           opts.onProgress(bytes, total) reports the fetch, for the deck's loading view
   loadMore(urls, onProgress)  the deck's extra files (its page names them): pictures, a model (through the kit's glTF
                           loader, fetched only then); each one that does not arrive is drawn plain, or left out (a Promise)
   supported()             can this device draw it
   run(url, opts)          play the crossing over the page, then go to url; false when it cannot be drawn, else {skip, stay}
                           opts.host  the element to draw into (the way in's own veil); opts.still  one still picture;
                           opts.lean  the light version, for a device with little memory or few cores; opts.stay  the
                           deck's own page, where Stay takes the reader, the view handed over; opts.keys  false when the
                           caller listens to the keyboard itself; opts.hold()  true while the reader reaches for Stay
   watch(canvas, opts)     the deck to sit on (see the comment above watch); returns its controller, or null
   still(t, w, h, opts)    one frame as a JPEG data URL (opts.png: a PNG), for checking a scene where frames are not drawn
                           (a Promise); opts.watch the deck, from opts.seat or opts.walk {x, z, yaw, pitch}, opts.more its files
   facts(opts)             what the scene works out about tonight's sky (a Promise)
   SEATS                   the deck's seats: id, name, a sentence, and where
*/
import * as THREE from "../vendor/three.module.min.js";

const FILES = {"stars":"stars.f580fc0141.bin","milkyway":"milkyway.4a1deb3187.jpg","moon":"moon.c0a7c05901.jpg","ridge":"ridge.a749a8a985.jpg","ridge_json":"ridge_json.ecf2d316e2.json","deck_diff":"deck_diff.8bde66640c.jpg","deck_nor":"deck_nor.b102d9adf5.jpg","deck_arm":"deck_arm.a9e830b562.jpg","logs_diff":"logs_diff.b8d0d8e1c1.jpg","logs_nor":"logs_nor.a653d46cdb.jpg"};
const asset = k => new URL(FILES[k], import.meta.url).href;
const DUR = 10.0;
const D2R = Math.PI / 180, R2D = 180 / Math.PI;
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const seg = (t, a, b) => clamp((t - a) / (b - a));
const smooth = x => x * x * (3 - 2 * x);
const inOut = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
const mix = (a, b, t) => a + (b - a) * t;
const V3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
function rng(seed){ let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const kept = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
const pt = {x: 0, y: 0, sx: 0, sy: 0};      // the pointer, -1 to 1 across the window; sx, sy follow it slowly, as a head does
addEventListener("pointermove", e => { pt.x = e.clientX / innerWidth * 2 - 1; pt.y = e.clientY / innerHeight * 2 - 1; }, {passive: true});

/* ================================ where and when: this device only ================================ */

/* a time zone's main city, for a reader who has kept no place on this site */
const ZONES = {
  "America/New_York": [40.71, -74.01], "America/Detroit": [42.33, -83.05], "America/Indiana/Indianapolis": [39.77, -86.16], "America/Kentucky/Louisville": [38.25, -85.76],
  "America/Chicago": [41.88, -87.63], "America/Menominee": [45.11, -87.61], "America/North_Dakota/Center": [47.12, -101.3], "America/Denver": [39.74, -104.99],
  "America/Boise": [43.62, -116.2], "America/Phoenix": [33.45, -112.07], "America/Los_Angeles": [34.05, -118.24], "America/Anchorage": [61.22, -149.9],
  "America/Juneau": [58.3, -134.42], "America/Sitka": [57.05, -135.33], "America/Nome": [64.5, -165.41], "America/Adak": [51.88, -176.66], "Pacific/Honolulu": [21.31, -157.86],
  "America/Puerto_Rico": [18.47, -66.11], "America/St_Thomas": [18.34, -64.93], "Pacific/Guam": [13.44, 144.79], "Pacific/Saipan": [15.18, 145.75], "Pacific/Pago_Pago": [-14.28, -170.7],
  "America/Toronto": [43.65, -79.38], "America/Vancouver": [49.28, -123.12], "America/Edmonton": [53.55, -113.49], "America/Winnipeg": [49.9, -97.14], "America/Regina": [50.45, -104.6],
  "America/Halifax": [44.65, -63.57], "America/St_Johns": [47.56, -52.71], "America/Mexico_City": [19.43, -99.13], "America/Bogota": [4.71, -74.07], "America/Lima": [-12.05, -77.04],
  "America/Sao_Paulo": [-23.55, -46.63], "America/Argentina/Buenos_Aires": [-34.6, -58.38], "America/Santiago": [-33.45, -70.67],
  "Europe/London": [51.51, -0.13], "Europe/Dublin": [53.35, -6.26], "Europe/Lisbon": [38.72, -9.14], "Europe/Madrid": [40.42, -3.7], "Europe/Paris": [48.86, 2.35],
  "Europe/Brussels": [50.85, 4.35], "Europe/Amsterdam": [52.37, 4.9], "Europe/Berlin": [52.52, 13.4], "Europe/Zurich": [47.38, 8.54], "Europe/Rome": [41.9, 12.5],
  "Europe/Vienna": [48.21, 16.37], "Europe/Prague": [50.08, 14.44], "Europe/Warsaw": [52.23, 21.01], "Europe/Stockholm": [59.33, 18.07], "Europe/Oslo": [59.91, 10.75],
  "Europe/Copenhagen": [55.68, 12.57], "Europe/Helsinki": [60.17, 24.94], "Europe/Athens": [37.98, 23.73], "Europe/Kyiv": [50.45, 30.52], "Europe/Istanbul": [41.01, 28.98],
  "Europe/Moscow": [55.76, 37.62], "Asia/Jerusalem": [31.77, 35.21], "Asia/Dubai": [25.2, 55.27], "Asia/Kolkata": [28.61, 77.21], "Asia/Shanghai": [31.23, 121.47],
  "Asia/Hong_Kong": [22.32, 114.17], "Asia/Taipei": [25.03, 121.57], "Asia/Tokyo": [35.68, 139.69], "Asia/Seoul": [37.57, 126.98], "Asia/Singapore": [1.35, 103.82],
  "Asia/Manila": [14.6, 120.98], "Asia/Bangkok": [13.76, 100.5], "Asia/Jakarta": [-6.21, 106.85], "Australia/Sydney": [-33.87, 151.21], "Australia/Melbourne": [-37.81, 144.96],
  "Australia/Brisbane": [-27.47, 153.03], "Australia/Perth": [-31.95, 115.86], "Australia/Adelaide": [-34.93, 138.6], "Pacific/Auckland": [-36.85, 174.76],
  "Africa/Johannesburg": [-26.2, 28.05], "Africa/Lagos": [6.52, 3.38], "Africa/Cairo": [30.04, 31.24], "Africa/Nairobi": [-1.29, 36.82], "Atlantic/Reykjavik": [64.15, -21.94]
};
/* the middle of each state, for a reader who chose a state on this site but kept no place */
const STATES = {AL: [32.8, -86.8], AK: [61.4, -150.0], AZ: [33.7, -111.9], AR: [34.9, -92.4], CA: [36.5, -119.5], CO: [39.6, -105.3], CT: [41.6, -72.7], DE: [39.0, -75.5],
  DC: [38.9, -77.03], FL: [28.1, -81.6], GA: [33.0, -83.6], HI: [21.3, -157.8], ID: [44.2, -114.6], IL: [40.3, -89.0], IN: [39.8, -86.3], IA: [42.0, -93.2], KS: [38.5, -98.4],
  KY: [37.7, -84.7], LA: [31.0, -92.0], ME: [44.7, -69.4], MD: [39.0, -76.8], MA: [42.2, -71.5], MI: [43.3, -84.5], MN: [45.7, -93.9], MS: [32.7, -89.7], MO: [38.5, -92.3],
  MT: [46.9, -110.4], NE: [41.1, -98.3], NV: [38.3, -117.1], NH: [43.5, -71.6], NJ: [40.3, -74.5], NM: [34.8, -106.2], NY: [42.2, -74.9], NC: [35.6, -79.8], ND: [47.5, -99.8],
  OH: [40.4, -82.8], OK: [35.6, -96.9], OR: [44.6, -122.1], PA: [40.6, -77.2], RI: [41.7, -71.5], SC: [33.9, -80.9], SD: [44.3, -99.4], TN: [35.7, -86.7], TX: [31.1, -97.6],
  UT: [40.2, -111.9], VT: [44.0, -72.7], VA: [37.8, -78.2], WA: [47.4, -121.5], WV: [38.5, -80.9], WI: [44.3, -89.6], WY: [42.8, -107.3], PR: [18.2, -66.5], GU: [13.44, 144.79]};

export function place(){
  try { const p = JSON.parse(kept("pin") || "null");
    if (p && isFinite(p.lat) && isFinite(p.lon) && Math.abs(p.lat) <= 90 && Math.abs(p.lon) <= 180) return {lat: +p.lat, lon: +p.lon, how: "kept"}; } catch (e) {}
  const st = String(kept("state") || "").toUpperCase();
  if (STATES[st]) return {lat: STATES[st][0], lon: STATES[st][1], how: "state", state: st};
  let tz = ""; try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (e) {}
  if (ZONES[tz]) return {lat: ZONES[tz][0], lon: ZONES[tz][1], how: "zone", zone: tz};
  const south = /^(Australia|Antarctica)\/|^Pacific\/(Auckland|Chatham|Fiji)|^America\/(Argentina|Sao_Paulo|Santiago|Montevideo|Asuncion|La_Paz)|^Africa\/(Johannesburg|Maputo|Harare|Windhoek|Lusaka|Gaborone)/.test(tz);
  return {lat: south ? -32 : 40, lon: clamp(-new Date().getTimezoneOffset() / 4, -180, 180), how: "offset"};
}

/* ================================ the sky's machinery (low precision: ample for the eye) ================================ */
const jdOf = d => d.getTime() / 864e5 + 2440587.5;
function gmst(jd){ const T = (jd - 2451545) / 36525; return (((280.46061837 + 360.98564736629 * (jd - 2451545) + 0.000387933 * T * T - T * T * T / 38710000) % 360) + 360) % 360; }
function eclToEq(lam, bet, eps){ const cb = Math.cos(bet), x = cb * Math.cos(lam), y = cb * Math.sin(lam), z = Math.sin(bet);
  return V3(x, y * Math.cos(eps) - z * Math.sin(eps), y * Math.sin(eps) + z * Math.cos(eps)); }
/* the Sun and the Moon, by the Astronomical Almanac's low-precision formulae (the Moon to about a third of a degree) */
function sunOf(jd){ const n = jd - 2451545, L = (280.460 + 0.9856474 * n) * D2R, g = (357.528 + 0.9856003 * n) * D2R;
  const lam = L + (1.915 * Math.sin(g) + 0.020 * Math.sin(2 * g)) * D2R, eps = (23.439 - 4e-7 * n) * D2R;
  return {v: eclToEq(lam, 0, eps), lam}; }
function moonOf(jd){ const T = (jd - 2451545) / 36525, s = d => Math.sin(d * D2R), c = d => Math.cos(d * D2R);
  const lam = 218.32 + 481267.881 * T + 6.29 * s(135.0 + 477198.87 * T) - 1.27 * s(259.3 - 413335.36 * T) + 0.66 * s(235.7 + 890534.22 * T)
    + 0.21 * s(269.9 + 954397.74 * T) - 0.19 * s(357.5 + 35999.05 * T) - 0.11 * s(186.5 + 966404.03 * T);
  const bet = 5.13 * s(93.3 + 483202.02 * T) + 0.28 * s(228.2 + 960400.89 * T) - 0.28 * s(318.3 + 6003.15 * T) - 0.17 * s(217.6 - 407332.21 * T);
  const par = 0.9508 + 0.0518 * c(135.0 + 477198.87 * T) + 0.0095 * c(259.3 - 413335.36 * T) + 0.0078 * c(235.7 + 890534.22 * T) + 0.0028 * c(269.9 + 954397.74 * T);
  return {v: eclToEq(lam * D2R, bet * D2R, (23.439 - 0.0130 * T) * D2R), lam: lam * D2R, par: par * D2R}; }
/* The planets, from JPL's Keplerian elements and their rates for 1800 to 2050 (E. M. Standish, "Approximate Positions
   of the Planets", Solar System Dynamics: a few minutes of arc at worst, ample for the eye), in the J2000 ecliptic; and
   their brightness by the Astronomical Almanac's formulae (distance and phase). Each keeps its own colour (B-V). */
const PLANETS = [
  ["Mercury", [0.38709927, 0.20563593, 7.00497902, 252.25032350, 77.45779628, 48.33076593], [0.00000037, 0.00001906, -0.00594749, 149472.67411175, 0.16047689, -0.12534081], 0.93],
  ["Venus", [0.72333566, 0.00677672, 3.39467605, 181.97909950, 131.60246718, 76.67984255], [0.00000390, -0.00004107, -0.00078890, 58517.81538729, 0.00268329, -0.27769418], 0.82],
  ["Earth", [1.00000261, 0.01671123, -0.00001531, 100.46457166, 102.93768193, 0.0], [0.00000562, -0.00004392, -0.01294668, 35999.37244981, 0.32327364, 0.0], 0],
  ["Mars", [1.52371034, 0.09339410, 1.84969142, -4.55343205, -23.94362959, 49.55953891], [0.00001847, 0.00007882, -0.00813131, 19140.30268499, 0.44441088, -0.29257343], 1.36],
  ["Jupiter", [5.20288700, 0.04838624, 1.30439695, 34.39644051, 14.72847983, 100.47390909], [-0.00011607, -0.00013253, -0.00183714, 3034.74612775, 0.21252668, 0.20469106], 0.87],
  ["Saturn", [9.53667594, 0.05386179, 2.48599187, 49.95424423, 92.59887831, 113.66242448], [-0.00125060, -0.00050991, 0.00193609, 1222.49362201, -0.41897216, -0.28867794], 1.09]
];
const PMAG = {Mercury: i => -0.42 + 0.038 * i - 0.000273 * i * i + 0.000002 * i ** 3, Venus: i => -4.40 + 0.0009 * i + 0.000239 * i * i - 0.00000065 * i ** 3,
  Mars: i => -1.52 + 0.016 * i, Jupiter: i => -9.40 + 0.005 * i, Saturn: i => -8.88 + 0.044 * i};
function helio(el, rt, T){
  const [a, e, I, L, wb, N] = el.map((v, k) => v + rt[k] * T);
  const M = ((((L - wb) % 360) + 540) % 360 - 180) * D2R;
  let E = M + e * Math.sin(M);
  for (let k = 0; k < 12; k++) { const dE = (M - (E - e * Math.sin(E))) / (1 - e * Math.cos(E)); E += dE; if (Math.abs(dE) < 1e-10) break; }
  const xp = a * (Math.cos(E) - e), yp = a * Math.sqrt(1 - e * e) * Math.sin(E);
  const w = (wb - N) * D2R, n = N * D2R, i = I * D2R, cw = Math.cos(w), sw = Math.sin(w), cN = Math.cos(n), sN = Math.sin(n), cI = Math.cos(i), sI = Math.sin(i);
  return [(cw * cN - sw * sN * cI) * xp + (-sw * cN - cw * sN * cI) * yp, (cw * sN + sw * cN * cI) * xp + (-sw * sN + cw * cN * cI) * yp, sw * sI * xp + cw * sI * yp];
}
function planetsOf(jd){
  const T = (jd - 2451545) / 36525, earth = helio(PLANETS[2][1], PLANETS[2][2], T), eps = 23.43928 * D2R, R0 = Math.hypot(...earth), out = [];
  for (const [name, el, rt, bv] of PLANETS) {
    if (name === "Earth") continue;
    const p = helio(el, rt, T), g = [p[0] - earth[0], p[1] - earth[1], p[2] - earth[2]], r = Math.hypot(...p), d = Math.hypot(...g);
    const x = g[0], y = Math.cos(eps) * g[1] - Math.sin(eps) * g[2], z = Math.sin(eps) * g[1] + Math.cos(eps) * g[2];
    const ph = Math.acos(clamp((r * r + d * d - R0 * R0) / (2 * r * d), -1, 1)) * R2D;
    out.push({name, ra: ((Math.atan2(y, x) * R2D) % 360 + 360) % 360, dec: Math.asin(clamp(z / d, -1, 1)) * R2D, mag: PMAG[name](ph) + 5 * Math.log10(r * d), bv});
  }
  return out;
}
/* J2000 to the mean equator of date (IAU 1976 precession) */
function precession(jd){
  const T = (jd - 2451545) / 36525, as = D2R / 3600;
  const ze = (2306.2181 * T + 0.30188 * T * T + 0.017998 * T ** 3) * as, z = (2306.2181 * T + 1.09468 * T * T + 0.018203 * T ** 3) * as, th = (2004.3109 * T - 0.42665 * T * T - 0.041833 * T ** 3) * as;
  const cz = Math.cos(ze), sz = Math.sin(ze), cZ = Math.cos(z), sZ = Math.sin(z), ct = Math.cos(th), st = Math.sin(th);
  return new THREE.Matrix3().set(cz * ct * cZ - sz * sZ, -sz * ct * cZ - cz * sZ, -st * cZ, cz * ct * sZ + sz * cZ, -sz * ct * sZ + cz * cZ, -st * sZ, cz * st, -sz * st, ct);
}
/* the observer's frame: equatorial (of date) to the scene's world, where -z is the direction faced (azimuth a0), +x its
   right and +y the zenith */
function frameOf(date, lat, lon, a0){
  const jd = jdOf(date), lst = (gmst(jd) + lon) * D2R, phi = lat * D2R;
  const Z = V3(Math.cos(phi) * Math.cos(lst), Math.cos(phi) * Math.sin(lst), Math.sin(phi));
  const E = V3(-Math.sin(lst), Math.cos(lst), 0);
  const N = V3(-Math.sin(phi) * Math.cos(lst), -Math.sin(phi) * Math.sin(lst), Math.cos(phi));
  const a = a0 * D2R, R = E.clone().multiplyScalar(Math.cos(a)).addScaledVector(N, -Math.sin(a)), F = N.clone().multiplyScalar(Math.cos(a)).addScaledVector(E, Math.sin(a));
  const toWorld = new THREE.Matrix3().set(R.x, R.y, R.z, Z.x, Z.y, Z.z, -F.x, -F.y, -F.z);
  const P = precession(jd), j2w = toWorld.clone().multiply(P);
  return {jd, lst, toWorld, j2w, w2j: j2w.clone().transpose(), Z};
}
const altOf = w => Math.asin(clamp(w.y, -1, 1)) * R2D;
const azOf = (w, a0) => ((Math.atan2(w.x, -w.z) * R2D + a0) % 360 + 360) % 360;
const radec = (ra, dec) => V3(Math.cos(dec * D2R) * Math.cos(ra * D2R), Math.cos(dec * D2R) * Math.sin(ra * D2R), Math.sin(dec * D2R));
function sunAltAt(date, lat, lon){ const f = frameOf(date, lat, lon, 0); return altOf(sunOf(f.jd).v.applyMatrix3(f.toWorld)); }
/* the night to draw: now, if it is dark; otherwise tonight, once the sky is fully dark */
function nightOf(now, lat, lon){
  if (sunAltAt(now, lat, lon) < -12) return {date: now, tonight: false};
  let low = now, lowAlt = 99;
  for (let k = 1; k <= 144; k++) { const u = new Date(now.getTime() + k * 6e5), a = sunAltAt(u, lat, lon);
    if (a < -16) return {date: u, tonight: true};
    if (a < lowAlt) { lowAlt = a; low = u; } }
  return {date: low, tonight: true};      // a summer night far north: the darkest moment there is
}
/* the meteor showers: the International Meteor Organization's working list (activity, peak, radiant at the peak in J2000
   degrees and its daily drift, speed in km/s, zenithal hourly rate and how sharply it falls from the peak) */
const SHOWERS = [
  {name: "Quadrantids", from: [12, 28], to: [1, 12], peak: [1, 3], ra: 230, dec: 49, dra: 0.8, ddec: -0.2, v: 41, zhr: 80, b: 1.0, major: 1},
  {name: "Lyrids", from: [4, 14], to: [4, 30], peak: [4, 22], ra: 271, dec: 34, dra: 1.1, ddec: 0, v: 49, zhr: 18, b: 0.25, major: 1},
  {name: "Eta Aquariids", from: [4, 19], to: [5, 28], peak: [5, 6], ra: 338, dec: -1, dra: 0.9, ddec: 0.4, v: 66, zhr: 50, b: 0.08, major: 1},
  {name: "Southern Delta Aquariids", from: [7, 12], to: [8, 23], peak: [7, 30], ra: 340, dec: -16, dra: 0.8, ddec: 0.2, v: 41, zhr: 25, b: 0.07, major: 1},
  {name: "Alpha Capricornids", from: [7, 3], to: [8, 15], peak: [7, 31], ra: 307, dec: -10, dra: 0.9, ddec: 0.3, v: 23, zhr: 5, b: 0.03},
  {name: "Perseids", from: [7, 17], to: [8, 24], peak: [8, 12], ra: 48, dec: 58, dra: 1.35, ddec: 0.12, v: 59, zhr: 100, b: 0.2, major: 1},
  {name: "Draconids", from: [10, 6], to: [10, 10], peak: [10, 8], ra: 262, dec: 54, dra: 0, ddec: 0, v: 20, zhr: 10, b: 2.0},
  {name: "Southern Taurids", from: [9, 10], to: [11, 20], peak: [10, 10], ra: 32, dec: 9, dra: 0.8, ddec: 0.2, v: 27, zhr: 5, b: 0.03},
  {name: "Orionids", from: [10, 2], to: [11, 7], peak: [10, 21], ra: 95, dec: 16, dra: 0.7, ddec: 0.1, v: 66, zhr: 20, b: 0.12, major: 1},
  {name: "Northern Taurids", from: [10, 20], to: [12, 10], peak: [11, 12], ra: 58, dec: 22, dra: 0.9, ddec: 0.17, v: 29, zhr: 5, b: 0.03},
  {name: "Leonids", from: [11, 6], to: [11, 30], peak: [11, 17], ra: 152, dec: 22, dra: 0.7, ddec: -0.35, v: 71, zhr: 15, b: 0.35, major: 1},
  {name: "Geminids", from: [12, 4], to: [12, 20], peak: [12, 14], ra: 112, dec: 33, dra: 1.0, ddec: -0.1, v: 35, zhr: 150, b: 0.4, major: 1},
  {name: "Ursids", from: [12, 17], to: [12, 26], peak: [12, 22], ra: 217, dec: 76, dra: 0, ddec: 0, v: 33, zhr: 10, b: 0.8}
];
function showerOf(date){
  const y = date.getFullYear(), day = (m, d, yy = y) => Date.UTC(yy, m - 1, d, 12) / 864e5, now = date.getTime() / 864e5;
  const near = (m, d) => [y - 1, y, y + 1].map(yy => day(m, d, yy)).reduce((a, b) => Math.abs(b - now) < Math.abs(a - now) ? b : a);
  let best = null, nearest = null;
  for (const s of SHOWERS) {
    const pk = near(...s.peak), dd = now - pk;
    let from = near(...s.from), to = near(...s.to); if (from > pk) from -= 365.25; if (to < pk) to += 365.25;
    const active = now >= from && now <= to, rate = s.zhr * Math.pow(10, -s.b * Math.abs(dd));
    if (active && (!best || rate > best.rate)) best = {s, dd, rate, active: true};
    if (s.major && (!nearest || Math.abs(dd) < Math.abs(nearest.dd))) nearest = {s, dd, rate: 0, active: false};
  }
  const p = best || nearest, dd = clamp(p.dd, -30, 30);
  return {name: p.s.name, active: p.active, v: p.s.v, ra: p.s.ra + p.s.dra * dd, dec: p.s.dec + p.s.ddec * dd, days: Math.round(p.dd), ends: p.active ? p.s.to.slice() : null};
}
/* the elk's season: the rut, September and October (Rocky Mountain National Park's own calendar), by the device's date */
export function elkSeason(d = new Date()){ const m = d.getMonth() + 1; return m === 9 || m === 10; }

/* ================================ the files ================================ */
let loading = null;
function image(url){ return new Promise((ok, no) => { const im = new Image(); im.decoding = "async"; im.onload = () => ok(im); im.onerror = () => no(new Error("could not load " + url)); im.src = url; }); }
/* a file fetched with its progress reported (bytes so far, and the total when the server says it), for the deck's loading view */
async function fetchBytes(url, onBytes){
  const r = await fetch(url);
  if (!r.ok) throw new Error("could not load " + url);
  if (!onBytes || !r.body || !r.body.getReader) { const b = await r.arrayBuffer(); if (onBytes) onBytes(b.byteLength, b.byteLength); return b; }
  const total = +r.headers.get("content-length") || 0, reader = r.body.getReader(), parts = [];
  let got = 0;
  for (;;) { const {done, value} = await reader.read(); if (done) break; parts.push(value); got += value.byteLength; onBytes(got, total); }
  onBytes(got, got);
  return new Blob(parts).arrayBuffer();
}
/* a picture, with its progress reported where asked; a picture that does not arrive is null */
async function picture(url, onBytes, must){
  try {
    if (!onBytes) return await image(url);
    const buf = await fetchBytes(url, onBytes), blob = new Blob([buf]), href = URL.createObjectURL(blob);
    try { return await image(href); } finally { setTimeout(() => URL.revokeObjectURL(href), 1000); }
  } catch (e) { if (must) throw e; return null; }
}
/* the progress of many fetches as one figure: bytes so far, and the total where it is known (the size the page said, else
   what the servers have said so far) */
function progressOf(onProgress, guess){
  if (!onProgress) return () => null;
  const got = {};
  const report = () => { let b = 0, t = 0; for (const k in got) { b += got[k][0]; t += got[k][1]; } onProgress(b, Math.max(t, guess || 0)); };
  return k => { got[k] = [0, 0]; return (b, t) => { got[k] = [b, t || got[k][1]]; report(); }; };
}
export function prepare(opts = {}){
  if (loading) return loading;
  const prog = progressOf(opts.onProgress, opts.total), need = k => picture(asset(k), prog(k), true), opt = k => picture(asset(k), prog(k), false);
  loading = Promise.all([
    fetchBytes(asset("stars"), prog("stars")),
    need("milkyway"),
    fetchBytes(asset("ridge_json"), prog("ridge_json")).then(b => JSON.parse(new TextDecoder().decode(b))),
    need("ridge"), opt("moon"),
    opt("deck_diff"), opt("deck_nor"), opt("deck_arm"), opt("logs_diff"), opt("logs_nor")
  ]).then(([stars, mw, ridgeMeta, ridge, moon, deckD, deckN, deckA, logD, logN]) => {
    const dv = new DataView(stars), n = dv.getUint16(4, true), S = [];
    for (let i = 0; i < n; i++) { const o = 8 + i * 8, bv = dv.getInt16(o + 6, true);
      S.push({ra: dv.getUint16(o, true) / 65536 * 360, dec: dv.getInt16(o + 2, true) / 32767 * 90, mag: dv.getInt16(o + 4, true) / 100, bv: bv === 32767 ? null : bv / 1000}); }
    /* the Milky Way's light on a coarse grid, for choosing which way to look */
    const gw = 96, gh = 48, c = document.createElement("canvas"); c.width = gw; c.height = gh;
    const g = c.getContext("2d", {willReadFrequently: true}); g.drawImage(mw, 0, 0, gw, gh);
    const px = g.getImageData(0, 0, gw, gh).data, grid = new Float32Array(gw * gh);
    for (let i = 0; i < gw * gh; i++) grid[i] = Math.max(0, MW.L0 * Math.exp(px[i * 4] / 255 * MW.K) - MW.L0);
    return {stars: S, mw, grid, gw, gh, ridgeMeta, ridge, moon, deck: [deckD, deckN, deckA], logs: [logD, logN]};
  });
  loading.catch(() => { loading = null; });
  return loading;
}
/* the deck's extra files, by address (its page names them): pictures; a model's glTF file through the kit's own loader
   (fetched only then); the sofa's cut-down shape (its glTF file as JSON and its buffer); each one that does not arrive is
   drawn plain, or left out. onProgress(bytes, total) reports the fetch. */
let gltfLoader = null;
export function loadMore(urls = {}, onProgress, total){
  const prog = progressOf(onProgress, total);
  const one = (k, u) => {
    if (/\.glb(\?|#|$)/i.test(u) || /\.gltf(\?|#|$)/i.test(u) && k !== "sofa") {
      return (gltfLoader || (gltfLoader = import("../vendor/jsm/loaders/GLTFLoader.js").then(m => new m.GLTFLoader()))).then(L => L.loadAsync(u)).then(g => g.scene);
    }
    if (/\.(gltf|json)(\?|#|$)/i.test(u)) return fetchBytes(u, prog(k)).then(b => JSON.parse(new TextDecoder().decode(b)));
    if (/\.bin(\?|#|$)/i.test(u)) return fetchBytes(u, prog(k));
    return picture(u, prog(k), true);
  };
  return Promise.all(Object.entries(urls).filter(([k, u]) => u && typeof u === "string").map(([k, u]) => one(k, u).then(v => [k, v], () => [k, null]))).then(Object.fromEntries);
}
const MW = {L0: 0.006, K: Math.log(0.5 / 0.006)};      // how the Milky Way's light is stored: a log scale from L0 to 0.5
let can = null;
export function supported(){      /* asked once; the context asked with is let go at once */
  if (can === null) { try { const c = document.createElement("canvas"), g = window.WebGL2RenderingContext && c.getContext("webgl2"); can = !!g;
    if (g) { const x = g.getExtension("WEBGL_lose_context"); if (x) x.loseContext(); } } catch (e) { can = false; } }
  return can;
}

/* ================================ the plan for tonight ================================ */
/* the camera's height of view, in degrees: a lens near 50 mm on a wide screen, opening up on a tall one */
const vfovOf = a => a >= 1 ? 52 : Math.min(76, 2 * Math.atan(Math.tan(26 * D2R) / Math.pow(a, 0.62)) * R2D);
function bvToRgb(bv){
  if (bv == null) return [1, 1, 1];
  const b = clamp(bv, -0.4, 2.0), T = 4600 * (1 / (0.92 * b + 1.7) + 1 / (0.92 * b + 0.62));
  const x = T <= 4000 ? -0.2661239e9 / T ** 3 - 0.2343589e6 / T ** 2 + 0.8776956e3 / T + 0.179910 : -3.0258469e9 / T ** 3 + 2.1070379e6 / T ** 2 + 0.2226347e3 / T + 0.240390;
  const y = T <= 2222 ? -1.1063814 * x ** 3 - 1.3481102 * x ** 2 + 2.18555832 * x - 0.20219683 : T <= 4000 ? -0.9549476 * x ** 3 - 1.37418593 * x ** 2 + 2.09137015 * x - 0.16748867
    : 3.081758 * x ** 3 - 5.8733867 * x ** 2 + 3.75112997 * x - 0.37001483;
  const X = x / y, Z = (1 - x - y) / y;
  let r = 3.2406 * X - 1.5372 - 0.4986 * Z, g = -0.9689 * X + 1.8758 + 0.0415 * Z, bl = 0.0557 * X - 0.204 + 1.057 * Z;
  r = Math.max(0, r); g = Math.max(0, g); bl = Math.max(0, bl); const m = Math.max(r, g, bl) || 1;
  return [r / m, g / m, bl / m];
}
function plan(A, opts = {}){
  const where = opts.place || place();
  const night = opts.date ? {date: new Date(opts.date), tonight: !!opts.tonight} : nightOf(new Date(), where.lat, where.lon);
  const date = night.date, f0 = frameOf(date, where.lat, where.lon, 0), jd = f0.jd;
  const sun = sunOf(jd), moonG = moonOf(jd), planets = planetsOf(jd);
  /* the Moon as seen from here (its parallax is near a degree) */
  const dist = 1 / Math.sin(moonG.par), moonT = moonG.v.clone().multiplyScalar(dist).sub(f0.Z).normalize();
  const sunW = sun.v.clone().applyMatrix3(f0.toWorld), moonW = moonT.clone().applyMatrix3(f0.toWorld);
  const elong = Math.acos(clamp(sun.v.dot(moonG.v), -1, 1)), frac = (1 - Math.cos(elong)) / 2;      // the lit fraction: 0 at new moon, 1 at full
  const waxing = ((moonG.lam - sun.lam) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) < Math.PI;
  const sh = showerOf(date), radW = radec(sh.ra, sh.dec).applyMatrix3(f0.j2w);
  /* the final look up: its pitch and half the frame. Held upright, a phone's tall frame reaches low; it looks up far
     enough that the frame's foot stays above the railing (whose top is a few degrees down), so only sky and mountains show */
  const aspect = opts.aspect || 1.6, portrait = aspect < 0.9, P = portrait ? Math.max(30, vfovOf(aspect) / 2 - 3.6) : 31, hh = portrait ? 22 : 36, vh = portrait ? 34 : 24;
  const mAlt = altOf(moonW), mAz = azOf(moonW, 0), rAlt = altOf(radW), rAz = azOf(radW, 0);
  const bright = A.stars.filter(s => s.mag < 3).concat(planets.filter(p => p.mag < 3)).map(s => { const w = radec(s.ra, s.dec).applyMatrix3(f0.j2w); return {alt: altOf(w), az: azOf(w, 0), f: Math.pow(10, -0.4 * s.mag)}; });
  const mwAt = (alt, az) => {      // the Milky Way's light in a direction (alt, az)
    const w = V3(Math.sin(az * D2R) * Math.cos(alt * D2R), Math.sin(alt * D2R), -Math.cos(az * D2R) * Math.cos(alt * D2R)).applyMatrix3(f0.w2j);
    const ra = Math.atan2(w.y, w.x), dec = Math.asin(clamp(w.z, -1, 1));
    const u = ((0.5 - ra / (2 * Math.PI)) % 1 + 1) % 1, v = 0.5 - dec / Math.PI;
    return A.grid[Math.min(A.gh - 1, Math.floor(v * A.gh)) * A.gw + Math.min(A.gw - 1, Math.floor(u * A.gw))];
  };
  const dAz = (a, b) => ((a - b + 540) % 360) - 180;
  let best = null;
  const scores = [];
  for (let a0 = 0; a0 < 360; a0 += 10) {
    let mw = 0, st = 0;
    for (let i = 0; i < 12; i++) for (let j = 0; j < 8; j++) {
      const alt = P - vh * 0.8 + (j + 0.5) / 8 * vh * 1.6, az = a0 + (-hh * 0.85 + (i + 0.5) / 12 * hh * 1.7) / Math.max(0.3, Math.cos(alt * D2R));
      mw += mwAt(alt, az) * (1.2 - Math.abs(i - 5.5) / 12);
    }
    for (const s of bright) if (Math.abs(dAz(s.az, a0)) * Math.cos(s.alt * D2R) < hh && Math.abs(s.alt - P) < vh) st += s.f;
    const moonIn = mAlt > 4 && Math.abs(dAz(mAz, a0)) * Math.cos(mAlt * D2R) < hh * 0.72 && mAlt > P - vh * 0.6 && mAlt < P + vh * 0.8;
    const c = V3(Math.sin(a0 * D2R) * Math.cos(P * D2R), Math.sin(P * D2R), -Math.cos(a0 * D2R) * Math.cos(P * D2R)), rw = radec(sh.ra, sh.dec).applyMatrix3(f0.j2w);
    const th = Math.acos(clamp(c.dot(rw), -1, 1)) * R2D, rad = th < 25 ? th / 25 * 0.6 : th <= 80 ? 1 : Math.max(0, 1 - (th - 80) / 70);
    scores.push({a0, mw, st, moonIn, rad});
  }
  const mwMax = Math.max(...scores.map(s => s.mw)) || 1, stMax = Math.max(...scores.map(s => s.st)) || 1;
  for (const s of scores) { s.score = s.mw / mwMax + 0.45 * s.st / stMax + (s.moonIn ? 0.7 : 0) + 0.35 * s.rad; if (!best || s.score > best.score) best = s; }
  const a0 = opts.az != null ? opts.az : best.a0;
  const f = frameOf(date, where.lat, where.lon, a0);
  const moonReal = mAlt > 4 && frac >= 0.03 && frac <= 0.5 && (opts.az == null ? best.moonIn : false);
  return {where, date, tonight: night.tonight, a0, f, P, portrait, sun: sun.v.clone().applyMatrix3(f.toWorld), moonW: moonT.clone().applyMatrix3(f.toWorld),
          moonAlt: mAlt, frac, waxing, moonReal, shower: sh, radiant: radec(sh.ra, sh.dec).applyMatrix3(f.j2w), radAlt: rAlt, radAz: rAz, planets};
}

/* ================================ drawing helpers ================================ */
function canvasTex(w, h, draw, srgb = true){
  const c = document.createElement("canvas"); c.width = w; c.height = h; draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c); if (srgb) t.colorSpace = THREE.SRGBColorSpace; return t;
}
function texOf(img, srgb, repeat){
  if (!img) return null;
  const t = new THREE.Texture(img); t.needsUpdate = true; if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; } t.anisotropy = 8; return t;
}
const TEXW = 1.05;      // the pine texture's real width in metres (as in the cabin)
const logR = rng(31);
function logGeo(len, r, seg = 14){
  const g = new THREE.CylinderGeometry(r, r, len, seg, 1, false), uv = g.attributes.uv, around = 2 * Math.PI * r / TEXW, k = len / TEXW, ou = logR(), ov = logR();
  for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getY(i) * k + ov, uv.getX(i) * around + ou);
  return g;
}
function logAt(len, r, mat, x, y, z, along, parent, seg){
  const m = new THREE.Mesh(logGeo(len, r, seg), mat); m.position.set(x, y, z);
  if (along === "x") m.rotation.z = Math.PI / 2; else if (along === "z") m.rotation.x = Math.PI / 2;
  m.castShadow = m.receiveShadow = true; parent.add(m); return m;
}
/* many meshes as one: one draw instead of a hundred (the pieces' own materials are dropped for the one given) */
function merged(meshes, mat){
  const pos = [], nor = [], uv = [], idx = [];
  for (const m of meshes) {
    m.updateMatrix(); const g = m.geometry.clone().applyMatrix4(m.matrix), base = pos.length / 3;
    pos.push(...g.attributes.position.array); nor.push(...g.attributes.normal.array); uv.push(...g.attributes.uv.array);
    if (g.index) for (const i of g.index.array) idx.push(base + i); else for (let i = 0; i < g.attributes.position.count; i++) idx.push(base + i);
    g.dispose(); m.geometry.dispose(); if (m.parent) m.parent.remove(m);
  }
  const mg = new THREE.BufferGeometry(); mg.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); mg.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3));
  mg.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2)); mg.setIndex(idx);
  return new THREE.Mesh(mg, mat);
}
/* quads gathered into one geometry, each with its own normal, texture coordinates and tint (for the planks and the boards) */
class Quads {
  constructor(){ this.p = []; this.n = []; this.u = []; this.c = []; this.i = []; }
  quad(a, b, c, d, n, uv, tint = [1, 1, 1]){      // a b c d counter-clockwise seen from the side n points to; uv: [ua, va, ub, vb, uc, vc, ud, vd]
    const base = this.p.length / 3;
    for (const v of [a, b, c, d]) this.p.push(v[0], v[1], v[2]);
    for (let k = 0; k < 4; k++) { this.n.push(n[0], n[1], n[2]); this.c.push(tint[0], tint[1], tint[2]); }
    this.u.push(...uv);
    this.i.push(base, base + 1, base + 2, base, base + 2, base + 3);
  }
  /* a box from its corner (x0, y0, z0) to (x1, y1, z1); uvs: the top takes [u0, v0, u1, v1] (u along x, v along z) and the
     sides a plain strip */
  box(x0, y0, z0, x1, y1, z1, top, tint, sideTint){
    const st = sideTint || tint, su = (x1 - x0) / TEXW, sv = (y1 - y0) / TEXW, sw = (z1 - z0) / TEXW;
    this.quad([x0, y1, z1], [x1, y1, z1], [x1, y1, z0], [x0, y1, z0], [0, 1, 0], top ? [top[0], top[3], top[2], top[3], top[2], top[1], top[0], top[1]] : [0, 0, su, 0, su, sw, 0, sw], tint);
    this.quad([x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1], [0, -1, 0], [0, 0, su, 0, su, sw, 0, sw], st);
    this.quad([x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1], [0, 0, 1], [0, 0, su, 0, su, sv, 0, sv], st);
    this.quad([x1, y0, z0], [x0, y0, z0], [x0, y1, z0], [x1, y1, z0], [0, 0, -1], [0, 0, su, 0, su, sv, 0, sv], st);
    this.quad([x1, y0, z1], [x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [1, 0, 0], [0, 0, sw, 0, sw, sv, 0, sv], st);
    this.quad([x0, y0, z0], [x0, y0, z1], [x0, y1, z1], [x0, y1, z0], [-1, 0, 0], [0, 0, sw, 0, sw, sv, 0, sv], st);
  }
  geometry(){
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(this.p, 3)); g.setAttribute("normal", new THREE.Float32BufferAttribute(this.n, 3));
    g.setAttribute("uv", new THREE.Float32BufferAttribute(this.u, 2)); g.setAttribute("color", new THREE.Float32BufferAttribute(this.c, 3));
    g.setIndex(this.i); return g;
  }
}
/* a model's shape from its glTF file and its binary buffer (positions, normals, indices; its own materials are not used):
   the cabin's sofa, for the room behind the window */
function gltfShape(json, bin){
  const T = {5126: Float32Array, 5125: Uint32Array, 5123: Uint16Array, 5121: Uint8Array}, N = {SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4};
  const acc = i => { const a = json.accessors[i], v = json.bufferViews[a.bufferView], C = T[a.componentType];
    if (!C || (v.byteStride && v.byteStride !== N[a.type] * C.BYTES_PER_ELEMENT)) throw new Error("an unexpected model layout");
    return new C(bin, (v.byteOffset || 0) + (a.byteOffset || 0), a.count * N[a.type]).slice(); };
  return json.nodes.filter(n => n.mesh != null).map(n => {
    const p = json.meshes[n.mesh].primitives[0], g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(acc(p.attributes.POSITION), 3));
    g.setAttribute("normal", new THREE.BufferAttribute(acc(p.attributes.NORMAL), 3));
    if (p.indices != null) g.setIndex(new THREE.BufferAttribute(acc(p.indices), 1));
    if (n.translation) g.translate(...n.translation);
    return g;
  });
}
/* a wool throw tossed over the front of the sofa's seat, on the lamp's side: it lies on the cushion, rolls over the front
   edge and hangs in folds to an uneven hem (in the sofa model's own units: the cushion's top at 0.41, its front at 0.34) */
function throwGeo(){
  const nu = 26, nv = 46, x0 = -0.78, x1 = -0.1, top = 0.41, edge = 0.29, rB = 0.066, zA = -0.07, pos = [], uvs = [], idx = [];
  for (let j = 0; j <= nv; j++) for (let i = 0; i <= nu; i++) {
    const u = i / nu, hem = 0.12 + 0.07 * (0.5 + 0.5 * Math.sin(u * 2.7 + 0.5)) + 0.04 * u;
    const lenA = edge - zA, lenB = Math.PI / 2 * rB, lenC = top - 0.05 - hem, L = lenA + lenB + lenC, s = j / nv * L;
    let y, z, ny, nz, d;
    if (s <= lenA) { y = top + 0.016; z = zA + s; ny = 1; nz = 0;      // on the cushion: soft lumps, bunched up at the back
      d = 0.005 * Math.sin(u * 11 + s * 17) * Math.sin(s * 6 + 1) + 0.03 * Math.exp(-s / 0.045) * (0.6 + 0.4 * Math.sin(u * 7));
    } else if (s <= lenA + lenB) { const a = (s - lenA) / rB; y = top - 0.05 + rB * Math.cos(a); z = edge + rB * Math.sin(a); ny = Math.cos(a); nz = Math.sin(a); d = 0;
    } else { const c = s - lenA - lenB, k = smooth(clamp(c / 0.17));      // hanging: folds that deepen and widen toward the hem
      y = top - 0.05 - c; z = edge + rB + 0.008 * k; ny = 0; nz = 1;
      d = (0.026 + 0.012 * u) * k * (0.65 * Math.sin(2 * Math.PI * u * 3.2 + 0.4 + c * 2.2) + 0.35 * Math.sin(2 * Math.PI * u * 7.1 + 1.7 - c * 3));
    }
    const xm = (x0 + x1) / 2, x = s > lenA + lenB ? xm + (mix(x0, x1, u) - xm) * (1 - 0.05 * smooth(clamp((s - lenA - lenB) / 0.2))) : mix(x0, x1, u);
    pos.push(x, y + ny * d, z + nz * d); uvs.push(u, s / L);
  }
  for (let j = 0; j < nv; j++) for (let i = 0; i < nu; i++) { const a = j * (nu + 1) + i, b = a + nu + 1; idx.push(a, b, a + 1, a + 1, b, b + 1); }
  const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  g.setIndex(idx); g.computeVertexNormals(); return g;
}
/* a cushion: two faces over one square, plump in the middle and meeting at the seam, its corners drawn in a little */
function pillowGeo(){
  const n = 18, pos = [], idx = [];
  for (const s of [1, -1]) {
    const base = pos.length / 3;
    for (let j = 0; j <= n; j++) for (let i = 0; i <= n; i++) {
      const u = i / n * 2 - 1, v = j / n * 2 - 1, f = Math.sqrt(Math.max(0, (1 - u ** 4) * (1 - v ** 4))), pinch = 1 - 0.08 * u * u * v * v;
      pos.push(u * 0.19 * pinch * (1 - 0.04 * v * v), v * 0.17 * pinch * (1 - 0.04 * u * u), s * 0.072 * f);
    }
    for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) { const a = base + j * (n + 1) + i, b = a + n + 1;
      if (s > 0) idx.push(a, a + 1, b, a + 1, b + 1, b); else idx.push(a, b, a + 1, a + 1, b, b + 1); }
  }
  const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals(); return g;
}
/* a folded wool blanket: a soft block with rounded edges and a seam of folds along its top (a flattened, lumpy box) */
function blanketGeo(w, h, d, seed){
  const g = new THREE.BoxGeometry(w, h, d, 12, 3, 8), P = g.attributes.position, r = rng(seed);
  const bumps = Array.from({length: 5}, () => [r() * 7 + 3, r() * 6.3, r() * 0.012 + 0.006]);
  for (let i = 0; i < P.count; i++) {
    const x = P.getX(i), y = P.getY(i), z = P.getZ(i), ex = Math.abs(x) / (w / 2), ez = Math.abs(z) / (d / 2), ey = (y + h / 2) / h;
    const round = 1 - 0.18 * Math.pow(Math.max(ex, ez), 6);      // the edges rounded
    let dy = 0; for (const [f, ph, a] of bumps) dy += a * Math.sin(x * f + ph) * Math.cos(z * f * 0.7 + ph);
    P.setXYZ(i, x * (1 - 0.06 * ey * ey * ex), (y + dy * ey) * round + (round - 1) * h * 0.5, z * (1 - 0.05 * ey * ey * ez));
  }
  g.computeVertexNormals(); return g;
}
/* a conifer against the sky, drawn as a silhouette: Engelmann spruce (a dense, drooping spire), lodgepole pine (a tall
   bare trunk under a narrow, ragged crown) or ponderosa pine (big irregular clumps) */
function conifer(seed, kind){
  return canvasTex(320, 1024, (g, w, h) => {
    const r = rng(seed), cx = w / 2, top = h * 0.02;
    g.fillStyle = "#fff"; g.strokeStyle = "#fff"; g.lineCap = g.lineJoin = "round";
    const trunkW = kind === "pond" ? 9 : 6;
    g.beginPath(); g.moveTo(cx - trunkW, h); g.lineTo(cx - 1, top); g.lineTo(cx + 1, top); g.lineTo(cx + trunkW, h); g.closePath(); g.fill();
    const clump = (x, y, rad, n) => {      // needles: a ragged mass of small strokes and blobs
      for (let i = 0; i < n; i++) {
        const a = r() * Math.PI * 2, d = Math.sqrt(r()) * rad, x1 = x + Math.cos(a) * d, y1 = y + Math.sin(a) * d * 0.7;
        g.beginPath(); g.ellipse(x1, y1, 1.2 + r() * rad * 0.45, 0.8 + r() * rad * 0.22, (r() - 0.5) * 1.2, 0, 7); g.fill();
      }
      for (let i = 0; i < n / 2; i++) {
        const a = (r() - 0.5) * 2.4 + (r() < 0.5 ? 0 : Math.PI), l = rad * (0.6 + r() * 0.8);
        g.lineWidth = 0.8 + r() * 0.8; g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l * 0.6 + l * 0.25); g.stroke();
      }
    };
    const crownFrom = kind === "lodge" ? 0.55 : kind === "pond" ? 0.62 : 0.93;      // how far down the crown reaches
    const reachAt = f => kind === "spruce" ? (6 + 118 * Math.pow(f, 0.9)) : kind === "lodge" ? (5 + 40 * Math.sqrt(f)) : (8 + 70 * Math.pow(f, 0.7));
    { /* the crown's dense heart, where the branches overlap and old twigs fill in: solid, with a ragged edge */
      const core = kind === "spruce" ? 0.42 : 0.3, steps = 60;
      g.beginPath(); g.moveTo(cx, top);
      for (let i = 0; i <= steps; i++) { const yy = top + (h * crownFrom - top) * i / steps, f = (yy - top) / (h - top); g.lineTo(cx + reachAt(f) * core * (0.75 + 0.5 * r()), yy); }
      for (let i = steps; i >= 0; i--) { const yy = top + (h * crownFrom - top) * i / steps, f = (yy - top) / (h - top); g.lineTo(cx - reachAt(f) * core * (0.75 + 0.5 * r()), yy); }
      g.closePath(); g.fill();
    }
    let y = top + 2;
    while (y < h * crownFrom) {
      const f = (y - top) / (h - top);      // 0 at the tip
      const reach = reachAt(f);
      const n = kind === "pond" ? 1 + (r() * 2 | 0) : 2 + (r() * 2 | 0);
      for (let b = 0; b < n; b++) {
        const side = b % 2 ? 1 : -1, l = reach * (0.45 + r() * 0.7), lift = kind === "spruce" ? (0.22 + 0.5 * f + 0.15 * r()) * l : (f < 0.2 ? -0.25 : 0.12 + 0.2 * r()) * l;
        const ex = cx + side * l, ey = y + lift;
        g.lineWidth = 1 + 2.4 * f; g.beginPath(); g.moveTo(cx, y); g.quadraticCurveTo(cx + side * l * 0.5, y + lift * 0.1, ex, ey); g.stroke();
        if (kind === "lodge" && f > 0.38 && r() < 0.35) continue;      // a dead branch, bare
        const k = kind === "pond" ? 3 : kind === "spruce" ? 3 + (r() * 3 | 0) : 2 + (r() * 3 | 0);
        for (let i = 0; i < k; i++) { const t = 0.35 + 0.65 * (i + r()) / k; clump(cx + side * l * t, y + lift * t * t, (kind === "pond" ? 7 : 4) + 6 * r() * (0.4 + f), kind === "pond" ? 22 : 12); }
      }
      y += (kind === "spruce" ? 3 : kind === "lodge" ? 8 : 12) + r() * (kind === "spruce" ? 4 : 14);
    }
    for (let i = 0; i < 4; i++) clump(cx + (r() - 0.5) * 3, top + 6 + i * 7, 3 + i, 8);      // the leader at the very top
    const img = g.getImageData(0, 0, w, h), px = img.data;      // a silhouette is solid: only its outermost edge stays soft
    for (let i = 3; i < px.length; i += 4) px[i] = Math.max(0, Math.min(255, (px[i] - 70) * 2.6));
    g.putImageData(img, 0, 0);
  });
}
function glowTex(){ return canvasTex(128, 128, (g, w) => { const r = g.createRadialGradient(w / 2, w / 2, 0, w / 2, w / 2, w / 2);
  r.addColorStop(0, "rgba(255,255,255,1)"); r.addColorStop(0.18, "rgba(255,255,255,.45)"); r.addColorStop(0.5, "rgba(255,255,255,.1)"); r.addColorStop(1, "rgba(255,255,255,0)"); g.fillStyle = r; g.fillRect(0, 0, w, w); }, false); }
/* a puff of smoke or mist: a soft blot with a broken, cloudy edge */
function puffTex(seed){ return canvasTex(128, 128, (g, w) => { const r = rng(seed);
  g.fillStyle = "#000"; g.fillRect(0, 0, w, w); g.globalCompositeOperation = "lighter";
  for (let i = 0; i < 34; i++) { const a = r() * 6.283, d = Math.pow(r(), 0.7) * w * 0.26, x = w / 2 + Math.cos(a) * d, y = w / 2 + Math.sin(a) * d * 0.85, rad = w * (0.09 + 0.17 * r());
    const gr = g.createRadialGradient(x, y, 0, x, y, rad); gr.addColorStop(0, "rgba(255,255,255,0.16)"); gr.addColorStop(1, "rgba(255,255,255,0)"); g.fillStyle = gr; g.fillRect(0, 0, w, w); }
  const img = g.getImageData(0, 0, w, w), px = img.data;      // the brightness is the alpha; the colour white
  for (let i = 0; i < px.length; i += 4) { const cx = (i / 4) % w - w / 2, cy = Math.floor(i / 4 / w) - w / 2, edge = clamp(1.1 - Math.hypot(cx, cy) / (w / 2) * 1.1);
    px[i + 3] = Math.min(255, px[i] * 1.6 * edge); px[i] = px[i + 1] = px[i + 2] = 255; }
  g.globalCompositeOperation = "source-over"; g.putImageData(img, 0, 0); }, false); }
/* a flame: a warm teardrop, white at the heart */
function flameTex(){ return canvasTex(64, 96, (g, w, h) => {
  g.clearRect(0, 0, w, h); const gr = g.createRadialGradient(w / 2, h * 0.62, 0, w / 2, h * 0.6, w * 0.5);
  gr.addColorStop(0, "rgba(255,246,220,1)"); gr.addColorStop(0.35, "rgba(255,190,90,0.9)"); gr.addColorStop(0.7, "rgba(255,110,30,0.45)"); gr.addColorStop(1, "rgba(255,60,10,0)");
  g.fillStyle = gr; g.beginPath(); g.moveTo(w / 2, h * 0.05); g.bezierCurveTo(w * 0.95, h * 0.5, w * 0.9, h * 0.98, w / 2, h * 0.98); g.bezierCurveTo(w * 0.1, h * 0.98, w * 0.05, h * 0.5, w / 2, h * 0.05); g.fill(); }, false); }

/* ================================ the shaders ================================ */
const SKYFRAG_HEAD = `
float airmass(float s, float altDeg){ return 1.0 / (max(s, 0.0) + 0.50572 * pow(max(altDeg, -1.0) + 6.07995, -1.6364)); }
float hash(float n){ return fract(sin(n) * 43758.5453123); }
float vnoise(float x){ float i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f); return mix(hash(i), hash(i + 1.0), f); }
`;
/* A point of light (a star, a meteor's head) drawn as the share of a small Gaussian that falls on each pixel, so its light
   on the screen is the same wherever it sits within a pixel and moves smoothly from one pixel to the next */
const POINTFRAG_HEAD = `
float erf1(float x){ float x2 = x * x; return sign(x) * sqrt(max(0.0, 1.0 - exp(-x2 * (1.2732395 + 0.147 * x2) / (1.0 + 0.147 * x2)))); }
float cell(float d, float s){ float k = 0.70710678 / s; return 0.5 * (erf1((d + 0.5) * k) - erf1((d - 0.5) * k)); }
float share(vec2 q, float s){ return cell(q.x, s) * cell(q.y, s); }
`;
/* The great room behind the glass (the deck to sit on only): lit by the two lamps at the sofa's ends, the lantern chandelier
   over the rug and the fire in the stone fireplace on the right-hand wall, whose light flickers. Its surfaces take no other
   light, so none of it leaks through the walls. Round logs darken where they meet; the room darkens into its corners; the
   sofa shades what lies behind it from each light (a ray against its box, softened at the edges); leather has a sheen;
   linen lets the light through. */
const ROOM_VERT = `varying vec3 vW, vN; varying vec2 vUv;
  void main(){ vW = (modelMatrix * vec4(position, 1.0)).xyz; vN = normalize(mat3(modelMatrix) * normal); vUv = uv; gl_Position = projectionMatrix * viewMatrix * vec4(vW, 1.0); }`;
const ROOM_FRAG = `uniform sampler2D uMap; uniform float uHas, uFlick, uFireI, uTri, uLog, uThin, uSpec, uOcc; uniform float uLampI[3];
  uniform vec3 uTint, uFireP, uOccMin, uOccMax, uRoomMin, uRoomMax, uCav; uniform vec3 uLampP[3]; uniform vec2 uRep;
  varying vec3 vW, vN; varying vec2 vUv;
  float hitBox(vec3 p, vec3 d, vec3 lo, vec3 hi){      // does the way p + d * (0..1) pass through the box?
    vec3 t0 = (lo - p) / d, t1 = (hi - p) / d, tn = min(t0, t1), tf = max(t0, t1);
    float a = max(max(tn.x, tn.y), tn.z), b = min(min(tf.x, tf.y), tf.z);
    return b > max(a, 0.0) && a < 1.0 ? 1.0 : 0.0;
  }
  float seen(vec3 p, vec3 l){      // how much of a light reaches p past the sofa
    if (uOcc < 0.5) return 1.0;
    vec3 d = l - p + vec3(1e-4), c = (uOccMin + uOccMax) * 0.5, h = (uOccMax - uOccMin) * 0.5;
    return 1.0 - 0.24 * (hitBox(p, d, c - h * 0.8, c + h * 0.8) + hitBox(p, d, c - h, c + h) + hitBox(p, d, c - h * 1.22, c + h * 1.22));
  }
  void main(){
    vec3 n = normalize(vN);
    if (!gl_FrontFacing) n = -n;
    vec3 an = abs(n), alb = vec3(0.45);
    if (uHas > 0.5) alb = uTri > 0.0 ? texture2D(uMap, (an.x > an.y && an.x > an.z ? vW.zy : an.y > an.z ? vW.xz : vW.xy) * uTri).rgb : texture2D(uMap, vUv * uRep).rgb;
    alb *= uTint;
    if (uLog > 0.5) alb *= mix(1.0, 0.22, smoothstep(0.5, 0.93, an.y));      // round logs, dark where one sits on the next
    if (uCav.x + uCav.y + uCav.z > 0.0) {      // the room darkens into its corners
      vec3 e3 = min(vW - uRoomMin, uRoomMax - vW) + (1.0 - uCav) * 9.0;
      alb *= mix(0.5, 1.0, smoothstep(0.0, 0.6, min(min(e3.x, e3.y), e3.z)));
    }
    vec3 p = vW + n * 0.02, v = normalize(cameraPosition - vW);
    vec3 lampC = vec3(1.0, 0.84, 0.64), fireC = vec3(1.0, 0.62, 0.32), warm = vec3(1.0, 0.86, 0.66);
    vec3 c = alb * vec3(0.02, 0.017, 0.014), spec = vec3(0.0);
    for (int i = 0; i < 3; i++) {      // the lamps and the chandelier
      vec3 dl = uLampP[i] - vW; float ll = length(dl); vec3 L1 = dl / ll; float a1 = dot(n, L1), w1;
      if (uThin > 0.5) w1 = 0.2 + 0.8 * (a1 > 0.0 ? a1 : -0.7 * a1); else w1 = 0.3 + 0.7 * max(a1, 0.0);      // thin cloth: the light comes through
      float lamp = w1 * uLampI[i] / (0.3 + ll * ll) * seen(p, uLampP[i]);
      vec3 lc = lampC * (uThin > 0.5 && a1 < 0.0 ? warm : vec3(1.0));
      c += alb * lc * lamp; spec += lc * lamp * pow(max(dot(n, normalize(L1 + v)), 0.0), 28.0);
    }
    vec3 df = uFireP - vW; float lf = length(df); vec3 L2 = df / lf; float a2 = dot(n, L2), w2;
    if (uThin > 0.5) w2 = 0.2 + 0.8 * (a2 > 0.0 ? a2 : -0.7 * a2); else w2 = 0.25 + 0.75 * max(a2, 0.0);
    float fire = w2 * uFireI * uFlick / (0.45 + lf * lf) * seen(p, uFireP);
    vec3 fc = fireC * (uThin > 0.5 && a2 < 0.0 ? warm : vec3(1.0));
    c += alb * fc * fire; spec += fc * fire * pow(max(dot(n, normalize(L2 + v)), 0.0), 28.0);
    if (uSpec > 0.0) c += uSpec * spec;      // a soft sheen on leather and brass, toward each light
    gl_FragColor = vec4(c, 1.0);
    #include <colorspace_fragment>
  }`;
/* the window's glass: the room through it, a little dimmed; what stands in front of it, faintly, as glass at night shows it
   (a reflection drawn from the eye's mirror image behind the glass, drawn again when the eye has moved), more of it at a
   slant; old glass wavers the reflection a little, pane by pane; dust and old rain marks catch the lamplight */
const GLASS_FRAG = `uniform sampler2D uRef; uniform float uHasRef, uLampI, uFlick, uRefK; uniform mat4 uRefVP; uniform vec3 uLampP; uniform vec2 uUv0, uUvSize, uPanes;
  varying vec3 vW; varying vec2 vUv;
  float h21(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float vn(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(h21(i), h21(i + vec2(1.0, 0.0)), f.x), mix(h21(i + vec2(0.0, 1.0)), h21(i + vec2(1.0, 1.0)), f.x), f.y); }
  void main(){
    vec3 V = normalize(vW - cameraPosition);
    float F = 0.045 + 0.955 * pow(1.0 - abs(V.z), 5.0);
    vec2 nuv = (vUv - uUv0) / uUvSize;      // 0 to 1 over the whole sheet
    vec2 pane = floor(nuv * uPanes);
    vec2 wob = vec2(0.004 * sin(nuv.y * 21.0 + pane.x * 2.3) + 0.002 * sin(nuv.y * 57.0 + pane.y * 4.1), 0.003 * sin(nuv.x * 17.0 + pane.y * 1.9 + pane.x));
    vec4 q = uRefVP * vec4(vW, 1.0);
    vec3 refl = vec3(0.003, 0.0035, 0.005);
    if (uHasRef > 0.5) { vec3 c = texture2D(uRef, clamp(q.xy / q.w * 0.5 + 0.5 + wob, 0.002, 0.998)).rgb; refl = c; }
    float dust = 0.55 * vn(nuv * vec2(48.0, 34.0) * uPanes / 3.0) + 0.45 * vn(nuv * vec2(8.0, 6.0));
    float rain = smoothstep(0.6, 1.0, vn(vec2(nuv.x * 64.0 + pane.x * 7.0, nuv.y * 3.0 * uPanes.y / 2.0))) * smoothstep(0.75, 0.05, fract(nuv.y * uPanes.y));
    float k = max(dot(V, normalize(uLampP - vW)), 0.0);
    vec3 haze = vec3(1.0, 0.78, 0.52) * uLampI * uFlick * (0.0012 + 0.016 * pow(k, 14.0) + 0.09 * pow(k, 110.0)) * (0.3 + 0.7 * dust + 0.45 * rain);
    refl /= 1.0 + 4.0 * refl;      // the moon's reflection kept a reflection, not a second moon
    gl_FragColor = vec4(refl * F * uRefK + haze, 0.07 + 0.85 * F);
    #include <colorspace_fragment>
  }`;
/* soft points (smoke, mist, the moths at the lantern): each its own size in metres, its own fading, its own tint */
const SOFT_VERT = `attribute float aSize, aAlpha; attribute vec3 aCol; uniform float uScale, uPx; varying float vA; varying vec3 vCol;
  void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); float d = max(0.05, -mv.z); vA = aAlpha; vCol = aCol;
    gl_PointSize = clamp(aSize * uScale / d, 1.0, 1024.0) * uPx; gl_Position = projectionMatrix * mv; if (aAlpha <= 0.001) gl_Position = vec4(2.0, 2.0, 2.0, 1.0); }`;
const SOFT_FRAG = `uniform sampler2D uMap; uniform vec3 uColor; varying float vA; varying vec3 vCol;
  void main(){ float a = texture2D(uMap, gl_PointCoord).a * vA; gl_FragColor = vec4(uColor * vCol, a);
    #include <colorspace_fragment>
  }`;

/* ================================ the lens ================================ */
/* The screen gets the scene through a lens (as the reading room and the polling place do): the scene is drawn into a
   high-range picture with its depth; the brightest things (the moon, the window, a fireball, the lantern) bloom softly;
   depth of field blurs what the eye is not on (the railing when it looks at the stars); the brightest values roll off on a
   quiet shoulder (the dark sky, the stars and the Milky Way, which were tuned in linear light, pass through unchanged);
   the picture darkens toward its corners, with a touch of colour fringing there; and the whole takes a very fine grain,
   added after the picture is encoded for the screen so that the dark sky is not swamped. A lean device gets no depth of
   field and a smaller bloom. The night's fades are drawn here too (veil). */
const FS_VERT = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;
class Lens {
  constructor(renderer, lean, opts = {}){
    this.r = renderer; this.lean = lean; this.dof = !lean && opts.dof !== false;
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3));
    g.setAttribute("uv", new THREE.Float32BufferAttribute([0, 0, 2, 0, 0, 2], 2));
    this.quad = new THREE.Mesh(g, null); this.quad.frustumCulled = false;
    this.qs = new THREE.Scene(); this.qs.add(this.quad); this.qc = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const caps = renderer.capabilities, ext = renderer.extensions;
    this.hdr = !!(ext.has("EXT_color_buffer_float") || ext.has("EXT_color_buffer_half_float"));
    this.type = this.hdr ? THREE.HalfFloatType : THREE.UnsignedByteType;
    this.samples = Math.min(lean ? 2 : 4, caps.maxSamples || 0);
    const mat = (frag, uniforms) => new THREE.ShaderMaterial({uniforms, vertexShader: FS_VERT, fragmentShader: frag, depthTest: false, depthWrite: false});
    const T = "uniform sampler2D tex; uniform vec2 texel; varying vec2 vUv;";
    this.mBright = mat(`${T} uniform float thr, knee;
      void main(){ vec3 c = 0.25 * (texture2D(tex, vUv + texel * vec2(-0.5, -0.5)).rgb + texture2D(tex, vUv + texel * vec2(0.5, -0.5)).rgb + texture2D(tex, vUv + texel * vec2(-0.5, 0.5)).rgb + texture2D(tex, vUv + texel * vec2(0.5, 0.5)).rgb);
        float l = dot(c, vec3(0.2126, 0.7152, 0.0722)); float s = clamp(l - thr + knee, 0.0, 2.0 * knee); s = s * s / (4.0 * knee + 1e-4);
        float w = max(l - thr, s) / max(l, 1e-4); gl_FragColor = vec4(c * w, 1.0); }`,
      {tex: {value: null}, texel: {value: new THREE.Vector2()}, thr: {value: 0.5}, knee: {value: 0.22}});
    this.mDown = mat(`${T} void main(){ vec2 h = texel * 0.5;
        vec3 c = texture2D(tex, vUv).rgb * 4.0 + texture2D(tex, vUv - h).rgb + texture2D(tex, vUv + h).rgb + texture2D(tex, vUv + vec2(h.x, -h.y)).rgb + texture2D(tex, vUv - vec2(h.x, -h.y)).rgb;
        gl_FragColor = vec4(c / 8.0, 1.0); }`, {tex: {value: null}, texel: {value: new THREE.Vector2()}});
    this.mUp = mat(`${T} uniform sampler2D add; void main(){ vec2 h = texel;
        vec3 c = texture2D(tex, vUv + vec2(-h.x * 2.0, 0.0)).rgb + texture2D(tex, vUv + vec2(-h.x, h.y)).rgb * 2.0 + texture2D(tex, vUv + vec2(0.0, h.y * 2.0)).rgb + texture2D(tex, vUv + vec2(h.x, h.y)).rgb * 2.0
          + texture2D(tex, vUv + vec2(h.x * 2.0, 0.0)).rgb + texture2D(tex, vUv + vec2(h.x, -h.y)).rgb * 2.0 + texture2D(tex, vUv + vec2(0.0, -h.y * 2.0)).rgb + texture2D(tex, vUv + vec2(-h.x, -h.y)).rgb * 2.0;
        gl_FragColor = vec4(c / 12.0 + texture2D(add, vUv).rgb, 1.0); }`, {tex: {value: null}, add: {value: null}, texel: {value: new THREE.Vector2()}});
    /* depth of field: a gather along one axis, its reach the circle of confusion at this pixel, each tap counting only as
       far as its own circle reaches (so a sharp thing never smears over a soft one) */
    this.mDof = mat(`${T} uniform sampler2D depth; uniform vec2 dir; uniform float near, far, focus, aper, maxC;
      float lin(float d){ float z = d * 2.0 - 1.0; return 2.0 * near * far / (far + near - z * (far - near)); }
      float coc(float z){ return clamp(aper * abs(1.0 / max(z, 0.02) - 1.0 / max(focus, 0.02)), 0.0, 1.0) * maxC; }
      void main(){ float c0 = coc(lin(texture2D(depth, vUv).x)); vec3 acc = vec3(0.0); float ws = 0.0;
        if (c0 < 0.7) { gl_FragColor = vec4(texture2D(tex, vUv).rgb, 1.0); return; }
        for (int i = -7; i <= 7; i++) { float fi = float(i); float dist = abs(fi) * c0 / 7.0; vec2 uv = vUv + dir * fi * c0 / 7.0;
          float ct = coc(lin(texture2D(depth, uv).x)); float w = exp(-fi * fi / 24.0) * (i == 0 ? 1.0 : clamp(ct / max(dist, 1e-3), 0.0, 1.0));
          acc += texture2D(tex, uv).rgb * w; ws += w; }
        gl_FragColor = vec4(acc / ws, 1.0); }`,
      {tex: {value: null}, texel: {value: new THREE.Vector2()}, depth: {value: null}, dir: {value: new THREE.Vector2()}, near: {value: 0.05}, far: {value: 3000}, focus: {value: 60}, aper: {value: 0}, maxC: {value: 8}});
    this.mFinal = mat(`${T} uniform sampler2D bloom; uniform float expo, bloomK, grain, vig, ca, veilA, knee, frame; uniform vec3 veil;
      float hash12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
      vec3 shoulder(vec3 x){ vec3 k = vec3(knee); vec3 s = k + (1.0 - k) * (1.0 - exp(-(x - k) / (1.0 - k))); return mix(x, s, step(k, x)); }
      vec3 toSRGB(vec3 c){ return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), c)); }
      void main(){
        vec2 q = vUv - 0.5; float r2 = dot(q, q); vec2 off = q * ca * (0.4 + r2);
        vec3 col = vec3(texture2D(tex, vUv + off).r, texture2D(tex, vUv).g, texture2D(tex, vUv - off).b);
        col += texture2D(bloom, vUv).rgb * bloomK;
        col = max(col * expo, 0.0);
        col = shoulder(col);
        col *= 1.0 - vig * smoothstep(0.1, 0.95, r2 * 2.0);
        col = mix(col, veil, veilA);
        vec3 s = toSRGB(clamp(col, 0.0, 1.0));
        float l = dot(s, vec3(0.2126, 0.7152, 0.0722));
        float gn = hash12(floor(gl_FragCoord.xy / 1.25) + vec2(frame * 7.13, frame * 3.71)) - 0.5;
        s += gn * grain * (1.0 - 0.7 * l);
        gl_FragColor = vec4(s, 1.0);
      }`,
      {tex: {value: null}, texel: {value: new THREE.Vector2()}, bloom: {value: null}, expo: {value: 1.0}, bloomK: {value: 0.22}, grain: {value: 0.016}, vig: {value: 0.26}, ca: {value: 0.0015},
       veilA: {value: 0}, veil: {value: new THREE.Color(0, 0, 0)}, knee: {value: 0.55}, frame: {value: 0}});
    this.mFinal.uniforms.grain.value = 0.012;
    this.rts = null; this.w = this.h = 0; this.frame = 0;
  }
  size(w, h){
    if (this.rts && this.w === w && this.h === h) return;
    this.w = w; this.h = h;
    if (this.rts) for (const k in this.rts) this.rts[k].dispose();
    const mk = (sw, sh, o = {}) => new THREE.WebGLRenderTarget(Math.max(1, Math.round(sw)), Math.max(1, Math.round(sh)), Object.assign({type: this.type, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, depthBuffer: false, generateMipmaps: false}, o));
    const depth = new THREE.DepthTexture(w, h, THREE.UnsignedIntType);
    this.rts = {scene: mk(w, h, {depthBuffer: true, depthTexture: depth, samples: this.samples}),
                b1: mk(w / 2, h / 2), b2: mk(w / 4, h / 4), b3: mk(w / 8, h / 8), b4: mk(w / 16, h / 16), u3: mk(w / 8, h / 8), u2: mk(w / 4, h / 4), u1: mk(w / 2, h / 2)};
    if (this.dof) { this.rts.d1 = mk(w, h); this.rts.d2 = mk(w, h); }
  }
  pass(m, from, to, add){
    m.uniforms.tex.value = from.texture; m.uniforms.texel.value.set(1 / from.width, 1 / from.height);
    if (add !== undefined) m.uniforms.add.value = add ? add.texture : null;
    this.quad.material = m; this.r.setRenderTarget(to); this.r.render(this.qs, this.qc);
  }
  /* draw: scene and camera into the lens, then to the canvas. P: {focus, aper, veilA, expo, grain} */
  render(scene, cam, P = {}){
    const R = this.rts, r = this.r;
    r.setRenderTarget(R.scene); r.render(scene, cam);
    r.setRenderTarget(null);
    this.pass(this.mBright, R.scene, R.b1); this.pass(this.mDown, R.b1, R.b2); this.pass(this.mDown, R.b2, R.b3); this.pass(this.mDown, R.b3, R.b4);
    this.pass(this.mUp, R.b4, R.u3, R.b3); this.pass(this.mUp, R.u3, R.u2, R.b2); this.pass(this.mUp, R.u2, R.u1, R.b1);
    let src = R.scene;
    if (this.dof && (P.aper || 0) > 0.001) {
      const u = this.mDof.uniforms; u.depth.value = R.scene.depthTexture; u.near.value = cam.near; u.far.value = cam.far; u.focus.value = P.focus || 60; u.aper.value = P.aper; u.maxC.value = Math.max(3, this.w / 200);
      u.dir.value.set(1 / this.w, 0); this.pass(this.mDof, R.scene, R.d1);
      u.dir.value.set(0, 1 / this.h); this.pass(this.mDof, R.d1, R.d2);
      src = R.d2;
    }
    const f = this.mFinal.uniforms;
    f.bloom.value = R.u1.texture; f.expo.value = P.expo ?? 1; f.veilA.value = P.veilA || 0;
    f.frame.value = (this.frame = (this.frame + 1) % 1000); f.grain.value = P.grain ?? (this.lean ? 0.009 : 0.012);
    this.pass(this.mFinal, src, null);
  }
  dispose(){ if (this.rts) for (const k in this.rts) this.rts[k].dispose(); for (const m of [this.mBright, this.mDown, this.mUp, this.mDof, this.mFinal]) m.dispose(); this.quad.geometry.dispose(); }
}
function lensFor(renderer, lean, opts){ const L = new Lens(renderer, lean, opts), v = new THREE.Vector2(); renderer.getDrawingBufferSize(v); L.size(v.x, v.y); return L; }

/* ================================ the deck's furniture and ground, as geometry ================================ */
/* An Adirondack chair of the deck's own weathered boards: two front legs, the runners the seat sits on, sloping back, wide
   flat arms on their back supports, the seat's slats, and, as a mesh of its own (hidden while the reader sits in it, since
   nobody sees the back of the chair they are in), the fanned back and its cross rail. A group of two meshes. */
function adirondack(mat){
  const parts = [], back = [], slat = (into, w, h, d, x, y, z, rx = 0, rz = 0) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); m.rotation.set(rx, 0, rz); into.push(m); };
  for (const s of [-1, 1]) {
    slat(parts, 0.05, 0.58, 0.09, s * 0.31, 0.29, -0.3);                       // the front legs
    slat(parts, 0.045, 0.09, 0.95, s * 0.27, 0.27, 0.06, 0.2);                 // the runners the seat sits on, sloping back
    slat(parts, 0.14, 0.025, 0.74, s * 0.38, 0.6, -0.06);                      // the wide flat arms
    slat(parts, 0.04, 0.3, 0.04, s * 0.37, 0.44, 0.24);                        // the arms' back supports
  }
  for (let i = 0; i < 6; i++) slat(parts, 0.6, 0.022, 0.075, 0, 0.385 - i * 0.022, -0.32 + i * 0.1, 0.2);       // the seat
  for (let i = -2; i <= 2; i++) slat(back, 0.085, 0.92, 0.02, i * 0.105, 0.72, 0.43, 0.42, -i * 0.045);           // the back, fanned
  slat(back, 0.62, 0.05, 0.03, 0, 0.6, 0.31, 0.42);                                                              // the back's cross rail
  const g = new THREE.Group(), a = merged(parts, mat), b = merged(back, mat); a.castShadow = a.receiveShadow = b.castShadow = b.receiveShadow = true; g.add(a, b); g.back = b; return g;
}
/* a log bench by the wall: a thick plank seat on two half-log blocks */
function benchParts(Q, x0, x1, z, plankStrip, R){
  const w = x1 - x0, seat = 0.45, d = 0.42, th = 0.065, tint = [0.92, 0.9, 0.86];
  Q.box(x0, seat - th, z - d / 2, x1, seat, z + d / 2, [plankStrip[0], R() * 3, plankStrip[1], R() * 3 + w / TEXW], tint, [0.7, 0.68, 0.64]);
  return {legs: [[x0 + 0.26, z], [x1 - 0.26, z]], seat, d};
}
/* a boulder: a sphere roughened by layered waves, squashed, with spherical texture coordinates (the seam turned away) */
function boulderGeo(seed, r, sx = 1, sy = 0.7, sz = 1){
  const g = new THREE.IcosahedronGeometry(r, 4), P = g.attributes.position, rr = rng(seed), waves = Array.from({length: 6}, () => [V3(rr() - .5, rr() - .5, rr() - .5).normalize(), 1.5 + rr() * 4, rr() * 6.3]);
  const uvs = new Float32Array(P.count * 2);
  for (let i = 0; i < P.count; i++) {
    const v = V3(P.getX(i), P.getY(i), P.getZ(i)), n = v.clone().normalize(); let d = 0;
    for (const [ax, f, ph] of waves) d += Math.sin(n.dot(ax) * f + ph) * 0.045 * r;
    d += 0.02 * r * Math.sin(n.x * 11 + n.y * 7) * Math.sin(n.z * 9 - n.x * 5);
    v.multiplyScalar(1 + d / r); P.setXYZ(i, v.x * sx, v.y * sy, v.z * sz);
    uvs[i * 2] = (Math.atan2(n.z, n.x) / (2 * Math.PI) + 0.5) * 2.2; uvs[i * 2 + 1] = (Math.asin(clamp(n.y, -1, 1)) / Math.PI + 0.5) * 1.2;
  }
  g.setAttribute("uv", new THREE.BufferAttribute(uvs, 2)); g.computeVertexNormals(); return g;
}
/* a pine's trunk: a tapered cylinder, a little bowed, flaring at the foot */
function trunkGeo(r, h, seed){
  const g = new THREE.CylinderGeometry(r * 0.72, r, h, 14, 8, true), P = g.attributes.position, rr = rng(seed), bow = (rr() - 0.5) * 0.06, bz = (rr() - 0.5) * 0.06, uv = g.attributes.uv;
  for (let i = 0; i < P.count; i++) {
    const y = P.getY(i), f = (y + h / 2) / h, flare = 1 + 0.35 * Math.exp(-f * 9), ang = Math.atan2(P.getZ(i), P.getX(i)), bumps = 1 + 0.05 * Math.sin(ang * 5 + f * 7) + 0.03 * Math.sin(ang * 11 - f * 13);
    P.setXYZ(i, P.getX(i) * flare * bumps + bow * h * f * f, y, P.getZ(i) * flare * bumps + bz * h * f * f);
    uv.setXY(i, uv.getX(i) * 2 * Math.PI * r / 1.7 * 2, uv.getY(i) * h / 1.7);
  }
  g.computeVertexNormals(); return g;
}
/* the lantern by the door: an iron bracket from the wall, a square iron lantern with glass sides, a flame inside */
function lanternParts(g, iron, glass, x, y, z){
  const add = (geo, mat, px, py, pz, rot) => { const m = new THREE.Mesh(geo, mat); m.position.set(px, py, pz); if (rot) m.rotation.set(...rot); m.castShadow = false; g.add(m); return m; };
  add(new THREE.BoxGeometry(0.03, 0.03, 0.34), iron, x, y + 0.26, z - 0.17);                 // the bracket's arm
  add(new THREE.BoxGeometry(0.03, 0.03, 0.26), iron, x, y + 0.13, z - 0.11, [0.6, 0, 0]);    // its brace
  add(new THREE.CylinderGeometry(0.008, 0.008, 0.06, 8), iron, x, y + 0.22, z - 0.33);        // the hook's chain
  const lz = z - 0.33, bw = 0.17, bh = 0.26;
  add(new THREE.BoxGeometry(bw + 0.02, 0.02, bw + 0.02), iron, x, y - bh / 2, lz);            // the floor
  add(new THREE.ConeGeometry(bw * 0.78, 0.1, 4), iron, x, y + bh / 2 + 0.05, lz, [0, Math.PI / 4, 0]);      // the roof
  add(new THREE.CylinderGeometry(0.012, 0.012, 0.04, 8), iron, x, y + bh / 2 + 0.11, lz);
  for (const [sx, sz] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) add(new THREE.BoxGeometry(0.014, bh, 0.014), iron, x + sx * bw / 2, y, lz + sz * bw / 2);
  add(new THREE.BoxGeometry(bw - 0.014, bh - 0.02, bw - 0.014), glass, x, y, lz);             // the glass
  add(new THREE.CylinderGeometry(0.022, 0.026, 0.05, 10), iron, x, y - bh / 2 + 0.035, lz);   // the candle's cup
  return V3(x, y - bh / 2 + 0.11, lz);                                                        // where the flame is
}

/* ================================ the look, the deck's layout and the seats ================================ */
const LOOK = {      // the night's light, tuned by eye against frames of the scene (linear values)
  zen: [0.0010, 0.0013, 0.0025], hor: [0.0048, 0.0056, 0.0078], glow: [0.0005, 0.0009, 0.0006], town: [0.0030, 0.0022, 0.0012],
  mwGain: 0.105, starK: 1.12, starG: 0.5, moonLit: 5.5, moonEarth: 0.06, window: 92, spill: 20, moonSize: 2.5, youngMoon: 0.22,
  bounce: 2.4, lampI: [1.45, 1.45, 1.1], fireI: 2.2,      // the deck's own: the room's light thrown back up off the boards, the two lamps and the chandelier, and the fire inside
  glassRef: 2.0,      // how much of the night in front the glass gives back, over the glass's own angle-dependent reflectance (about four percent head-on, as real glass)
  moonKey: 0.22, moonKeyFull: 0.6,      // the moon's light on the deck: a crescent's (faint, its shadows soft and shallow), and a full moon's, before the eyes adjust
  sky: 0.42,          // the sky's own light on everything, from above (as eyes used to the dark see it)
  fog: [16, 44],      // the yard fades into the dark of the valley between these distances (metres)
  lantern: 1.9        // the lantern by the door
};
const STAY = "tca.night.stay";      // the view handed from the crossing to the deck's own page (this tab only)
const COMPASS = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"];
export const compass = az => COMPASS[Math.round((((az % 360) + 360) % 360) / 45) % 8];
/* The deck, in metres: the reader faces -z toward the railing, +x is their right, the cabin's wall is behind them at +z. The
   planks run parallel to the wall. The steps go down from the deck's right-hand edge to the yard, which lies about a metre
   below; the yard falls away toward the valley beyond. The cabin is the great room itself, seen from outside (its
   measurements are the room's own, in the same frame: x across, the glass wall at the front, the fireplace on the right-hand
   wall, the loft over the back, the ridge running front to back): the gable end of glass rises from the sill to the ridge,
   with the glazed door at its right, log walls either side, the stone chimney up the right-hand end. */
const L = {
  deck: {x0: -4.5, x1: 4.5, z0: -2.05, z1: 1.0},
  rail: {z: -2.0, top: 1.0, mid: 0.5},
  steps: {x0: 4.5, z0: -1.55, z1: -0.55, tread: 0.3, rise: 0.24, n: 4},
  ground: -0.96,
  wall: {z: 1.0, half: 5.2, eave: 4.2, ridge: 7.0, depth: 9.0, logR: 0.17, course: 0.325},      // the room's inside half-width, eave and ridge heights, depth, and its logs
  glass: {x0: -3.05, x1: 3.05, y0: 0.68, mull: [-1.02, 1.02], trans: [2.75, 4.35, 5.95]},      // the gable window: posts, sill, mullions, transoms (as in the room)
  door: {x0: 2.0, x1: 2.95, y1: 2.15},      // the glazed door out to the deck, at the right of the glass (as in the room)
  chairs: [{x: -0.6, z: -0.62, ry: 0.08}, {x: 0.85, z: -0.65, ry: -0.14}],
  table: {x: 0.14, z: -0.84, r: 0.24},
  bench: {x0: 3.15, x1: 4.25, z: 0.62},      // under the lantern, between the door and the right-hand rail
  lantern: {x: 3.68, y: 2.05},
  chimney: {x0: 5.56, x1: 6.76, z0: 6.15, z1: 7.6, top: 8.2},      // up the outside of the right-hand wall, where the fireplace is
  roof: {z0: 0.35, over: 0.7}      // the rake's overhang over the deck, and the eaves' beyond the side walls
};
/* Where a reader can sit (John, 2026-10-11): the eye's place, which way it faces, and where you stand when you get up.
   Yaw 0 faces the railing (-z); yaw 90 faces right (+x). The chair is the crossing's own seat. */
export const SEATS = [
  {id: "chair", name: "The chair at the railing", where: "an Adirondack chair at the railing, the empty one beside you, the mountains and the whole sky ahead",
   eye: [-0.6, 1.1, -0.52], yaw: 0, pitch: 14, pitchPhone: 24, stand: [-0.62, -1.45], sat: "chair"},
  {id: "steps", name: "The top of the steps", where: "sitting on the deck's edge at the top of the steps, your feet on the step below, the yard and the pines to your right",
   eye: [4.46, 0.97, -1.05], yaw: 90, pitch: 6, pitchPhone: 14, stand: [3.9, -1.05], sat: "steps"},
  {id: "bench", name: "The bench by the wall", where: "a log bench against the cabin's wall under the lantern, the door and the lit wall of glass at your shoulder, the deck and the two chairs before you",
   eye: [3.7, 1.16, 0.52], yaw: -40, pitch: 10, pitchPhone: 18, stand: [3.7, 0.1], sat: "bench"}
];
const STAND_EYE = 1.62, WALK_SPEED = 1.25;      // standing eyes, and a walking pace, in metres (and metres a second)
/* the trees: where each stands (x, z), its height, its kind and its seed; the nearest have trunks of their own and are in
   the walker's way */
const TREES = [[-8.6, -12.5, 19, "spruce", 3], [-13, -7, 17, "lodge", 5], [10.5, -14, 17, "spruce", 7], [14.5, -5, 18, "pond", 11], [-15, -19, 15, "lodge", 13], [17, -20, 14, "spruce", 19]];
const TREES_MORE = [[-11.5, 1.5, 18, "spruce", 7], [-17, 7.5, 20, "lodge", 13], [-20, -3.5, 16, "spruce", 19], [12.5, 2.5, 19, "lodge", 5], [18, 8, 17, "spruce", 3],
                    [21.5, -2.5, 15, "pond", 11], [-24, 13, 21, "spruce", 19], [25, 14, 20, "spruce", 7]];
const NEAR_TREES = [[7.4, -3.6, 16, "lodge", 23, 0.3], [-7.6, -5.2, 18, "spruce", 29, 0.36], [8.9, -7.9, 15, "pond", 31, 0.42]];      // with trunks: x, z, height, kind, seed, trunk radius
const BOULDERS = [[7.7, -2.9, 0.55, 41, 1.2, 0.6, 1.0], [-6.4, -3.1, 0.75, 43, 1.0, 0.65, 1.3], [-2.6, -7.4, 1.1, 47, 1.3, 0.55, 1.0], [3.1, -8.1, 0.9, 53, 1.0, 0.7, 1.4]];      // x, z, radius, seed, scale x y z (none in the way at the foot of the steps)
/* the yard: level near the cabin, falling toward the valley beyond, with gentle swells */
function groundY(x, z){
  const fall = Math.max(0, -(z + 5.5));
  return L.ground - 0.07 * fall - 0.0025 * fall * fall + 0.06 * Math.sin(x * 0.7 + 1.3) * Math.sin(z * 0.55 - 0.4) + 0.03 * Math.sin(x * 1.9) * Math.cos(z * 2.3);
}
function onDeck(x, z){ const d = L.deck; return x >= d.x0 + 0.12 && x <= d.x1 - 0.1 && z >= d.z0 + 0.17 && z <= d.z1 - 0.3; }      // inside the railing, short of the wall's logs
function onSteps(x, z){ const s = L.steps; return x > L.deck.x1 - 0.1 && x <= s.x0 + s.tread * s.n + 0.05 && z >= s.z0 + 0.12 && z <= s.z1 - 0.12; }
/* the floor under a point: the deck, a step, or the ground */
function heightAt(x, z){
  if (onDeck(x, z)) return 0;
  if (onSteps(x, z)) { const s = L.steps; if (x <= s.x0) return 0; return -s.rise * Math.min(s.n, Math.max(1, Math.ceil((x - s.x0) / s.tread))); }
  return groundY(x, z);
}
const inCircle = (x, z, cx, cz, r) => (x - cx) * (x - cx) + (z - cz) * (z - cz) < r * r;
function deckClear(x, z){
  for (const c of L.chairs) if (inCircle(x, z, c.x, c.z + 0.05, 0.56)) return false;
  if (inCircle(x, z, L.table.x, L.table.z, L.table.r + 0.22)) return false;
  if (x > L.bench.x0 - 0.2 && x < L.bench.x1 + 0.2 && z > L.bench.z - 0.45) return false;
  return true;
}
function yardOK(x, z){
  if (x < -9.5 || x > 9.5 || z < -8.8 || z > 0.55) return false;
  const d = L.deck, s = L.steps;
  if (x > d.x0 - 0.25 && x < d.x1 + 0.25 && z > d.z0 - 0.3) return false;      // under the deck, and its rim
  if (x > d.x1 && x < s.x0 + s.tread * s.n + 0.15 && z > s.z0 - 0.35 && z < s.z1 + 0.35 && !(z >= s.z0 + 0.12 && z <= s.z1 - 0.12)) return false;      // the steps' stringers: the treads are the way
  for (const t of NEAR_TREES) if (inCircle(x, z, t[0], t[1], t[5] + 0.3)) return false;
  for (const b of BOULDERS) if (inCircle(x, z, b[0], b[1], b[2] * Math.max(b[4], b[6]) + 0.2)) return false;
  return true;
}
/* where a reader on foot may stand (nothing walks through the railing, the furniture, a tree or the wall) */
function walkOK(x, z){ if (onDeck(x, z)) return deckClear(x, z); if (onSteps(x, z)) return true; return yardOK(x, z); }
const floorKind = (x, z) => onDeck(x, z) ? "deck" : onSteps(x, z) ? "steps" : "ground";
/* the wind: gusts that come and go, 0 to 1, with a second phase for the far side of the yard */
const gustAt = (t, ph = 0) => clamp(0.42 + 0.34 * Math.sin(t * 0.21 + ph) * Math.sin(t * 0.073 + 1.0 + ph * 0.3) + 0.24 * Math.sin(t * 0.9 + ph * 2) * Math.sin(t * 0.17 + 2.1), 0, 1);

/* ================================ the sound of the place ================================ */
/* Off until the reader turns it on (John, 2026-10-11). The wind in the pines, the fire behind the window's glass, an owl in
   the trees and the reader's own steps are made here, on the device, from oscillators and shaped noise. The creek far down
   the slope, the elk bugling across the valley in September and October, and the coyotes far off now and then are the
   National Park Service's own public-domain recordings (its Natural Sounds gallery), fetched only when the sound is turned
   on and placed far away through a long valley echo. Each sound sits where its thing is, so turning the head turns the
   sound; the listener is wherever the eyes are. */
class DeckSound {
  constructor(opts = {}){
    this.urls = opts.urls || {}; this.season = opts.season != null ? !!opts.season : elkSeason();
    this.ctx = null; this.on = false; this.dead = false; this.bufs = {}; this.loaded = null; this.R = rng(777);
    this.timers = {owl: 0, elk: 0, coy: 0, pop: 0, creek: 0}; this.gust = 0.4; this.flick = 1; this.stepSide = false; this.creekSrc = [];
  }
  /* the recordings, decoded once; a recording that does not arrive is left out (the creek then is made here) */
  load(){
    if (this.loaded) return this.loaded;
    const c = this.ctx, one = (k, u) => !u ? Promise.resolve() : fetch(u).then(r => { if (!r.ok) throw new Error(u); return r.arrayBuffer(); })
      .then(b => new Promise((ok, no) => c.decodeAudioData(b, ok, no))).then(buf => { this.bufs[k] = buf; }, () => {});
    this.loaded = Promise.all(Object.entries(this.urls).map(([k, u]) => one(k, u)));
    return this.loaded;
  }
  mk(){
    const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return false;
    const c = this.ctx = new AC(), sr = c.sampleRate, R = rng(4242);
    this.master = c.createGain(); this.master.gain.value = 0; this.master.connect(c.destination);
    /* the valley's echo: a long, sparse tail that darkens as it decays, with the far slopes' own returns */
    const Lir = Math.floor(sr * 3.4), ir = c.createBuffer(2, Lir, sr);
    for (let ch = 0; ch < 2; ch++) { const d = ir.getChannelData(ch), r2 = rng(ch + 9); let lp = 0;
      for (let i = 0; i < Lir; i++) { const t = i / sr, n = r2() * 2 - 1; lp += (n - lp) * (0.3 - 0.26 * Math.min(1, t / 2.5)); d[i] = lp * Math.exp(-t * 1.35) * (t < 0.02 ? 0 : 1) * 0.22; }
      for (const [at, g] of [[0.38, 0.5], [0.86, 0.42], [1.47, 0.3], [2.2, 0.18]]) { const i0 = Math.floor((at + ch * 0.011) * sr); for (let k = 0; k < 900 && i0 + k < Lir; k++) d[i0 + k] += g * (r2() * 2 - 1) * Math.exp(-k / 220) * 0.5; } }
    this.verb = c.createConvolver(); this.verb.buffer = ir; this.verbIn = c.createGain(); this.verbIn.gain.value = 0.5; this.verbIn.connect(this.verb); this.verb.connect(this.master);
    /* noise to build on: white, pink and brown, four seconds each, looped */
    const N = sr * 4, mkBuf = fill => { const b = c.createBuffer(1, N, sr), d = b.getChannelData(0); fill(d); return b; };
    this.white = mkBuf(d => { for (let i = 0; i < N; i++) d[i] = R() * 2 - 1; });
    this.pink = mkBuf(d => { let b0 = 0, b1 = 0, b2 = 0; for (let i = 0; i < N; i++) { const w = R() * 2 - 1; b0 = 0.99765 * b0 + w * 0.099; b1 = 0.963 * b1 + w * 0.2965; b2 = 0.57 * b2 + w * 1.0526; d[i] = (b0 + b1 + b2 + w * 0.1848) * 0.12; } });
    this.brown = mkBuf(d => { let b = 0; for (let i = 0; i < N; i++) { const w = R() * 2 - 1; b = (b + 0.02 * w) / 1.02; d[i] = b * 3.0; } });
    const bq = (type, f, q = 1, gain = 0) => { const b = c.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q; b.gain.value = gain; return b; };
    const loop = (buf, gain, filt, rate = 1) => { const s = c.createBufferSource(); s.buffer = buf; s.loop = true; s.playbackRate.value = rate; s.loopStart = R() * 2; let n = s; for (const f of filt) { n.connect(f); n = f; }
      const g = c.createGain(); g.gain.value = gain; n.connect(g); s.start(); return g; };
    this.bq = bq; this.loop = loop;
    /* the wind: a low rush all round, a little into the valley's echo; and the needles' hiss in the near trees to either side */
    this.windBed = loop(this.brown, 0.05, [bq("lowpass", 150, 0.6)]); this.windBed.connect(this.master); const bedSend = c.createGain(); bedSend.gain.value = 0.25; this.windBed.connect(bedSend); bedSend.connect(this.verbIn);
    this.hissL = bq("bandpass", 1400, 0.8); this.hissR = bq("bandpass", 1900, 0.8);
    const hl = loop(this.pink, 0.0, [this.hissL], 1.0), hr = loop(this.pink, 0.0, [this.hissR], 1.07);
    this.hissLG = hl; this.hissRG = hr; hl.connect(this.panner([-8.5, 7, -5.5], 4)); hr.connect(this.panner([8.6, 7, -6.5], 4));
    /* the fire behind the glass (the hearth is on the room's right-hand wall, some way in): the pops come from pop(); a low
       murmur stays, all of it muffled by the glass, so it seems to come from the glass wall's right-hand part */
    this.glass = bq("lowpass", 720, 0.7); this.fireP = this.panner([2.4, 1.1, 1.5], 2.4); this.glass.connect(this.fireP);
    this.fireBed = loop(this.brown, 0.02, [bq("lowpass", 110, 0.6)]); this.fireBed.connect(this.glass);
    /* the creek far down the slope: the recording, looped without a seam, else water made from noise */
    this.creekP = this.panner([-14, -2.5, -17], 6); this.creekF = bq("lowpass", 2600, 0.6); this.creekF.connect(this.creekP);
    this.creekG = c.createGain(); this.creekG.gain.value = 0.55; this.creekG.connect(this.creekF);
    /* where the far recordings play from: across the valley, and far off to the side. A big sound far off stays a big
       sound: the bugle and the chorus fall off from a long way out, so they stand above the wind rather than under it */
    this.elkP = this.panner([12, 2, -70], 40); this.coyP = this.panner([-45, 2, -52], 36);
    this.stepPan = c.createStereoPanner ? c.createStereoPanner() : c.createGain(); this.stepPan.connect(this.master);
    const ss = c.createGain(); ss.gain.value = 0.18; this.stepPan.connect(ss); ss.connect(this.verbIn);
    return true;
  }
  panner(p, ref = 2){
    const c = this.ctx, pn = c.createPanner(); pn.panningModel = "HRTF"; pn.distanceModel = "inverse"; pn.refDistance = ref; pn.rolloffFactor = 1.0; pn.maxDistance = 400;
    if (pn.positionX) { pn.positionX.value = p[0]; pn.positionY.value = p[1]; pn.positionZ.value = p[2]; } else pn.setPosition(p[0], p[1], p[2]);
    pn.connect(this.master); const send = this.ctx.createGain(); send.gain.value = 0.45; pn.connect(send); send.connect(this.verbIn); return pn;
  }
  burst(dest, when, dur, gain, filt, buf){
    const c = this.ctx, s = c.createBufferSource(); s.buffer = buf || this.white; s.loop = true; s.loopStart = this.R() * 3; let n = s; for (const f of filt) { n.connect(f); n = f; }
    const g = c.createGain(); g.gain.setValueAtTime(0, when); g.gain.linearRampToValueAtTime(gain, when + 0.004); g.gain.exponentialRampToValueAtTime(0.0005, when + dur); n.connect(g); g.connect(dest); s.start(when); s.stop(when + dur + 0.05);
  }
  tone(dest, when, f0, f1, dur, gain, type = "sine", attack = 0.003){
    const c = this.ctx, o = c.createOscillator(); o.type = type; o.frequency.setValueAtTime(f0, when); o.frequency.exponentialRampToValueAtTime(Math.max(1, f1), when + dur);
    const g = c.createGain(); g.gain.setValueAtTime(0, when); g.gain.linearRampToValueAtTime(gain, when + attack); g.gain.exponentialRampToValueAtTime(0.0005, when + dur); o.connect(g); g.connect(dest); o.start(when); o.stop(when + dur + 0.05);
    return g;
  }
  /* a great horned owl: four or five soft hoots, each a near-pure tone that sags a little, from a tree some way off */
  owl(when, p, pitch = 1){
    const c = this.ctx, pn = this.panner(p, 6), lp = this.bq("lowpass", 1100, 0.7); lp.connect(pn);
    const pattern = [[0, 0.27], [0.36, 0.2], [0.56, 0.3], [0.98, 0.32], [1.4, 0.36]];
    for (const [dt, dur] of pattern.slice(0, 3 + Math.floor(this.R() * 3))) {
      const f = (330 + this.R() * 25) * pitch, t = when + dt, o = c.createOscillator(); o.type = "sine"; o.frequency.setValueAtTime(f * 1.03, t); o.frequency.exponentialRampToValueAtTime(f * 0.93, t + dur);
      const vib = c.createOscillator(), vg = c.createGain(); vib.frequency.value = 5.5; vg.gain.value = f * 0.012; vib.connect(vg); vg.connect(o.frequency); vib.start(t); vib.stop(t + dur + 0.1);
      const g = c.createGain(); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(0.22, t + 0.05); g.gain.setValueAtTime(0.22, t + dur - 0.08); g.gain.linearRampToValueAtTime(0, t + dur);
      o.connect(g); g.connect(lp); o.start(t); o.stop(t + dur + 0.05);
      const o2 = c.createOscillator(); o2.type = "sine"; o2.frequency.setValueAtTime(f * 2.02, t); o2.frequency.exponentialRampToValueAtTime(f * 1.86, t + dur);
      const g2 = c.createGain(); g2.gain.setValueAtTime(0, t); g2.gain.linearRampToValueAtTime(0.03, t + 0.06); g2.gain.linearRampToValueAtTime(0, t + dur); o2.connect(g2); g2.connect(lp); o2.start(t); o2.stop(t + dur + 0.05);
    }
    setTimeout(() => { try { pn.disconnect(); } catch (e) {} }, 6000);
  }
  /* one of the recordings, from far away, through the valley */
  far(key, dest, when, gain, lp){
    const buf = this.bufs[key]; if (!buf) return 0;
    const c = this.ctx, s = c.createBufferSource(); s.buffer = buf; const f = this.bq("lowpass", lp, 0.6), g = c.createGain(); g.gain.setValueAtTime(0, when); g.gain.linearRampToValueAtTime(gain, when + 0.3);
    g.gain.setValueAtTime(gain, when + buf.duration - 0.4); g.gain.linearRampToValueAtTime(0, when + buf.duration); s.connect(f); f.connect(g); g.connect(dest); s.start(when); return buf.duration;
  }
  /* the creek: the recording's five seconds, two players handing over with a half-second cross-fade, so there is no seam */
  creekSegment(when){
    const c = this.ctx, buf = this.bufs.stream; if (!buf) return;
    const s = c.createBufferSource(); s.buffer = buf; const g = c.createGain(), dur = buf.duration, fade = 0.5;
    g.gain.setValueAtTime(0, when); g.gain.linearRampToValueAtTime(1, when + fade); g.gain.setValueAtTime(1, when + dur - fade); g.gain.linearRampToValueAtTime(0, when + dur);
    s.connect(g); g.connect(this.creekG); s.start(when); s.stop(when + dur + 0.02);
    this.timers.creek = when + dur - fade;
  }
  start(){
    if (this.dead) return null;
    if (!this.ctx) { try { if (!this.mk()) { this.dead = true; return null; } } catch (e) { this.dead = true; return null; } }
    const c = this.ctx; if (c.state === "suspended") c.resume().catch(() => {});
    this.on = true; const t = c.currentTime;
    this.master.gain.cancelScheduledValues(t); this.master.gain.setValueAtTime(this.master.gain.value, t); this.master.gain.linearRampToValueAtTime(0.9, t + 1.4);
    this.timers.owl = t + 12 + this.R() * 40; this.timers.elk = t + 20 + this.R() * 90; this.timers.coy = t + 90 + this.R() * 200; this.timers.pop = t + 0.2; this.timers.creek = 0;
    const ready = this.load().then(() => { if (this.on && !this.bufs.stream && !this.creekSynth) {      // no recording: water made from noise
      this.creekSynth = this.loop(this.white, 0.09, [this.bq("bandpass", 1800, 0.5), this.bq("highpass", 500, 0.7)]); this.creekSynth.connect(this.creekG); } });
    return ready;
  }
  stop(){ if (!this.ctx || !this.on) return; this.on = false; const t = this.ctx.currentTime; this.master.gain.cancelScheduledValues(t); this.master.gain.setValueAtTime(this.master.gain.value, t); this.master.gain.linearRampToValueAtTime(0, t + 0.6);
    setTimeout(() => { if (!this.on && this.ctx && this.ctx.state === "running") this.ctx.suspend().catch(() => {}); }, 800); }
  close(){ if (this.ctx) { try { this.ctx.close(); } catch (e) {} this.ctx = null; } this.on = false; }
  pause(){ if (this.ctx && this.ctx.state === "running") this.ctx.suspend().catch(() => {}); }
  resume(){ if (this.ctx && this.on && this.ctx.state === "suspended") this.ctx.resume().catch(() => {}); }
  /* each frame: the listener where the eyes are; the wind's strength; the fire's pops; the far sounds a little ahead of time */
  update(cam, gust, flick){
    if (!this.ctx || !this.on) return;
    const c = this.ctx, Ln = c.listener, p = cam.position, f = V3(0, 0, -1).applyQuaternion(cam.quaternion), u = V3(0, 1, 0).applyQuaternion(cam.quaternion);
    if (Ln.positionX) { Ln.positionX.value = p.x; Ln.positionY.value = p.y; Ln.positionZ.value = p.z; Ln.forwardX.value = f.x; Ln.forwardY.value = f.y; Ln.forwardZ.value = f.z; Ln.upX.value = u.x; Ln.upY.value = u.y; Ln.upZ.value = u.z; }
    else { Ln.setPosition(p.x, p.y, p.z); Ln.setOrientation(f.x, f.y, f.z, u.x, u.y, u.z); }
    const t = c.currentTime, g2 = gustAt(t, 2.1);
    this.windBed.gain.setTargetAtTime(0.035 + 0.11 * gust, t, 0.4);
    this.hissLG.gain.setTargetAtTime(0.004 + 0.045 * gust * gust, t, 0.5); this.hissRG.gain.setTargetAtTime(0.004 + 0.045 * g2 * g2, t, 0.5);
    this.hissL.frequency.setTargetAtTime(1100 + 900 * gust, t, 0.8); this.hissR.frequency.setTargetAtTime(1400 + 1100 * g2, t, 0.8);
    this.fireBed.gain.setTargetAtTime(0.018 * flick, t, 0.2);
    while (this.timers.pop < t + 0.3) {      /* the fire: a pop or a crackle, more often as it flares */
      const w = this.timers.pop, n = this.R() < 0.75 ? 1 : 2 + Math.floor(this.R() * 3);
      for (let i = 0; i < n; i++) { const at = w + i * (0.02 + this.R() * 0.05); this.burst(this.glass, at, 0.012 + this.R() * 0.03, 0.12 + this.R() * 0.2, [this.bq("bandpass", 1500 + this.R() * 2500, 2.5)]); }
      this.timers.pop = w + 0.1 + this.R() * 0.55 * (1.4 - 0.6 * flick); }
    if (this.bufs.stream && this.timers.creek < t + 0.6) this.creekSegment(Math.max(t + 0.05, this.timers.creek));
    if (this.timers.owl < t + 0.3) {      /* an owl, from one of the far trees; sometimes answered from another */
      const trees = TREES.concat(TREES_MORE), tr = trees[Math.floor(this.R() * trees.length)];
      this.owl(this.timers.owl, [tr[0], tr[2] * 0.6, tr[1]]);
      if (this.R() < 0.4) { const t2 = trees[Math.floor(this.R() * trees.length)]; this.owl(this.timers.owl + 3 + this.R() * 2, [t2[0], t2[2] * 0.5, t2[1]], 0.88); }
      this.timers.owl += 45 + this.R() * 100; }
    if (this.season && this.timers.elk < t + 0.3) { const d = this.far("elk", this.elkP, this.timers.elk, 1.0, 3600); this.timers.elk += Math.max(30, d) + 110 + this.R() * 170; }      // about ten decibels over the wind
    if (this.timers.coy < t + 0.3) { const d = this.far("coyotes", this.coyP, this.timers.coy, 0.8, 3000); this.timers.coy += Math.max(20, d) + 240 + this.R() * 300; }
  }
  /* the reader's own step: on the boards (a hollow knock), on a step (brighter), or on the needles of the yard (a crunch) */
  step(kind, speed){
    if (!this.ctx || !this.on) return;
    const t = this.ctx.currentTime, k = clamp(speed, 0.25, 1), pan = (this.stepSide = !this.stepSide) ? 0.2 : -0.2;
    if (this.stepPan.pan) this.stepPan.pan.setValueAtTime(pan, t);
    if (kind === "ground") { this.burst(this.stepPan, t, 0.09, 0.09 * k, [this.bq("bandpass", 2300, 0.9)]); this.burst(this.stepPan, t + 0.02, 0.05, 0.05 * k, [this.bq("bandpass", 900, 1.5)]); this.tone(this.stepPan, t, 90, 50, 0.07, 0.03 * k); }
    else { const bright = kind === "steps" ? 1.3 : 1; this.tone(this.stepPan, t, 125 * bright, 52, 0.11, 0.11 * k); this.burst(this.stepPan, t, 0.03, 0.09 * k, [this.bq("bandpass", 700 * bright, 1.4)]); this.burst(this.stepPan, t + 0.012, 0.02, 0.03 * k, [this.bq("highpass", 2200, 1)]); }
  }
  /* sitting down: the chair's wood creaks; the bench knocks; the deck's edge, nothing much */
  sit(kind){
    if (!this.ctx || !this.on) return;
    const t = this.ctx.currentTime;
    if (kind === "chair") { const g = this.tone(this.stepPan, t + 0.05, 95, 140, 0.32, 0.028, "sawtooth", 0.08); const f = this.bq("bandpass", 850, 5); g.disconnect(); g.connect(f); f.connect(this.stepPan); this.tone(this.stepPan, t, 110, 60, 0.08, 0.06); }
    else if (kind === "bench") { this.tone(this.stepPan, t, 140, 60, 0.12, 0.09); this.burst(this.stepPan, t, 0.04, 0.07, [this.bq("bandpass", 600, 1.5)]); }
    else this.burst(this.stepPan, t, 0.05, 0.05, [this.bq("bandpass", 500, 1.2)]);
  }
}

/* ================================ the scene ================================ */
function build(renderer, aspect, A, opts = {}){
  const WATCH = !!opts.watch, from = WATCH && opts.from ? opts.from : null, MORE = opts.more || {}, LEAN = !!opts.lean;
  const W = plan(A, Object.assign({aspect}, opts, from ? {date: from.date, az: from.a0, tonight: from.tonight} : {}));
  let STILL = opts.still ? 1 : 0;
  const seed = opts.seed != null ? opts.seed : (Math.random() * 1e9) | 0, R = rng(seed);
  const scene = new THREE.Scene(); scene.background = new THREE.Color("#000000");
  scene.fog = new THREE.Fog(0x020304, LOOK.fog[0], LOOK.fog[1]);      // the yard fades into the dark of the valley (the sky, the mountains and the room inside take no fog)
  const cam = new THREE.PerspectiveCamera(50, aspect, 0.05, 3000); scene.add(cam);
  const EYE = V3(...SEATS[0].eye);      // the crossing's seat: the chair at the railing
  const sky = new THREE.Group(); scene.add(sky);      // everything far away moves with the eye, so it stays at infinity
  const cel = new THREE.Group(); sky.add(cel);      // the sky's own sphere (the stars, the planets, the Moon): on the deck it turns as the Earth does
  const U = {uTime: {value: 0}, uAdapt: {value: 0}, uLimit: {value: 1}, uFlash: {value: 0}, uFlashDir: {value: V3(0, 1, 0)}, uFlashCol: {value: new THREE.Color(0.78, 0.95, 0.85)},
             uPx: {value: renderer.getPixelRatio()}, uStill: {value: STILL}};
  const lensP = {veilA: 1, focus: 60, aper: 0, expo: 1};

  /* the sky: its own faint glow, brighter toward the horizon, the glow of far towns low on one side, and the Milky Way
     where it stands tonight */
  const mwTex = new THREE.Texture(A.mw); mwTex.format = THREE.RedFormat; mwTex.generateMipmaps = false; mwTex.minFilter = THREE.LinearFilter; mwTex.magFilter = THREE.LinearFilter;
  mwTex.wrapS = THREE.RepeatWrapping; mwTex.needsUpdate = true;
  const moonDir = W.moonW.clone();
  const domeMat = new THREE.ShaderMaterial({
    uniforms: Object.assign({uMW: {value: mwTex}, uW2J: {value: W.f.w2j.clone()}, uL0: {value: MW.L0}, uLK: {value: MW.K}, uMWGain: {value: LOOK.mwGain},
      uZen: {value: V3(...LOOK.zen)}, uHor: {value: V3(...LOOK.hor)}, uGlowCol: {value: V3(...LOOK.glow)}, uTown: {value: V3(...LOOK.town)}, uTownDir: {value: new THREE.Vector2(Math.sin(104 * D2R), -Math.cos(104 * D2R))},
      uMoonDir: {value: moonDir}, uMoonGlow: {value: 0}}, U),
    vertexShader: `varying vec3 vDir; void main(){ vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `uniform sampler2D uMW; uniform mat3 uW2J; uniform float uL0, uLK, uMWGain, uAdapt, uMoonGlow, uFlash; uniform vec3 uZen, uHor, uGlowCol, uTown, uMoonDir, uFlashDir, uFlashCol; uniform vec2 uTownDir;
      varying vec3 vDir;
      ${SKYFRAG_HEAD}
      void main(){
        vec3 d = normalize(vDir); float s = d.y, altDeg = asin(clamp(s, -1.0, 1.0)) * 57.29578, X = airmass(s, altDeg);
        vec3 j = uW2J * d; float ra = atan(j.y, j.x), dec = asin(clamp(j.z, -1.0, 1.0));
        float v = texture2D(uMW, vec2(fract(0.5 - ra / 6.2831853), 0.5 + dec / 3.1415927)).r;
        float L = max(uL0 * exp(v * uLK) - uL0, 0.0);
        float ext = pow(10.0, -0.1 * min(X - 1.0, 30.0)) * smoothstep(-1.0, 6.0, altDeg);
        vec3 mw = vec3(0.90, 0.93, 1.0) * L * uMWGain * uAdapt * ext;
        float h = pow(1.0 - clamp(s, 0.0, 1.0), 4.0);
        vec3 bg = mix(uZen, uHor, h) * mix(0.35, 1.0, uAdapt);
        bg += uGlowCol * exp(-pow((altDeg - 10.0) / 9.0, 2.0)) * uAdapt;
        float town = pow(max(dot(normalize(vec2(d.x, d.z) + vec2(1e-5)), uTownDir), 0.0), 7.0) * exp(-pow(max(altDeg - 1.0, 0.0) / 6.5, 1.4)) * smoothstep(-6.0, 0.0, altDeg);
        bg += uTown * town * uAdapt;
        float cm = dot(d, uMoonDir);
        bg += vec3(0.86, 0.88, 0.94) * uMoonGlow * (exp((cm - 1.0) * 6000.0) * 0.35 + exp((cm - 1.0) * 400.0) * 0.05 + exp((cm - 1.0) * 25.0) * 0.01);
        bg += uFlashCol * uFlash * (0.006 + 0.04 * pow(max(dot(d, uFlashDir), 0.0), 8.0));
        vec3 col = bg + mw;
        col = mix(col, vec3(0.0008, 0.0009, 0.0011), smoothstep(0.0, -0.04, s));
        gl_FragColor = vec4(col, 1.0);
        #include <colorspace_fragment>
      }`,
    side: THREE.BackSide, depthWrite: false});
  const dome = new THREE.Mesh(new THREE.SphereGeometry(900, 64, 40), domeMat); dome.renderOrder = -10; sky.add(dome);

  /* the stars: the Bright Star Catalogue, where each stands over the reader tonight, with its colour and brightness; and
     the planets, where JPL's elements put them tonight, steadier than the stars, as planets are */
  const list = A.stars.concat(W.planets.map(p => ({ra: p.ra, dec: p.dec, mag: p.mag, bv: p.bv, steady: 1})));
  const n = list.length, pos = new Float32Array(n * 3), mag = new Float32Array(n), col = new Float32Array(n * 3), sd = new Float32Array(n), stdy = new Float32Array(n);
  const tmp = V3();
  list.forEach((s, i) => {
    tmp.copy(radec(s.ra, s.dec)).applyMatrix3(W.f.j2w).multiplyScalar(850); pos.set([tmp.x, tmp.y, tmp.z], i * 3);
    mag[i] = s.mag; const c = bvToRgb(s.bv), k = clamp((3.6 - s.mag) / 3.2) * 0.8;      // only bright stars show their colour to the eye
    col.set([mix(1, c[0], k), mix(1, c[1], k), mix(1, c[2], k)], i * 3); sd[i] = R() * 1000; stdy[i] = s.steady ? 1 : 0;
  });
  const sg = new THREE.BufferGeometry(); sg.setAttribute("position", new THREE.BufferAttribute(pos, 3)); sg.setAttribute("aMag", new THREE.BufferAttribute(mag, 1));
  sg.setAttribute("aCol", new THREE.BufferAttribute(col, 3)); sg.setAttribute("aSeed", new THREE.BufferAttribute(sd, 1)); sg.setAttribute("aSteady", new THREE.BufferAttribute(stdy, 1));
  /* Each star is a small Gaussian of light whose share on each pixel is worked out (a core half a pixel wide, as the eye
     and a lens spread a point, and for the bright ones a faint wider skirt), never a fraction of a sprite that the pixels
     happen to sample: a star moved by part of a pixel (a breath, the pointer) keeps its light and passes smoothly to the
     next pixel, so only the air's own twinkling changes it. Its total light is the one the stars were tuned to give, a
     little more for the faint ones, whose light is no longer packed into one pixel (so they stay as visible as tuned).
     Its height above the horizon is taken in the world, so the sky may turn. */
  const starMat = new THREE.ShaderMaterial({
    uniforms: Object.assign({uK: {value: LOOK.starK}, uG: {value: LOOK.starG}}, U),
    vertexShader: `attribute float aMag, aSeed, aSteady; attribute vec3 aCol; uniform float uTime, uLimit, uPx, uK, uG, uStill, uFlash; varying vec3 vCol; varying float vI, vSize, vSc, vSh;
      ${SKYFRAG_HEAD}
      void main(){
        vec3 d = normalize(mat3(modelMatrix) * position); float s = d.y, altDeg = asin(clamp(s, -1.0, 1.0)) * 57.29578;
        float m = aMag + 0.25 * (airmass(s, altDeg) - 1.0);                 // dimmer through more air
        float low = clamp(1.0 - s, 0.0, 1.0);
        float amp = (0.10 + 0.55 * low * low) * (1.0 - uStill) * (1.0 - 0.8 * aSteady);      // twinkling: more near the horizon; a planet hardly at all
        float tw = vnoise(aSeed + uTime * 11.0) * 0.65 + vnoise(aSeed * 1.7 + uTime * 23.0) * 0.35;
        float f = pow(10.0, -0.4 * m) * (1.0 + amp * (tw - 0.5) * 2.0);
        float vis = smoothstep(uLimit + 0.35, uLimit - 0.55, m) * (1.0 - 0.3 * min(uFlash, 2.0));
        float I = clamp(uK * pow(max(f, 0.0), uG), 0.0, 2.5) * vis;
        float tint = vnoise(aSeed * 3.1 + uTime * 17.0) - 0.5;
        vCol = aCol * (1.0 + vec3(tint, -tint * 0.6, tint * 0.4) * 0.6 * low * low * smoothstep(1.5, -0.5, m) * (1.0 - uStill) * (1.0 - aSteady));
        float R = 0.5 * (1.7 + 2.3 * pow(max(f, 0.0), 0.3)) * uPx;          // the reach of the star's light as tuned, in device pixels
        vI = I * 0.551 * R * R * max(1.0, 2.25 - 1.06 * exp(-0.35 * m));   // its total light
        vSc = max(0.5, 0.5 * uPx);                                          // the core's spread, in device pixels: fixed
        vSh = max(vSc, 0.48 * R);                                           // the skirt's
        vSize = max(5.0, ceil(6.0 * vSh) + 2.0);
        gl_PointSize = vSize;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        if (s < -0.01 || I < 0.003) gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
      }`,
    fragmentShader: `varying vec3 vCol; varying float vI, vSize, vSc, vSh;
      ${POINTFRAG_HEAD}
      void main(){ vec2 q = (gl_PointCoord - 0.5) * vSize;               // this pixel's centre, from the star, in pixels
        float a = 0.815 * share(q, vSc) + 0.185 * share(q, vSh);
        gl_FragColor = vec4(vCol * vI * a, 1.0);
        #include <colorspace_fragment>
      }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending});
  const stars = new THREE.Points(sg, starMat); stars.renderOrder = -9; stars.frustumCulled = false; cel.add(stars);

  /* the Moon: tonight's crescent where tonight has one, otherwise a young crescent; where it stands, or placed in view */
  const PHASE_ANGLE = W.frac >= 0.03 && W.frac <= 0.5 ? Math.acos(clamp(2 * W.frac - 1, -1, 1)) : Math.acos(2 * LOOK.youngMoon - 1);
  const moonGeo = new THREE.SphereGeometry(1, 48, 32);
  const moonTex = texOf(A.moon, true);
  const moonMat = new THREE.ShaderMaterial({
    uniforms: Object.assign({uMap: {value: moonTex}, uHasMap: {value: moonTex ? 1 : 0}, uSun: {value: V3(1, 0, 0)}, uLit: {value: LOOK.moonLit}, uEarth: {value: LOOK.moonEarth},
      uLow: {value: 0}}, U),
    vertexShader: `varying vec3 vN, vW; varying vec2 vUv; void main(){ vN = normalize(mat3(modelMatrix) * normal); vW = (modelMatrix * vec4(position, 1.0)).xyz; vUv = uv;
      gl_Position = projectionMatrix * viewMatrix * vec4(vW, 1.0); }`,
    fragmentShader: `uniform sampler2D uMap; uniform float uHasMap, uLit, uEarth, uAdapt, uLow; uniform vec3 uSun; varying vec3 vN, vW; varying vec2 vUv;
      void main(){ vec3 n = normalize(vN), v = normalize(cameraPosition - vW); float mu0 = max(dot(n, uSun), 0.0), mu = max(dot(n, v), 0.0);
        vec3 alb = uHasMap > 0.5 ? texture2D(uMap, vUv).rgb : vec3(0.32);
        vec3 tint = mix(vec3(1.0, 0.97, 0.90), vec3(1.0, 0.72, 0.45), uLow);
        vec3 c = alb * (mu0 / (mu0 + mu + 1e-4) * uLit * tint + uEarth * mix(0.5, 1.0, uAdapt) * vec3(0.62, 0.68, 0.80));
        gl_FragColor = vec4(c, 1.0);
        #include <colorspace_fragment>
      }`});
  const moon = new THREE.Mesh(moonGeo, moonMat); moon.renderOrder = -8; cel.add(moon);
  const halo = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({map: glowTex(), color: new THREE.Color(0.75, 0.78, 0.86), transparent: true, opacity: 0,
    blending: THREE.AdditiveBlending, depthWrite: false})); halo.renderOrder = -7; cel.add(halo);

  /* the mountains: the skyline of Longs Peak and Mount Meeker from a National Park Service photograph, black against the
     sky, the snow faintly grey in the starlight; beyond the photograph's sides it carries on in mirror image */
  const RM = A.ridgeMeta, SPAN = 74;      // the photograph shown across 74 degrees, its horizon at eye level
  const skyline = new Uint16Array(RM.sky.length);
  for (let i = 0; i < RM.sky.length; i++) skyline[i] = THREE.DataUtils.toHalfFloat(RM.top + RM.sky[i] / 8 * (RM.photo_w / RM.w));
  const skyTex = new THREE.DataTexture(skyline, RM.sky.length, 1, THREE.RedFormat, THREE.HalfFloatType); skyTex.minFilter = skyTex.magFilter = THREE.LinearFilter; skyTex.needsUpdate = true;
  const ridgeTex = texOf(A.ridge, true); ridgeTex.generateMipmaps = true;
  const landMat = new THREE.ShaderMaterial({
    uniforms: Object.assign({uRidge: {value: ridgeTex}, uSky: {value: skyTex}, uSpan: {value: SPAN}, uPW: {value: RM.photo_w}, uPH: {value: RM.photo_h}, uTop: {value: RM.top},
      uHzn: {value: RM.horizon}, uHor: {value: V3(...LOOK.hor)}, uMoonDir: {value: moonDir}, uMoonLit: {value: 0}}, U),
    vertexShader: `varying vec3 vDir; void main(){ vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `uniform sampler2D uRidge, uSky; uniform float uSpan, uPW, uPH, uTop, uHzn, uAdapt, uFlash, uMoonLit; uniform vec3 uHor, uFlashCol, uMoonDir; varying vec3 vDir;
      void main(){
        vec3 d = normalize(vDir); float az = atan(d.x, -d.z) * 57.29578, altDeg = asin(clamp(d.y, -1.0, 1.0)) * 57.29578;
        float k = uPW / uSpan, px = uPW * 0.5 + az * k, py = uHzn * uPH - altDeg * k;
        float u = px / uPW; u = 1.0 - abs(1.0 - mod(u, 2.0));
        float edge = texture2D(uSky, vec2(u, 0.5)).r;
        float a = clamp((py - edge) / max(fwidth(py), 0.001) + 0.5, 0.0, 1.0);
        if (a < 0.003) discard;
        float vv = (py - uTop) / (uPH - uTop);
        float g = texture2D(uRidge, vec2(u, 1.0 - clamp(vv, 0.0, 1.0))).r;
        float dark = mix(1.0, 0.55, smoothstep(1.0, 1.15, vv)) * mix(0.3, 1.0, smoothstep(-14.0, 1.0, altDeg));      // the valley floor lies in the dark
        /* At night the land is lit by the sky, from all of it at once, so the photograph's sunlit and shadowed faces are
           evened out (only a little of its relief is kept) and snow, the palest thing there, stays a grey a little below the
           sky behind it: snow lit by the sky cannot outshine the sky. The moon adds a little, on the faces toward it. Rock
           and forest are near black. */
        float snow = smoothstep(0.32, 0.80, g);
        float relief = mix(0.70, 1.0, smoothstep(0.30, 0.95, g));
        float moonSide = 0.5 + 0.5 * clamp(-uMoonDir.x * sign(uMoonDir.x) * 0.0 + dot(normalize(vec3(-d.x, 0.35, -d.z)), uMoonDir), -1.0, 1.0);
        vec3 c = uHor * (0.06 + 0.46 * snow) * relief * dark * mix(0.45, 1.0, uAdapt) * (1.0 + uMoonLit * (0.4 + 1.6 * snow) * moonSide);
        c += uHor * 0.22 * exp(-(py - edge) / 110.0) * mix(0.45, 1.0, uAdapt);      // the air between, faintly lit by the sky
        c += uFlashCol * uFlash * 0.03 * (g + 0.2);
        gl_FragColor = vec4(c, a);
        #include <colorspace_fragment>
      }`,
    side: THREE.BackSide, transparent: true, depthWrite: true});
  const land = new THREE.Mesh(new THREE.CylinderGeometry(600, 600, 600 * (Math.tan(28 * D2R) + Math.tan(26 * D2R)), 160, 1, true), landMat);
  land.position.y = 600 * (Math.tan(28 * D2R) - Math.tan(26 * D2R)) / 2; land.renderOrder = -6; sky.add(land);

  /* ---------- the materials: the planks (the big set on a computer), the logs, the ground, bark, rock, stone, boards ---------- */
  const texR = (img, srgb) => texOf(img, srgb, true);
  const HI = !!MORE.planks_diff;
  const [dD, dN, dA] = A.deck, [lD, lN] = A.logs;
  const plankMat = new THREE.MeshStandardMaterial({color: "#8d857b", roughness: 0.9, vertexColors: true});
  { const pd = MORE.planks_diff || dD, pn = MORE.planks_nor || dN, pa = MORE.planks_arm || dA;
    if (pd) { plankMat.map = texR(pd, true); plankMat.color.set("#ffffff"); }
    if (pn) { plankMat.normalMap = texR(pn, false); plankMat.normalScale.set(0.75, 0.75); }
    if (pa) { plankMat.roughnessMap = texR(pa, false); plankMat.aoMap = plankMat.roughnessMap; plankMat.aoMap.channel = 0; plankMat.roughness = 1; } }
  const deckMat = new THREE.MeshStandardMaterial({color: "#8d857b", roughness: 0.9});      // the same boards, plain texture coordinates: the chairs, the steps, the bench
  if (dD) { deckMat.map = texR(dD, true); deckMat.color.set("#ffffff"); }
  if (dN) { deckMat.normalMap = texR(dN, false); deckMat.normalScale.set(0.8, 0.8); }
  if (dA) { deckMat.roughnessMap = texR(dA, false); deckMat.aoMap = deckMat.roughnessMap; deckMat.aoMap.channel = 0; deckMat.roughness = 1; }
  const logMat = new THREE.MeshStandardMaterial({color: lD ? "#b3a596" : "#7a6450", roughness: 0.78});
  /* the photographed board is varnished and far more orange than weathered pine: most of that orange is taken out, so the
     rail reads as honey-coloured pine in the warm light, not rust */
  if (lD) { logMat.map = texR(lD, true); logMat.color.setRGB(0.363, 0.605, 0.605); }
  if (lN) { logMat.normalMap = texR(lN, false); logMat.normalScale.set(0.9, 0.9); }
  const darkWood = new THREE.MeshStandardMaterial({color: "#3b3129", roughness: 0.92});      // the deck's underside and the stringers: weathered, unlit by the window
  if (dD) { darkWood.map = texR(dD, true); darkWood.color.setRGB(0.42, 0.37, 0.33); }
  /* the forest floor under a crescent moon lies darker than the sky above the ridge, as it does in any dark-sky photograph:
     the photographed ground is taken well down */
  const groundMat = new THREE.MeshStandardMaterial({color: MORE.ground_diff ? "#ffffff" : "#121009", roughness: 1});
  if (MORE.ground_diff) { groundMat.map = texR(MORE.ground_diff, true); groundMat.map.repeat.set(35, 35); groundMat.color.setRGB(0.18, 0.165, 0.14); }
  if (MORE.ground_nor) { groundMat.normalMap = texR(MORE.ground_nor, false); groundMat.normalMap.repeat.set(35, 35); groundMat.normalScale.set(0.9, 0.9); }
  if (MORE.ground_arm) { groundMat.roughnessMap = texR(MORE.ground_arm, false); groundMat.roughnessMap.repeat.set(35, 35); groundMat.aoMap = groundMat.roughnessMap; groundMat.aoMap.channel = 0; }
  const barkMat = new THREE.MeshStandardMaterial({color: MORE.bark_diff ? "#c8bfb0" : "#3a2e24", roughness: 0.95});
  if (MORE.bark_diff) { barkMat.map = texR(MORE.bark_diff, true); }
  if (MORE.bark_nor) { barkMat.normalMap = texR(MORE.bark_nor, false); barkMat.normalScale.set(1.0, 1.0); }
  const rockMat = new THREE.MeshStandardMaterial({color: MORE.rock_diff ? "#bdbdb6" : "#454340", roughness: 0.95});
  if (MORE.rock_diff) { rockMat.map = texR(MORE.rock_diff, true); }
  if (MORE.rock_nor) { rockMat.normalMap = texR(MORE.rock_nor, false); rockMat.normalScale.set(0.8, 0.8); }
  const stoneMat = new THREE.MeshStandardMaterial({color: MORE.stone_diff ? "#d6d0c6" : "#5a544c", roughness: 0.95});
  if (MORE.stone_diff) { stoneMat.map = texR(MORE.stone_diff, true); stoneMat.map.repeat.set(1 / 1.6, 1 / 1.6); }
  if (MORE.stone_nor) { stoneMat.normalMap = texR(MORE.stone_nor, false); stoneMat.normalMap.repeat.set(1 / 1.6, 1 / 1.6); stoneMat.normalScale.set(1, 1); }
  if (MORE.stone_arm) { stoneMat.roughnessMap = texR(MORE.stone_arm, false); stoneMat.roughnessMap.repeat.set(1 / 1.6, 1 / 1.6); stoneMat.aoMap = stoneMat.roughnessMap; stoneMat.aoMap.channel = 0; }
  const boardsMat = new THREE.MeshStandardMaterial({color: "#2a2018", roughness: 0.85});
  if (MORE.boards) { boardsMat.map = texR(MORE.boards, true); boardsMat.map.repeat.set(5, 1); boardsMat.color.setRGB(0.42, 0.34, 0.27); }
  const trimMat = new THREE.MeshStandardMaterial({color: "#3e2c20", roughness: 0.75});
  if (dD) { trimMat.map = texR(dD, true); trimMat.color.setRGB(0.36, 0.25, 0.18); }
  const plaidMat = new THREE.MeshStandardMaterial({color: MORE.plaid ? "#d9cfc4" : "#6a4b36", roughness: 1});
  if (MORE.plaid) { plaidMat.map = texR(MORE.plaid, true); plaidMat.map.repeat.set(1.6, 1.6); }
  const iron = new THREE.MeshStandardMaterial({color: "#121212", roughness: 0.45, metalness: 0.7});

  /* ---------- the deck: planks, each one its own board; the rim and the posts beneath; the log railing; the steps ---------- */
  const deck = new THREE.Group(); scene.add(deck);
  const focusBoxes = [];      // what the eye can settle on, for the lens
  { const Q = new Quads(), D = L.deck, w = 0.2, gap = 0.008, th = 0.038, rows = Math.floor((0.862 - D.z0) / (w + gap)), rp = rng(seed ^ 0x51);
    const plank = (x0, x1, z0, z1, strip, off, tint) => {
      const su0 = strip / 5 + 0.012, su1 = (strip + 1) / 5 - 0.012, v0 = x0 / TEXW + off, v1 = x1 / TEXW + off, side = [tint[0] * 0.55, tint[1] * 0.55, tint[2] * 0.55];
      Q.quad([x0, 0, z1], [x1, 0, z1], [x1, 0, z0], [x0, 0, z0], [0, 1, 0], [su1, v0, su1, v1, su0, v1, su0, v0], tint);
      Q.quad([x0, -th, z1], [x1, -th, z1], [x1, 0, z1], [x0, 0, z1], [0, 0, 1], [su0, v0, su0, v1, su0 + 0.03, v1, su0 + 0.03, v0], side);
      Q.quad([x1, -th, z0], [x0, -th, z0], [x0, 0, z0], [x1, 0, z0], [0, 0, -1], [su1, v1, su1, v0, su1 - 0.03, v0, su1 - 0.03, v1], side);
      Q.quad([x1, -th, z1], [x1, -th, z0], [x1, 0, z0], [x1, 0, z1], [1, 0, 0], [su1, v1, su0, v1, su0, v1 + 0.03, su1, v1 + 0.03], side);
      Q.quad([x0, -th, z0], [x0, -th, z1], [x0, 0, z1], [x0, 0, z0], [-1, 0, 0], [su0, v0, su1, v0, su1, v0 - 0.03, su0, v0 - 0.03], side);
    };
    for (let j = 0; j < rows; j++) {
      const z0 = D.z0 + j * (w + gap) + 0.004, z1 = z0 + w - 0.008 + (rp() - 0.5) * 0.004;
      let x = D.x0, first = true;
      while (x < D.x1 - 0.05) {
        const len = first ? 1.2 + rp() * 2.4 : 2.4 + rp() * 1.8, x1 = Math.min(D.x1, x + len), g = 0.82 + rp() * 0.18, wt = (rp() - 0.5) * 2;
        plank(x, x1 - 0.004, z0, z1, Math.floor(rp() * 5), rp() * 3, [g * (1 + 0.04 * wt), g, g * (1 - 0.05 * wt)]);
        x = x1; first = false;
      }
    }
    const planks = new THREE.Mesh(Q.geometry(), plankMat); planks.receiveShadow = true; planks.castShadow = true; deck.add(planks);
    focusBoxes.push(new THREE.Box3(V3(D.x0, -0.1, D.z0), V3(D.x1, 0.02, D.z1)));
    /* the rim joist round the deck, the joists beneath and the posts down to the ground: what the yard sees under it */
    const Qu = new Quads(), under = [0.62, 0.6, 0.58];
    Qu.box(D.x0 - 0.02, -0.26, D.z0 - 0.045, D.x1 + 0.02, -0.04, D.z0, null, under); Qu.box(D.x0 - 0.045, -0.26, D.z0 - 0.045, D.x0, -0.04, D.z1 - 0.1, null, under); Qu.box(D.x1, -0.26, D.z0 - 0.045, D.x1 + 0.045, -0.04, D.z1 - 0.1, null, under);
    for (let x = D.x0 + 0.4; x < D.x1 - 0.3; x += 0.6) Qu.box(x - 0.02, -0.24, D.z0, x + 0.02, -0.04, D.z1 - 0.2, null, under);
    const underMesh = new THREE.Mesh(Qu.geometry(), darkWood); underMesh.receiveShadow = true; deck.add(underMesh);
    const posts = [];
    for (const [px, pz] of [[D.x0 + 0.2, D.z0 + 0.25], [-1.5, D.z0 + 0.25], [1.5, D.z0 + 0.25], [D.x1 - 0.2, D.z0 + 0.25], [D.x0 + 0.2, 0.3], [D.x1 - 0.2, 0.3]]) {
      const gy = groundY(px, pz) - 0.2, m = new THREE.Mesh(logGeo(-0.26 - gy, 0.085, 10), logMat); m.position.set(px, (gy - 0.26) / 2, pz); posts.push(m); }
    deck.add(merged(posts, logMat));
  }
  { /* the railing: posts, a top rail and a mid rail of round logs, balusters between; the right side opens for the steps,
       a newel post at each side of the opening, and a handrail down the steps */
    const RZ = L.rail.z, D = L.deck, S = L.steps, logs = [];
    const post = (x, z, h = 1.05, r = 0.065) => logs.push(logAt(h, r, logMat, x, h / 2 - 0.08, z, "y", deck, 12));
    const between = (a, b, r, seg = 12) => { const d = V3(...b).sub(V3(...a)), len = d.length(), m = new THREE.Mesh(logGeo(len, r, seg), logMat);
      m.position.copy(V3(...a).add(V3(...b)).multiplyScalar(0.5)); m.quaternion.setFromUnitVectors(V3(0, 1, 0), d.normalize()); m.castShadow = m.receiveShadow = true; deck.add(m); logs.push(m); return m; };
    const run = (a, b) => {      // a stretch of railing from a to b (on the deck's edge): the rails, the balusters
      const d = V3(...b).sub(V3(...a)), len = d.length(), dir = d.clone().normalize();
      between([a[0], L.rail.top, a[1]], [b[0], L.rail.top, b[1]], 0.06, 14); between([a[0], L.rail.mid, a[1]], [b[0], L.rail.mid, b[1]], 0.045, 12);
      for (let s = 0.16; s < len - 0.1; s += 0.16) { const p = V3(...a).addScaledVector(dir, s); logs.push(logAt(0.5, 0.022, logMat, p.x, 0.75, p.z, "y", deck, 7)); }
    };
    for (let x = D.x0 + 0.1; x <= D.x1 - 0.09; x += 1.1) post(x, RZ);
    run([D.x0 + 0.1, RZ], [D.x1 - 0.1, RZ]);
    post(D.x0 + 0.1, 0.84); run([D.x0 + 0.1, RZ], [D.x0 + 0.1, 0.84]);      // the left side, to the wall
    post(D.x1 - 0.1, S.z0 - 0.08, 1.12, 0.075); post(D.x1 - 0.1, S.z1 + 0.08, 1.12, 0.075); post(D.x1 - 0.1, 0.84);      // the right side: the newels either side of the steps
    run([D.x1 - 0.1, RZ], [D.x1 - 0.1, S.z0 - 0.08]); run([D.x1 - 0.1, S.z1 + 0.08], [D.x1 - 0.1, 0.84]);
    const foot = S.x0 + S.tread * S.n + 0.05, gy = groundY(foot, S.z0 - 0.08);
    logs.push(logAt(0.95 - gy, 0.06, logMat, foot, (0.95 + gy) / 2 - 0.02, S.z0 - 0.08, "y", deck, 10));
    between([D.x1 - 0.1, L.rail.top + 0.04, S.z0 - 0.08], [foot, 0.93, S.z0 - 0.08], 0.05, 12);      // the handrail down the steps
    const rail = merged(logs, logMat); rail.receiveShadow = rail.castShadow = true; deck.add(rail);
    focusBoxes.push(new THREE.Box3(V3(D.x0 - 0.1, 0.35, RZ - 0.08), V3(D.x1 + 0.1, 1.07, RZ + 0.08)), new THREE.Box3(V3(D.x0 - 0.02, 0.35, RZ), V3(D.x0 + 0.2, 1.07, 0.9)), new THREE.Box3(V3(D.x1 - 0.2, 0.35, RZ), V3(D.x1 + 0.02, 1.07, 0.9)));
    /* the steps: treads of two boards each, risers under their fronts, a stringer board each side */
    const Qs = new Quads(), tint = [0.9, 0.88, 0.84], dark = [0.5, 0.48, 0.45];
    for (let k = 1; k <= S.n; k++) {
      const x0 = S.x0 + S.tread * (k - 1), x1 = x0 + S.tread, y = -S.rise * k;
      Qs.box(x0 + 0.005, y - 0.036, S.z0, x0 + S.tread / 2 - 0.004, y, S.z1, [0.03, 0, 0.17, (S.z1 - S.z0) / TEXW], tint); Qs.box(x0 + S.tread / 2 + 0.004, y - 0.036, S.z0, x1 - 0.005, y, S.z1, [0.43, 0, 0.57, (S.z1 - S.z0) / TEXW], tint);
      Qs.box(x0, y - S.rise + 0.01, S.z0 + 0.02, x0 + 0.03, y - 0.036, S.z1 - 0.02, null, dark);
    }
    for (const zs of [S.z0 - 0.045, S.z1]) for (let k = 1; k <= S.n; k++) { const x0 = S.x0 + S.tread * (k - 1), y = -S.rise * k; Qs.box(x0 - 0.01, y - S.rise - 0.02, zs, x0 + S.tread + 0.01, y - 0.02, zs + 0.045, null, dark); }
    const steps = new THREE.Mesh(Qs.geometry(), plankMat); steps.castShadow = steps.receiveShadow = true; deck.add(steps);
    focusBoxes.push(new THREE.Box3(V3(S.x0, -1.0, S.z0), V3(S.x0 + S.tread * S.n, 0, S.z1)));
  }

  /* ---------- the furniture: two Adirondack chairs, a stump table with a mug, the bench by the wall, folded blankets ---------- */
  const chairMat = deckMat.clone(); chairMat.color.setRGB(0.92, 0.84, 0.74);
  const chairs = L.chairs.map(c => { const m = adirondack(chairMat); m.position.set(c.x, 0, c.z); m.rotation.y = c.ry; scene.add(m); focusBoxes.push(new THREE.Box3().setFromObject(m)); return m; });
  const inChair = on => { chairs[0].back.visible = !on; };      // the reader's own chair: its back is not drawn while they sit in it
  inChair(true);
  { const b = new THREE.Mesh(blanketGeo(0.46, 0.09, 0.3, 61), plaidMat); b.position.set(L.chairs[1].x + 0.02, 0.52, L.chairs[1].z + 0.02); b.rotation.set(0.42, L.chairs[1].ry, 0.03); b.castShadow = b.receiveShadow = true; scene.add(b); }      // a folded blanket over the empty chair's seat
  { const T = L.table, stump = new THREE.Mesh(trunkGeo(0.2, 0.5, 71), barkMat); stump.position.set(T.x, 0.25, T.z); stump.castShadow = stump.receiveShadow = true; scene.add(stump);
    const top = new THREE.Mesh(new THREE.CylinderGeometry(T.r, T.r, 0.04, 28), deckMat); top.position.set(T.x, 0.52, T.z); top.castShadow = top.receiveShadow = true; scene.add(top);
    const enamel = new THREE.MeshStandardMaterial({color: "#5d6f7a", roughness: 0.35, metalness: 0.15});
    const mug = new THREE.Mesh(new THREE.CylinderGeometry(0.044, 0.04, 0.1, 20), enamel); mug.position.set(T.x - 0.07, 0.59, T.z + 0.04); mug.castShadow = true; scene.add(mug);
    const handle = new THREE.Mesh(new THREE.TorusGeometry(0.03, 0.006, 8, 16, Math.PI), enamel); handle.position.set(T.x - 0.028, 0.6, T.z + 0.04); handle.rotation.set(0, 0, -Math.PI / 2); scene.add(handle);
    focusBoxes.push(new THREE.Box3(V3(T.x - T.r, 0, T.z - T.r), V3(T.x + T.r, 0.62, T.z + T.r))); }
  { const B = L.bench, Qb = new Quads(), rb = rng(seed ^ 0x77), info = benchParts(Qb, B.x0, B.x1, B.z, [0.03, 0.17], rb), bench = new THREE.Mesh(Qb.geometry(), plankMat); bench.castShadow = bench.receiveShadow = true; scene.add(bench);
    for (const [lx, lz] of info.legs) { const leg = new THREE.Mesh(logGeo(0.42, 0.19, 14), logMat); leg.position.set(lx, 0.19, lz); leg.rotation.x = Math.PI / 2; leg.castShadow = leg.receiveShadow = true; scene.add(leg); }
    const bl = new THREE.Mesh(blanketGeo(0.42, 0.11, 0.34, 67), plaidMat); bl.position.set(B.x1 - 0.3, info.seat + 0.055, B.z - 0.01); bl.rotation.y = 0.12; bl.castShadow = bl.receiveShadow = true; scene.add(bl);
    focusBoxes.push(new THREE.Box3(V3(B.x0, 0, B.z - 0.25), V3(B.x1, 0.6, B.z + 0.25))); }

  /* ---------- the trees: pines in silhouette; the near ones with trunks of their own ---------- */
  const trees = [], treeTex = {};
  const treeMat = (tex) => new THREE.MeshBasicMaterial({map: tex, color: new THREE.Color(0.00035, 0.0004, 0.00055), alphaTest: 0.5, alphaToCoverage: true, side: THREE.DoubleSide});
  const treeList = TREES.concat(NEAR_TREES).concat(WATCH ? TREES_MORE.slice(0, LEAN ? 4 : 8) : []);
  for (const [x, z, h, kind, s] of treeList) {
    const key = kind + s, tex = treeTex[key] || (treeTex[key] = conifer(s, kind));
    const m = new THREE.Mesh(new THREE.PlaneGeometry(h * 320 / 1024, h), treeMat(tex));
    m.position.set(x, h / 2 + groundY(x, z) - 0.6, z); m.lookAt(EYE.x, m.position.y, EYE.z); m.userData = {s, x, z, h}; scene.add(m); trees.push(m);
  }
  for (const [x, z, h, kind, s, r] of NEAR_TREES) {
    const gy = groundY(x, z), th = h * 0.62, m = new THREE.Mesh(trunkGeo(r, th, s), barkMat); m.position.set(x, gy - 0.15 + th / 2, z); m.castShadow = m.receiveShadow = true; scene.add(m);
    focusBoxes.push(new THREE.Box3(V3(x - r, gy, z - r), V3(x + r, gy + th, z + r)));
  }

  /* ---------- the yard: the ground falling toward the valley, boulders, a little mist far out ---------- */
  const yard = new THREE.Group(); scene.add(yard);
  { const gg = new THREE.PlaneGeometry(70, 70, 56, 56); gg.rotateX(-Math.PI / 2); const P = gg.attributes.position;
    for (let i = 0; i < P.count; i++) P.setY(i, groundY(P.getX(i), P.getZ(i)));
    gg.computeVertexNormals(); const ground = new THREE.Mesh(gg, groundMat); ground.receiveShadow = true; yard.add(ground);
    focusBoxes.push(new THREE.Box3(V3(-35, -8, -35), V3(35, -0.5, 1)));
    for (const [bx, bz, br, bs, sx, sy, sz] of BOULDERS) { const b = new THREE.Mesh(boulderGeo(bs, br, sx, sy, sz), rockMat); b.position.set(bx, groundY(bx, bz) + br * sy * 0.35, bz); b.rotation.y = bs * 0.37; b.castShadow = b.receiveShadow = true; yard.add(b);      // bedded into the ground, its flattened underside buried
      focusBoxes.push(new THREE.Box3().setFromObject(b)); } }
  /* soft points: the mist over the yard, the smoke from the chimney, the moths at the lantern */
  const softMat = (tex, color, additive) => new THREE.ShaderMaterial({uniforms: {uMap: {value: tex}, uColor: {value: new THREE.Color(...color)}, uScale: {value: 1}, uPx: U.uPx},
    vertexShader: SOFT_VERT, fragmentShader: SOFT_FRAG, transparent: true, depthWrite: false, blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending});
  const softPoints = (count, tex, color, additive) => {
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(count * 3), 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute("aSize", new THREE.BufferAttribute(new Float32Array(count), 1).setUsage(THREE.DynamicDrawUsage)); g.setAttribute("aAlpha", new THREE.BufferAttribute(new Float32Array(count), 1).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute("aCol", new THREE.BufferAttribute(new Float32Array(count * 3).fill(1), 3).setUsage(THREE.DynamicDrawUsage));
    const p = new THREE.Points(g, softMat(tex, color, additive)); p.frustumCulled = false; return p;
  };
  const puff = puffTex(seed ^ 0x99);
  const MIST = WATCH ? (LEAN ? 6 : 10) : 6, mist = softPoints(MIST, puff, [1, 1, 1], false), mistSeeds = Array.from({length: MIST}, (_, i) => ({x: -9 + 18 * ((i + 0.5) / MIST) + (R() - 0.5) * 2, z: -5.5 - R() * 4, s: 6 + R() * 5, ph: R() * 6.3}));
  mist.renderOrder = 3; yard.add(mist);
  const SMOKE = WATCH ? (LEAN ? 24 : 40) : 0, smoke = SMOKE ? softPoints(SMOKE, puff, [1, 1, 1], false) : null; if (smoke) { smoke.renderOrder = 4; scene.add(smoke); }
  const smokeSeeds = Array.from({length: SMOKE}, (_, i) => ({t0: i / SMOKE * 9, life: 9, a: R() * 6.3, b: R() * 6.3, c: 0.5 + R()}));
  const MOTHS = WATCH ? 6 : 0, moths = MOTHS ? softPoints(MOTHS, glowTex(), [1.0, 0.86, 0.6], true) : null; if (moths) { moths.renderOrder = 8; scene.add(moths); }
  const mothSeeds = Array.from({length: MOTHS}, () => ({a: R() * 6.3, b: R() * 6.3, f: 1.4 + R() * 1.6, r: 0.08 + R() * 0.2}));

  /* ---------- light: the great room's glass behind you (its lamps and its fire), the lantern by the door, the moon, the sky, a fireball when it comes ---------- */
  const win = new THREE.SpotLight("#ffd2a6", LOOK.window, 32, 1.02, 0.65, 2.0);      // the lamps' light through the wall of glass, as eyes that have adjusted to it see it: the posts, mullions and transoms bar it
  win.position.set(0.85, 1.55, 5.05); win.target.position.set(0.3, 0.1, -1.7); win.castShadow = true; win.shadow.mapSize.setScalar(LEAN ? 512 : 1024); win.shadow.bias = -0.0004; win.shadow.normalBias = 0.02;
  win.shadow.camera.near = 0.5; win.shadow.camera.far = 18; scene.add(win, win.target);
  const spill = new THREE.SpotLight("#ff9a4c", LOOK.spill, 24, 0.82, 0.8, 2.0);      // the fire's own light, from the hearth on the right-hand wall, flickering out through the glass over the boards
  spill.position.set(4.4, 0.95, 6.87); spill.target.position.set(0.0, -0.2, -1.4); spill.castShadow = true; spill.shadow.mapSize.setScalar(512); spill.shadow.bias = -0.0005; spill.shadow.normalBias = 0.03;
  spill.shadow.camera.near = 0.5; spill.shadow.camera.far = 20; scene.add(spill, spill.target);
  const bounce = new THREE.PointLight("#ffbd85", LOOK.bounce, 2.6, 2); bounce.position.set(0.4, 0.16, L.wall.z - 0.8); scene.add(bounce);      // the room's light thrown back up off the boards: just above them, so it lights the boards, the chairs and the wall, never the yard beneath
  const flameAt = V3(L.lantern.x, L.lantern.y - 0.02, L.wall.z - 0.33);
  const lantern = new THREE.PointLight("#ffb46a", LOOK.lantern, 7, 2); lantern.position.copy(flameAt).add(V3(0, 0.03, -0.04)); scene.add(lantern);
  const hemi = new THREE.HemisphereLight("#9fb0d8", "#1a1410", LOOK.sky); scene.add(hemi);      // the sky's light: blue-grey from above, next to nothing from the dark ground
  const moonLight = new THREE.DirectionalLight("#9fb3dc", 0); moonLight.castShadow = true; moonLight.shadow.mapSize.setScalar(LEAN ? 1024 : 2048);
  moonLight.shadow.camera.left = moonLight.shadow.camera.bottom = -9; moonLight.shadow.camera.right = moonLight.shadow.camera.top = 9; moonLight.shadow.camera.near = 1; moonLight.shadow.camera.far = 90;
  moonLight.shadow.bias = -0.0006; moonLight.shadow.normalBias = 0.025; moonLight.shadow.radius = 3; scene.add(moonLight, moonLight.target);
  const flashLight = new THREE.DirectionalLight("#cfe8d8", 0); scene.add(flashLight, flashLight.target);
  /* the cabin's measurements, as the room has them: the walls' logs, the eave and the ridge, the roof's slope, the glass */
  const CB = L.wall, LR = CB.logR, STEP = CB.course, HX = CB.half, HE = CB.eave, HR = CB.ridge, GL = L.glass, DR = L.door, WZ = CB.z;
  const GZ = WZ + 2 * LR - 0.02, RZ0 = WZ + 2 * LR, RZ1 = RZ0 + CB.depth;      // the glass plane, and the room's inside from the front wall to the back
  const slopeY = x => HE + (HR - HE) * (1 - Math.abs(x) / HX), xMax = y => y <= HE ? HX : HX * (HR - y) / (HR - HE), top = x => slopeY(x) - 0.05;
  const brassMat = new THREE.MeshStandardMaterial({color: "#b8894a", roughness: 0.35, metalness: 0.9});
  const facade = facadeOf();
  const cabin = WATCH ? roomBehind() : null;

  /* ---------- the front of the cabin: the great room's gable end, as the room itself would be seen from its deck ---------- */
  /* Built for the crossing too: the frame of the glass bars the room's light on the boards, the log wall catches the
     lantern's. Log courses either side of the glass with their ends proud of the corners, shortening with the roof above
     the eave; the posts, mullions and transoms of the glass; the sill; the header log under the roof; the glazed door at
     the right, with its brass lever; the lantern on its bracket beside the door; the side walls' logs running back. */
  function facadeOf(){
    const g = new THREE.Group(); scene.add(g);
    const rl = rng(91), logs = [];
    const box = (w, h, d, mat, x, y, z, shadow = true) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); m.receiveShadow = true; m.castShadow = shadow; g.add(m); return m; };
    const logBetween = (a, b, r, seg = 12) => { const d = b.clone().sub(a), len = d.length(), m = new THREE.Mesh(logGeo(len, r, seg), logMat); m.position.copy(a).add(b).multiplyScalar(0.5); m.quaternion.setFromUnitVectors(V3(0, 1, 0), d.normalize()); m.castShadow = m.receiveShadow = true; g.add(m); return m; };
    const cuts = [[GL.x0 - 0.08, GL.x1 + 0.08, GL.y0 - LR, 99], [DR.x0 - 0.1, DR.x1 + 0.1, -1, DR.y1 + 0.12]];
    for (let k = 0; k < 40; k++) {
      const y = LR + k * STEP; if (y - LR > HR - 0.25) break;
      const r = LR * (0.95 + 0.1 * rl()), xm = xMax(y) + (y <= HE ? 0.3 : -0.02); if (xm < 0.3) break;
      let from = -xm; const here = cuts.filter(c => y > c[2] && y - LR < c[3]).sort((a, b) => a[0] - b[0]);
      for (const c of here) { if (c[0] - from > 0.12) logs.push(logAt(c[0] - from, r, logMat, (from + c[0]) / 2, y, WZ + LR, "x", g, 16)); from = Math.max(from, c[1]); }
      if (xm - from > 0.12) logs.push(logAt(xm - from, r, logMat, (from + xm) / 2, y, WZ + LR, "x", g, 16));
    }
    for (let k = 0; k < 14; k++) {      // the side walls, half a course up, from the front corner to the back
      const y = LR + k * STEP + STEP / 2; if (y + LR > HE + 0.14) break; const r = LR * (0.95 + 0.1 * rl());
      for (const s of [-1, 1]) logs.push(logAt(RZ1 + 0.3 - (WZ - 0.13), r, logMat, s * (HX + LR + 0.02), y, (WZ - 0.13 + RZ1 + 0.3) / 2, "z", g, 14));
    }
    const wall = merged(logs, logMat); wall.receiveShadow = wall.castShadow = true; g.add(wall);
    focusBoxes.push(new THREE.Box3(V3(-HX - 0.3, -1, WZ - 0.1), V3(-GL.x0 + 0.1, HE, WZ + 0.4)), new THREE.Box3(V3(GL.x1 - 0.1, -1, WZ - 0.1), V3(HX + 0.3, HE, WZ + 0.4)));
    /* the frame of the glass: posts, mullions, transoms, the sill up to the door, the header log following the roof */
    const post = x => box(0.14, top(x) - GL.y0, 0.2, trimMat, x, (top(x) + GL.y0) / 2, GZ);
    post(GL.x0); post(GL.x1); for (const x of GL.mull) box(0.08, top(x) - GL.y0, 0.12, trimMat, x, (top(x) + GL.y0) / 2, GZ);
    for (const y of GL.trans) { const xr = Math.min(GL.x1, xMax(y + 0.05) - 0.02); box(2 * xr, 0.08, 0.12, trimMat, 0, y, GZ); }
    box(DR.x0 - 0.05 - (GL.x0 - 0.25), 0.1, 0.46, trimMat, (GL.x0 - 0.25 + DR.x0 - 0.05) / 2, GL.y0 - 0.05, WZ + LR + 0.08);
    box(GL.x1 + 0.25 - (DR.x1 + 0.05), 0.1, 0.46, trimMat, (DR.x1 + 0.05 + GL.x1 + 0.25) / 2, GL.y0 - 0.05, WZ + LR + 0.08);
    for (const s of [-1, 1]) logBetween(V3(s * (GL.x1 + 0.1), slopeY(GL.x1) - 0.3, GZ - 0.02), V3(s * 0.02, slopeY(0) - 0.3, GZ - 0.02), 0.1, 10);
    /* the glazed door: its frame, the rail across, the kick panel, the threshold, the lever */
    const dmx = (DR.x0 + DR.x1) / 2, dw = DR.x1 - DR.x0;
    for (const x of [DR.x0, DR.x1]) box(0.09, DR.y1 + 0.05, 0.16, trimMat, x, (DR.y1 + 0.05) / 2, GZ - 0.02);
    box(dw, 0.1, 0.16, trimMat, dmx, DR.y1, GZ - 0.02); box(dw, 0.07, 0.12, trimMat, dmx, 1.02, GZ - 0.03);
    box(dw, 0.36, 0.1, trimMat, dmx, 0.2, GZ - 0.03); box(dw + 0.2, 0.05, 0.3, trimMat, dmx, 0.025, WZ + LR + 0.02);
    box(0.12, 0.022, 0.022, brassMat, DR.x0 + 0.13, 1.0, GZ - 0.11, false); const kn = box(0.028, 0.028, 0.08, brassMat, DR.x0 + 0.08, 1.0, GZ - 0.08, false); kn.rotation.x = Math.PI / 2;
    focusBoxes.push(new THREE.Box3(V3(DR.x0 - 0.1, 0, GZ - 0.12), V3(DR.x1 + 0.1, DR.y1 + 0.1, GZ + 0.1)), new THREE.Box3(V3(GL.x0 - 0.1, GL.y0 - 0.1, GZ - 0.12), V3(GL.x1 + 0.1, HR, GZ + 0.12)));
    /* the lantern on its bracket beside the door, its flame, and a little of its light on the logs */
    const glassM = new THREE.MeshStandardMaterial({color: "#ffd9a0", roughness: 0.15, metalness: 0, transparent: true, opacity: 0.22, emissive: new THREE.Color(0.9, 0.5, 0.18), emissiveIntensity: 0.9});
    lanternParts(g, iron, glassM, L.lantern.x, L.lantern.y, WZ);
    const flame = new THREE.Sprite(new THREE.SpriteMaterial({map: flameTex(), color: new THREE.Color(1, 0.9, 0.7), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false}));
    flame.position.copy(flameAt); flame.scale.set(0.05, 0.085, 1); flame.renderOrder = 7; g.add(flame);
    const lanternGlow = new THREE.Sprite(new THREE.SpriteMaterial({map: glowTex(), color: new THREE.Color(0.55, 0.32, 0.12), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, opacity: 0.6}));
    lanternGlow.position.copy(flameAt); lanternGlow.scale.set(0.9, 0.9, 1); lanternGlow.renderOrder = 7; g.add(lanternGlow);
    return {flame, lanternGlow, update(flick2){ flame.scale.set(0.045 + 0.012 * flick2, 0.075 + 0.02 * flick2, 1); lanternGlow.material.opacity = 0.45 + 0.2 * flick2; }};
  }

  /* ---------- the room behind the glass, and the rest of the cabin: only on the deck to sit on, since the crossing never looks back ---------- */
  /* The great room as the cabin draws it, from outside: the glass, with the deck's night reflected in it; the roof over the
     ridge with its purlin ends out over the deck, the rake, the chimney up the right-hand end; and inside, lit by its own
     lamps and fire, the floor and the rug, the leather sofa facing the fire with a throw and a pillow, the two armchairs,
     the coffee table, the lamps at the sofa's ends, the lantern chandelier over the rug, the stone fireplace with the fire
     burning in it and the mantel, the loft over the back with its log railing and the stair up to it, the plank door in
     the back wall, the rocking chair by the glass, the curtains tied back. */
  function roomBehind(){
    const g = new THREE.Group(); scene.add(g);
    const rl = rng(93), LOFT_Z = RZ1 - 2.2, LOFT_Y = 3.0, RY1 = HR;
    const box = (w, h, d, mat, x, y, z, shadow = true) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); m.receiveShadow = true; m.castShadow = shadow; g.add(m); return m; };
    /* the roof: two slopes of boards from the ridge down past the eaves, their undersides the room's ceiling; the rake
       boards over the deck; the ridge log and the purlins whose ends come out through the gable over the deck */
    { const RF = L.roof, z0 = RF.z0, z1 = RZ1 + LR + RF.over, len = z1 - z0, xe = HX + RF.over, ye = slopeY(xe), slope = Math.hypot(xe, HR - ye), th = Math.atan2(HR - ye, xe);
      const roofMat = boardsMat.clone(); roofMat.side = THREE.DoubleSide; roofMat.map = boardsMat.map ? boardsMat.map.clone() : null;
      if (roofMat.map) { roofMat.map.repeat.set(slope / 1.5, len / 1.5); roofMat.map.needsUpdate = true; } roofMat.color.setRGB(0.3, 0.26, 0.22);
      for (const s of [-1, 1]) { const pg = new THREE.PlaneGeometry(slope, len); pg.rotateX(-Math.PI / 2); pg.rotateZ(-s * th);
        const roof = new THREE.Mesh(pg, roofMat); roof.position.set(s * xe / 2, (HR + ye) / 2, (z0 + z1) / 2); roof.receiveShadow = roof.castShadow = true; g.add(roof);
        const rake = new THREE.Mesh(new THREE.BoxGeometry(slope + 0.1, 0.22, 0.05), trimMat); rake.position.set(s * xe / 2, (HR + ye) / 2 - 0.08, z0 - 0.01); rake.rotation.z = -s * th; g.add(rake); }
      const ridgeEnd = logAt(RF.over + 0.6, 0.19, logMat, 0, HR - 0.38, WZ - RF.over / 2 + 0.3, "z", g, 12); ridgeEnd.castShadow = false;
      for (const s of [-1, 1]) logAt(RF.over + 0.5, 0.14, logMat, s * 2.6, slopeY(2.6) - 0.46, WZ - RF.over / 2 + 0.25, "z", g, 12); }
    /* the chimney: stacked stone up the outside of the right-hand wall, rising past the roof, a slab on top */
    { const C = L.chimney, Qc = new Quads(), gy = groundY((C.x0 + C.x1) / 2, (C.z0 + C.z1) / 2) - 0.2;
      Qc.box(C.x0, gy, C.z0, C.x1, C.top, C.z1, [0, 0, (C.x1 - C.x0) / 1.6, (C.z1 - C.z0) / 1.6], [1, 1, 1]);
      const chimney = new THREE.Mesh(Qc.geometry(), stoneMat); chimney.castShadow = chimney.receiveShadow = true; g.add(chimney);
      box(C.x1 - C.x0 + 0.2, 0.08, C.z1 - C.z0 + 0.2, stoneMat, (C.x0 + C.x1) / 2, C.top + 0.04, (C.z0 + C.z1) / 2);
      focusBoxes.push(new THREE.Box3(V3(C.x0, gy, C.z0), V3(C.x1, C.top, C.z1))); }
    /* the room's own light: the two lamps at the sofa's ends, the chandelier over the rug, the fire in the hearth on the
       right-hand wall; shared by every surface inside and by the glass */
    const FIREP = V3(HX - 0.55, 0.85, 6.87), LAMPS = [V3(0.85, 1.12, 5.05), V3(0.85, 1.12, 8.5), V3(2.2, 3.3, 6.77)];
    const RU = {uFlick: {value: 1}, uLampI: {value: LOOK.lampI.slice()}, uFireI: {value: LOOK.fireI}, uLampP: {value: LAMPS}, uFireP: {value: FIREP},
                uOccMin: {value: V3(99, 99, 99)}, uOccMax: {value: V3(99, 99, 99)}, uRoomMin: {value: V3(-HX, 0, RZ0)}, uRoomMax: {value: V3(HX, RY1, RZ1)}};
    /* the glass: one sheet shaped to the roof, the deck's night reflected in it (GLASS_FRAG), the panes of the frame */
    const shape = new THREE.Shape(); shape.moveTo(GL.x0, 0.02); shape.lineTo(GL.x1, 0.02); shape.lineTo(GL.x1, top(GL.x1)); shape.lineTo(0, top(0)); shape.lineTo(GL.x0, top(GL.x0)); shape.closePath();
    const glassMat = new THREE.ShaderMaterial({uniforms: {uRef: {value: null}, uHasRef: {value: 0}, uRefVP: {value: new THREE.Matrix4()}, uRefK: {value: LOOK.glassRef},
      uLampI: {value: LOOK.lampI[0]}, uFlick: RU.uFlick, uLampP: {value: LAMPS[0]}, uUv0: {value: new THREE.Vector2(GL.x0, 0.02)}, uUvSize: {value: new THREE.Vector2(GL.x1 - GL.x0, top(0) - 0.02)}, uPanes: {value: new THREE.Vector2(3, 4)}},
      vertexShader: "varying vec3 vW; varying vec2 vUv; void main(){ vW = (modelMatrix * vec4(position, 1.0)).xyz; vUv = uv; gl_Position = projectionMatrix * viewMatrix * vec4(vW, 1.0); }",
      fragmentShader: GLASS_FRAG, transparent: true, depthWrite: false, side: THREE.DoubleSide, blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor});
    const glass = new THREE.Mesh(new THREE.ShapeGeometry(shape), glassMat); glass.position.z = GZ; glass.renderOrder = 2; g.add(glass);
    /* what the glass shows of the night in front of it: drawn from the eye's mirror image behind the glass, through the
       glass's own outline (its near plane on the glass, so nothing behind the glass is drawn), onto a corner of the screen
       just before a frame covers it, and copied from there; drawn again when the eye has moved. The stars are left out:
       against a lit room their reflections are far too faint to see (the moon's is not) */
    const PAD = 0.04, RW0 = LEAN ? 256 : 512, RASP = (top(0) - 0.02 + 2 * PAD) / (GL.x1 - GL.x0 + 2 * PAD), refCam = new THREE.PerspectiveCamera(), refAt = V3(1e9, 0, 0);
    let refTex = null, lastRef = -1e9;
    const reflect = (eye, t) => {
      if (refTex && eye.distanceTo(refAt) < 0.45) return;
      if (refTex && t - lastRef < 0.4) return;
      const ME = V3(eye.x, eye.y, 2 * GZ - eye.z);
      refCam.position.copy(ME); refCam.updateMatrixWorld();
      refCam.projectionMatrix.makePerspective(GL.x0 - PAD - ME.x, GL.x1 + PAD - ME.x, top(0) + PAD - ME.y, 0.02 - PAD - ME.y, Math.max(0.05, ME.z - GZ), 3000);
      refCam.projectionMatrixInverse.copy(refCam.projectionMatrix).invert();
      const pr = renderer.getPixelRatio(), size = renderer.getDrawingBufferSize(new THREE.Vector2());
      const RW = Math.min(RW0, size.x, Math.floor(size.y / RASP)), RH = Math.round(RW * RASP);
      if (RW < 32) return;
      const target = renderer.getRenderTarget();
      const hide = [glass, stars, streaks, heads, fbGlow, moths, smoke].filter(Boolean), was = hide.map(o => o.visible), keep = [sky.position.clone(), U.uAdapt.value, U.uLimit.value, U.uFlash.value];
      const vp = renderer.getViewport(new THREE.Vector4()), sc = renderer.getScissor(new THREE.Vector4()), sct = renderer.getScissorTest();
      for (const o of hide) o.visible = false;
      sky.position.copy(ME); U.uAdapt.value = 1; U.uLimit.value = 6.3; U.uFlash.value = 0;      // eyes used to the dark, as they are by the time they turn round
      try {
        renderer.setRenderTarget(null); renderer.setViewport(0, 0, RW / pr, RH / pr); renderer.setScissor(0, 0, RW / pr, RH / pr); renderer.setScissorTest(true);
        renderer.render(scene, refCam);
        if (!refTex || refTex.image.width !== RW || refTex.image.height !== RH) { if (refTex) refTex.dispose(); refTex = new THREE.FramebufferTexture(RW, RH); refTex.minFilter = refTex.magFilter = THREE.LinearFilter; }
        renderer.copyFramebufferToTexture(refTex, new THREE.Vector2(0, 0));
        glassMat.uniforms.uRef.value = refTex; glassMat.uniforms.uHasRef.value = 1;
        glassMat.uniforms.uRefVP.value.multiplyMatrices(refCam.projectionMatrix, refCam.matrixWorldInverse);
        refAt.copy(eye); lastRef = t;
      } catch (e) { /* the glass keeps a plain dark reflection */ }
      renderer.setScissorTest(sct); renderer.setScissor(sc); renderer.setViewport(vp); renderer.setRenderTarget(target);
      hide.forEach((o, i) => { o.visible = was[i]; });
      sky.position.copy(keep[0]); U.uAdapt.value = keep[1]; U.uLimit.value = keep[2]; U.uFlash.value = keep[3];
    };
    /* inside: everything takes the room's own light (ROOM_FRAG) */
    const texs = new Map([[lD, logMat.map], [dD, deckMat.map]]);
    const tx = img => !img ? null : img.isTexture ? img : texs.get(img) || texs.set(img, texOf(img, true, true)).get(img);
    const rmat = (img, tint, rep, o = {}) => new THREE.ShaderMaterial({uniforms: Object.assign({uMap: {value: tx(img)}, uHas: {value: img ? 1 : 0},
      uTint: {value: new THREE.Color(...tint)}, uRep: {value: new THREE.Vector2(...rep)}, uTri: {value: o.tri || 0}, uLog: {value: o.log ? 1 : 0}, uThin: {value: o.thin ? 1 : 0},
      uSpec: {value: o.spec || 0}, uOcc: {value: o.occ === false ? 0 : 1}, uCav: {value: V3(...(o.cav || [0, 0, 0]))}}, RU),
      vertexShader: ROOM_VERT, fragmentShader: ROOM_FRAG, side: o.side || THREE.FrontSide});
    const add = (geo, mat, x = 0, y = 0, z = 0, parent = g) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); parent.add(m); return m; };
    const LOGT = [0.5, 0.64, 0.66];      // the pine's own orange, taken down as on the railing
    const logsIn = rmat(lD, LOGT, [1, 1], {log: true}), boardsIn = rmat(MORE.boards || dD, MORE.boards ? [0.42, 0.37, 0.33] : [0.36, 0.44, 0.45], [1, 1], {cav: [1, 0, 1]});
    const noOcc = {occ: false};
    /* the side walls from inside, the back wall with its plank door, the gable above it */
    const inner = [], far = [], backCut = [-2.35, -1.05, -1, 2.2];
    for (let k = 0; k < 14; k++) { const y = LR + k * STEP + STEP / 2; if (y + LR > HE + 0.14) break; const r = LR * (0.95 + 0.1 * rl());
      for (const s of [-1, 1]) inner.push(logAt(RZ1 - RZ0 + 0.3, r, null, s * (HX + LR - 0.02), y, (RZ0 + RZ1) / 2, "z", g, 14)); }
    for (let k = 0; k < 40; k++) { const y = LR + k * STEP; if (y - LR > HR - 0.25) break; const r = LR * (0.95 + 0.1 * rl()), xm = xMax(y) - 0.02; if (xm < 0.3) break;
      let from = -xm; if (y > backCut[2] && y - LR < backCut[3]) { if (backCut[0] - from > 0.12) far.push(logAt(backCut[0] - from, r, null, (from + backCut[0]) / 2, y, RZ1 + LR, "x", g, 14)); from = backCut[1]; }
      if (xm - from > 0.12) far.push(logAt(xm - from, r, null, (from + xm) / 2, y, RZ1 + LR, "x", g, 14)); }
    g.add(merged(inner, rmat(lD, LOGT, [1, 1], {log: true, cav: [0, 1, 1]})), merged(far, rmat(lD, LOGT, [1, 1], {log: true, cav: [1, 1, 0]})));
    const backing = rmat(null, [0.07, 0.05, 0.035], [1, 1], noOcc);
    for (const s of [-1, 1]) { const b = add(new THREE.PlaneGeometry(RZ1 - RZ0 + 0.3, HE + 0.4), backing, s * (HX + LR - 0.02), (HE + 0.4) / 2, (RZ0 + RZ1) / 2); b.rotation.y = -s * Math.PI / 2; }
    { const b = add(new THREE.PlaneGeometry(2 * HX, HR), backing, 0, HR / 2, RZ1 + LR); b.rotation.y = Math.PI; }
    const plankDoor = add(new THREE.BoxGeometry(1.28, 2.14, 0.07), rmat(MORE.boards, MORE.boards ? [0.5, 0.42, 0.34] : [0.3, 0.22, 0.15], [0.9, 1.4], noOcc), -1.7, 1.07, RZ1 + 0.02);
    for (const yy of [0.6, 1.5]) add(new THREE.BoxGeometry(1.0, 0.08, 0.03), rmat(null, [0.12, 0.08, 0.05], [1, 1], noOcc), -1.7, yy, RZ1 - 0.04);
    /* the floor and the rug in front of the fire */
    const floor = add(new THREE.PlaneGeometry(2 * HX, RZ1 - RZ0), rmat(dD, [0.5, 0.4, 0.3], [5.2, 4.5], {cav: [1, 0, 1]}), 0, 0.02, (RZ0 + RZ1) / 2); floor.rotation.x = -Math.PI / 2;
    const rugTex = canvasTex(384, 288, (c, w, h) => { c.fillStyle = "#1c2946"; c.fillRect(0, 0, w, h); c.fillStyle = "#7a1d18"; c.fillRect(34, 34, w - 68, h - 68);
      c.strokeStyle = "#e6d9bf"; c.lineWidth = 4; c.strokeRect(14, 14, w - 28, h - 28); c.lineWidth = 2; c.strokeStyle = "#c3923a"; c.strokeRect(44, 44, w - 88, h - 88);
      c.fillStyle = "#1c2946"; c.beginPath(); c.moveTo(w / 2, h / 2 - 70); c.lineTo(w / 2 + 110, h / 2); c.lineTo(w / 2, h / 2 + 70); c.lineTo(w / 2 - 110, h / 2); c.closePath(); c.fill();
      c.fillStyle = "#e6d9bf"; c.beginPath(); c.moveTo(w / 2, h / 2 - 50); c.lineTo(w / 2 + 80, h / 2); c.lineTo(w / 2, h / 2 + 50); c.lineTo(w / 2 - 80, h / 2); c.closePath(); c.fill();
      c.fillStyle = "#7a1d18"; c.beginPath(); c.arc(w / 2, h / 2, 22, 0, 7); c.fill(); });
    const rug = add(new THREE.PlaneGeometry(3.8, 2.8), rmat(rugTex, [0.62, 0.6, 0.58], [1, 1], noOcc), 2.4, 0.035, 6.77); rug.rotation.x = -Math.PI / 2;
    /* the roof's underside and its logs: the ridge, the purlins, the rafters, the two trusses */
    { const xe = HX + 0.3, ye = slopeY(xe), slope = Math.hypot(xe, HR - ye), th = Math.atan2(HR - ye, xe), ceil = rmat(MORE.boards || dD, MORE.boards ? [0.42, 0.37, 0.33] : [0.36, 0.44, 0.45], [(RZ1 - RZ0) / 1.5, slope / 1.5], {cav: [0, 0, 1]});
      for (const s of [-1, 1]) { const pg = new THREE.PlaneGeometry(slope, RZ1 - RZ0 + 0.4); pg.rotateX(Math.PI / 2); pg.rotateZ(-s * th); add(pg, ceil, s * xe / 2, (HR + ye) / 2 - 0.03, (RZ0 + RZ1) / 2); }
      const rf = [];
      rf.push(logAt(RZ1 - RZ0 + 0.4, 0.19, null, 0, HR - 0.38, (RZ0 + RZ1) / 2, "z", g, 12));
      for (const s of [-1, 1]) rf.push(logAt(RZ1 - RZ0 + 0.4, 0.14, null, s * 2.6, slopeY(2.6) - 0.46, (RZ0 + RZ1) / 2, "z", g, 12));
      const between = (a, b, r) => { const d = b.clone().sub(a), len = d.length(), m = new THREE.Mesh(logGeo(len, r, 10), null); m.position.copy(a).add(b).multiplyScalar(0.5); m.quaternion.setFromUnitVectors(V3(0, 1, 0), d.normalize()); g.add(m); rf.push(m); };
      for (let z = RZ0 + 0.25; z < RZ1; z += 1.25) for (const s of [-1, 1]) between(V3(s * (HX + 0.3), HE - 0.32, z), V3(s * 0.12, HR - 0.32, z), 0.12);
      for (const z of [RZ0 + 3.0, RZ0 + 6.8]) { rf.push(logAt(2 * HX + 0.6, 0.17, null, 0, HE - 0.12, z, "x", g, 12)); between(V3(0, HE - 0.12, z), V3(0, HR - 0.5, z), 0.14); }
      g.add(merged(rf, rmat(lD, [0.44, 0.57, 0.59], [1, 1], noOcc))); }
    /* the loft over the back of the room: joists and boards, the header log on two posts, the log railing with its opening for the stair, the stair up to it */
    { const loftD = RZ1 - LOFT_Z, lg = [];
      add(new THREE.BoxGeometry(2 * HX, 0.08, loftD), boardsIn, 0, LOFT_Y - 0.04, (LOFT_Z + RZ1) / 2);
      lg.push(logAt(2 * HX + 0.3, 0.17, null, 0, LOFT_Y - 0.25, LOFT_Z, "x", g, 12));
      for (const x of [-3.4, 3.4]) lg.push(logAt(LOFT_Y - 0.4, 0.16, null, x, (LOFT_Y - 0.4) / 2, LOFT_Z, "y", g, 12));
      const sx = -3.6, gap0 = sx - 0.45, gap1 = sx + 0.45;
      for (let x = -HX + 0.45; x < HX; x += 1.3) if (x < gap0 - 0.05 || x > gap1 + 0.05) lg.push(logAt(1.0, 0.065, null, x, LOFT_Y + 0.5, LOFT_Z, "y", g, 8));
      for (const x of [gap0, gap1]) lg.push(logAt(1.0, 0.065, null, x, LOFT_Y + 0.5, LOFT_Z, "y", g, 8));
      lg.push(logAt(gap0 + HX, 0.065, null, (-HX + gap0) / 2, LOFT_Y + 0.98, LOFT_Z, "x", g, 8)); lg.push(logAt(HX - gap1, 0.065, null, (gap1 + HX) / 2, LOFT_Y + 0.98, LOFT_Z, "x", g, 8));
      for (let x = -HX + 0.3; x < HX; x += 0.15) if (x < gap0 - 0.04 || x > gap1 + 0.04) lg.push(logAt(0.92, 0.024, null, x, LOFT_Y + 0.5, LOFT_Z, "y", g, 5));
      const steps = 11, run = 2.6, z0 = LOFT_Z - run;
      for (let i = 1; i <= steps; i++) add(new THREE.BoxGeometry(0.9, 0.09, 0.3), boardsIn, sx, i * LOFT_Y / (steps + 1), z0 + i * run / steps);
      for (const s of [-1, 1]) { const a = V3(sx + s * 0.47, 0.05, z0 - 0.1), b = V3(sx + s * 0.47, LOFT_Y - 0.1, LOFT_Z), d = b.clone().sub(a), m = new THREE.Mesh(logGeo(d.length(), 0.07, 8), null); m.position.copy(a).add(b).multiplyScalar(0.5); m.quaternion.setFromUnitVectors(V3(0, 1, 0), d.normalize()); g.add(m); lg.push(m); }
      g.add(merged(lg, rmat(lD, LOGT, [1, 1], noOcc))); }
    /* the fireplace on the right-hand wall: the stacked-stone breast floor to roof with the firebox cut into it, the raised
       hearth, the half-log mantel, and the fire burning: flames, the glowing bed, and the light the room shares */
    { const fz = FIREP.z, fw = 2.7, fx = HX, ox = fx - 0.75, oz0 = fz - 0.62, oz1 = fz + 0.62, oy0 = 0.42, oy1 = 1.3, fd = 0.62, fh = slopeY(fx - 0.4) + 0.3;
      const stone = rmat(MORE.stone_diff, MORE.stone_diff ? [0.55, 0.53, 0.5] : [0.3, 0.29, 0.27], [1, 1], {tri: 1 / 1.6, occ: false});
      const stoneBox = (x0, x1, y0, y1, z0, z1) => add(new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0), stone, (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
      stoneBox(ox, fx, 0, fh, fz - fw / 2, oz0); stoneBox(ox, fx, 0, fh, oz1, fz + fw / 2); stoneBox(ox, fx, oy1, fh, oz0, oz1); stoneBox(ox + fd, fx, 0, oy1, oz0, oz1); stoneBox(ox, fx, 0, oy0, oz0, oz1);
      stoneBox(ox - 0.62, ox, 0, oy0, fz - fw / 2 - 0.15, fz + fw / 2 + 0.15); stoneBox(ox - 0.66, ox + 0.02, oy0, oy0 + 0.06, fz - fw / 2 - 0.2, fz + fw / 2 + 0.2);
      const soot = new THREE.MeshBasicMaterial({color: "#120a06"});
      add(new THREE.BoxGeometry(0.02, oy1 - oy0, oz1 - oz0), soot, ox + fd - 0.02, (oy0 + oy1) / 2, fz); add(new THREE.BoxGeometry(fd, 0.02, oz1 - oz0), soot, ox + fd / 2, oy1 - 0.012, fz);
      add(new THREE.BoxGeometry(fd, oy1 - oy0, 0.02), soot, ox + fd / 2, (oy0 + oy1) / 2, oz0 + 0.012); add(new THREE.BoxGeometry(fd, oy1 - oy0, 0.02), soot, ox + fd / 2, (oy0 + oy1) / 2, oz1 - 0.012);
      const mantel = logAt(fw + 0.3, 0.13, null, ox - 0.1, 1.68, fz, "z", g, 12); g.add(merged([mantel], rmat(lD, LOGT, [1, 1], noOcc)));
      const bed = add(new THREE.PlaneGeometry(0.56, 0.56), new THREE.MeshBasicMaterial({map: glowTex(), color: new THREE.Color(2.4, 0.8, 0.16), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false}), ox + 0.3, oy0 + 0.03, fz); bed.rotation.x = -Math.PI / 2;
      const flames = [], flameMap = flameTex();
      for (const [w, h, dz, ry] of [[0.5, 0.66, 0, 0], [0.36, 0.5, 0.14, 1.1], [0.32, 0.46, -0.15, 2.2]]) {
        const f = add(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({map: flameMap, color: new THREE.Color(2.6, 2.0, 1.1), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide}), ox + 0.3, oy0 + 0.05 + h / 2, fz + dz);      // bright enough to bloom a little through the glass, as a fire does
        f.rotation.y = ry; f.userData = {h, ry}; flames.push(f); }
      const hearthGlow = add(new THREE.PlaneGeometry(2.2, 1.6), new THREE.MeshBasicMaterial({map: glowTex(), color: new THREE.Color(0.8, 0.34, 0.1), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false}), ox - 0.02, 0.86, fz); hearthGlow.rotation.y = -Math.PI / 2;
      focusBoxes.push(new THREE.Box3(V3(ox - 0.7, 0, fz - fw / 2), V3(fx, fh, fz + fw / 2)));
      g.userData.fire = {flames, hearthGlow, bed}; }
    /* the seating: the cabin's own sofa (Poly Haven's Sofa 02, in the cabin's brown leather) facing the fire, a wool throw
       over the front of its seat and a pillow; the same shape narrowed stands in for the two armchairs; the coffee table */
    let shapes = null;
    try { shapes = MORE.sofa && MORE.sofa_bin ? gltfShape(MORE.sofa, MORE.sofa_bin) : null; } catch (e) { shapes = null; }
    const sofa = new THREE.Group(); sofa.position.set(0.85, 0, 6.77); sofa.rotation.y = Math.PI / 2; sofa.scale.setScalar(1.15); g.add(sofa);
    if (shapes) {
      const leather = rmat(MORE.leather, MORE.leather ? [0.9, 0.88, 1.4] : [0.16, 0.09, 0.05], [1, 1], {tri: 2.5, spec: 0.28, occ: false, side: THREE.DoubleSide});
      for (const geo of shapes) sofa.add(new THREE.Mesh(geo, leather));
      sofa.add(new THREE.Mesh(throwGeo(), rmat(MORE.plaid, MORE.plaid ? [0.44, 0.4, 0.36] : [0.4, 0.3, 0.22], [2.2, 1.9], {occ: false, side: THREE.DoubleSide})));
      const pil = add(pillowGeo(), rmat(null, [0.11, 0.14, 0.1], [1, 1], noOcc), 0.56, 0.55, -0.08, sofa); pil.rotation.set(-0.34, 0.28, 0.1);
      sofa.updateMatrixWorld(true);
      const bb = new THREE.Box3().setFromObject(sofa); RU.uOccMin.value.copy(bb.min); RU.uOccMax.value.copy(bb.max);
      const cream = rmat(MORE.plaid, MORE.plaid ? [0.5, 0.46, 0.4] : [0.42, 0.36, 0.28], [1.4, 1.4], {occ: false, side: THREE.DoubleSide});
      for (const [x, z, ry] of [[3.0, 5.07, 0.69], [3.0, 8.57, 2.42]]) { const ch = new THREE.Group(); ch.position.set(x, 0, z); ch.rotation.y = ry; ch.scale.set(0.5, 0.95, 0.95); g.add(ch); for (const geo of shapes) ch.add(new THREE.Mesh(geo, cream)); }
      focusBoxes.push(bb);
    }
    const walnut = rmat(MORE.boards, [0.3, 0.2, 0.14], [0.5, 0.5], {occ: false, tri: 1.4});
    add(new THREE.BoxGeometry(1.1, 0.05, 0.6), walnut, 2.5, 0.44, 6.77); for (const [sx, sz] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) add(new THREE.BoxGeometry(0.05, 0.42, 0.05), walnut, 2.5 + sx * 0.5, 0.21, 6.77 + sz * 0.25);
    /* the lamps at the sofa's ends on their tall tables, and the lantern chandelier over the rug */
    const shadeTex = canvasTex(64, 128, (c, w, h) => { const gr = c.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, "#7a4a22"); gr.addColorStop(0.5, "#d99a58"); gr.addColorStop(1, "#ffd9a0");
      c.fillStyle = gr; c.fillRect(0, 0, w, h); c.globalAlpha = 0.08; for (let x = 0; x < w; x += 3) { c.fillStyle = x % 6 ? "#000" : "#fff"; c.fillRect(x, 0, 1, h); } });
    const jar = [[0, 0], [0.07, 0], [0.085, 0.015], [0.1, 0.06], [0.112, 0.13], [0.104, 0.2], [0.08, 0.25], [0.045, 0.28], [0.04, 0.3], [0, 0.3]].map(([r, y]) => new THREE.Vector2(r, y));
    const brass = rmat(null, [0.62, 0.42, 0.18], [1, 1], {occ: false, spec: 0.6}), lampGlows = [];
    for (const P of LAMPS.slice(0, 2)) {
      add(new THREE.CylinderGeometry(0.27, 0.27, 0.035, 40), walnut, P.x, 0.6, P.z); add(new THREE.CylinderGeometry(0.04, 0.055, 0.56, 18), walnut, P.x, 0.3, P.z); add(new THREE.CylinderGeometry(0.19, 0.21, 0.035, 32), walnut, P.x, 0.02, P.z);
      add(new THREE.LatheGeometry(jar, 36), rmat(null, [0.085, 0.075, 0.064], [1, 1], {occ: false, spec: 0.55}), P.x, 0.6175, P.z);
      add(new THREE.CylinderGeometry(0.011, 0.011, 0.07, 10), brass, P.x, 0.95, P.z); add(new THREE.SphereGeometry(0.018, 12, 8), brass, P.x, 1.245, P.z);
      add(new THREE.CylinderGeometry(0.13, 0.2, 0.26, 28, 1, true), new THREE.MeshBasicMaterial({map: shadeTex, side: THREE.DoubleSide}), P.x, 1.1, P.z);
      const lg = add(new THREE.PlaneGeometry(1.4, 1.4), new THREE.MeshBasicMaterial({map: glowTex(), color: new THREE.Color(0.55, 0.36, 0.18), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false}), P.x, 1.1, P.z - 0.05); lampGlows.push(lg);
    }
    { const C = LAMPS[2], ironIn = rmat(null, [0.08, 0.075, 0.07], [1, 1], noOcc);
      add(new THREE.CylinderGeometry(0.012, 0.012, HR - 0.5 - C.y - 0.3, 8), ironIn, C.x, (HR - 0.5 + C.y + 0.3) / 2, C.z);
      add(new THREE.BoxGeometry(0.44, 0.03, 0.44), ironIn, C.x, C.y + 0.3, C.z); add(new THREE.BoxGeometry(0.44, 0.03, 0.44), ironIn, C.x, C.y - 0.25, C.z);
      for (const [sx, sz] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) add(new THREE.BoxGeometry(0.02, 0.55, 0.02), ironIn, C.x + sx * 0.21, C.y + 0.025, C.z + sz * 0.21);
      add(new THREE.SphereGeometry(0.035, 12, 10), new THREE.MeshBasicMaterial({color: new THREE.Color(1.0, 0.9, 0.7)}), C.x, C.y, C.z);
      const cg = add(new THREE.PlaneGeometry(1.2, 1.2), new THREE.MeshBasicMaterial({map: glowTex(), color: new THREE.Color(0.5, 0.34, 0.17), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false}), C.x, C.y, C.z - 0.03); lampGlows.push(cg); }
    /* the curtains tied back at the glass, in linen the light comes through */
    const linen = rmat(null, [0.36, 0.27, 0.17], [1, 1], {thin: true, occ: false, side: THREE.DoubleSide});
    const curtain = (outer, inner, seedC) => {
      const geo = new THREE.PlaneGeometry(1, 1, 22, 30), P = geo.attributes.position, ph = rng(seedC)() * 6, tp = GL.trans[0] - 0.1, bot = 0.25, tie = 0.58;
      for (let i = 0; i < P.count; i++) {
        const u = P.getX(i) + 0.5, v = 0.5 - P.getY(i);      // u from the outer edge to the inner, v from the rod to the hem
        const gather = 1 - 0.62 * Math.exp(-Math.pow((v - tie) / 0.16, 2)) - 0.25 * smooth(clamp((v - tie) / (1 - tie)));
        P.setXYZ(i, outer + (inner - outer) * u * gather, tp - v * (tp - bot), GZ + 0.16 + (0.018 + 0.03 * (1 - gather)) * Math.sin(u * 2 * Math.PI * 4.5 + ph + v * 0.8) + 0.025 * u * (1 - gather));
      }
      geo.computeVertexNormals(); add(geo, linen);
    };
    curtain(GL.x0 + 0.12, GL.x0 + 0.92, 5); curtain(DR.x0 - 0.06, DR.x0 - 0.86, 9);
    /* the rocking chair by the glass (the cabin's own, Poly Haven's Rocking Chair 01), when its model came */
    if (MORE.rocker && MORE.rocker.isObject3D) { const rc = MORE.rocker; rc.position.set(-3.3, 0.02, RZ0 + 2.0); rc.rotation.y = 1.03; rc.traverse(o => { if (o.isMesh) { o.castShadow = o.receiveShadow = true; } }); g.add(rc);
      focusBoxes.push(new THREE.Box3().setFromObject(rc)); }
    focusBoxes.push(new THREE.Box3(V3(-HX, 0, RZ0), V3(HX, 0.05, RZ1)));
    const lampGlow = lampGlows[0];
    for (const lg of lampGlows) lg.lookAt(EYE);
    return {update(flick, flick2){ RU.uFlick.value = flick; const F = g.userData.fire; if (F) { F.flames.forEach((f, i) => { f.scale.y = 0.86 + 0.22 * Math.sin(flick * 37 + i * 2.1) * (flick - 0.6); f.scale.x = 0.9 + 0.1 * Math.sin(flick * 53 + i); }); F.hearthGlow.material.opacity = 0.55 + 0.45 * (flick - 0.9) * 5; F.bed.material.opacity = 0.6 + 0.4 * flick; } }, reflect, lampGlow,
            dispose(){ if (refTex) refTex.dispose(); }};
  }

  /* ---------- where you look, second by second (the crossing) ---------- */
  const P_END = W.P, cur = {yaw: 0, pitch: 0, adapt: 0};
  const poseCrossing = (t, out) => {
    const rise = inOut(seg(t, 0.5, 3.4)), up = inOut(seg(t, 4.1, 6.9));
    let pitch = mix(-30, 3, rise) + (P_END - 3) * up, yaw = 2.4 * smooth(seg(t, 6.6, 10)) - 1.2 * smooth(seg(t, 0, 3.5));
    pitch += (0.22 * Math.sin(t * 1.45 + 0.4) + 0.12 * Math.sin(t * 0.61)) * (1 - STILL);      // breathing
    yaw += 0.18 * Math.sin(t * 0.37 + 1.3) * (1 - STILL);
    if (FB) { const g = smooth(seg(t, FB.t0 + 0.25, FB.t0 + 1.2)) * (1 - smooth(seg(t, FB.t0 + 2.3, FB.t0 + 3.4))); pitch += FB.lookP * g; yaw += FB.lookY * g; }      // a glance at the fireball
    if (!STILL) { yaw += pt.sx * 3.2; pitch -= pt.sy * 2.2; }
    out.position.copy(EYE); out.position.y += 0.004 * Math.sin(t * 1.45);
    out.rotation.set(pitch * D2R, -yaw * D2R, 0.006 * Math.sin(t * 0.5), "YXZ");
    if (out === cam) { cur.yaw = yaw; cur.pitch = pitch; }
  };
  /* on the deck to sit on, the page's walker sets the eyes each frame */
  const setView = (p, yaw, pitch, roll) => { cam.position.copy(p); cam.rotation.set(pitch * D2R, -yaw * D2R, (roll || 0) * D2R, "YXZ"); cur.yaw = yaw; cur.pitch = pitch; };
  cam.fov = vfovOf(aspect); cam.updateProjectionMatrix();

  /* the Moon, in view: where it stands, when it does; otherwise placed for the scene */
  const probe = new THREE.PerspectiveCamera(cam.fov, aspect, 0.05, 3000);
  const dirAt = (t, sx, sy) => { poseCrossing(t, probe); probe.updateMatrixWorld(); return V3(sx, sy, 0.5).unproject(probe).sub(probe.position).normalize(); };
  const probeAt = (yaw, pitch, sx, sy) => { probe.position.copy(EYE); probe.rotation.set(pitch * D2R, -yaw * D2R, 0, "YXZ"); probe.updateMatrixWorld();
    return V3(sx, sy, 0.5).unproject(probe).sub(probe.position).normalize(); };
  let FB = null;
  let mDir = W.moonW.clone();
  const handed = from && Array.isArray(from.moon) && from.moon.length === 3 && from.moon.every(isFinite) ? V3(...from.moon).normalize() : null;
  const seat0 = SEATS.find(s => s.id === opts.seat) || SEATS[0], look0 = {yaw: seat0.yaw, pitch: W.portrait ? seat0.pitchPhone : seat0.pitch};
  if (handed) mDir = handed;
  else if (!W.moonReal) {
    /* placed up and to one side of the final look (on the deck, of the chair's first look), away from the radiant */
    const mView = WATCH ? probeAt(0, SEATS[0].pitch, 0, 0) : dirAt(8.4, 0, 0).clone();
    const radScreen = W.radiant.clone().sub(mView).dot(V3(1, 0, 0).applyQuaternion(probe.quaternion)), side = radScreen > 0 ? -1 : 1;
    mDir = WATCH ? probeAt(0, SEATS[0].pitch, side * (W.portrait ? 0.42 : 0.5), W.portrait ? 0.5 : 0.55) : dirAt(8.4, side * (W.portrait ? 0.42 : 0.52), W.portrait ? 0.48 : 0.42);
  }
  moonDir.copy(mDir);
  const MOON_R = 800 * Math.tan(0.259 * LOOK.moonSize * D2R);
  moon.position.copy(mDir).multiplyScalar(800); moon.scale.setScalar(MOON_R);
  halo.position.copy(mDir).multiplyScalar(790); halo.scale.setScalar(MOON_R * 7); halo.lookAt(0, 0, 0);
  /* the light on it: from the Sun, below the horizon; for a placed moon, turned so its phase is the chosen one and its
     lit edge still faces the Sun's side of the sky */
  const toEye = mDir.clone().negate(), sunSide = W.sun.clone().sub(mDir.clone().multiplyScalar(W.sun.dot(mDir)));
  if (sunSide.lengthSq() < 1e-6) sunSide.set(0, -1, 0); sunSide.normalize();
  const light = toEye.clone().multiplyScalar(Math.cos(PHASE_ANGLE)).addScaledVector(sunSide, Math.sin(PHASE_ANGLE)).normalize();
  moonMat.uniforms.uSun.value.copy(light);
  const ncp = V3(0, 0, 1).applyMatrix3(W.f.toWorld), north = ncp.clone().sub(mDir.clone().multiplyScalar(ncp.dot(mDir))).normalize();
  moon.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(toEye, north, toEye.clone().cross(north)));
  const mAlt = altOf(mDir); moonMat.uniforms.uLow.value = smoothstep01(12, 2, mAlt);
  const litFrac = (1 + Math.cos(PHASE_ANGLE)) / 2;
  const moonKey = LOOK.moonKey + (LOOK.moonKeyFull - LOOK.moonKey) * litFrac;      // the moon's light on the deck: a crescent gives little, a full moon much
  const placeMoonLight = () => { moonLight.position.copy(moonDir).multiplyScalar(40); moonLight.target.position.set(0, 0, -1); landMat.uniforms.uMoonLit.value = 0.9 * litFrac * clamp(moonDir.y * 3); };
  placeMoonLight();

  /* ---------- the meteors ---------- */
  const RE = 6371, rad = W.radiant.clone();
  const shV = W.shower.v, fast = clamp((shV - 25) / 45);
  const COLS = {white: [1.0, 0.97, 0.92], green: [0.62, 1.0, 0.70], gold: [1.0, 0.80, 0.48], orange: [1.0, 0.62, 0.32]};
  const spot = (w, h) => { const d = -RE * w.y + Math.sqrt(RE * RE * w.y * w.y + (RE + h) ** 2 - RE * RE); return w.clone().multiplyScalar(d); };
  const meteors = [];
  /* Colour and trains follow the shower's speed. Slow meteors (the Taurids enter at 27 km/s) burn white to yellow and
     orange and seldom leave more than a brief wake behind the head; fast ones (the Perseids, Orionids and Leonids, 59 to
     71 km/s) show more green, and the bright ones leave a glowing green train (oxygen) that lingers and drifts. */
  const hueOf = p => { const green = 0.04 + 0.30 * fast, orange = 0.12 * (1 - fast), gold = 0.26 - 0.08 * fast;
    return p < 1 - green - orange - gold ? "white" : p < 1 - orange - gold ? "green" : p < 1 - orange ? "gold" : "orange"; };
  const TRAIN = 2, WAKE = 1;
  const make = (t0, sx, sy, mg, o = {}) => {
    const dur = (o.dur || mix(0.85, 0.32, fast) * (0.8 + 0.4 * R())) * (mg < 0 ? 1.25 : 1);
    const mid = dirAt(t0 + dur * 0.5, sx, sy);
    if (mid.y < 0.12) mid.y = 0.12, mid.normalize();
    const M = spot(mid, o.h || mix(88, 100, fast)), Lm = shV * dur * (o.lenK || 1);
    const S = M.clone().addScaledVector(rad, Lm / 2), E = M.clone().addScaledVector(rad, -Lm / 2);
    const pick = R(), hue = o.hue || hueOf(pick);
    const train = fast > 0.5 ? (o.fb || mg <= -1.5 ? TRAIN : 0) : (o.fb ? WAKE : 0);
    meteors.push({t0, dur, S, E, mag: mg, hue, train, fb: !!o.fb, flick: R() * 50});
  };
  /* on the deck to sit on: a meteor where the reader looks, or anywhere above the mountains, moving away from the radiant;
     while the radiant is below the horizon, the ones that come are the night's stray meteors, from all over the sky */
  const strayRad = () => { const alt = (15 + 50 * R()) * D2R, az = R() * 2 * Math.PI; return V3(Math.sin(az) * Math.cos(alt), Math.sin(alt), -Math.cos(az) * Math.cos(alt)); };
  const makeAt = (t0, mid, mg, o = {}) => {
    const dur = (o.dur || mix(0.85, 0.32, fast) * (0.8 + 0.4 * R())) * (mg < 0 ? 1.25 : 1);
    mid = mid.clone(); if (mid.y < 0.12) { mid.y = 0.12; mid.normalize(); }
    const r = rad.y > -0.035 && !(o.stray || R() < 0.12) ? rad : strayRad();
    const M = spot(mid, o.h || mix(88, 100, fast)), Lm = shV * dur * (o.lenK || 1);
    const S = M.clone().addScaledVector(r, Lm / 2), E = M.clone().addScaledVector(r, -Lm / 2);
    const hue = o.hue || hueOf(R()), train = fast > 0.5 ? (o.fb || mg <= -1.5 ? TRAIN : 0) : (o.fb ? WAKE : 0);
    meteors.push({t0, dur, S, E, mag: mg, hue, train, fb: !!o.fb, flick: R() * 50});
  };
  if (!WATCH) {
    const T = [1.85, 3.1, 4.55, 5.2, 5.95, 6.45, 6.75, 8.75, 9.3];
    const spots = [[-0.45, 0.25], [0.4, 0.15], [-0.2, 0.45], [0.42, 0.5], [-0.5, 0.05], [0.12, 0.6], [-0.35, 0.55], [0.3, 0.3], [-0.15, 0.2]];
    const mags = [2.4, 1.6, 0.6, -1.7, 2.0, 0.9, -0.6, 2.2, 1.4];
    T.forEach((t0, i) => make(t0, spots[i][0] + (R() - 0.5) * 0.12, spots[i][1] + (R() - 0.5) * 0.1, mags[i] + (R() - 0.5) * 0.4));
  }
  /* the fireball: slower and far brighter, breaking up near its end; green when fast, gold when slow */
  const fbT0 = 7.0, fbDur = 1.9, fbHue = fast > 0.5 ? "green" : "gold";
  if (!WATCH) make(fbT0, W.portrait ? 0.05 : 0.08, W.portrait ? 0.32 : 0.28, -6.5, {dur: fbDur, fb: true, hue: fbHue, h: 82, lenK: mix(1.25, 0.5, fast)});
  const FBCOL = fbHue === "green" ? [0.78, 0.95, 0.85] : [1.0, 0.90, 0.74];      // the colour of its light on the sky, the land and the deck
  U.uFlashCol.value.setRGB(...FBCOL);
  if (!WATCH) { const fb = meteors[meteors.length - 1];
    const md = fb.S.clone().lerp(fb.E, 0.6).normalize(); poseCrossing(fbT0, probe); const q = probe.quaternion.clone().invert(), local = md.clone().applyQuaternion(q);
    FB = {t0: fbT0, lookY: clamp(Math.atan2(local.x, -local.z) * R2D * 0.18, -3, 3), lookP: clamp(Math.atan2(local.y, -local.z) * R2D * 0.15, -2.5, 2.5), dir: md}; }

  const MAXQ = 400, qPos = new Float32Array(MAXQ * 4 * 3), qUV = new Float32Array(MAXQ * 4 * 2), qCol = new Float32Array(MAXQ * 4 * 3), qIdx = new Uint16Array(MAXQ * 6);
  for (let i = 0; i < MAXQ; i++) qIdx.set([i * 4, i * 4 + 1, i * 4 + 2, i * 4 + 2, i * 4 + 1, i * 4 + 3], i * 6);
  const qGeo = new THREE.BufferGeometry(); qGeo.setAttribute("position", new THREE.BufferAttribute(qPos, 3).setUsage(THREE.DynamicDrawUsage));
  qGeo.setAttribute("aUV", new THREE.BufferAttribute(qUV, 2).setUsage(THREE.DynamicDrawUsage)); qGeo.setAttribute("aCol", new THREE.BufferAttribute(qCol, 3).setUsage(THREE.DynamicDrawUsage));
  qGeo.setIndex(new THREE.BufferAttribute(qIdx, 1));
  const streakMat = new THREE.ShaderMaterial({
    vertexShader: `attribute vec2 aUV; attribute vec3 aCol; varying vec2 vUV; varying vec3 vCol; void main(){ vUV = aUV; vCol = aCol; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `varying vec2 vUV; varying vec3 vCol; void main(){ float a = exp(-vUV.y * vUV.y * 3.2) * (1.0 - vUV.y * vUV.y); gl_FragColor = vec4(vCol * a, 1.0);
      #include <colorspace_fragment>
    }`, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide});
  const streaks = new THREE.Mesh(qGeo, streakMat); streaks.frustumCulled = false; streaks.renderOrder = 5; sky.add(streaks);
  const MAXH = 64, hPos = new Float32Array(MAXH * 3), hSize = new Float32Array(MAXH), hCol = new Float32Array(MAXH * 3);
  const hGeo = new THREE.BufferGeometry(); hGeo.setAttribute("position", new THREE.BufferAttribute(hPos, 3).setUsage(THREE.DynamicDrawUsage));
  hGeo.setAttribute("aSize", new THREE.BufferAttribute(hSize, 1).setUsage(THREE.DynamicDrawUsage)); hGeo.setAttribute("aCol", new THREE.BufferAttribute(hCol, 3).setUsage(THREE.DynamicDrawUsage));
  /* a meteor's head: a point of light drawn as a star's is (a core never narrower than half a pixel), so it does not
     flicker as it crosses the pixels; its total light is the one it was tuned to give */
  const headMat = new THREE.ShaderMaterial({uniforms: U,
    vertexShader: `attribute float aSize; attribute vec3 aCol; uniform float uPx; varying vec3 vCol; varying float vI, vSize, vSc, vSh;
      void main(){ float R = 0.5 * aSize * uPx; vCol = aCol; vI = 0.481 * R * R;
        vSc = max(max(0.5, 0.5 * uPx), 0.236 * R); vSh = max(vSc, 0.44 * R); vSize = max(5.0, ceil(6.0 * vSh) + 2.0);
        gl_PointSize = vSize; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `varying vec3 vCol; varying float vI, vSize, vSc, vSh;
      ${POINTFRAG_HEAD}
      void main(){ vec2 q = (gl_PointCoord - 0.5) * vSize;
        float a = 0.725 * share(q, vSc) + 0.275 * share(q, vSh);
        gl_FragColor = vec4(vCol * vI * a, 1.0);
        #include <colorspace_fragment>
      }`, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending});
  const heads = new THREE.Points(hGeo, headMat); heads.frustumCulled = false; heads.renderOrder = 6; sky.add(heads);
  const fbGlow = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({map: glowTex(), color: new THREE.Color(...(fbHue === "green" ? [0.7, 1.0, 0.78] : [1.0, 0.86, 0.62])),
    transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false})); fbGlow.renderOrder = 7; fbGlow.visible = false; sky.add(fbGlow);
  flashLight.color.set(fbHue === "green" ? "#cfe8d8" : "#ffe2bc");

  const RS = 700;      // meteors are drawn on a sphere behind the mountains and in front of the stars
  let nq = 0, nh = 0;
  const pxWorld = () => 2 * RS * Math.tan(cam.fov * D2R / 2) / Math.max(1, renderer.domElement.height / renderer.getPixelRatio());
  const quad = (a, b, wa, wb, ca, cb) => {      // a ribbon piece from a to b (unit directions), widths in pixels, colours (brightness folded in)
    if (nq >= MAXQ) return;
    const A3 = a.clone().multiplyScalar(RS), B3 = b.clone().multiplyScalar(RS), side = B3.clone().sub(A3).cross(A3.clone().add(B3)).normalize(), k = pxWorld();
    const sa = side.clone().multiplyScalar(wa * k), sb = side.clone().multiplyScalar(wb * k), o = nq * 4;
    qPos.set([A3.x - sa.x, A3.y - sa.y, A3.z - sa.z, A3.x + sa.x, A3.y + sa.y, A3.z + sa.z, B3.x - sb.x, B3.y - sb.y, B3.z - sb.z, B3.x + sb.x, B3.y + sb.y, B3.z + sb.z], o * 3);
    qUV.set([0, -1, 0, 1, 1, -1, 1, 1], o * 2);
    qCol.set([...ca, ...ca, ...cb, ...cb], o * 3); nq++;
  };
  const head = (d, size, c) => { if (nh >= MAXH) return; hPos.set([d.x * RS, d.y * RS, d.z * RS], nh * 3); hSize[nh] = size; hCol.set(c, nh * 3); nh++; };
  const scale = (c, k) => [c[0] * k, c[1] * k, c[2] * k];
  const lerpC = (a, b, t) => [mix(a[0], b[0], t), mix(a[1], b[1], t), mix(a[2], b[2], t)];
  const at = (m, u) => m.S.clone().lerp(m.E, u).normalize();
  /* how bright a meteor of magnitude m looks, on the scale the stars use */
  const glowOf = mg => clamp(LOOK.starK * Math.pow(Math.pow(10, -0.4 * mg), LOOK.starG), 0, 12);
  let flash = 0, flashDir = V3(0, 1, 0);
  function drawMeteors(t){
    nq = nh = 0; flash = 0; fbGlow.visible = false;
    for (const m of meteors) {
      const tau = (t - m.t0) / m.dur;
      /* the glowing train a fast, bright meteor leaves behind: green, lingering, drifting in the wind up there */
      if (m.train === TRAIN && tau > 0.15) {
        const age = (t - m.t0) - m.dur * 0.15, life = m.fb ? 3.2 : 1.6, k = Math.exp(-age / (life * 0.45)) * (tau < 1 ? smooth(seg(tau, 0.15, 0.6)) : 1);
        if (k > 0.01) {
          const end = Math.min(1, tau), from = m.fb ? 0.12 : 0.25, N = 10, drift = V3(0.0008, 0.0003, 0).multiplyScalar(age);
          for (let i = 0; i < N; i++) {
            const u0 = mix(from, end, i / N), u1 = mix(from, end, (i + 1) / N);
            if (u1 > tau - 0.02 && tau < 1) break;
            const w0 = 1.2 + age * (m.fb ? 2.2 : 1.4), shade = m.fb ? lerpC(COLS.orange, COLS.green, 0.35) : COLS.green, along = Math.sin(Math.PI * clamp((u0 - from) / (end - from + 1e-3)));
            const c = scale(shade, 0.07 * k * (m.fb ? 2.2 : 1) * (0.4 + 0.6 * along) * glowOf(Math.max(m.mag, -2)) / 3);
            quad(at(m, u0).add(drift).normalize(), at(m, u1).add(drift).normalize(), w0, w0, c, c);
          }
        }
      }
      /* a slow fireball's wake: a short, faint, warm afterglow just behind the head, gone within half a second of its
         passing (each piece fades from the moment the head went by) */
      if (m.train === WAKE && tau > 0.1) {
        const hd0 = Math.min(1, m.fb ? tau * (1.08 - 0.08 * tau) : tau), from = Math.max(0.08, hd0 - 0.4), N = 8;
        for (let i = 0; i < N; i++) {
          const u0 = mix(from, hd0, i / N), u1 = mix(from, hd0, (i + 1) / N), ago = (tau - (u0 + u1) / 2) * m.dur;
          const k = Math.exp(-Math.max(0, ago) / 0.22) * smooth(seg(tau, 0.1, 0.3));
          if (k < 0.01 || u1 > hd0 - 0.015) continue;
          const c = scale(lerpC(COLS.orange, COLS.gold, 0.45), 0.05 * k * glowOf(Math.max(m.mag, -2)) / 3);
          quad(at(m, u0), at(m, u1), 1.0, 1.0, c, c);
        }
      }
      if (tau < 0 || tau > 1) continue;
      /* the meteor itself: it brightens, flares and fades as it burns */
      const ease = m.fb ? tau * (1.08 - 0.08 * tau) : tau;
      let b = Math.pow(Math.sin(Math.PI * clamp(ease * 0.92 + 0.04)), 0.7);
      if (m.fb) b = smooth(seg(tau, 0, 0.18)) * (0.75 + 0.25 * Math.sin(t * 37 + m.flick)) * (1 + 1.6 * Math.exp(-Math.pow((tau - 0.72) / 0.05, 2)) + 3.2 * Math.exp(-Math.pow((tau - 0.9) / 0.035, 2))) * (1 - smooth(seg(tau, 0.93, 1)));
      else b *= 0.85 + 0.15 * Math.sin(t * 41 + m.flick);
      const I = glowOf(m.mag) * b, base = COLS[m.hue], headC = lerpC(COLS.white, base, 0.35);
      const hd = at(m, ease), tailU = Math.max(0, ease - (m.fb ? 0.3 : WATCH ? 0.27 : 0.22));      // on the deck, watched for longer, a little more of the trail the eye keeps
      const NS = m.fb ? 8 : 5;
      for (let i = 0; i < NS; i++) {      // the streak: brightest at the head, fading behind it, a thin line
        const u0 = mix(tailU, ease, i / NS), u1 = mix(tailU, ease, (i + 1) / NS), f0 = Math.pow(i / NS, 1.8), f1 = Math.pow((i + 1) / NS, 1.8);
        const tc = m.fb ? lerpC(COLS.orange, headC, f1) : lerpC(base, headC, f1);
        quad(at(m, u0), at(m, u1), 0.35 + (m.fb ? 2.4 : 0.9) * f0, 0.35 + (m.fb ? 2.4 : 0.9) * f1, scale(tc, I * 0.55 * f0), scale(tc, I * 0.55 * f1));
      }
      head(hd, (m.fb ? 7 : 3.2) + Math.min(m.fb ? 26 : 8, I * (m.fb ? 2.2 : 2.6)), scale(headC, Math.min(1.6, I)));
      if (m.fb) {
        fbGlow.visible = true; fbGlow.position.copy(hd).multiplyScalar(RS - 5); fbGlow.lookAt(0, 0, 0);      // the glow around it, in the air
        fbGlow.scale.setScalar(pxWorld() * (26 + 20 * Math.min(b, 4))); fbGlow.material.opacity = clamp(0.12 * b, 0, 0.75);
        if (tau > 0.62) for (let k = 1; k <= 4; k++) {      // it breaks up: pieces trail behind, each fading
          const lag = 0.012 * k + 0.004 * k * k, u = Math.max(0, ease - lag), fade = (1 - smooth(seg(tau, 0.62 + 0.06 * k, 0.98))) * smooth(seg(tau, 0.62, 0.68));
          const off = V3(Math.sin(k * 2.1), Math.cos(k * 1.7), Math.sin(k * 3.3)).multiplyScalar(0.0009 * k * (tau - 0.62));
          head(at(m, u).add(off).normalize(), 2.5 + 3 * fade, scale(COLS.gold, 0.9 * fade));
        }
        flash = Math.max(flash, clamp(0.06 * b * b, 0, 1.6)); flashDir = hd;
      } else if (m.mag < 0) { flash = Math.max(flash, 0.05 * b * (-m.mag)); flashDir = hd; }
    }
    qGeo.setDrawRange(0, nq * 6); qGeo.attributes.position.needsUpdate = qGeo.attributes.aUV.needsUpdate = qGeo.attributes.aCol.needsUpdate = true;
    hGeo.setDrawRange(0, nh); hGeo.attributes.position.needsUpdate = hGeo.attributes.aSize.needsUpdate = hGeo.attributes.aCol.needsUpdate = true;
  }

  /* ---------- the living things: the wind in the trees, the mist, the smoke, the moths, the lights' flicker ---------- */
  const softScale = () => Math.max(1, renderer.domElement.height / renderer.getPixelRatio()) / (2 * Math.tan(cam.fov * D2R / 2));
  const skyCol = new THREE.Color(0.55, 0.62, 0.8);
  function living(t, adapt, gust){
    const sc = softScale();
    for (const m of trees) m.rotation.z = (0.0025 + 0.006 * gust) * Math.sin(t * 0.7 + m.userData.s) * (1 - STILL);
    { const P = mist.geometry.attributes.position, S = mist.geometry.attributes.aSize, Al = mist.geometry.attributes.aAlpha, C = mist.geometry.attributes.aCol;
      mistSeeds.forEach((s, i) => { const x = s.x + 0.35 * Math.sin(t * 0.05 + s.ph) + 0.18 * t * (1 - STILL) % 1 * 0, z = s.z + 0.2 * Math.sin(t * 0.04 + s.ph * 1.7);
        P.setXYZ(i, x, groundY(x, z) + 0.45 + 0.1 * Math.sin(t * 0.09 + s.ph), z); S.setX(i, s.s); Al.setX(i, (0.035 + 0.02 * Math.sin(t * 0.07 + s.ph)) * adapt); C.setXYZ(i, skyCol.r * 0.05, skyCol.g * 0.05, skyCol.b * 0.05); });
      P.needsUpdate = S.needsUpdate = Al.needsUpdate = C.needsUpdate = true; mist.material.uniforms.uScale.value = sc; }
    if (smoke) {
      const C = L.chimney, top = V3((C.x0 + C.x1) / 2, C.top + 0.1, (C.z0 + C.z1) / 2), P = smoke.geometry.attributes.position, S = smoke.geometry.attributes.aSize, Al = smoke.geometry.attributes.aAlpha, Cc = smoke.geometry.attributes.aCol;
      smokeSeeds.forEach((s, i) => {
        const age = ((t + s.t0) % s.life), u = age / s.life, rise = 1.1 * age - 0.03 * age * age, drift = (0.35 + 0.9 * gust) * age;
        const x = top.x + drift + 0.25 * Math.sin(s.a + age * 0.9) * Math.sqrt(age), y = top.y + rise, z = top.z + 0.3 * age * (0.4 + 0.3 * Math.sin(s.b)) + 0.2 * Math.cos(s.b + age * 0.7) * Math.sqrt(age);
        P.setXYZ(i, x, y, z); S.setX(i, 0.6 + 3.0 * u + 0.5 * s.c); Al.setX(i, 0.2 * Math.sin(Math.PI * Math.pow(u, 0.6)) * (1 - 0.5 * u) * (0.5 + 0.5 * adapt));
        const lit = 0.02 + 0.045 * adapt * (0.4 + litFrac); Cc.setXYZ(i, lit * 0.95, lit, lit * 1.15); });
      P.needsUpdate = S.needsUpdate = Al.needsUpdate = Cc.needsUpdate = true; smoke.material.uniforms.uScale.value = sc;
    }
    if (moths) {
      const P = moths.geometry.attributes.position, S = moths.geometry.attributes.aSize, Al = moths.geometry.attributes.aAlpha;
      mothSeeds.forEach((s, i) => { const r = s.r * (0.6 + 0.4 * Math.sin(t * 0.7 + s.b)), a = t * s.f + s.a + 0.6 * Math.sin(t * 3.1 + s.b);
        P.setXYZ(i, flameAt.x + r * Math.cos(a) + 0.03 * Math.sin(t * 9 + s.a), flameAt.y + 0.08 + r * 0.5 * Math.sin(a * 1.3 + s.b) + 0.04 * Math.sin(t * 7 + s.b), flameAt.z - 0.02 + r * Math.sin(a) * 0.8);
        S.setX(i, 0.012); Al.setX(i, 0.35 + 0.3 * Math.sin(t * 11 + s.a)); });
      P.needsUpdate = S.needsUpdate = Al.needsUpdate = true; moths.material.uniforms.uScale.value = sc;
    }
  }
  const flickerOf = t => 1 + 0.05 * Math.sin(t * 7.1) + 0.035 * Math.sin(t * 12.7 + 1) + 0.02 * Math.sin(t * 23.3);      // the fire inside
  const flicker2Of = (t, gust) => 1 + (0.08 + 0.1 * gust) * Math.sin(t * 9.3) + 0.06 * Math.sin(t * 17.1 + 2) + 0.05 * gust * Math.sin(t * 31.7);      // the lantern's flame, in the draught
  function lights(t, adapt, gust, flick, still){
    const f2 = still ? 1 : flicker2Of(t, gust);
    win.intensity = LOOK.window * (0.92 + 0.08 * flick) * (1 - 0.2 * adapt);      // the lamps are steady; the fire's share of the room's light flickers a little
    spill.intensity = LOOK.spill * flick * (1 - 0.2 * adapt);
    lantern.intensity = LOOK.lantern * f2 * (1 - 0.15 * adapt);
    hemi.intensity = LOOK.sky * mix(0.3, 1, adapt) + 0.6 * flash;
    moonLight.intensity = moonKey * mix(0.3, 1, adapt);
    flashLight.intensity = 1.2 * flash; flashLight.position.copy(flashDir).multiplyScalar(50); flashLight.target.position.set(0, 0, 0);
    facade.update(f2);
    if (cabin) cabin.update(flick, f2);
    return f2;
  }
  const frame = (t, end = DUR) => {
    poseCrossing(t, cam); cam.updateMatrixWorld(); sky.position.copy(cam.position);
    const adapt = smooth(seg(t, 0.7, 3.9));      // the eyes adjust: the faint stars and the Milky Way come out
    cur.adapt = STILL ? 1 : adapt;
    U.uTime.value = STILL ? 7 : t; U.uAdapt.value = adapt; U.uLimit.value = mix(1.3, 6.3, smooth(seg(t, 0.35, 3.4)));
    drawMeteors(t);
    U.uFlash.value = flash; U.uFlashDir.value.copy(flashDir);
    domeMat.uniforms.uMoonGlow.value = (0.3 + 0.7 * adapt) * litFrac * 0.35;
    halo.material.opacity = (0.025 + 0.06 * litFrac) * (0.4 + 0.6 * adapt);
    const gust = gustAt(t), flick = STILL ? 1 : flickerOf(t);
    lights(t, adapt, gust, flick, STILL); living(t, adapt, gust);
    const v = STILL ? 0 : Math.max(1 - smooth(seg(t, 0.05, 1.1)), smooth(seg(t, end - 0.95, end)));
    lensP.veilA = v;
    /* the eyes are on the railing and the boards at first, and rack to the sky as they lift */
    const far = smooth(seg(t, 3.5, 5.2)); lensP.focus = STILL ? 60 : mix(1.5, 60, far); lensP.aper = STILL ? 0 : mix(1.3, 0.8, far);
    return v;
  };

  /* ---------- the deck to sit on: the sky turning in real time, a meteor every few seconds ---------- */
  const rad0 = W.radiant.clone(), moon0 = mDir.clone(), light0 = light.clone(), turnM = new THREE.Matrix4();
  let Qnow = new THREE.Matrix3(), tSky = 0;
  const turn = t => {      // the Earth's own turning, from the moment the sky was worked out: about a quarter of a degree a minute
    tSky = t;
    const f = frameOf(new Date(W.date.getTime() + t * 1000), W.where.lat, W.where.lon, W.a0);
    Qnow = f.j2w.clone().multiply(W.f.w2j);
    turnM.setFromMatrix3(Qnow); cel.quaternion.setFromRotationMatrix(turnM);
    domeMat.uniforms.uW2J.value.copy(f.w2j);
    moonDir.copy(moon0).applyMatrix3(Qnow); moonMat.uniforms.uSun.value.copy(light0).applyMatrix3(Qnow);
    rad.copy(rad0).applyMatrix3(Qnow);
  };
  let nextAt = 1.4 + R() * 2.2, nextBig = 35 + R() * 40, lastT = 0, tHeld = 0, lastMoonSet = -1e9;
  const adapt0 = from ? clamp(+from.adapt || 0) : 0.3;
  const gap = () => clamp(-Math.log(1 - R()) * 3.4, 1.0, 10);      // a meteor every few seconds, at random
  const magOf = () => clamp(2.0 + Math.log(1 - R()) * 1.0, -2.6, 3.0);      // most of them faint; now and then a bright one (about one in seven)
  const inView = (sx, sy) => V3(sx, sy, 0.5).unproject(cam).sub(cam.position).normalize();
  const anySky = () => { const alt = (10 + 70 * Math.pow(R(), 0.8)) * D2R, az = R() * 2 * Math.PI; return V3(Math.sin(az) * Math.cos(alt), Math.sin(alt), -Math.cos(az) * Math.cos(alt)); };
  const pickDir = () => { for (let k = 0; k < 6; k++) { const d = R() < 0.8 ? inView((R() - 0.5) * 1.6, -0.45 + R() * 1.3) : anySky(); if (d.y > 0.16) return d; } return anySky(); };
  const skyward = () => cur.pitch > 4;      // the reader is looking at the sky, not at the deck
  if (WATCH && STILL) makeAt(-0.6, probeAt(look0.yaw, look0.pitch, 0.24, 0.32), -0.4);      // a still picture holds one meteor, mid-flight, as a long exposure would
  const fireball = t => {
    const mid = skyward() ? inView((R() - 0.5) * 0.4, 0.2 + R() * 0.25) : probeAt(cur.yaw, 28, (R() - 0.5) * 0.5, 0.2);
    makeAt(t, mid, -5.4 - R() * 1.6, {dur: 1.6 + R() * 0.5, fb: true, hue: fbHue, h: 82, lenK: mix(1.25, 0.5, fast)});
  };
  const spawn = t => {
    if (t - lastT > 2) { nextAt = Math.max(nextAt, t + 0.6 + R() * 2); nextBig = Math.max(nextBig, t + 20 + R() * 30); }      // after a pause (a hidden tab), from now on
    lastT = t;
    while (nextAt <= t) { makeAt(nextAt, pickDir(), magOf()); nextAt += gap(); }
    if (t >= nextBig) { fireball(t); nextBig = t + 100 + R() * 150; }
    for (let i = meteors.length - 1; i >= 0; i--) if (t > meteors[i].t0 + meteors[i].dur + (meteors[i].fb ? 6 : 3.5)) meteors.splice(i, 1);
  };
  /* where the eye settles: the first thing the look lands on among the deck's things, else the sky (for the lens) */
  const ray = new THREE.Ray(), hitP = V3();
  const focusAt = () => {
    ray.origin.copy(cam.position); ray.direction.set(0, 0, -1).applyQuaternion(cam.quaternion);
    let best = 60;
    for (const b of focusBoxes) { if (b.containsPoint(ray.origin)) continue; if (ray.intersectBox(b, hitP)) { const d = hitP.distanceTo(cam.position); if (d < best && d > 0.25) best = d; } }
    return best;
  };
  const frameWatch = (tReal, env = {}) => {
    const t = STILL ? tHeld : tReal;
    cam.updateMatrixWorld(); sky.position.copy(cam.position);
    turn(t);
    const adapt = STILL ? 1 : mix(adapt0, 1, smooth(seg(t, 0.2, 2.8)));
    cur.adapt = adapt;
    U.uTime.value = STILL ? 7 : t; U.uAdapt.value = adapt; U.uLimit.value = mix(1.3, 6.3, adapt);
    if (!STILL) spawn(t);
    drawMeteors(t);
    U.uFlash.value = flash; U.uFlashDir.value.copy(flashDir);
    domeMat.uniforms.uMoonGlow.value = (0.3 + 0.7 * adapt) * litFrac * 0.35;
    halo.material.opacity = (0.025 + 0.06 * litFrac) * (0.4 + 0.6 * adapt);
    const gust = env.gust != null ? env.gust : gustAt(t), flick = STILL ? 1 : flickerOf(t);
    lights(t, adapt, gust, flick, STILL); living(t, adapt, gust);
    if (t - lastMoonSet > 45) { placeMoonLight(); lastMoonSet = t; renderer.shadowMap.needsUpdate = true; }      // the moon has moved on a little: its shadows are drawn again
    for (const m of trees) m.lookAt(cam.position.x, m.position.y, cam.position.z);
    if (cabin && (tReal > 1.2 || Math.abs(cur.yaw) > 60)) cabin.reflect(cam.position, tReal);      // the glass's reflection, once the deck has opened or the reader turns round
    lensP.veilA = 0;
    return 0;
  };

  const facts = {place: W.where, date: W.date.toISOString(), tonight: W.tonight, facing: W.a0, pitch: P_END, shower: W.shower, radiantAlt: Math.round(W.radAlt), radiantAz: Math.round(W.radAz),
    moon: {real: W.moonReal || !!(handed && from.moonReal), tonightFraction: +W.frac.toFixed(3), shownFraction: +litFrac.toFixed(3), waxing: W.waxing, alt: Math.round(altOf(mDir)), tonightAlt: Math.round(W.moonAlt)},
    planets: W.planets.map(p => { const w = radec(p.ra, p.dec).applyMatrix3(W.f.j2w); return {name: p.name, mag: +p.mag.toFixed(1), alt: Math.round(altOf(w)), az: Math.round(azOf(w, W.a0))}; }), seed, elk: elkSeason(W.date)};
  const dispose = () => { if (cabin) cabin.dispose(); scene.traverse(o => { if (o.geometry) o.geometry.dispose(); const ms = o.material ? (Array.isArray(o.material) ? o.material : [o.material]) : [];
    for (const m of ms) { for (const k in m) if (m[k] && m[k].isTexture) m[k].dispose(); if (m.uniforms) for (const k in m.uniforms) { const v = m.uniforms[k].value; if (v && v.isTexture) v.dispose(); } m.dispose(); } }); };
  /* what the sky holds as it stands now, on the deck (the planets and the radiant turn with it) */
  const factsNow = () => {
    const pl = W.planets.map(p => { const w = radec(p.ra, p.dec).applyMatrix3(W.f.j2w).applyMatrix3(Qnow); return {name: p.name, mag: +p.mag.toFixed(1), alt: Math.round(altOf(w)), az: Math.round(azOf(w, W.a0))}; });
    return Object.assign({}, facts, {date: new Date(W.date.getTime() + tSky * 1000).toISOString(), planets: pl, radiantAlt: Math.round(altOf(rad)), radiantAz: Math.round(azOf(rad, W.a0))});
  };
  return {scene, cam, facts, factsNow, dispose, frame, frameWatch, setView, focusAt, lensP, a0: W.a0, portrait: W.portrait, P_END, look0, inChair,
          resize(a, px){ cam.aspect = a; cam.fov = vfovOf(a); cam.updateProjectionMatrix(); if (px) U.uPx.value = px; },
          /* the crossing hands its view to the deck's own page, so the night carries on where it was: seated in the same chair */
          handoff: t => ({a0: W.a0, yaw: +cur.yaw.toFixed(2), pitch: +cur.pitch.toFixed(2), adapt: +cur.adapt.toFixed(3), moon: [mDir.x, mDir.y, mDir.z].map(v => +v.toFixed(5)),
                          moonReal: W.moonReal, date: new Date(W.date.getTime() + t * 1000).toISOString(), tonight: W.tonight, seat: "chair", at: Date.now()}),
          setStill(on, t){ STILL = on ? 1 : 0; U.uStill.value = STILL; tHeld = t; },
          busy: t => flash > 0.001 || meteors.some(m => t >= m.t0 - 0.05 && t <= m.t0 + m.dur + (m.train ? 1.5 : 0.2)),
          reflectNow: () => { if (cabin) cabin.reflect(cam.position, 1e9); },
          meteorNow(t, o = {}){ cam.updateMatrixWorld(); if (o.fireball) { fireball(t); return; } makeAt(t, inView(o.sx != null ? o.sx : 0.18, o.sy != null ? o.sy : 0.3), o.mag != null ? o.mag : 0.6, o); },      // the eyes as they are set now, before the frame has been drawn
          debug: () => ({nq, nh, px: pxWorld(), meteors: meteors.length, turned: +(2 * Math.acos(Math.min(1, Math.abs(cel.quaternion.w))) * R2D).toFixed(4), hi: HI, focus: +lensP.focus.toFixed(2),
            flying: meteors.map(m => ({tau: +((U.uTime.value - m.t0) / m.dur).toFixed(2), mag: +m.mag.toFixed(1), fb: m.fb})).filter(m => m.tau >= 0 && m.tau <= 1)})};
}
function smoothstep01(a, b, x){ return smooth(clamp((x - a) / (b - a))); }

function setup(renderer, w, h, ratio){
  renderer.setPixelRatio(ratio); renderer.setSize(w, h, false);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.NoToneMapping; renderer.outputColorSpace = THREE.SRGBColorSpace;
}

/* ================================ playing it over the page ================================ */
const ARRIVE = "tca.night.arrive";
function leave(url, how){ try { sessionStorage.setItem(ARRIVE, how); } catch (e) {} location.href = url; }
const pixelRatio = (w, h, lean) => lean ? Math.min(1.5, devicePixelRatio || 1, Math.sqrt(1.2e6 / (w * h))) : Math.min(2, devicePixelRatio || 1, Math.sqrt(4.2e6 / (w * h)));
export function run(url, opts = {}){
  if (!supported()) return false;
  let renderer;
  try { renderer = new THREE.WebGLRenderer({antialias: false, powerPreference: "high-performance"}); } catch (e) { return false; }
  const host = opts.host || document.body.appendChild(document.createElement("div"));
  const w = innerWidth, h = innerHeight, lean = !!opts.lean;      // a lean device: the light version, with fewer pixels and a smaller shadow
  setup(renderer, w, h, pixelRatio(w, h, lean));
  let S, lens;
  try { S = build(renderer, w / h, opts.assets, {still: !!opts.still, lean}); lens = lensFor(renderer, lean, {dof: !lean}); } catch (e) { renderer.dispose(); return false; }
  const cv = renderer.domElement; cv.setAttribute("aria-hidden", "true"); cv.style.cssText = "position:absolute;inset:0;display:block;width:100%;height:100%;opacity:0;transition:opacity .45s ease";
  host.prepend(cv);
  let gone = false, dead = false, t0 = 0, raf = 0, tNow = 0, tEnd = DUR;
  const begun = performance.now(), ac = new AbortController(), signal = ac.signal;
  const bye = () => { try { S.dispose(); lens.dispose(); renderer.dispose(); } catch (e) {} };
  const draw = (t, end) => { const v = S.frame(t, end); lens.render(S.scene, S.cam, S.lensP); renderer.shadowMap.autoUpdate = false; return v; };      // nothing that casts a shadow moves: the shadows are drawn once
  const go = (how) => { if (gone) return; gone = true; cancelAnimationFrame(raf); leave(url, how); };
  /* the reader went Back while it played: Forward brings back the page as it was (its pageshow comes before any timer the
     page had waiting), and nothing more happens */
  const halt = () => { gone = dead = true; cancelAnimationFrame(raf); };
  const skip = () => go("skip");
  /* Stay and watch the sky: the deck's own page, the view handed over (this tab only), no fade into Election Night */
  const stay = () => {
    if (gone || !opts.stay) return;
    gone = true; cancelAnimationFrame(raf);
    try { sessionStorage.setItem(STAY, JSON.stringify(S.handoff(opts.still ? 7.4 : tNow))); } catch (e) {}
    cv.style.transition = "opacity .3s ease"; cv.style.opacity = 0;
    setTimeout(() => { if (!dead) location.href = opts.stay; }, 300);
  };
  const onStay = e => !!(e.target && e.target.closest && e.target.closest("[data-stay]"));
  host.addEventListener("pointerdown", e => { if (onStay(e)) return; if (e.button === 0 || e.pointerType !== "mouse") skip(); });
  host.addEventListener("click", e => { if (!onStay(e)) skip(); });      /* the Skip button, however it is pressed (a screen reader may send only a click) */
  if (opts.keys !== false) addEventListener("keydown", skip, {capture: true, once: true, signal});
  addEventListener("resize", () => { renderer.setSize(innerWidth, innerHeight, false); S.resize(innerWidth / innerHeight); const v = new THREE.Vector2(); renderer.getDrawingBufferSize(v); lens.size(v.x, v.y); }, {signal});
  addEventListener("pageshow", e => { if (e.persisted) { halt(); ac.abort(); host.remove(); bye(); } }, {signal});
  if (opts.onStart) opts.onStart(S.facts);
  const holding = () => { try { return !!(opts.hold && opts.hold()); } catch (e) { return false; } };
  if (opts.still) {      // motion off, Calm, or reduced motion: one still picture, then a plain fade (it waits while the reader reaches for Stay)
    draw(7.4); cv.style.transition = "none"; cv.style.opacity = 1;
    const end = () => { if (gone) return; if (holding() && performance.now() - begun < 9000) { setTimeout(end, 250); return; }
      if (opts.fade) opts.fade(); setTimeout(() => go("still"), 420); };
    setTimeout(end, 1700);
    return {skip, stay};
  }
  renderer.compile(S.scene, S.cam); draw(0);
  requestAnimationFrame(() => { cv.style.opacity = 1; });
  const tick = now => {
    if (gone) return;
    if (!t0) t0 = now;
    const t = (now - t0) / 1000;
    if (holding() && t > tEnd - 1.6 && tEnd < DUR + 6) tEnd = Math.min(DUR + 6, t + 1.6);      // reaching for Stay: the night waits a little
    tNow = Math.min(t, tEnd);
    pt.sx += (pt.x - pt.sx) * 0.05; pt.sy += (pt.y - pt.sy) * 0.05;
    draw(tNow, tEnd);
    if (t < tEnd) raf = requestAnimationFrame(tick); else go("full");
  };
  raf = requestAnimationFrame(tick);
  const guard = () => { if (gone) return; if (performance.now() - begun < (tEnd + 1.8) * 1000) { setTimeout(guard, 400); return; } go("full"); };
  setTimeout(guard, DUR * 1000 + 1800);      // a window that is not drawing frames still gets there
  return {skip, stay};
}

/* ================================ the deck to sit on ================================ */
/* Election Night's own page for the deck (John, 2026-10-11): the reader starts seated where they chose and stays as long
   as they like. Drag, touch or the arrow keys look around (no pointer capture: the listeners sit on the window and all go
   with stop()); a button gets them up to walk (W A S D or the arrows; on a phone a thumb control the page gives), down the
   steps and about the yard, never through the railing, the furniture, a tree or the wall; a seat is one tap away again.
   The sky turns in real time; a meteor every few seconds, now and then a brighter one, a fireball every few minutes. Sound
   is off until the reader turns it on. With motion off it is one still picture that still turns with a drag or a key. A
   lean device draws fewer pixels, fewer trees and fewer frames. While nothing moves fast it draws about thirty frames a
   second (twenty on a lean device), to spare the battery.
     watch(canvas, {assets, more, sounds: {elk, coyotes, stream}, seat, from, still, lean, stick, keysOK(e), onReady(facts),
                    onInput(kind), onLook(facing), onMove(state), onStick(x, y), onLost()})
   returns a controller: stop(), seat(id), stand(), sit(), setStill(on), setSound(on) (a Promise while the recordings
   load, else null), soundOn(), walkHold(on), look(yaw, pitch), facing(), state(), facts, factsNow(), meteor(o), seats, t */
export function watch(canvas, opts = {}){
  if (!canvas || !opts.assets || !supported()) return null;
  let renderer;
  try { renderer = new THREE.WebGLRenderer({canvas, antialias: false, powerPreference: opts.lean ? "low-power" : "high-performance", preserveDrawingBuffer: !!opts.keep}); } catch (e) { return null; }
  const lean = !!opts.lean, ac = new AbortController(), on = (el, ev, fn, o) => el.addEventListener(ev, fn, Object.assign({signal: ac.signal}, o || {}));
  const dims = () => { const r = canvas.getBoundingClientRect(); return [Math.max(1, Math.round(r.width || innerWidth)), Math.max(1, Math.round(r.height || innerHeight))]; };
  let [w, h] = dims();
  setup(renderer, w, h, pixelRatio(w, h, lean));
  let from = null;
  const f = opts.from;
  if (f && isFinite(f.a0) && isFinite(f.yaw) && isFinite(f.pitch) && isFinite(Date.parse(f.date)) && isFinite(f.at)) {
    from = Object.assign({}, f, {date: new Date(Date.parse(f.date) + clamp(Date.now() - f.at, 0, 6e5)).toISOString()});
  }
  let S, lens;
  try { S = build(renderer, w / h, opts.assets, {watch: true, still: !!opts.still, lean, from, more: opts.more, seed: opts.seed, place: opts.place, date: opts.date, seat: opts.seat}); lens = lensFor(renderer, lean, {dof: !lean}); }
  catch (e) { console.warn("The deck could not be drawn:", e); renderer.dispose(); return null; }
  const sound = new DeckSound({urls: opts.sounds || {}, season: opts.elk});
  let still = !!opts.still, alive = true, raf = 0, t0 = performance.now(), last = t0, drawn = 0, settleT = 0, veilA = 0, focus = 60, ready = false;
  const tNow = () => (performance.now() - t0) / 1000;
  /* the reader: where they are, which way they look, seated or on foot */
  const seatOf = id => SEATS.find(s => s.id === id) || null;
  const seatPitch = s => S.portrait ? s.pitchPhone : s.pitch;
  const me = {pos: V3(), y: 0, floor: 0, eye: 1.1, yaw: 0, pitch: 0, mode: "seated", seat: "chair", bob: 0, phase: 0, vel: V3()};
  const place = s => { me.pos.set(s.eye[0], 0, s.eye[2]); me.floor = heightAt(s.eye[0], s.eye[2]); me.eye = s.eye[1] - me.floor; me.y = s.eye[1]; me.yaw = s.yaw; me.pitch = seatPitch(s); me.seat = s.id; me.mode = "seated"; me.vel.set(0, 0, 0); };
  place(seatOf(opts.seat) || SEATS[0]);
  /* the view the crossing handed over (this tab only, within two minutes): the same chair, looking the same way; handed
     over before the crossing looked up, it carries on up */
  let glide = null;
  if (from) { place(SEATS[0]); me.yaw = clamp(+from.yaw || 0, -180, 180); me.pitch = clamp(+from.pitch || 0, -40, 88);
    if (from.pitch < S.P_END - 4) glide = {from: me.pitch, to: S.P_END - 2, t0: 0.5, t1: 3.6}; }
  const wrapDeg = a => { a = (a + 180) % 360; if (a < 0) a += 360; return a - 180; };
  /* the move between seats: a fade down, the move, a fade up (a cut, as a film cuts); getting up and sitting down nearby
     are played out over a second and a quarter */
  let cut = null, rising = null;
  const cutTo = fn => { if (cut) return; cut = {t: tNow(), fn}; poke(); };
  const standUp = () => {
    if (me.mode !== "seated" || rising) return;
    const s = seatOf(me.seat), to = V3(s.stand[0], 0, s.stand[1]), fl = heightAt(to.x, to.z), pitch1 = clamp(me.pitch * 0.6, -30, 30);
    if (still) { me.pos.copy(to); me.floor = fl; me.eye = STAND_EYE; me.y = fl + STAND_EYE; me.pitch = pitch1; me.mode = "walking"; if (opts.onMove) opts.onMove(state()); poke(); return; }
    rising = {t: tNow(), from: me.pos.clone(), fromY: me.y, to, toY: fl + STAND_EYE, dir: 1, pitch0: me.pitch, pitch1, yaw0: me.yaw, yaw1: null};
    me.mode = "walking"; me.eye = STAND_EYE; if (opts.onMove) opts.onMove(state()); poke();
  };
  const nearestSeat = () => { let best = SEATS[0], bd = 1e9; for (const s of SEATS) { const d = Math.hypot(me.pos.x - s.stand[0], me.pos.z - s.stand[1]); if (d < bd) { bd = d; best = s; } } return best.id; };
  const sitDown = id => {
    const want = id && seatOf(id) ? id : nearestSeat(), s = seatOf(want);
    if (me.mode === "walking" && !rising && Math.hypot(me.pos.x - s.stand[0], me.pos.z - s.stand[1]) < 1.7) {      // close by: sit, no cut
      if (still) { place(s); sound.sit(s.sat); if (opts.onMove) opts.onMove(state()); poke(); return; }
      rising = {t: tNow(), from: me.pos.clone(), fromY: me.y, to: V3(s.eye[0], 0, s.eye[2]), toY: s.eye[1], dir: -1, pitch0: me.pitch, pitch1: seatPitch(s), yaw0: me.yaw, yaw1: s.yaw, seat: want};
      me.seat = want; me.vel.set(0, 0, 0); poke(); return;
    }
    cutTo(() => { place(s); sound.sit(s.sat); if (opts.onMove) opts.onMove(state()); });
  };
  /* looking around: drag (a mouse, a finger, a pen), with a little glide after a quick drag; the arrow keys turn the head
     when seated, and on foot the arrows and W A S D walk */
  const kdeg = () => S.cam.fov / Math.max(1, h);      // degrees per pixel at the middle: the sky follows the finger
  let drag = null; const inertia = {y: 0, p: 0}, held = new Set(), stick = {x: 0, y: 0, on: false};
  let walkHeld = false;
  const turnBy = (dy, dp) => { glide = null; me.yaw = wrapDeg(me.yaw + dy); me.pitch = clamp(me.pitch + dp, -62, 88); };
  const said = () => { clearTimeout(settleT); settleT = setTimeout(() => { if (opts.onLook) opts.onLook(facing()); }, 650); };
  const onStick = e => stick.on && e.target && e.target.closest && e.target.closest("[data-stick]");
  on(canvas, "pointerdown", e => {
    if (drag || (e.pointerType === "mouse" && e.button !== 0) || onStick(e)) return;
    drag = {id: e.pointerId, x: e.clientX, y: e.clientY, s: []}; inertia.y = inertia.p = 0;
    canvas.classList.add("dragging"); if (opts.onInput) opts.onInput("drag"); poke();
  });
  on(window, "pointermove", e => {
    if (!drag || e.pointerId !== drag.id) return;
    const kk = kdeg(), dy = -(e.clientX - drag.x) * kk, dp = (e.clientY - drag.y) * kk;
    drag.x = e.clientX; drag.y = e.clientY; turnBy(dy, dp);
    drag.s.push([performance.now(), dy, dp]); if (drag.s.length > 8) drag.s.shift();
    poke();
  }, {passive: true});
  const endDrag = e => {
    if (!drag || (e && e.pointerId != null && e.pointerId !== drag.id)) return;
    const now = performance.now(), sm = drag.s.filter(q => now - q[0] < 90);
    if (!still && sm.length >= 2) { const span = Math.max(0.03, (now - sm[0][0]) / 1000); inertia.y = clamp(sm.reduce((a, q) => a + q[1], 0) / span, -240, 240); inertia.p = clamp(sm.reduce((a, q) => a + q[2], 0) / span, -160, 160); }
    drag = null; canvas.classList.remove("dragging"); poke(); said();
  };
  on(window, "pointerup", endDrag); on(window, "pointercancel", endDrag);
  on(window, "blur", () => { endDrag(); held.clear(); walkHeld = false; });
  const KEYS = {ArrowLeft: "left", ArrowRight: "right", ArrowUp: "up", ArrowDown: "down", w: "fwd", W: "fwd", s: "back", S: "back", a: "strafeL", A: "strafeL", d: "strafeR", D: "strafeR"};
  on(window, "keydown", e => {
    const k = KEYS[e.key];
    if (!k || e.altKey || e.ctrlKey || e.metaKey || (opts.keysOK && !opts.keysOK(e))) return;
    if (me.mode === "seated" && (k === "fwd" || k === "back" || k === "strafeL" || k === "strafeR")) return;      // the letters only walk
    e.preventDefault(); if (opts.onInput) opts.onInput("key");
    if (still && me.mode === "seated") { turnBy(k === "left" ? -6 : k === "right" ? 6 : 0, k === "up" ? 4 : k === "down" ? -4 : 0); poke(); said(); return; }      // a still picture turns a step at a time
    held.add(k); poke();
  });
  on(window, "keyup", e => { const k = KEYS[e.key]; if (k && held.delete(k)) { poke(); said(); } });
  /* a phone's thumb control: the page gives an element; a finger on it walks the way the eyes look */
  const stickEl = opts.stick || null;
  if (stickEl) {
    let sid = null; const rect = () => stickEl.getBoundingClientRect();
    const set = e => { const r = rect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2, rad = Math.max(20, r.width / 2); stick.x = clamp((e.clientX - cx) / rad, -1, 1); stick.y = clamp(-(e.clientY - cy) / rad, -1, 1); if (opts.onStick) opts.onStick(stick.x, stick.y); };
    on(stickEl, "pointerdown", e => { if (me.mode !== "walking") return; sid = e.pointerId; stick.on = true; set(e); e.preventDefault(); if (opts.onInput) opts.onInput("stick"); poke(); });
    on(window, "pointermove", e => { if (stick.on && e.pointerId === sid) { set(e); poke(); } }, {passive: true});
    const off = e => { if (stick.on && (!e || e.pointerId === sid)) { stick.on = false; stick.x = stick.y = 0; if (opts.onStick) opts.onStick(0, 0); poke(); } };
    on(window, "pointerup", off); on(window, "pointercancel", off);
  }
  /* a step on foot: the floor's rules, tried whole and then along each axis, so a reader slides along what they meet */
  const tryMove = (dx, dz) => {
    if (walkOK(me.pos.x + dx, me.pos.z + dz)) { me.pos.x += dx; me.pos.z += dz; return true; }
    let moved = false;
    if (dx && walkOK(me.pos.x + dx, me.pos.z)) { me.pos.x += dx; moved = true; }
    if (dz && walkOK(me.pos.x, me.pos.z + dz)) { me.pos.z += dz; moved = true; }
    return moved;
  };
  const step = dt => {
    let moving = !!drag;
    const sp = (a, b) => held.has(a) ? 1 : held.has(b) ? -1 : 0;
    if (me.mode === "seated") {
      if (held.size) { turnBy(sp("right", "left") * 62 * dt, sp("up", "down") * 40 * dt); moving = true; }
    } else if (!rising) {
      const turn = sp("right", "left");
      if (turn) { turnBy(turn * 70 * dt, 0); moving = true; }
      /* on foot: the arrows turn and walk; W A S D walk; the thumb control walks the way you look */
      const fwd = (held.has("fwd") || held.has("up") || walkHeld ? 1 : 0) - (held.has("back") || held.has("down") ? 1 : 0), side = sp("strafeR", "strafeL");
      const yawR = me.yaw * D2R, fdir = V3(Math.sin(yawR), 0, -Math.cos(yawR)), rdir = V3(Math.cos(yawR), 0, Math.sin(yawR));
      const want = V3().addScaledVector(fdir, fwd + (stick.on ? stick.y : 0)).addScaledVector(rdir, side + (stick.on ? stick.x : 0));
      if (want.lengthSq() > 1) want.normalize();
      want.multiplyScalar(WALK_SPEED);
      me.vel.lerp(want, 1 - Math.exp(-dt / 0.18));      // weight: a person gets going and stops over a fifth of a second
      if (me.vel.lengthSq() > 1e-4) {
        const moved = tryMove(me.vel.x * dt, me.vel.z * dt);
        if (!moved) me.vel.multiplyScalar(0.5);
        const v = me.vel.length(), ph0 = me.phase;
        me.phase += dt * v * 1.75;      // steps: about 1.75 a second at walking pace
        if (Math.floor(me.phase) !== Math.floor(ph0) && v > 0.3) sound.step(floorKind(me.pos.x, me.pos.z), v / WALK_SPEED);
        me.bob = Math.min(1, v / WALK_SPEED);
        moving = true;
      } else { me.bob *= Math.exp(-dt / 0.3); }
      me.floor = heightAt(me.pos.x, me.pos.z);
    }
    if (!drag && (Math.abs(inertia.y) > 0.6 || Math.abs(inertia.p) > 0.6)) {
      turnBy(inertia.y * dt, inertia.p * dt); const q = Math.exp(-dt / 0.32); inertia.y *= q; inertia.p *= q; moving = true;
      if (Math.abs(inertia.y) <= 0.6 && Math.abs(inertia.p) <= 0.6) said();
    } else if (!drag) inertia.y = inertia.p = 0;
    return moving;
  };
  /* the eyes, this frame: the seat or the walk, the rise between them, the breath, the step's bob, the head's small
     unsteadiness, then the lens's focus easing toward what the eyes are on */
  const eyes = (t, dt) => {
    const p = V3(me.pos.x, 0, me.pos.z);
    let yaw = me.yaw, pitch = me.pitch, roll = 0;
    if (glide && !still) { const k = smooth(seg(t, glide.t0, glide.t1)); me.pitch = pitch = mix(glide.from, glide.to, k); if (k >= 1) glide = null; }
    if (rising) {
      const u = inOut(clamp((t - rising.t) / 1.25));
      p.copy(rising.from).lerp(rising.to, u); p.y = mix(rising.fromY, rising.toY, u) + Math.sin(u * Math.PI) * 0.03 * rising.dir;
      me.pitch = pitch = mix(rising.pitch0, rising.pitch1, u);
      if (rising.yaw1 != null) me.yaw = yaw = rising.yaw0 + wrapDeg(rising.yaw1 - rising.yaw0) * u;
      me.y = p.y;
      if (u >= 1) { if (rising.dir < 0) { place(seatOf(rising.seat)); sound.sit(seatOf(rising.seat).sat); } else { me.pos.copy(rising.to); me.floor = heightAt(me.pos.x, me.pos.z); me.eye = STAND_EYE; me.y = me.floor + STAND_EYE; }
        rising = null; if (opts.onMove) opts.onMove(state()); }
      else me.pos.set(p.x, 0, p.z);
    } else if (me.mode === "seated") {
      p.y = me.floor + me.eye + (still ? 0 : 0.004 * Math.sin(t * 1.45)); me.y = p.y;
      if (!still) { pitch += 0.22 * Math.sin(t * 1.45 + 0.4) + 0.12 * Math.sin(t * 0.61); yaw += 0.18 * Math.sin(t * 0.37 + 1.3); }
    } else {
      me.y += (me.floor + STAND_EYE - me.y) * (1 - Math.exp(-dt / 0.12));      // the eyes follow the floor down the steps smoothly
      p.y = me.y + (still ? 0 : 0.006 * Math.sin(t * 1.35) + me.bob * 0.022 * Math.sin(me.phase * Math.PI * 2));
      roll = me.bob * 0.35 * Math.sin(me.phase * Math.PI); yaw += me.bob * 0.25 * Math.sin(me.phase * Math.PI);
    }
    if (!still) { yaw += 0.05 * Math.sin(t * 0.53 + 1.3); pitch += 0.04 * Math.sin(t * 0.47); roll += 0.05 * Math.sin(t * 0.33) + 0.3 * Math.sin(t * 0.5) * 0.02; }
    S.setView(p, yaw, pitch, roll);
    const want = S.focusAt(); focus += (want - focus) * (1 - Math.exp(-dt / 0.45));
    S.lensP.focus = focus; S.lensP.aper = lean || still ? 0 : (me.mode === "seated" ? 0.9 : 0.7);
    S.inChair(me.mode === "seated" && me.seat === "chair" || (rising && rising.dir < 0 && rising.seat === "chair"));
  };
  const flickOf = t => 1 + 0.05 * Math.sin(t * 7.1) + 0.035 * Math.sin(t * 12.7 + 1) + 0.02 * Math.sin(t * 23.3);
  const draw = (t, dt) => {
    eyes(t, dt); const gust = gustAt(t); S.frameWatch(t, {gust});
    if (cut) { const u = (t - cut.t); if (u < 0.32) veilA = u / 0.32; else if (cut.fn) { cut.fn(); cut.fn = null; veilA = 1; } else veilA = Math.max(0, 1 - (u - 0.4) / 0.6); if (u > 1.0) cut = null; }
    else veilA = 0;
    S.lensP.veilA = veilA;
    lens.render(S.scene, S.cam, S.lensP);
    renderer.shadowMap.autoUpdate = false;      // the window's light and what it falls on never move; the moon's shadows are drawn again as it moves on
    sound.update(S.cam, gust, still ? 1 : flickOf(t));
  };
  const tick = now => {
    raf = 0; if (!alive) return;
    const dt = Math.min(0.1, Math.max(0, (now - last) / 1000)); last = now;
    const moving = step(dt), t = tNow();
    if (still) { draw(t, dt); drawn = now; if (cut || rising || stick.on || held.size || drag) raf = requestAnimationFrame(tick); return; }      // a still picture is drawn again only when the reader turns it, moves seat, or walks (a held key, the thumb control)
    const busy = moving || !!rising || !!cut || t < 3.2 || S.busy(t), gapMs = busy ? (lean ? 31 : 0) : (lean ? 48 : 31);
    if (now - drawn >= gapMs) { drawn = now; draw(t, dt); }
    raf = requestAnimationFrame(tick);
  };
  const poke = () => { if (!raf && alive) raf = requestAnimationFrame(tick); };
  const resize = () => { [w, h] = dims(); renderer.setPixelRatio(pixelRatio(w, h, lean)); renderer.setSize(w, h, false); S.resize(w / h, renderer.getPixelRatio()); const v = new THREE.Vector2(); renderer.getDrawingBufferSize(v); lens.size(v.x, v.y); poke(); };
  on(window, "resize", resize); if (window.visualViewport) on(window.visualViewport, "resize", resize);
  on(canvas, "webglcontextlost", e => { e.preventDefault(); ctl.stop(); if (opts.onLost) opts.onLost(); });
  on(window, "pagehide", e => { if (e.persisted) { alive = false; if (raf) cancelAnimationFrame(raf); raf = 0; sound.pause(); } else ctl.stop(); });
  on(window, "pageshow", e => { if (e.persisted && !alive) { alive = true; last = performance.now(); sound.resume(); poke(); } });
  on(document, "visibilitychange", () => { if (document.hidden) sound.pause(); else sound.resume(); });
  const facing = () => ({az: (((S.a0 + me.yaw) % 360) + 360) % 360, alt: me.pitch, yaw: me.yaw});
  const state = () => ({seat: me.mode === "seated" ? me.seat : null, mode: me.mode, near: me.mode === "walking" ? nearestSeat() : me.seat, floor: floorKind(me.pos.x, me.pos.z),
                        pos: [+me.pos.x.toFixed(2), +me.y.toFixed(2), +me.pos.z.toFixed(2)]});
  if (still) S.setStill(true, 0);
  renderer.compile(S.scene, S.cam); draw(0, 0); drawn = performance.now(); ready = true;
  if (opts.onReady) setTimeout(() => opts.onReady(S.facts), 0);
  const ctl = {
    stop(){ if (!ac.signal.aborted) { alive = false; if (raf) cancelAnimationFrame(raf); raf = 0; clearTimeout(settleT); ac.abort(); sound.close(); S.dispose(); lens.dispose(); renderer.dispose(); } },
    seat(id){ if (!seatOf(id)) return; if (me.mode === "seated" && me.seat === id && !rising) return; sitDown(id); },
    stand(){ standUp(); },
    sit(){ sitDown(null); },
    setStill(on){ still = !!on; S.setStill(still, tNow()); inertia.y = inertia.p = 0; held.clear(); walkHeld = false; poke(); },
    setSound(v){ if (v) return sound.start(); sound.stop(); return null; },
    soundOn: () => sound.on,
    walkHold(v){ walkHeld = !!v; poke(); },
    look(yaw, pitch){ glide = null; me.yaw = wrapDeg(yaw); me.pitch = clamp(pitch, -62, 88); poke(); },
    facing, state, seats: SEATS, facts: S.facts, factsNow: () => S.factsNow(),
    get t(){ return tNow(); }, get ready(){ return ready; },
    meteor(o = {}){ S.meteorNow(tNow() + 0.05, o); poke(); },      // for checking: one meteor where the reader looks, now
    debug: () => Object.assign(S.debug(), state()), scene: S.scene, redraw: () => poke(), _sound: sound
  };
  if (!still) poke();
  return ctl;
}

/* one frame, for checking: at second t of the crossing; opts.watch draws the deck instead, from opts.seat (chair, steps,
   bench) or opts.walk {x, z, yaw, pitch} (standing), with opts.look {yaw, pitch} turning the head, opts.more the deck's
   files by address, opts.meteor one meteor in view; opts.lean the light version; opts.still the still picture */
export async function still(t = 6, w = 960, h = 540, opts = {}){
  const A = await prepare(), more = opts.more ? await loadMore(opts.more) : null;
  if (opts.pt) { pt.x = pt.sx = opts.pt.x; pt.y = pt.sy = opts.pt.y; } else { pt.x = pt.sx = pt.y = pt.sy = 0; }
  const renderer = new THREE.WebGLRenderer({antialias: false, preserveDrawingBuffer: true});
  setup(renderer, w, h, opts.ratio || 1);
  const lean = !!opts.lean, t1 = performance.now();
  const S = build(renderer, w / h, A, Object.assign({seed: 7}, opts, {more}));
  const lens = lensFor(renderer, lean, {dof: opts.dof !== false && !lean});
  let v = 0;
  renderer.compile(S.scene, S.cam);
  if (opts.watch) {
    const seat = SEATS.find(s => s.id === opts.seat) || SEATS[0];
    let p = V3(seat.eye[0], seat.eye[1], seat.eye[2]), yaw = seat.yaw, pitch = S.portrait ? seat.pitchPhone : seat.pitch;
    if (opts.walk) { p = V3(opts.walk.x, heightAt(opts.walk.x, opts.walk.z) + STAND_EYE, opts.walk.z); yaw = opts.walk.yaw != null ? opts.walk.yaw : yaw; pitch = opts.walk.pitch != null ? opts.walk.pitch : 0; }
    if (opts.look) { if (opts.look.yaw != null) yaw = opts.look.yaw; if (opts.look.pitch != null) pitch = opts.look.pitch; }
    S.setView(p, yaw, pitch, 0);
    if (opts.still) S.setStill(true, t);
    if (opts.meteor) { const ago = opts.meteor.ago != null ? opts.meteor.ago : 0.3, o = Object.assign({}, opts.meteor); if (o.dur == null && !o.fireball) o.dur = Math.max(0.45, ago / 0.6); S.meteorNow(t - ago, o); }      // mid-flight at t, whatever the shower's speed
    S.frameWatch(t); S.reflectNow(); S.frameWatch(t);
    S.inChair(!opts.walk && seat.id === "chair");
    S.lensP.focus = opts.focus != null ? opts.focus : S.focusAt(); S.lensP.aper = lean || opts.still ? 0 : (opts.aper != null ? opts.aper : opts.walk ? 0.7 : 0.9); S.lensP.veilA = 0;
  } else v = S.frame(t);
  lens.render(S.scene, S.cam, S.lensP);
  const gl = renderer.getContext(); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4));
  const t2 = performance.now(), url = renderer.domElement.toDataURL(opts.png ? "image/png" : "image/jpeg", 0.92), dbg = S.debug();
  const info = {hdr: lens.hdr, samples: lens.samples, focus: +S.lensP.focus.toFixed(2), aper: S.lensP.aper, ms: Math.round(t2 - t1), size: [renderer.domElement.width, renderer.domElement.height], hi: dbg.hi};
  S.dispose(); lens.dispose(); renderer.dispose(); renderer.forceContextLoss();
  return {url, veil: v, facts: S.facts, debug: dbg, info};
}
export async function facts(opts = {}){
  const A = await prepare();
  const W = plan(A, opts);
  return {place: W.where, date: W.date.toISOString(), tonight: W.tonight, facing: W.a0, shower: W.shower, moonReal: W.moonReal, tonightFraction: +W.frac.toFixed(3), elk: elkSeason(W.date),
          planets: W.planets.map(p => { const w = radec(p.ra, p.dec).applyMatrix3(W.f.j2w); return {name: p.name, mag: +p.mag.toFixed(1), alt: Math.round(altOf(w)), az: Math.round(azOf(w, W.a0))}; })};
}
