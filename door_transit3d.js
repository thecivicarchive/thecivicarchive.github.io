/*
 door_transit3d.js - the two crossings between the front door and On The Ballot, in 3D and in the first person
 (John, 2026-09-29: "3D anchored as if it were in reality right in front of the person, as if you could see your hand
 reaching out to it ... immersive in reality"). The camera is your eyes. Your hand is never drawn, but the ballot is
 held where a hand holds it, with a hand's small unsteadiness, and leans toward the pointer; the book you pull is the
 one nearest the pointer; and the room shifts a little as the pointer moves, as a room does when you move your head.

   run("scanner", url)    a polling place: you step up to the scanner on the ballot box and feed your ballot into its
                          slot, as on the real machines; the rollers take it, the screen says it was counted, and you
                          lean in to the screen
   run("bookshelf", url)  a study: you pull one book, the shelves shudder and the books tumble toward you, the empty
                          bookcase pushes back and swings aside, and the lit passage behind it draws you through

 Uses three.js (MIT licence, vendor/three.module.min.js), kept with the site so nothing is fetched from anyone else's
 server. build_door.py copies this file to site/dev/transit3d.js; the doors load it on the first hover or tap and call
 run() on a click. run() returns false when the device cannot draw WebGL, and the page then plays its flat scenes.
 still(kind, seconds) draws a single frame to a picture, for checking a scene without playing it.
 The ballot is generic: no names, no parties.
*/
import * as THREE from "./vendor/three.module.min.js";

const clamp01 = x => Math.max(0, Math.min(1, x));
const seg = (t, a, b) => clamp01((t - a) / (b - a));
const smooth = x => x * x * (3 - 2 * x);
const inOut = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
const outBack = x => 1 + 1.8 * Math.pow(x - 1, 3) + .8 * Math.pow(x - 1, 2);      // a heavy door: past its mark and back
const rnd = (a, b) => a + Math.random() * (b - a);
const V3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const box = (w, h, d) => new THREE.BoxGeometry(w, h, d);
const std = o => new THREE.MeshStandardMaterial(o);
const fov = (v, aspect) => aspect >= 1 ? v : 2 * Math.atan(Math.tan(v * Math.PI / 360) / aspect) * 180 / Math.PI;      // a tall phone screen keeps the width of view
const pt = {x: 0, y: 0, sx: 0, sy: 0};      // the pointer, -1 to 1 across the window; sx, sy follow it slowly, as a head does
addEventListener("pointermove", e => { pt.x = e.clientX / innerWidth * 2 - 1; pt.y = e.clientY / innerHeight * 2 - 1; }, {passive: true});

function mesh(geo, mat, x, y, z, parent, shadow = true){
  const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = m.receiveShadow = shadow; parent.add(m); return m;
}
function tex(w, h, draw, rx, ry){
  const c = document.createElement("canvas"); c.width = w; c.height = h; draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  if (rx) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(rx, ry || rx); }
  return t;
}
function words(w, h, text, font, color){
  return tex(w, h, (g) => { g.fillStyle = color; g.font = font; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(text, w / 2, h / 2 + 2); });
}
function star(g, x, y, r){
  g.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, q = i % 2 ? r * .4 : r; g.lineTo(x + q * Math.cos(a), y + q * Math.sin(a)); }
  g.closePath(); g.fill();
}
const glowDot = () => tex(64, 64, (g) => { const r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  r.addColorStop(0, "rgba(255,255,255,1)"); r.addColorStop(.35, "rgba(255,255,255,.45)"); r.addColorStop(1, "rgba(255,255,255,0)"); g.fillStyle = r; g.fillRect(0, 0, 64, 64); });
function worldUV(geo, w, h, x0, y0, size){      // lay a repeating pattern in metres, so the pieces of one wall line up
  const uv = geo.attributes.uv;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, (x0 + uv.getX(i) * w) / size, (y0 + uv.getY(i) * h) / size);
  return geo;
}
function environment(renderer, [wall, ceiling, floor], lights){      // a soft room, blurred, for reflections and fill light
  const env = new THREE.Scene(), face = c => new THREE.MeshBasicMaterial({color: c, side: THREE.BackSide});
  const room = new THREE.Mesh(box(14, 5, 14), [face(wall), face(wall), face(ceiling), face(floor), face(wall), face(wall)]);
  room.position.y = 1; env.add(room);
  for (const [x, y, z, w, h, d, color, k] of lights) mesh(box(w, h, d), new THREE.MeshBasicMaterial({color: new THREE.Color(color).multiplyScalar(k)}), x, y, z, env, false);
  const pm = new THREE.PMREMGenerator(renderer), map = pm.fromScene(env, .04).texture;
  pm.dispose(); return map;
}
function setup(renderer, w, h, ratio){
  renderer.setPixelRatio(ratio); renderer.setSize(w, h, false);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1; renderer.outputColorSpace = THREE.SRGBColorSpace;
}

