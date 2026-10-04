/* The Civic Archive: the first thing every page runs, in its head, before anything is drawn (Shell Spec sections 0 and 4).
   It reads the reader's settings from this browser and writes the eleven axes onto <html> as data-* attributes, so the
   very first frame is already right: the right type, size, contrast and motion. Nothing is sent anywhere.
   On a first visit (no saved settings) it honours the device's own wishes: reduced motion, more contrast.
   The rest of the site still keeps two older switches of its own, "theme" (light or dark) and "motion" (on or off);
   they are read here so that a choice made on any page carries to every other page. */
(function () {
  var d = document.documentElement, KEY = "tca.a11y.v1";
  var ALLOW = {
    depth: ["standard", "detailed", "focus"], lang: ["standard", "plain"], face: ["standard", "dyslexia", "hyperlegible"],
    scale: ["100", "115", "130", "150", "200"], space: ["standard", "generous"], contrast: ["standard", "high", "dark"],
    palette: ["standard", "deut", "prot", "trit", "mono"], motion: ["full", "reduced"], calm: ["off", "on"],
    reveal: ["full", "subtle", "off"], companion: ["on", "still", "off"]
  };
  var PERCH = __PERCH__;
  var get = function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } };
  var mq = function (q) { try { return window.matchMedia(q).matches; } catch (e) { return false; } };
  var ax = {}, k, saved = null;
  for (k in ALLOW) ax[k] = ALLOW[k][0];      /* the first value of each axis is its default */
  try { saved = JSON.parse(get(KEY) || "null"); } catch (e) { saved = null; }
  if (saved && typeof saved === "object") {
    for (k in ALLOW) if (ALLOW[k].indexOf(String(saved[k])) >= 0) ax[k] = String(saved[k]);
  } else {
    if (mq("(prefers-reduced-motion: reduce)")) ax.motion = "reduced";
    if (mq("(prefers-contrast: more)")) ax.contrast = "high";
  }
  /* the older switches, set on the record and ballot pages: the newer choice wins, high contrast is never undone */
  var theme = get("theme"), motion = get("motion");
  if (theme === "dark" && ax.contrast === "standard") ax.contrast = "dark";
  if (theme === "light" && ax.contrast === "dark") ax.contrast = "standard";
  if (motion === "off") ax.motion = "reduced";
  if (motion === "on") ax.motion = "full";
  for (k in ax) d.setAttribute("data-" + k, ax[k]);
  /* a chickadee perches under the top bar: make room before the first frame, so nothing moves when it lands */
  var skin = get("tca.companion.skin");
  d.setAttribute("data-perch", (ax.companion !== "off" && skin && PERCH.indexOf(skin) >= 0) ? "on" : "off");
  /* a lean device (little memory, few cores, or a reader who asked to save data) gets the light version of every effect.
     The browser's guess at the line's speed is left out: on a fresh tab it can read "3g", even "slow-2g", on a fast
     machine, and the effects it would lighten are drawn by the device, not fetched */
  var n = navigator, c = n.connection || {}, lean = false;
  try { lean = (n.deviceMemory && n.deviceMemory < 4) || (n.hardwareConcurrency && n.hardwareConcurrency <= 4) || !!c.saveData; } catch (e) { lean = false; }
  d.setAttribute("data-lean", lean ? "on" : "off");
  d.classList.add("js");
})();
