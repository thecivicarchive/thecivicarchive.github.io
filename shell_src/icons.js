/* The Civic Archive: the six icons, defined once (Shell Spec section 8; Election Night added 2026-10-10).
   Bills, Ballot, Election Night, Officials, Method, Access. Every page that shows one of them takes it from here: the page builder
   reads the registry between the two markers below and writes the drawing into the page (so an icon is fully drawn
   even when no script runs), and fillIcons() fills any empty data-icon slot a page leaves for the script.
   The registry between the markers must stay plain JSON. Every path carries pathLength="1" so the draw-in can run;
   the drawing itself is the rest state, and every move in the stylesheet ends on it.
   Icons are decorative: aria-hidden and not focusable. The visible label beside each one is the accessible name. */

/*ICONS-BEGIN*/
export const ICONS = {
  "bills": {
    "label": "Bills",
    "tile": "brass",
    "move": "the page lifts and two sheets fan out behind it",
    "svg": "<g class=\"i-s2\"><path class=\"i-fill\" pathLength=\"1\" d=\"M7.4 5h7.3l2.9 2.9V19.6H7.4z\"/></g><g class=\"i-s1\"><path class=\"i-fill\" pathLength=\"1\" d=\"M7.4 5h7.3l2.9 2.9V19.6H7.4z\"/></g><g class=\"i-pg\"><path class=\"i-fill\" pathLength=\"1\" d=\"M7.4 5h7.3l2.9 2.9V19.6H7.4z\"/><path pathLength=\"1\" d=\"M14.7 5v2.9h2.9\"/><path pathLength=\"1\" d=\"M9.8 11.1h5.4\"/><path pathLength=\"1\" d=\"M9.8 13.9h5.4\"/><path pathLength=\"1\" d=\"M9.8 16.7h3.4\"/></g>"
  },
  "ballot": {
    "label": "Ballot",
    "tile": "verd",
    "move": "the ballot drops in, the box thunks, a fresh ballot is checked",
    "svg": "<g class=\"i-box\"><path pathLength=\"1\" d=\"M4.4 12.6h15.2v7.4H4.4z\"/><path pathLength=\"1\" d=\"M8.3 15.4h7.4\"/></g><g class=\"i-paper\"><path class=\"i-fill\" pathLength=\"1\" d=\"M8.4 3.8h7.2v8.8H8.4z\"/><path class=\"i-tick\" pathLength=\"1\" d=\"M10.1 8.3l1.5 1.5 2.4-2.7\"/></g>"
  },
  "night": {
    "label": "Election Night",
    "tile": "brass",
    "move": "the count comes in bar by bar under a rocking moon",
    "svg": "<path class=\"i-moon\" pathLength=\"1\" d=\"M6.81 3.92A3.5 3.5 0 1 0 10.61 8.17A2.9 2.9 0 0 1 6.81 3.92z\"/><path class=\"i-fill i-b1\" pathLength=\"1\" d=\"M5.4 19.6V15.6h2.8v4z\"/><path class=\"i-fill i-b2\" pathLength=\"1\" d=\"M10.6 19.6V12.4h2.8v7.2z\"/><path class=\"i-fill i-b3\" pathLength=\"1\" d=\"M15.8 19.6V9.2h2.8v10.4z\"/><path pathLength=\"1\" d=\"M3.6 19.6h16.8\"/>"
  },
  "officials": {
    "label": "Officials",
    "tile": "brass",
    "move": "the delegation rises behind the centre figure",
    "svg": "<g class=\"i-l\"><path pathLength=\"1\" d=\"M6.1 8.3a1.9 1.9 0 1 1 0 3.8a1.9 1.9 0 1 1 0-3.8z\"/><path pathLength=\"1\" d=\"M2.6 18.6c0-2.4 1.5-4.2 3.5-4.2c.9 0 1.7.3 2.3.9\"/></g><g class=\"i-r\"><path pathLength=\"1\" d=\"M17.9 8.3a1.9 1.9 0 1 1 0 3.8a1.9 1.9 0 1 1 0-3.8z\"/><path pathLength=\"1\" d=\"M21.4 18.6c0-2.4-1.5-4.2-3.5-4.2c-.9 0-1.7.3-2.3.9\"/></g><g class=\"i-c\"><path class=\"i-fill i-solid\" d=\"M6.8 20.2c0-3.2 2.3-5.7 5.2-5.7s5.2 2.5 5.2 5.7z\"/><path class=\"i-fill\" pathLength=\"1\" d=\"M12 5.5a2.7 2.7 0 1 1 0 5.4a2.7 2.7 0 1 1 0-5.4z\"/><path pathLength=\"1\" d=\"M6.8 20.2c0-3.2 2.3-5.7 5.2-5.7s5.2 2.5 5.2 5.7\"/></g>"
  },
  "method": {
    "label": "Method",
    "tile": "verd",
    "move": "a scan sweeps the shield; the check is wiped and re-ticked",
    "svg": "<path class=\"i-fill\" pathLength=\"1\" d=\"M12 3.5l6.9 2.6v5.3c0 4.3-2.9 7.6-6.9 9.1c-4-1.5-6.9-4.8-6.9-9.1V6.1z\"/><path class=\"i-scan\" pathLength=\"1\" d=\"M7.2 7.4h9.6\"/><path class=\"i-ck\" pathLength=\"1\" d=\"M8.8 12.2l2.3 2.3 4.2-4.5\"/>"
  },
  "access": {
    "label": "Access",
    "tile": "both",
    "move": "both arms rise and the ring ripples out",
    "svg": "<path class=\"i-rip\" pathLength=\"1\" d=\"M12 2.9a9.1 9.1 0 1 1 0 18.2a9.1 9.1 0 1 1 0-18.2z\"/><path class=\"i-ring\" pathLength=\"1\" d=\"M12 2.9a9.1 9.1 0 1 1 0 18.2a9.1 9.1 0 1 1 0-18.2z\"/><path pathLength=\"1\" d=\"M12 5.8a1.5 1.5 0 1 1 0 3a1.5 1.5 0 1 1 0-3z\"/><path class=\"i-arm-l\" pathLength=\"1\" d=\"M12 10.7L7.5 9.8\"/><path class=\"i-arm-r\" pathLength=\"1\" d=\"M12 10.7l4.5-.9\"/><path pathLength=\"1\" d=\"M12 10.7v3.6\"/><path pathLength=\"1\" d=\"M12 14.3l-2.3 4.1\"/><path pathLength=\"1\" d=\"M12 14.3l2.3 4.1\"/>"
  }
};
/*ICONS-END*/

/* The markup for one icon: a tile with the drawing inside. */
export function iconHTML(name, extra) {
  const i = ICONS[name];
  if (!i) return "";
  return `<span class="tca-ico${extra ? " " + extra : ""}" data-icon="${name}" data-tile="${i.tile}"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">${i.svg}</svg></span>`;
}

/* Fills every data-icon slot under `root` that has no drawing yet. Slots the page builder already filled are left alone. */
export function fillIcons(root) {
  for (const el of (root || document).querySelectorAll("[data-icon]")) {
    const i = ICONS[el.dataset.icon];
    if (!i || el.querySelector("svg")) continue;
    el.classList.add("tca-ico");
    el.dataset.tile = i.tile;
    el.insertAdjacentHTML("beforeend", `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">${i.svg}</svg>`);
  }
}