/* ---------- the polling place: your ballot into the scanner ---------- */
function scanner(renderer, aspect){
  const scene = new THREE.Scene(), bg = new THREE.Color("#DCD6CA");
  scene.background = bg; scene.fog = new THREE.Fog(bg, 6, 14);
  scene.environment = environment(renderer, ["#8F8A80", "#C9C4BA", "#6F6A60"],
    [[-2.2, 3.4, -1, .5, .06, 7, "#FFF7EA", 7], [2.2, 3.4, -1, .5, .06, 7, "#FFF7EA", 7], [0, 3.4, 2, 7, .06, .5, "#FFF7EA", 6]]);
  scene.environmentIntensity = .8;
  const cam = new THREE.PerspectiveCamera(50, aspect, .01, 40);
  scene.add(new THREE.HemisphereLight("#FFF8EE", "#8A8274", .35));
  const key = new THREE.DirectionalLight("#FFF3E2", 1.7);
  key.position.set(-1.6, 3.6, 2.2); key.target.position.set(0, .9, 0); key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -.0004; key.shadow.normalBias = .02;
  Object.assign(key.shadow.camera, {left: -2.8, right: 2.8, top: 2.8, bottom: -2.8, near: .5, far: 9}); key.shadow.camera.updateProjectionMatrix();
  scene.add(key, key.target);

  // the room: a school gym or a church hall on election day
  const floor = mesh(new THREE.PlaneGeometry(24, 24), std({roughness: .42, map: tex(512, 512, (g, w) => {
    for (let y = 0; y < 4; y++) for (let x = 0; x < 4; x++) { g.fillStyle = (x + y) % 2 ? "#CEC6B4" : "#C2B9A6"; g.fillRect(x * 128, y * 128, 128, 128); }
    for (let i = 0; i < 2600; i++) { g.fillStyle = Math.random() < .5 ? "rgba(90,80,60,.16)" : "rgba(255,255,255,.18)"; g.fillRect(Math.random() * w, Math.random() * w, 2, 2); }
    g.fillStyle = "rgba(80,70,55,.35)"; for (let i = 0; i <= 4; i++) { g.fillRect(i * 128 - 1, 0, 2, w); g.fillRect(0, i * 128 - 1, w, 2); }
  }, 20)}), 0, 0, 0, scene);
  floor.rotation.x = -Math.PI / 2; floor.castShadow = false;
  const WZ = -2.6;
  mesh(new THREE.PlaneGeometry(24, 6), std({roughness: .92, map: tex(512, 256, (g, w, h) => {      // painted block wall
    g.fillStyle = "#CFC8B8"; g.fillRect(0, 0, w, h);
    for (let r = 0; r < 4; r++) for (let c = -1; c < 5; c++) { const v = 226 + ((Math.random() * 10) | 0);
      g.fillStyle = `rgb(${v},${v - 5},${v - 17})`; g.fillRect(c * 128 + (r % 2) * 64 + 3, r * 64 + 3, 122, 58); }
  }, 15, 7.5)}), 0, 3, WZ, scene).castShadow = false;
  mesh(box(24, .1, .012), std({color: "#3B3833", roughness: .6}), 0, .05, WZ + .006, scene, false);
  mesh(new THREE.PlaneGeometry(1.2, .3), std({roughness: .5, map: tex(1024, 256, (g, w, h) => {
    g.fillStyle = "#1F3B6E"; g.fillRect(0, 0, w, h); g.strokeStyle = "#FFFFFF"; g.lineWidth = 8; g.strokeRect(16, 16, w - 32, h - 32);
    g.fillStyle = "#FFFFFF"; g.font = "700 100px system-ui, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("POLLING PLACE", w / 2, h / 2 + 4);
  })}), -1.25, 1.9, WZ + .01, scene, false);
  const flag = mesh(new THREE.PlaneGeometry(.95, .5, 24, 1), std({roughness: .8, side: THREE.DoubleSide, map: tex(760, 400, (g, w, h) => {
    for (let i = 0; i < 13; i++) { g.fillStyle = i % 2 ? "#FFFFFF" : "#B22234"; g.fillRect(0, i * h / 13, w, h / 13 + 1); }
    const cw = w * .4, ch = h * 7 / 13; g.fillStyle = "#3C3B6E"; g.fillRect(0, 0, cw, ch); g.fillStyle = "#FFFFFF";
    for (let r = 0; r < 9; r++) for (let c = 0; c < (r % 2 ? 5 : 6); c++) star(g, cw * ((r % 2 ? 2 : 1) + c * 2) / 12, ch * (r + 1) / 10, 9);
  })}), 1.45, 1.85, WZ + .03, scene, false);
  const fp = flag.geometry.attributes.position;
  for (let i = 0; i < fp.count; i++) fp.setZ(i, Math.sin(fp.getX(i) * 7) * .015);      // hung, not ironed
  flag.geometry.computeVertexNormals();
  const metal = std({color: "#BFC4CB", roughness: .35, metalness: .7}), panel = std({color: "#E9ECEF", roughness: .55});
  const vote = tex(512, 200, (g, w) => { g.fillStyle = "#1F3B6E"; g.font = "800 132px system-ui, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle";
    g.fillText("VOTE", w / 2, 86); g.fillStyle = "#B22234"; g.fillRect(56, 160, 400, 12); g.fillStyle = "#1F3B6E"; g.fillRect(56, 178, 400, 12); });
  const booth = (x, z, ry) => {      // a voting booth seen from behind: its privacy screen faces the room
    const b = new THREE.Group(); b.position.set(x, 0, z); b.rotation.y = ry; scene.add(b);
    for (const [lx, lz] of [[-.28, -.19], [.28, -.19], [-.28, .19], [.28, .19]]) mesh(new THREE.CylinderGeometry(.011, .011, .9, 10), metal, lx, .45, lz, b);
    mesh(box(.62, .022, .44), std({color: "#DCD8CF", roughness: .6}), 0, .9, 0, b);
    mesh(box(.58, .016, .016), metal, 0, .3, .19, b); mesh(box(.58, .016, .016), metal, 0, .3, -.19, b);
    mesh(box(.62, .5, .008), panel, 0, 1.16, .216, b);
    mesh(box(.008, .5, .44), panel, -.306, 1.16, 0, b); mesh(box(.008, .5, .44), panel, .306, 1.16, 0, b);
    mesh(new THREE.PlaneGeometry(.46, .18), std({map: vote, transparent: true, roughness: .55}), 0, 1.2, .2206, b, false);
  };
  booth(-1.2, -1.3, .22); booth(1.25, -1.45, -.18); booth(2.55, -1.65, -.3);

  // the ballot box, and the scanner on top of it with its slot at the front
  const bin = std({color: "#2E3B52", roughness: .4, metalness: .2}), shell = std({color: "#C9CDD3", roughness: .36}), trim = std({color: "#1B1E23", roughness: .5});
  mesh(box(.56, .84, .46), bin, 0, .44, 0, scene);
  for (const [fx, fz] of [[-.24, -.19], [.24, -.19], [-.24, .19], [.24, .19]]) mesh(box(.05, .02, .05), trim, fx, .01, fz, scene);
  mesh(box(.58, .026, .48), trim, 0, .873, 0, scene);
  mesh(new THREE.PlaneGeometry(.5, .74), std({transparent: true, roughness: .4, map: tex(500, 740, (g, w, h) => {
    g.strokeStyle = "rgba(10,14,22,.8)"; g.lineWidth = 5; g.strokeRect(14, 14, w - 28, h - 28); })}), 0, .45, .2303, scene, false);
  mesh(new THREE.PlaneGeometry(.36, .062), std({transparent: true, roughness: .5, map: words(720, 124, "OFFICIAL BALLOT BOX", "700 64px system-ui, sans-serif", "#DCE3EE")}), 0, .66, .2306, scene, false);
  mesh(new THREE.CylinderGeometry(.012, .012, .012, 16), metal, .2, .42, .232, scene).rotation.x = Math.PI / 2;
  mesh(box(.6, .15, .42), shell, 0, .96, -.01, scene);
  mesh(box(.6, .012, .4), std({color: "#D6D9DE", roughness: .3}), 0, 1.041, -.02, scene);
  mesh(box(.36, .034, .016), std({color: "#4B525C", roughness: .4}), 0, .958, .2, scene);      // the slot's mouth
  mesh(box(.31, .011, .02), std({color: "#030405", roughness: 1}), 0, .958, .2, scene, false);
  mesh(box(.36, .006, .1), std({color: "#8D949E", roughness: .35}), 0, .958, .255, scene).rotation.x = -.12;      // the tray the ballot slides along
  mesh(new THREE.PlaneGeometry(.22, .024), std({transparent: true, roughness: .5, map: tex(660, 72, (g, w, h) => {
    g.fillStyle = "#3E4550"; g.font = "700 40px system-ui, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("INSERT BALLOT", w / 2, h / 2 + 2);
    for (const x of [120, w - 120]) { g.beginPath(); g.moveTo(x - 14, 24); g.lineTo(x + 14, 24); g.lineTo(x, 50); g.closePath(); g.fill(); }
  })}), 0, .99, .2013, scene, false);
  const led = mesh(box(.034, .007, .004), std({color: "#3A3320", emissive: "#FFB02E", emissiveIntensity: .25}), .2, .99, .2022, scene, false);
  const glow = new THREE.PointLight("#5BF08A", 0, .6, 2); glow.position.set(.18, 1.0, .28); scene.add(glow);
  const bezel = mesh(box(.28, .18, .03), trim, 0, 1.095, .095, scene); bezel.rotation.x = -.95;
  mesh(box(.2, .12, .12), shell, 0, 1.05, .03, scene).rotation.x = -.95;
  const scr = document.createElement("canvas"); scr.width = 640; scr.height = 400;
  const sg = scr.getContext("2d"), screenTex = new THREE.CanvasTexture(scr); screenTex.colorSpace = THREE.SRGBColorSpace; screenTex.anisotropy = 8;
  const screen = mesh(new THREE.PlaneGeometry(.25, .156), new THREE.MeshBasicMaterial({map: screenTex, toneMapped: false}), 0, 0, 0, scene, false);
  screen.position.copy(bezel.position); screen.rotation.copy(bezel.rotation); screen.translateZ(.0152);
  let shown = "";
  const draw = (state, p) => {      // what a scanner's screen says: ready, reading, counted
    const k = state === 1 ? "1:" + Math.round(p * 30) : String(state); if (k === shown) return; shown = k;
    const g = sg, W = 640, cx = W / 2;
    g.fillStyle = "#0F1C2F"; g.fillRect(0, 0, W, 400); g.fillStyle = "#1F3B6E"; g.fillRect(0, 0, W, 58);
    g.textAlign = "center"; g.textBaseline = "middle"; g.fillStyle = "#DCE6F5"; g.font = "600 25px system-ui, sans-serif";
    g.fillText("General Election · November 3, 2026", cx, 30);
    if (state === 0) {
      g.fillStyle = "#FFFFFF"; g.font = "700 52px system-ui, sans-serif"; g.fillText("Insert your ballot", cx, 150);
      g.fillStyle = "#8FB3E8"; g.beginPath(); g.moveTo(cx - 34, 214); g.lineTo(cx + 34, 214); g.lineTo(cx, 262); g.closePath(); g.fill();
    } else if (state === 1) {
      g.fillStyle = "#FFFFFF"; g.font = "700 46px system-ui, sans-serif"; g.fillText("Reading your ballot…", cx, 150);
      g.fillStyle = "#26364F"; g.fillRect(120, 214, 400, 26); g.fillStyle = "#6FA8FF"; g.fillRect(120, 214, 400 * p, 26);
    } else {
      g.fillStyle = "#2FBF62"; g.beginPath(); g.arc(cx, 140, 52, 0, 7); g.fill();
      g.strokeStyle = "#FFFFFF"; g.lineWidth = 12; g.lineCap = g.lineJoin = "round";
      g.beginPath(); g.moveTo(cx - 24, 142); g.lineTo(cx - 6, 162); g.lineTo(cx + 26, 118); g.stroke();
      g.fillStyle = "#FFFFFF"; g.font = "700 42px system-ui, sans-serif"; g.fillText("Your ballot was counted", cx, 240);
      g.fillStyle = "#A9C4EA"; g.font = "500 30px system-ui, sans-serif"; g.fillText("Thank you for voting!", cx, 292);
    }
    g.fillStyle = "#7F93B2"; g.font = "500 24px system-ui, sans-serif"; g.fillText("Ballots cast: " + (state === 2 ? "1,248" : "1,247"), cx, 368);
    screenTex.needsUpdate = true;
  };
  draw(0);

  // the ballot, a marked sheet held by its near edge, face up
  const BW = .216, BH = .28;
  const face = tex(864, 1120, (g, w, h) => {
    g.fillStyle = "#FFFFFF"; g.fillRect(0, 0, w, h); g.fillStyle = "#15171B";
    for (let y = 60; y < h - 40; y += 34) { g.fillRect(14, y, 26, 11); g.fillRect(w - 40, y, 26, 11); }      // the timing marks a scanner reads by
    g.fillRect(60, 40, w - 120, 124);
    g.fillStyle = "#FFFFFF"; g.textAlign = "center"; g.font = "700 50px system-ui, sans-serif"; g.fillText("OFFICIAL BALLOT", w / 2, 98);
    g.fillStyle = "#C9CCD2"; g.font = "500 26px system-ui, sans-serif"; g.fillText("GENERAL ELECTION · NOVEMBER 3, 2026", w / 2, 142);
    g.fillStyle = "#3A3D44"; g.font = "italic 24px system-ui, sans-serif"; g.fillText("To vote, fill in the oval completely next to your choice.", w / 2, 204);
    let y = 240;
    for (const [n, pick] of [[3, 0], [2, 1], [3, 2]]) {
      g.fillStyle = "#2B2E35"; g.fillRect(60, y, w - 120, 40); y += 66;      // an office's heading
      for (let i = 0; i < n; i++, y += 58) {
        g.fillStyle = "#C9CDD4"; g.fillRect(170, y - 12, 300 + ((i * 97) % 160), 22);      // a line where a name would be
        g.beginPath(); g.ellipse(112, y, 30, 18, 0, 0, 7); g.lineWidth = 5; g.strokeStyle = "#15171B"; g.stroke();
        if (i === pick) { g.fillStyle = "#101114"; g.fill(); }
      }
      y += 20;
    }
  });
  const geo = new THREE.PlaneGeometry(BW, BH, 10, 12), flat = Float32Array.from(geo.attributes.position.array);
  const ballot = new THREE.Group(); scene.add(ballot);
  const front = new THREE.Mesh(geo, std({map: face, roughness: .88, shadowSide: THREE.DoubleSide})); front.castShadow = true;
  ballot.add(front, new THREE.Mesh(geo, std({color: "#F3F2EE", roughness: .9, side: THREE.BackSide})));
  const bend = (curl, droop) => {      // paper held at one edge bows across and sags at the far end
    const p = geo.attributes.position;
    for (let i = 0; i < p.count; i++) { const x = flat[i * 3], y = flat[i * 3 + 1];
      p.setZ(i, -.008 * curl * (x / (BW / 2)) ** 2 - .02 * droop * ((y + BH / 2) / BH) ** 2); }
    p.needsUpdate = true; geo.computeVertexNormals();
  };
  const SLOT = V3(0, .958, .2025), U = V3(0, 1, 0).applyEuler(new THREE.Euler(-Math.PI / 2 - .12, 0, 0));      // into the slot, a little downhill
  const Q1 = new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2 - .12, 0, 0));
  const Q0 = new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2 + .55, .35, .55));
  const at = s => SLOT.clone().addScaledVector(U, s - BH / 2);      // the ballot's middle when its leading edge is s past the slot's mouth
  const P0 = V3(.3, .78, .78), C1 = V3(.2, 1.02, .62), READY = at(-.035);
  const screenPos = V3(), n = V3(0, 0, 1);
  screen.updateMatrixWorld(); screen.getWorldPosition(screenPos); n.applyQuaternion(screen.quaternion);
  const camEnd = screenPos.clone().addScaledVector(n, .26);
  const E0 = V3(.05, 1.62, 1.35), E1 = V3(.03, 1.6, .95), L0 = V3(0, 1.15, -.3), L1 = V3(0, 1.05, -.05), eye = V3(), look = V3(), tmp = V3();
  let state = 0;
  return {scene, cam, dur: 3.7, frame(t){
    // your hand: up from your side along an arc, turning the ballot square to the slot, a little unsteady until it is in
    const a = inOut(seg(t, .1, 1.05)), A = .0035 * (1 - seg(t, 1.0, 1.3)), aim = seg(t, .1, .4) * (1 - seg(t, .65, 1.0));
    if (t < 1.05) {
      const u = 1 - a; ballot.position.set(0, 0, 0).addScaledVector(P0, u * u).addScaledVector(C1, 2 * u * a).addScaledVector(READY, a * a);
      ballot.position.x += pt.sx * .05 * aim; ballot.position.y -= pt.sy * .03 * aim;
    } else {
      let s = -.035 + .055 * inOut(seg(t, 1.05, 1.3)) + .006 * smooth(seg(t, 1.3, 1.4));      // you push it in; the rollers catch it
      s += (.31 - .026) * inOut(seg(t, 1.4, 1.95));      // and draw it through
      ballot.position.copy(at(s));
      if (t > 1.4 && t < 1.95) ballot.position.y += (Math.random() - .5) * .0008;
    }
    ballot.position.x += Math.sin(t * 7.3) * A; ballot.position.y += Math.sin(t * 9.1 + 1) * A * .8; ballot.position.z += Math.sin(t * 5.7 + 2) * A * .6;
    ballot.quaternion.slerpQuaternions(Q0, Q1, smooth(seg(t, .1, 1.0)));
    ballot.visible = t < 1.97;
    bend(1 - .7 * seg(t, .9, 1.3), 1 - seg(t, .7, 1.05));
    // the machine
    if (t >= 1.3 && state === 0) state = 1;
    if (state === 1) { draw(1, seg(t, 1.3, 2.15)); led.material.emissiveIntensity = Math.sin(t * 28) > 0 ? .9 : .2; }
    if (t >= 2.15 && state === 1) { state = 2; draw(2); led.material.emissive.set("#35E16A"); led.material.color.set("#1E5E33"); led.material.emissiveIntensity = 2.2; glow.intensity = .12; }
    // you: two steps up to the machine, breathing, your eyes on the ballot, then on the screen, then leaning in to it
    const w = inOut(seg(t, 0, .95)), le = inOut(seg(t, 2.4, 3.4)), over = inOut(seg(t, .85, 1.35)) * (1 - inOut(seg(t, 1.9, 2.4)));
    eye.lerpVectors(E0, E1, w); eye.y -= .045 * over; eye.z -= .07 * over;      // leaning over the machine to feed it
    eye.x += Math.sin(w * Math.PI * 2) * .006 + Math.sin(t * 1.1) * .002 + pt.sx * .03;
    eye.y += Math.sin(w * Math.PI * 4) * .008 * (1 - w) + Math.sin(t * 1.7) * .003 - pt.sy * .02;
    look.lerpVectors(L0, L1, w);
    look.lerp(tmp.copy(ballot.position), .3 * seg(t, .35, .8) * (1 - seg(t, 1.4, 1.9)));
    look.lerp(screenPos, .45 * seg(t, 1.5, 2.1));
    cam.position.lerpVectors(eye, camEnd, le); look.lerp(screenPos, le); cam.lookAt(look);
    cam.fov = fov(50 - 14 * le, cam.aspect); cam.updateProjectionMatrix();
    return smooth(seg(t, 3.0, 3.6));
  }};
}

