/* Hero voxel animation — a cute human commands a little robot to fetch a parcel;
   the robot delivers it and the human pays a coin. Hearts & "!" emotes pop.
   Vanilla three.js (r128 UMD global THREE). Chibi, bouncy, adorable. */
(function () {
  var mount = document.getElementById('voxel');
  if (!mount || typeof THREE === 'undefined') { if (mount) fallback(mount); return; }
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function cssVar(n, f) { var v = getComputedStyle(document.documentElement).getPropertyValue(n).trim(); return v || f; }
  var TEAL = new THREE.Color(cssVar('--accent', '#6ad7c2'));
  var GOLD = new THREE.Color('#f5c542');
  var PINK = new THREE.Color('#ff7a9c');

  var W = mount.clientWidth || 480, H = mount.clientHeight || 460;
  var scene = new THREE.Scene();
  var d = 4.0, aspect = W / H;
  var camera = new THREE.OrthographicCamera(-d * aspect, d * aspect, d, -d, -50, 100);
  camera.position.set(7.5, 6.2, 8.5); camera.lookAt(0, 0.75, 0);

  var renderer;
  try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); } catch (e) { renderer = null; }
  if (!renderer || !renderer.getContext || !renderer.getContext()) { fallback(mount); return; }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(W, H);
  mount.appendChild(renderer.domElement);

  scene.add(new THREE.AmbientLight(0xffffff, 0.85));
  var key = new THREE.DirectionalLight(0xffffff, 0.8); key.position.set(5, 11, 5); scene.add(key);
  var rim = new THREE.DirectionalLight(TEAL.getHex(), 0.22); rim.position.set(-6, 3, -5); scene.add(rim);

  function mat(c) { return new THREE.MeshLambertMaterial({ color: c }); }
  function flat(c) { return new THREE.MeshBasicMaterial({ color: c }); }
  var M = {
    tileA: mat(0x161820), tileB: mat(0x1e2029),
    bot: mat(0xe2e5ec), bot2: mat(0xaab0bd), dark: mat(0x2a2d36),
    teal: flat(TEAL),
    skin: mat(0xf0c39c), hair: mat(0x3a3540), shirt: mat(0x7fd8c6), pants: mat(0x46506a),
    crate: mat(0xd6a15a), crateEdge: mat(0xb9843f),
    coin: new THREE.MeshStandardMaterial({ color: GOLD, metalness: 0.5, roughness: 0.35, emissive: GOLD, emissiveIntensity: 0.25 })
  };
  function box(w, h, dp, m, x, y, z) { var e = new THREE.Mesh(new THREE.BoxGeometry(w, h, dp), m); e.position.set(x, y, z); return e; }

  // (isometric floor removed — characters float on the transparent hero background)

  // ---- little robot (chibi: big head, stubby body) ----
  var robot = new THREE.Group();
  var rBody = box(0.62, 0.5, 0.5, M.bot, 0, 0.62, 0); robot.add(rBody);
  robot.add(box(0.34, 0.12, 0.26, M.teal, 0, 0.64, 0.25));           // chest light
  var rHead = new THREE.Group(); rHead.position.set(0, 1.12, 0);
  rHead.add(box(0.66, 0.56, 0.6, M.bot, 0, 0, 0));                    // head
  rHead.add(box(0.5, 0.26, 0.06, M.teal, 0, 0.02, 0.31));            // visor
  rHead.add(box(0.11, 0.13, 0.04, mat(0x0f1418), -0.12, 0.03, 0.345)); // eyes (dark on visor)
  rHead.add(box(0.11, 0.13, 0.04, mat(0x0f1418), 0.12, 0.03, 0.345));
  rHead.add(box(0.05, 0.16, 0.05, M.bot2, 0, 0.36, 0));               // antenna
  rHead.add(box(0.12, 0.12, 0.12, M.teal, 0, 0.5, 0));                // antenna ball
  robot.add(rHead);
  var rArmL = box(0.14, 0.34, 0.14, M.bot2, -0.4, 0.66, 0.02);
  var rArmR = box(0.14, 0.34, 0.14, M.bot2, 0.4, 0.66, 0.02);
  robot.add(rArmL); robot.add(rArmR);
  robot.add(box(0.18, 0.2, 0.2, M.dark, -0.16, 0.24, 0));
  robot.add(box(0.18, 0.2, 0.2, M.dark, 0.16, 0.24, 0));
  scene.add(robot);

  // ---- little human (chibi) ----
  var human = new THREE.Group();
  human.add(box(0.5, 0.5, 0.4, M.shirt, 0, 0.66, 0));                 // torso
  var hHead = new THREE.Group(); hHead.position.set(0, 1.16, 0);
  hHead.add(box(0.5, 0.5, 0.46, M.skin, 0, 0, 0));                    // head
  hHead.add(box(0.54, 0.2, 0.5, M.hair, 0, 0.2, 0));                  // hair top
  hHead.add(box(0.08, 0.1, 0.04, mat(0x2a2530), -0.11, -0.01, 0.235)); // eyes
  hHead.add(box(0.08, 0.1, 0.04, mat(0x2a2530), 0.11, -0.01, 0.235));
  hHead.add(box(0.12, 0.04, 0.03, mat(0xd98a86), 0, -0.16, 0.235));   // smile
  human.add(hHead);
  var hArmL = box(0.13, 0.36, 0.13, M.skin, -0.34, 0.66, 0.02);
  var hArmR = box(0.13, 0.36, 0.13, M.skin, 0.34, 0.66, 0.02);
  human.add(hArmL); human.add(hArmR);
  human.add(box(0.17, 0.24, 0.18, M.pants, -0.13, 0.26, 0));
  human.add(box(0.17, 0.24, 0.18, M.pants, 0.13, 0.26, 0));
  scene.add(human);

  var HUMAN = new THREE.Vector3(2.15, 0, -0.5);
  var CRATE = new THREE.Vector3(-2.15, 0, 0.6);
  human.position.copy(HUMAN); human.rotation.y = -0.6;

  // ---- parcel ----
  function makeCrate() {
    var g = new THREE.Group();
    g.add(box(0.5, 0.5, 0.5, M.crate, 0, 0, 0));
    g.add(box(0.55, 0.07, 0.55, M.crateEdge, 0, 0.24, 0));
    g.add(box(0.07, 0.5, 0.55, M.crateEdge, 0, 0, 0));
    return g;
  }
  var crate = makeCrate(); scene.add(crate);
  crate.position.set(CRATE.x, 0.28, CRATE.z);

  // ---- emotes (!, ♥) as camera-facing sprites ----
  var emotes = [];
  function emoteTex(txt, col) {
    var s = 128, cv = document.createElement('canvas'); cv.width = cv.height = s;
    var x = cv.getContext('2d');
    x.font = 'bold 104px -apple-system,Segoe UI,Arial'; x.textAlign = 'center'; x.textBaseline = 'middle';
    x.fillStyle = '#' + col.getHexString(); x.fillText(txt, s / 2, s / 2 + 8);
    var t = new THREE.CanvasTexture(cv); t.needsUpdate = true; return t;
  }
  function pop(txt, col, at) {
    var sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: emoteTex(txt, col), transparent: true, depthTest: false, depthWrite: false }));
    sp.position.copy(at); sp.scale.set(0.01, 0.01, 0.01); sp.userData.t = 0; sp.userData.base = at.clone();
    scene.add(sp); emotes.push(sp);
  }

  // ---- coins ----
  var coins = [], coinGeo = new THREE.CylinderGeometry(0.22, 0.22, 0.06, 18);
  var counter = document.getElementById('coincount'), earned = 0;
  function payCoin(from, to) {
    var c = new THREE.Mesh(coinGeo, M.coin);
    c.position.copy(from); c.rotation.x = Math.PI / 2;
    c.userData = { t: 0, from: from.clone(), to: to.clone() };
    scene.add(c); coins.push(c);
    earned++; if (counter) counter.textContent = earned;
  }

  // ---- FSM ----
  var PH = reduce ? [{ n: 'idle', d: 999 }] : [
    { n: 'command', d: 0.9 },
    { n: 'toCrate', d: 1.15 },
    { n: 'pick', d: 0.5 },
    { n: 'toHuman', d: 1.15 },
    { n: 'deliver', d: 0.55 },
    { n: 'pay', d: 1.0 }
  ];
  var ph = 0, pt = 0, from = new THREE.Vector3(), to = new THREE.Vector3(), carry = false;
  robot.position.set(0.4, 0, -0.1); robot.rotation.y = -0.6;

  function ease(x) { return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; }
  function face(dx, dz) { if (dx || dz) robot.rotation.y = Math.atan2(dx, dz); }

  function enter(n) {
    if (n === 'command') { pop('!', TEAL, human.position.clone().add(new THREE.Vector3(0, 2.05, 0))); }
    else if (n === 'toCrate') { from.copy(robot.position); to.set(CRATE.x + 0.55, 0, CRATE.z); face(to.x - from.x, to.z - from.z); }
    else if (n === 'toHuman') { from.copy(robot.position); to.set(HUMAN.x - 0.7, 0, HUMAN.z); face(to.x - from.x, to.z - from.z); carry = true; }
    else if (n === 'deliver') { /* hand parcel to human */ }
    else if (n === 'pay') {
      crate.visible = false;
      payCoin(human.position.clone().add(new THREE.Vector3(0, 1.0, 0)), robot.position.clone().add(new THREE.Vector3(0, 1.1, 0)));
      pop('♥', PINK, robot.position.clone().add(new THREE.Vector3(0, 1.9, 0)));
    }
  }
  enter('command');

  function update(dt, tsec) {
    var p = PH[ph], k = Math.min(1, (pt += dt) / p.d), e = ease(k);

    // idle life: head bob, blink-ish sway
    rHead.rotation.z = Math.sin(tsec * 2) * 0.04;
    hHead.rotation.z = Math.sin(tsec * 1.7 + 1) * 0.04;
    human.position.y = Math.abs(Math.sin(tsec * 2.2)) * 0.03;

    if (p.n === 'command') {
      var s = 1 + Math.sin(k * Math.PI) * 0.12; human.scale.set(1, s, 1);       // human bounce
      hArmR.rotation.x = -Math.sin(k * Math.PI) * 1.2;                            // point/wave
    } else if (p.n === 'toCrate' || p.n === 'toHuman') {
      robot.position.x = from.x + (to.x - from.x) * e;
      robot.position.z = from.z + (to.z - from.z) * e;
      robot.position.y = Math.abs(Math.sin(k * Math.PI * 6)) * 0.1;               // hop
      var sw = Math.sin(k * Math.PI * 6) * 0.6; rArmL.rotation.x = sw; rArmR.rotation.x = -sw;
      if (p.n === 'toHuman') { crate.visible = true; crate.position.set(robot.position.x, robot.position.y + 1.55, robot.position.z); crate.rotation.y += dt; }
    } else if (p.n === 'pick') {
      rArmL.rotation.x = -0.7; rArmR.rotation.x = -0.7;
      var sq = 1 - Math.sin(k * Math.PI) * 0.18; robot.scale.set(1 + (1 - sq) * 0.6, sq, 1 + (1 - sq) * 0.6); // squash
      crate.position.set(robot.position.x, 0.28 + e * (1.55 - 0.28), robot.position.z);
    } else if (p.n === 'deliver') {
      robot.scale.set(1, 1, 1);
      var hx = HUMAN.x, hz = HUMAN.z;
      crate.position.set(robot.position.x + (hx - robot.position.x) * e, 1.55 - e * 0.9, robot.position.z + (hz - robot.position.z) * e);
      hArmL.rotation.x = -e * 1.0; hArmR.rotation.x = -e * 1.0;
    } else if (p.n === 'pay') {
      rArmL.rotation.x = 0; rArmR.rotation.x = 0; hArmL.rotation.x = 0; hArmR.rotation.x = 0;
      robot.position.y = Math.abs(Math.sin(k * Math.PI * 3)) * 0.14;              // happy hop
    }

    // coins fly along an arc
    for (var i = coins.length - 1; i >= 0; i--) {
      var c = coins[i], u = c.userData; u.t += dt / 0.8;
      if (u.t >= 1) { scene.remove(c); coins.splice(i, 1); continue; }
      c.position.lerpVectors(u.from, u.to, u.t);
      c.position.y += Math.sin(u.t * Math.PI) * 0.8;                              // arc
      c.rotation.z += dt * 10;
    }
    // emotes pop + rise + fade
    for (var j = emotes.length - 1; j >= 0; j--) {
      var m = emotes[j]; m.userData.t += dt;
      var tt = m.userData.t, sc = tt < 0.18 ? (tt / 0.18) * 0.62 : 0.62;          // pop in
      m.scale.set(sc, sc, sc);
      m.position.y = m.userData.base.y + Math.min(tt, 1) * 0.5;
      m.material.opacity = tt > 0.7 ? Math.max(0, 1 - (tt - 0.7) / 0.35) : 1;
      if (tt > 1.05) { scene.remove(m); emotes.splice(j, 1); }
    }

    if (k >= 1 && !reduce) {
      if (p.n === 'command') { human.scale.set(1, 1, 1); }
      ph = (ph + 1) % PH.length; pt = 0;
      if (PH[ph].n === 'command') { crate.visible = true; crate.position.set(CRATE.x, 0.28, CRATE.z); carry = false; }
      enter(PH[ph].n);
    }
  }

  var clock = new THREE.Clock();
  (function loop() {
    if (document.hidden) { requestAnimationFrame(loop); return; }
    var dt = Math.min(clock.getDelta(), 0.05);
    if (!reduce) update(dt, clock.elapsedTime);
    scene.rotation.y = Math.sin(clock.elapsedTime * 0.13) * 0.05;
    renderer.render(scene, camera);
    requestAnimationFrame(loop);
  })();

  window.addEventListener('resize', function () {
    W = mount.clientWidth || W; H = mount.clientHeight || H; aspect = W / H;
    camera.left = -d * aspect; camera.right = d * aspect; camera.top = d; camera.bottom = -d;
    camera.updateProjectionMatrix(); renderer.setSize(W, H);
  });

  // ---- static fallback (no WebGL): human + robot + coin + heart ----
  function fallback(el) {
    var t = '#' + TEAL.getHexString(), g = '#f5c542', p = '#ff7a9c';
    el.innerHTML =
      '<style>.vx-fb{width:100%;height:100%;display:flex;align-items:center;justify-content:center}' +
      '.vx-a{animation:vxb 3s ease-in-out infinite}.vx-b{animation:vxb 3s ease-in-out infinite .4s}' +
      '.vx-h{animation:vxf 2.4s ease-in-out infinite}' +
      '@keyframes vxb{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}' +
      '@keyframes vxf{0%,100%{transform:translateY(0);opacity:.85}50%{transform:translateY(-8px);opacity:1}}' +
      '@media(prefers-reduced-motion:reduce){.vx-a,.vx-b,.vx-h{animation:none}}</style>' +
      '<div class="vx-fb"><svg viewBox="0 0 360 300" width="90%" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="A human pays a little robot a coin for moving a parcel">' +
      '<ellipse cx="180" cy="256" rx="140" ry="24" fill="' + t + '" opacity="0.08"/>' +
      // heart over robot
      '<g class="vx-h"><path d="M104 60c-9-16-34-8-34 10 0 14 18 24 34 36 16-12 34-22 34-36 0-18-25-26-34-10z" fill="' + p + '"/></g>' +
      // "!" over human
      '<g class="vx-h"><rect x="272" y="44" width="10" height="30" rx="5" fill="' + t + '"/><circle cx="277" cy="86" r="6" fill="' + t + '"/></g>' +
      // coin between
      '<circle cx="180" cy="120" r="16" fill="none" stroke="' + g + '" stroke-width="4"/><circle cx="180" cy="120" r="7" fill="' + g + '" opacity="0.5"/>' +
      // robot (left)
      '<g class="vx-a"><rect x="66" y="150" width="70" height="58" rx="12" fill="#e2e5ec"/>' +
      '<rect x="78" y="110" width="46" height="40" rx="10" fill="#e2e5ec"/>' +
      '<rect x="84" y="120" width="34" height="16" rx="6" fill="' + t + '"/>' +
      '<line x1="101" y1="98" x2="101" y2="110" stroke="#aab0bd" stroke-width="4"/><circle cx="101" cy="94" r="5" fill="' + t + '"/></g>' +
      // human (right)
      '<g class="vx-b"><rect x="228" y="150" width="60" height="58" rx="12" fill="#7fd8c6"/>' +
      '<rect x="234" y="104" width="48" height="46" rx="12" fill="#f0c39c"/>' +
      '<rect x="230" y="100" width="56" height="16" rx="8" fill="#3a3540"/>' +
      '<circle cx="248" cy="128" r="3.5" fill="#2a2530"/><circle cx="268" cy="128" r="3.5" fill="#2a2530"/></g>' +
      '</svg></div>';
  }
})();