/* ---------- the study: a book pulled, the shelves emptied, the bookcase swung aside ---------- */
function bookshelf(renderer, aspect){
  const scene = new THREE.Scene(), bg = new THREE.Color("#1A130E");
  scene.background = bg; scene.fog = new THREE.Fog(bg, 6, 14);
  scene.environment = environment(renderer, ["#3A2A1E", "#4A3B2E", "#2E2118"], [[-2.4, 1.5, 1.2, .5, .6, .5, "#FFD49A", 14], [2.5, 2.2, -1, .08, 1.2, 1.2, "#C9D8FF", 3]]);
  scene.environmentIntensity = .55;
  const cam = new THREE.PerspectiveCamera(50, aspect, .01, 40);
  const WZ = -1.2, OW = .675, OH = 2.27, T = .34, CW = .95;      // the wall's face, half the opening's width, its height, the wall's thickness, the passage's half width
  const planks = tex(1024, 1024, (g, w) => {      // oak boards running away from you
    const cols = 8, cw = w / cols;
    for (let c = 0; c < cols; c++) { let y = -((c * 373) % 700);
      while (y < w) { const len = 500 + Math.random() * 500, v = Math.random();
        g.fillStyle = `hsl(${24 + v * 6},${38 + v * 10}%,${22 + v * 8}%)`; g.fillRect(c * cw, y, cw, len);
        for (let k = 0; k < 14; k++) { g.fillStyle = `rgba(0,0,0,${.05 + Math.random() * .06})`; g.fillRect(c * cw + Math.random() * cw, y, 1 + Math.random() * 2, len); }
        g.fillStyle = "rgba(0,0,0,.45)"; g.fillRect(c * cw, y, cw, 3); y += len; }
      g.fillStyle = "rgba(0,0,0,.5)"; g.fillRect(c * cw, 0, 3, w); }
  }, 22);
  const floor = mesh(new THREE.PlaneGeometry(24, 24), std({map: planks, roughness: .48}), 0, 0, 0, scene); floor.rotation.x = -Math.PI / 2; floor.castShadow = false;
  const rug = mesh(new THREE.PlaneGeometry(2.4, 1.7), std({roughness: .95, map: tex(768, 544, (g, w, h) => {
    g.fillStyle = "#5E1A1A"; g.fillRect(0, 0, w, h);
    for (let i = 0; i < 9000; i++) { g.fillStyle = `rgba(${Math.random() < .5 ? "0,0,0" : "255,220,200"},.05)`; g.fillRect(Math.random() * w, Math.random() * h, 2, 2); }
    g.strokeStyle = "#C9A55A"; g.lineWidth = 10; g.strokeRect(26, 26, w - 52, h - 52);
    g.strokeStyle = "#1F2A44"; g.lineWidth = 22; g.strokeRect(52, 52, w - 104, h - 104);
    g.strokeStyle = "#C9A55A"; g.lineWidth = 4; g.strokeRect(74, 74, w - 148, h - 148);
    g.fillStyle = "#1F2A44"; g.beginPath(); g.ellipse(w / 2, h / 2, 150, 96, 0, 0, 7); g.fill(); g.lineWidth = 6; g.stroke();
  })}), 0, .003, WZ + 1.25, scene); rug.rotation.x = -Math.PI / 2; rug.castShadow = false;
  // the wall: green paper above, panelling below, and an opening the bookcase fills
  const paper = tex(256, 256, (g, w, h) => {
    g.fillStyle = "#23392F"; g.fillRect(0, 0, w, h); g.fillStyle = "rgba(0,0,0,.08)"; for (let x = 0; x < w; x += 32) g.fillRect(x, 0, 3, h);
    g.fillStyle = "rgba(200,176,112,.12)";
    for (const [x, y] of [[0, 0], [256, 0], [0, 256], [256, 256], [128, 128]]) { g.beginPath(); g.moveTo(x, y - 40); g.lineTo(x + 26, y); g.lineTo(x, y + 40); g.lineTo(x - 26, y); g.closePath(); g.fill(); }
  }, 1);
  const panels = tex(256, 256, (g, w, h) => { g.fillStyle = "#3F2718"; g.fillRect(0, 0, w, h);
    g.strokeStyle = "rgba(0,0,0,.45)"; g.lineWidth = 6; g.strokeRect(24, 30, w - 48, h - 60); g.strokeStyle = "rgba(255,210,160,.08)"; g.lineWidth = 3; g.strokeRect(30, 36, w - 60, h - 72); }, 1);
  const paperMat = std({map: paper, roughness: .9}), panelMat = std({map: panels, roughness: .55}), rail = std({color: "#3A2416", roughness: .5});
  const piece = (x0, x1, y0, y1, mat, size) => { const w = x1 - x0, h = y1 - y0;
    mesh(worldUV(new THREE.PlaneGeometry(w, h), w, h, x0, y0, size), mat, (x0 + x1) / 2, (y0 + y1) / 2, WZ, scene); };
  for (const [x0, x1] of [[-7, -OW], [OW, 7]]) {
    piece(x0, x1, .95, 5, paperMat, .36); piece(x0, x1, 0, .95, panelMat, .95);
    mesh(box(x1 - x0, .05, .03), rail, (x0 + x1) / 2, .95, WZ + .015, scene); mesh(box(x1 - x0, .14, .02), rail, (x0 + x1) / 2, .07, WZ + .01, scene);
  }
  piece(-OW, OW, OH, 5, paperMat, .36);
  const plaster = std({color: "#D9C7A6", roughness: .85});
  for (const s of [-1, 1]) mesh(new THREE.PlaneGeometry(T, OH), plaster, s * OW, OH / 2, WZ - T / 2, scene).rotation.y = -s * Math.PI / 2;      // the opening's sides
  mesh(new THREE.PlaneGeometry(2 * OW, T), plaster, 0, OH, WZ - T / 2, scene).rotation.x = Math.PI / 2;
  // the passage behind, and the light at its end
  for (const s of [-1, 1]) mesh(new THREE.PlaneGeometry(3.4, 2.45), plaster, s < 0 ? -CW : .9, 1.225, WZ - T - 1.7, scene).rotation.y = -s * Math.PI / 2;
  mesh(new THREE.PlaneGeometry(CW + .9, 3.4), plaster, (.9 - CW) / 2, 2.45, WZ - T - 1.7, scene).rotation.x = Math.PI / 2;
  const endMat = new THREE.MeshBasicMaterial({color: "#FFE9C4"});
  mesh(new THREE.PlaneGeometry(CW + .9, 2.45), endMat, (.9 - CW) / 2, 1.225, WZ - 3.7, scene, false);
  const spill = new THREE.SpotLight("#FFE0AE", 0, 12, .85, .6, 2);      // the light that pours out when the bookcase moves
  spill.position.set(-.1, 2.1, WZ - 3.3); spill.target.position.set(0, 0, WZ + 2.6); spill.castShadow = true;
  spill.shadow.mapSize.set(1024, 1024); spill.shadow.bias = -.0005; spill.shadow.camera.near = .3; spill.shadow.camera.far = 10;
  scene.add(spill, spill.target);
  const inner = new THREE.PointLight("#FFD8A0", 0, 2.6, 2); inner.position.set(0, 1.9, WZ - 1.9); scene.add(inner);
  const seamMat = new THREE.MeshBasicMaterial({color: new THREE.Color("#FFB45C").multiplyScalar(1.6), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false});
  mesh(new THREE.PlaneGeometry(.01, OH), seamMat, -OW + .006, OH / 2, WZ + .004, scene, false);      // light at the edges of a door that is not quite shut
  mesh(new THREE.PlaneGeometry(.01, OH), seamMat, OW - .006, OH / 2, WZ + .004, scene, false);
  mesh(new THREE.PlaneGeometry(2 * OW, .012), seamMat, 0, OH - .007, WZ + .004, scene, false);
  const haze = mesh(new THREE.PlaneGeometry(3.4, 3), new THREE.MeshBasicMaterial({map: glowDot(), color: "#FFCF8A", transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false}), 0, 1.15, WZ + .25, scene, false);
  const DUST = 420, dpos = new Float32Array(DUST * 3), dph = [];
  for (let i = 0; i < DUST; i++) { dpos.set([rnd(-.9, .9), rnd(.1, 2.3), rnd(WZ - 2.6, WZ + 1.3)], i * 3); dph.push(rnd(0, 6.3)); }
  const dgeo = new THREE.BufferGeometry(); dgeo.setAttribute("position", new THREE.BufferAttribute(dpos, 3));
  const dust = new THREE.Points(dgeo, new THREE.PointsMaterial({size: .014, map: glowDot(), color: "#FFE2B0", transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending}));
  scene.add(dust);
  // the room's own light: a floor lamp, a lamp overhead, two pictures
  const brass = std({color: "#B08D57", roughness: .35, metalness: .85});
  mesh(new THREE.CylinderGeometry(.14, .16, .03, 32), brass, -1.35, .015, WZ + .55, scene);
  mesh(new THREE.CylinderGeometry(.011, .011, 1.42, 12), brass, -1.35, .74, WZ + .55, scene);
  mesh(new THREE.CylinderGeometry(.13, .21, .27, 32, 1, true), std({color: "#E9D7B0", emissive: "#FFC978", emissiveIntensity: 1.1, roughness: .9, side: THREE.DoubleSide}), -1.35, 1.5, WZ + .55, scene, false);
  const bulb = new THREE.PointLight("#FFC98A", 2.2, 5, 2); bulb.position.set(-1.35, 1.45, WZ + .55); scene.add(bulb);
  const lamp = new THREE.SpotLight("#FFD9A6", 38, 14, .55, .7, 2);
  lamp.position.set(-1.2, 3.0, 1.9); lamp.target.position.set(.1, 1.1, WZ); lamp.castShadow = true; lamp.shadow.mapSize.set(2048, 2048); lamp.shadow.bias = -.0004;
  scene.add(lamp, lamp.target);
  const picture = (x, y, w, h, dusk) => {
    mesh(box(w + .08, h + .08, .035), std({color: "#6B4A22", roughness: .45, metalness: .3}), x, y, WZ + .02, scene);
    mesh(new THREE.PlaneGeometry(w, h), std({roughness: .7, map: tex(256, Math.round(256 * h / w), (g, W, H) => {
      const sky = g.createLinearGradient(0, 0, 0, H); sky.addColorStop(0, dusk ? "#5E6E86" : "#8FA3AE"); sky.addColorStop(.6, dusk ? "#D9A06A" : "#E4D6B4"); g.fillStyle = sky; g.fillRect(0, 0, W, H);
      g.fillStyle = dusk ? "#3E3A34" : "#5B6A48"; g.beginPath(); g.moveTo(0, H * .72); g.quadraticCurveTo(W * .35, H * .52, W * .6, H * .7); g.quadraticCurveTo(W * .8, H * .6, W, H * .68); g.lineTo(W, H); g.lineTo(0, H); g.fill();
      g.fillStyle = dusk ? "#2A2622" : "#3F4B33"; g.fillRect(0, H * .85, W, H * .15);
    })}), x, y, WZ + .038, scene, false);
  };
  picture(-1.75, 1.62, .5, .64, false); picture(1.78, 1.55, .58, .44, true);

  // the bookcase: it fills the opening and turns on a hinge at its back right corner
  const CWD = 1.32, CH = 2.25, CD = .34;
  const grain = tex(256, 1024, (g, w, h) => { g.fillStyle = "#5A3A24"; g.fillRect(0, 0, w, h);
    for (let i = 0; i < 90; i++) { g.strokeStyle = `rgba(${Math.random() < .5 ? "0,0,0" : "255,200,150"},${.04 + Math.random() * .07})`; g.lineWidth = 1 + Math.random() * 3;
      g.beginPath(); let x = Math.random() * w; g.moveTo(x, 0); for (let y = 0; y <= h; y += 64) { x += (Math.random() - .5) * 8; g.lineTo(x, y); } g.stroke(); } });
  const wood = std({map: grain, roughness: .5});
  const H0 = V3(CWD / 2, 0, WZ + .02 - CD);
  const hinge = new THREE.Group(); hinge.position.copy(H0); scene.add(hinge);
  const cab = new THREE.Group(); cab.position.set(-CWD / 2, 0, CD / 2); hinge.add(cab);
  const part = (w, h, d, x, y, z) => mesh(box(w, h, d), wood, x, y, z, cab);
  part(.04, CH, CD, -CWD / 2 + .02, CH / 2, 0); part(.04, CH, CD, CWD / 2 - .02, CH / 2, 0);
  part(CWD, .05, CD, 0, CH - .025, 0); part(CWD, .08, CD, 0, .04, 0);
  part(CWD - .08, CH - .13, .015, 0, (CH - .13) / 2 + .08, -CD / 2 + .0075);
  for (const y of [.5, .94, 1.38, 1.82]) part(CWD - .08, .03, CD - .02, 0, y, .01);
  const PAL = ["#27365E", "#7C2D2D", "#2F5D4A", "#9C7A3A", "#5B3A6E", "#8C5A2B", "#3E4A57", "#9A3F2C", "#1F3F3A", "#6B2438"];
  const covers = PAL.map(c => std({color: c, roughness: .7})), pages = std({color: "#E9DFC6", roughness: .92});
  const spines = PAL.map(c => std({roughness: .62, map: tex(64, 256, (g, w, h) => {
    g.fillStyle = c; g.fillRect(0, 0, w, h);
    const r = g.createLinearGradient(0, 0, w, 0); r.addColorStop(0, "rgba(0,0,0,.35)"); r.addColorStop(.4, "rgba(255,255,255,.08)"); r.addColorStop(1, "rgba(0,0,0,.35)"); g.fillStyle = r; g.fillRect(0, 0, w, h);
    g.fillStyle = "rgba(222,186,98,.9)"; g.fillRect(0, 18, w, 6); g.fillRect(0, h - 26, w, 6); g.fillRect(14, 60, w - 28, 3); g.fillRect(14, 70, w - 28, 3); g.fillRect(18, 84, w - 36, 30);
  })}));
  const books = [], BASES = [.08, .515, .955, 1.395, 1.835], ROOM = [.4, .4, .4, .4, .355];
  BASES.forEach((base, row) => {
    for (let x = -CWD / 2 + .045; ;) {
      if (Math.random() < .06) x += rnd(.02, .06);      // a gap where a book is out
      const w = rnd(.024, .058), h = Math.min(ROOM[row] - .02, rnd(.21, .3) + (row < 2 ? .05 : 0)), d = rnd(.17, .25), k = (Math.random() * PAL.length) | 0;
      if (x + w > CWD / 2 - .045) break;
      const m = mesh(box(w, h, d), [covers[k], covers[k], pages, pages, spines[k], pages], x + w / 2, base + h / 2, CD / 2 - .012 - d / 2, cab);
      const rz = rnd(-.012, .012); m.rotation.z = rz;
      books.push({m, w, h, d, row, rz, x0: x + w / 2, y0: base, z0: CD / 2 - .012, state: 0, phi0: 0, s0: 0,
        corners: [-1, 1].flatMap(a => [-1, 1].flatMap(b => [-1, 1].map(c => V3(a * w / 2, b * h / 2, c * d / 2))))});
      x += w + rnd(.001, .004);
    }
  });
  const E0 = V3(0, 1.62, 1.75), L0 = V3(0, 1.2, WZ), EEND = V3(-.22, 1.55, WZ - 2.3), LEND = V3(-.22, 1.45, WZ - 3.6);
  cam.position.copy(E0); cam.lookAt(L0); cam.fov = fov(50, aspect); cam.updateProjectionMatrix(); cam.updateMatrixWorld(); scene.updateMatrixWorld(true);
  let pick = books[0], best = 1e9;      // the book your hand goes to: the one nearest the pointer, within reach
  for (const b of books) { if (b.row < 2) continue; const v = b.m.getWorldPosition(V3()).project(cam), d = (v.x - pt.x) ** 2 + (v.y + pt.y) ** 2; if (d < best) { best = d; pick = b; } }
  const PW = pick.m.getWorldPosition(V3()), px = pick.x0, py = pick.y0 + pick.h / 2;
  for (const b of books) {
    if (b === pick) Object.assign(b, {td: .6, w0: 1.4, al: 11, as: 1.0});
    else Object.assign(b, {td: .62 + Math.hypot(b.x0 - px, b.y0 + b.h / 2 - py) * .42 + rnd(0, .08), w0: rnd(.4, 1.2), al: rnd(9, 14), as: rnd(.6, 1.6)});
    b.tip = Math.atan2(b.d, b.h) + .45;
  }
  const pose = (b, tau, p) => {      // tipping forward about its front bottom edge, and sliding out as the shelf shakes
    const phi = b.phi0 + b.w0 * tau + .5 * b.al * tau * tau, slide = b.s0 + .5 * b.as * tau * tau;
    const c = Math.cos(phi), s = Math.sin(phi), hy = b.h / 2, hz = -b.d / 2;
    p.set(b.x0, b.y0 + hy * c - hz * s, b.z0 + slide + hy * s + hz * c);
    return phi;
  };
  const G = .08, GX = 50, GZ = 40, gx0 = -2, gz0 = WZ - .4, heights = new Float32Array(GX * GZ), bb = new THREE.Box3();
  const cell = (x, z) => { const i = Math.floor((x - gx0) / G), j = Math.floor((z - gz0) / G); return i >= 0 && j >= 0 && i < GX && j < GZ ? j * GX + i : -1; };
  const ground = (x, z) => { const k = cell(x, z); return Math.max(.004, k < 0 ? 0 : heights[k]); };
  const stack = b => { bb.setFromObject(b.m);      // a book at rest is something the next one lands on
    for (let x = bb.min.x; x <= bb.max.x; x += G / 2) for (let z = bb.min.z; z <= bb.max.z; z += G / 2) { const k = cell(x, z); if (k >= 0) heights[k] = Math.max(heights[k], bb.max.y); } };
  const AXES = [V3(1, 0, 0)], UP = V3(0, 1, 0), DOWN = V3(0, -1, 0), P0 = V3(), P1 = V3(), tmp = V3(), dq = new THREE.Quaternion(), dq2 = new THREE.Quaternion();
  const release = (b, tau) => {
    cab.updateMatrixWorld(true);
    pose(b, tau - .01, P0); cab.localToWorld(P0); pose(b, tau, P1); cab.localToWorld(P1);
    b.v = P1.clone().sub(P0).multiplyScalar(100).add(V3(rnd(-.2, .2), rnd(0, .15), rnd(.05, .4)));
    b.ang = V3(1, 0, 0).transformDirection(cab.matrixWorld).multiplyScalar(b.w0 + b.al * tau).add(V3(rnd(-1.2, 1.2), rnd(-2, 2), rnd(-1.2, 1.2)));
    scene.attach(b.m); b.state = 2;
  };
  const fly = (b, dt) => {
    b.v.y -= 9.8 * dt; b.m.position.addScaledVector(b.v, dt);
    const a = b.ang.length(); if (a > 1e-4) { dq.setFromAxisAngle(tmp.copy(b.ang).divideScalar(a), a * dt); b.m.quaternion.premultiply(dq); }
    let low = Infinity; for (const c of b.corners) { tmp.copy(c).applyQuaternion(b.m.quaternion); if (tmp.y < low) low = tmp.y; }
    low += b.m.position.y;
    let gy = ground(b.m.position.x, b.m.position.z);
    if (gy - low > .06) gy = .004;      // it came into the pile from the side: it slides in rather than jumping on top
    if (low < gy) { b.m.position.y += gy - low;
      if (b.v.y < 0) b.v.y = b.v.y < -1 ? -b.v.y * .2 : 0;
      b.v.x *= .7; b.v.z *= .7; b.ang.multiplyScalar(.6); b.down = true; }
    if (b.down) {      // down: a book topples onto a cover and lies flat
      tmp.copy(AXES[0]).applyQuaternion(b.m.quaternion); const by = tmp.y;
      dq.setFromUnitVectors(tmp, by > 0 ? UP : DOWN); dq2.identity().slerp(dq, .22); b.m.quaternion.premultiply(dq2);
      b.ang.multiplyScalar(.75); b.v.x *= .88; b.v.z *= .88;
      if (b.v.lengthSq() < .01 && Math.abs(by) > .995) { b.state = 3; b.m.updateMatrixWorld(); stack(b); }
    }
  };
  const eye = V3(), look = V3();
  let last = 0;
  return {scene, cam, dur: 4.0, frame(t){
    const dt = Math.min(.05, Math.max(0, t - last)); last = t;
    // your hand at the book: it slides out, tips toward you, and something behind the shelves gives with a clunk
    if (pick.state === 0) { pick.s0 = .07 * inOut(seg(t, .12, .38)); pick.phi0 = .5 * inOut(seg(t, .3, .52)); pick.m.rotation.set(pose(pick, 0, pick.m.position), 0, pick.rz); }
    const jolt = t > .55 ? -.004 * Math.sin(seg(t, .55, .8) * Math.PI * 3) * (1 - seg(t, .55, .8)) + .0015 * Math.sin(t * 60) * seg(t, .6, .7) * (1 - seg(t, 1.3, 1.6)) : 0;
    cab.position.z = CD / 2 + jolt;
    for (const b of books) {
      if (b.state === 0 && t >= b.td) b.state = 1;
      if (b.state === 1) { const tau = t - b.td, phi = pose(b, tau, b.m.position); b.m.rotation.set(phi, 0, b.rz);
        if (phi > b.tip || b.s0 + .5 * b.as * tau * tau > b.d * .5 || t > 1.62) release(b, tau); }      // every book is off its shelf before the bookcase moves
      else if (b.state === 2) fly(b, dt);
    }
    // the empty bookcase pushes back into the wall and swings aside; the light pours out
    hinge.position.z = H0.z - .36 * inOut(seg(t, 1.65, 2.0));
    hinge.rotation.y = -1.45 * outBack(seg(t, 1.95, 2.8));
    const leak = smooth(seg(t, .55, .85)) * (1 - smooth(seg(t, 1.7, 2.0))), open = smooth(seg(t, 1.65, 2.6));
    seamMat.opacity = .85 * leak; spill.intensity = 95 * open + 6 * leak; inner.intensity = 7 * open;
    endMat.color.set("#FFE9C4").multiplyScalar(.4 + 5 * open);
    dust.material.opacity = .7 * open;
    for (let i = 0; i < DUST; i++) { dpos[i * 3] += Math.sin(t * .7 + dph[i]) * .0004; dpos[i * 3 + 1] += Math.cos(t * .5 + dph[i]) * .0003 + .0002; }
    dgeo.attributes.position.needsUpdate = true;
    // you: reaching toward the book, a step back as the books come down, then drawn through the doorway
    const reach = inOut(seg(t, 0, .45)) * (1 - inOut(seg(t, .6, 1.0))), back = inOut(seg(t, .65, 1.05)), walk = Math.pow(seg(t, 2.2, 3.7), 2.2);
    eye.copy(E0).lerp(PW, .11 * reach); eye.z += .12 * back;
    eye.x += pt.sx * .035 * (1 - walk); eye.y += Math.sin(t * 1.6) * .003 - pt.sy * .025 * (1 - walk);
    eye.lerp(EEND, walk); eye.y += Math.sin(walk * 30) * .008 * (1 - walk);
    look.copy(L0).lerp(PW, .3 * reach); look.y -= .12 * seg(t, .8, 1.4) * (1 - seg(t, 1.8, 2.3)); look.lerp(LEND, smooth(seg(t, 2.0, 3.0)));
    cam.position.copy(eye); cam.lookAt(look);
    cam.fov = fov(50 + 14 * walk, cam.aspect); cam.updateProjectionMatrix();
    haze.material.opacity = .45 * open * clamp01((cam.position.z - haze.position.z) / 1.2);
    return smooth(seg(t, 3.45, 3.95));
  }};
}

/* ---------- playing a scene over the page ---------- */
function stage(bg){
  let renderer;
  try { renderer = new THREE.WebGLRenderer({antialias: true, powerPreference: "high-performance"}); } catch (e) { return null; }
  const w = innerWidth, h = innerHeight;
  setup(renderer, w, h, Math.min(1.75, devicePixelRatio || 1, Math.sqrt(4.2e6 / (w * h))));
  const host = document.createElement("div"), veil = document.createElement("div"), lens = document.createElement("div"), skip = document.createElement("div");
  host.id = "t3d"; host.setAttribute("aria-hidden", "true");
  host.style.cssText = `position:fixed;inset:0;z-index:95;background:${bg};opacity:0;transition:opacity .35s ease;cursor:pointer`;
  renderer.domElement.style.cssText = "display:block;width:100%;height:100%";
  lens.style.cssText = "position:absolute;inset:0;pointer-events:none;background:radial-gradient(120% 95% at 50% 50%,transparent 58%,rgba(0,0,0,.26))";
  veil.style.cssText = "position:absolute;inset:0;background:#FFFDF6;opacity:0;pointer-events:none";      // the light you step into at the end
  skip.textContent = "Click or tap to skip";
  skip.style.cssText = "position:absolute;right:16px;bottom:14px;font:12.5px system-ui,sans-serif;color:rgba(255,255,255,.75);text-shadow:0 1px 2px rgba(0,0,0,.55);opacity:0;transition:opacity .5s .9s;pointer-events:none";
  host.append(renderer.domElement, lens, veil, skip); document.body.appendChild(host);
  addEventListener("pageshow", e => { if (e.persisted) { host.remove(); renderer.dispose(); } });      // back from the next page: the page, not the scene
  return {host, renderer, veil, show(){ host.style.opacity = 1; skip.style.opacity = 1; }};
}
function play(st, S, url){
  let gone = false, t0 = 0;
  const go = () => { if (!gone) { gone = true; location.href = url; } };
  st.host.addEventListener("click", go, {once: true});      // a click skips the rest
  addEventListener("resize", () => { S.cam.aspect = innerWidth / innerHeight; st.renderer.setSize(innerWidth, innerHeight, false); });
  S.frame(0); st.renderer.compile(S.scene, S.cam); st.renderer.render(S.scene, S.cam);
  requestAnimationFrame(() => st.show());
  const tick = now => {
    if (!t0) t0 = now;
    const t = Math.min(S.dur, (now - t0) / 1000);
    pt.sx += (pt.x - pt.sx) * .06; pt.sy += (pt.y - pt.sy) * .06;
    st.veil.style.opacity = S.frame(t);
    st.renderer.render(S.scene, S.cam);
    if (t < S.dur) requestAnimationFrame(tick); else go();
  };
  requestAnimationFrame(tick);
  setTimeout(go, S.dur * 1000 + 2500);      // a window in the background draws no frames; the crossing still ends
}
export function run(kind, url, opts = {}){
  if (opts.pt) { pt.x = pt.sx = opts.pt.x; pt.y = pt.sy = opts.pt.y; }
  const st = stage(kind === "bookshelf" ? "#1A130E" : "#DCD6CA"); if (!st) return false;
  try { play(st, (kind === "bookshelf" ? bookshelf : scanner)(st.renderer, innerWidth / innerHeight), url); return true; }
  catch (e) { st.host.remove(); st.renderer.dispose(); return false; }
}
export function still(kind, t, w = 960, h = 540, where){
  if (where) { pt.x = pt.sx = where.x; pt.y = pt.sy = where.y; }
  const renderer = new THREE.WebGLRenderer({antialias: true, preserveDrawingBuffer: true});
  setup(renderer, w, h, 1);
  const S = (kind === "bookshelf" ? bookshelf : scanner)(renderer, w / h);
  for (let s = 0; s < t; s += 1 / 60) S.frame(s);
  const veil = S.frame(t); renderer.render(S.scene, S.cam);
  const url = renderer.domElement.toDataURL("image/jpeg", .85);
  renderer.dispose(); renderer.forceContextLoss();
  return {url, veil};
}
