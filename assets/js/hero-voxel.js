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
  var TRGB = Math.round(TEAL.r * 255) + ',' + Math.round(TEAL.g * 255) + ',' + Math.round(TEAL.b * 255);

  var W = mount.clientWidth || 480, H = mount.clientHeight || 460;
  var scene = new THREE.Scene();
  // 모바일에선 프레임(d)을 좁혀 로봇을 ~1.8배 크게 보여준다(가로 잘림 없는 최소값). 시선도 살짝 위로 올려 하트/코인이 안 잘리게.
  function frame(w) { return w < 560 ? 2.2 : 4.0; }
  var d = frame(W), aspect = W / H, look = d < 3 ? 1.0 : 0.75;
  var camera = new THREE.OrthographicCamera(-d * aspect, d * aspect, d, -d, -50, 100);
  camera.position.set(7.5, 6.2, 8.5); camera.lookAt(0, look, 0);

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
  // KAIST wordmark on the chest (textured plane)
  var _kaistTex = new THREE.TextureLoader().load('/assets/img/kaist.png');
  _kaistTex.minFilter = THREE.LinearFilter; _kaistTex.magFilter = THREE.LinearFilter;
  var _lw = 0.4, _lh = _lw / 4.44;
  var chestLogo = new THREE.Mesh(new THREE.PlaneGeometry(_lw, _lh), new THREE.MeshBasicMaterial({ map: _kaistTex, transparent: true }));
  chestLogo.position.set(0, 0.64, 0.256);
  robot.add(chestLogo);
  var rHead = new THREE.Group(); rHead.position.set(0, 1.12, 0);
  rHead.add(box(0.66, 0.56, 0.6, M.bot, 0, 0, 0));                    // head
  rHead.add(box(0.5, 0.26, 0.06, M.teal, 0, 0.02, 0.31));            // visor
  var eyeMat = new THREE.MeshLambertMaterial({ color: 0x0f1418 });    // eyes (dark; glow teal when firing)
  rHead.add(box(0.11, 0.13, 0.05, eyeMat, -0.12, 0.03, 0.345));
  rHead.add(box(0.11, 0.13, 0.05, eyeMat, 0.12, 0.03, 0.345));
  rHead.add(box(0.05, 0.16, 0.05, M.bot2, 0, 0.36, 0));               // antenna
  rHead.add(box(0.12, 0.12, 0.12, M.teal, 0, 0.5, 0));                // antenna ball
  robot.add(rHead);
  var rArmL = box(0.14, 0.34, 0.14, M.bot2, -0.4, 0.66, 0.02);
  var rArmR = box(0.14, 0.34, 0.14, M.bot2, 0.4, 0.66, 0.02);
  robot.add(rArmL); robot.add(rArmR);
  robot.add(box(0.18, 0.2, 0.2, M.dark, -0.16, 0.24, 0));
  robot.add(box(0.18, 0.2, 0.2, M.dark, 0.16, 0.24, 0));
  scene.add(robot);

  // ---- AI core: a floating hologram brain that guides the robot ----
  function glowTex(alpha) {
    var s = 128, cv = document.createElement('canvas'); cv.width = cv.height = s;
    var x = cv.getContext('2d'), g = x.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
    g.addColorStop(0, 'rgba(' + TRGB + ',' + alpha + ')');
    g.addColorStop(0.45, 'rgba(' + TRGB + ',' + (alpha * 0.35) + ')');
    g.addColorStop(1, 'rgba(' + TRGB + ',0)');
    x.fillStyle = g; x.fillRect(0, 0, s, s);
    var t = new THREE.CanvasTexture(cv); t.needsUpdate = true; return t;
  }
  var ai = new THREE.Group();
  var aiCore = new THREE.Mesh(new THREE.IcosahedronGeometry(0.2, 0),
    new THREE.MeshBasicMaterial({ color: TEAL, wireframe: true, transparent: true, opacity: 0.95 }));
  var aiInner = new THREE.Mesh(new THREE.IcosahedronGeometry(0.12, 0),
    new THREE.MeshBasicMaterial({ color: TEAL, transparent: true, opacity: 0.55 }));
  ai.add(aiCore); ai.add(aiInner);
  var halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex(0.85), transparent: true, opacity: 0.85, depthWrite: false, blending: THREE.AdditiveBlending }));
  halo.scale.set(1.0, 1.0, 1.0); ai.add(halo);
  var aiNodes = [];
  for (var an = 0; an < 3; an++) { var nd = new THREE.Mesh(new THREE.SphereGeometry(0.04, 8, 8), flat(TEAL)); ai.add(nd); aiNodes.push(nd); }
  scene.add(ai);

  // guidance link (AI → robot) and scan link (AI → target)
  function line(op) { return new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]), new THREE.LineBasicMaterial({ color: TEAL, transparent: true, opacity: op })); }
  var link = line(0.3); scene.add(link);
  // eye lasers — two beams fired from the robot's eyes onto the parcel
  var beamGeo = new THREE.CylinderGeometry(0.022, 0.022, 1, 6);
  function beam() { return new THREE.Mesh(beamGeo, new THREE.MeshBasicMaterial({ color: TEAL, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending, depthWrite: false })); }
  var beamL = beam(), beamR = beam(); beamL.visible = beamR.visible = false; scene.add(beamL); scene.add(beamR);
  var impact = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex(0.95), transparent: true, opacity: 0.9, depthWrite: false, blending: THREE.AdditiveBlending }));
  impact.visible = false; scene.add(impact);
  var UP = new THREE.Vector3(0, 1, 0);
  function orientBeam(m, a, b) {
    var dir = new THREE.Vector3().subVectors(b, a), len = dir.length();
    m.position.copy(a).addScaledVector(dir, 0.5);
    m.scale.set(1, len, 1);
    m.quaternion.setFromUnitVectors(UP, dir.clone().normalize());
  }
  function eyeWorld(sx) {
    return new THREE.Vector3(sx * 0.12, 1.15, 0.36).applyAxisAngle(UP, robot.rotation.y).add(robot.position);
  }
  // targeting reticle on the parcel
  var reticle = new THREE.Group();
  var ring1 = new THREE.Mesh(new THREE.TorusGeometry(0.42, 0.02, 6, 32), flat(TEAL)); ring1.rotation.x = Math.PI / 2; reticle.add(ring1);
  var ring2 = new THREE.Mesh(new THREE.TorusGeometry(0.3, 0.015, 6, 28), new THREE.MeshBasicMaterial({ color: TEAL, transparent: true, opacity: 0.6 })); ring2.rotation.x = Math.PI / 2; reticle.add(ring2);
  reticle.visible = false; scene.add(reticle);

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
    { n: 'pose', d: 1.4 },
    { n: 'deliver', d: 0.55 },
    { n: 'pay', d: 0.9 },
    { n: 'celebrate', d: 1.9 }
  ];
  var ph = 0, pt = 0, from = new THREE.Vector3(), to = new THREE.Vector3(), carry = false;
  var faceCam = Math.atan2(camera.position.x - HUMAN.x, camera.position.z - HUMAN.z), poseFrom = 0;
  robot.position.set(0.4, 0, -0.1); robot.rotation.y = -0.6;

  function ease(x) { return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; }
  function face(dx, dz) { if (dx || dz) robot.rotation.y = Math.atan2(dx, dz); }

  function enter(n) {
    if (n === 'command') { pop('!', TEAL, human.position.clone().add(new THREE.Vector3(0, 2.05, 0))); }
    else if (n === 'toCrate') { from.copy(robot.position); to.set(CRATE.x + 0.55, 0, CRATE.z); face(to.x - from.x, to.z - from.z); }
    else if (n === 'toHuman') { from.copy(robot.position); to.set(HUMAN.x - 0.7, 0, HUMAN.z); face(to.x - from.x, to.z - from.z); carry = true; }
    else if (n === 'pose') { poseFrom = robot.rotation.y; }
    else if (n === 'deliver') { /* hand parcel to human */ }
    else if (n === 'pay') {
      crate.visible = false;
      payCoin(human.position.clone().add(new THREE.Vector3(0, 1.0, 0)), robot.position.clone().add(new THREE.Vector3(0, 1.1, 0)));
    }
    else if (n === 'celebrate') {                      // heart burst on receiving the coin
      var hp = robot.position.clone();
      pop('♥', PINK, hp.clone().add(new THREE.Vector3(0, 1.98, 0)));
      pop('♥', PINK, hp.clone().add(new THREE.Vector3(-0.42, 1.72, 0)));
      pop('♥', PINK, hp.clone().add(new THREE.Vector3(0.42, 1.72, 0)));
    }
  }
  enter('command');

  function update(dt, tsec) {
    var p = PH[ph], k = Math.min(1, (pt += dt) / p.d), e = ease(k);

    // idle life: head bob, blink-ish sway
    rHead.rotation.z = Math.sin(tsec * 2) * 0.04;
    hHead.rotation.z = Math.sin(tsec * 1.7 + 1) * 0.04;
    human.position.y = Math.abs(Math.sin(tsec * 2.2)) * 0.03;

    // --- AI core: hovers above the robot, "thinks", and guides it ---
    var aiY = robot.position.y + 2.05 + Math.sin(tsec * 2.6) * 0.08;
    ai.position.set(robot.position.x, aiY, robot.position.z);
    aiCore.rotation.y += dt * 1.3; aiCore.rotation.x += dt * 0.7; aiInner.rotation.y -= dt * 1.8;
    var thinking = (p.n === 'command' || p.n === 'toCrate' || p.n === 'pick');
    var apulse = 1 + Math.sin(tsec * (thinking ? 9 : 4)) * (thinking ? 0.18 : 0.08);
    halo.scale.setScalar(1.15 * apulse);
    halo.material.opacity = thinking ? 1.0 : 0.7;
    for (var q = 0; q < aiNodes.length; q++) {
      var a2 = tsec * (thinking ? 3.2 : 1.8) + q * (Math.PI * 2 / 3);
      aiNodes[q].position.set(Math.cos(a2) * 0.33, Math.sin(a2 * 1.4) * 0.1, Math.sin(a2) * 0.33);
    }
    link.geometry.setFromPoints([ai.position.clone(), robot.position.clone().add(new THREE.Vector3(0, 1.35, 0))]);
    var targeting = (p.n === 'command' || p.n === 'toCrate') && crate.visible;
    reticle.visible = targeting;
    beamL.visible = beamR.visible = impact.visible = targeting;
    if (targeting) {
      var tgt = new THREE.Vector3(crate.position.x, 0.32, crate.position.z);
      reticle.position.set(crate.position.x, 0.05, crate.position.z);
      reticle.rotation.z += dt * 1.6;
      reticle.scale.setScalar(1 + Math.sin(tsec * 6) * 0.12);
      orientBeam(beamL, eyeWorld(-1), tgt);
      orientBeam(beamR, eyeWorld(1), tgt);
      var fl = 0.55 + Math.abs(Math.sin(tsec * 26)) * 0.45;                 // laser flicker
      beamL.material.opacity = beamR.material.opacity = fl;
      impact.position.copy(tgt);
      impact.scale.setScalar(0.4 + Math.sin(tsec * 12) * 0.08);
      eyeMat.color.set(TEAL);                                              // eyes glow while firing
    } else {
      eyeMat.color.setHex(0x0f1418);                                       // eyes back to normal
    }

    if (p.n === 'command') {
      var s = 1 + Math.sin(k * Math.PI) * 0.12; human.scale.set(1, s, 1);       // human bounce
      hArmR.rotation.x = -Math.sin(k * Math.PI) * 1.2;                            // point/wave
    } else if (p.n === 'toCrate' || p.n === 'toHuman') {
      robot.position.x = from.x + (to.x - from.x) * e;
      robot.position.z = from.z + (to.z - from.z) * e;
      robot.position.y = Math.abs(Math.sin(k * Math.PI * 6)) * 0.1;               // hop
      var sw = Math.sin(k * Math.PI * 6) * 0.6; rArmL.rotation.x = sw; rArmR.rotation.x = -sw;
      if (p.n === 'toHuman') { crate.visible = true; crate.position.set(robot.position.x, robot.position.y + 1.55, robot.position.z); crate.rotation.y += dt; }
    } else if (p.n === 'pose') {
      // arrive in front of the human, turn to face the viewer, hold the parcel, pause
      robot.rotation.y = poseFrom + (faceCam - poseFrom) * ease(Math.min(1, k * 1.7));
      robot.position.y = Math.abs(Math.sin(tsec * 3)) * 0.04;
      crate.visible = true;
      crate.position.set(robot.position.x, robot.position.y + 1.55 + Math.sin(tsec * 3) * 0.03, robot.position.z);
      crate.rotation.y = faceCam;
      rArmL.rotation.x = 0; rArmR.rotation.x = Math.max(0, Math.sin(k * Math.PI * 3)) * 0.5; // little hello wave
    } else if (p.n === 'pick') {
      rArmL.rotation.x = -0.7; rArmR.rotation.x = -0.7;
      var sq = 1 - Math.sin(k * Math.PI) * 0.18; robot.scale.set(1 + (1 - sq) * 0.6, sq, 1 + (1 - sq) * 0.6); // squash
      crate.position.set(robot.position.x, 0.28 + e * (1.55 - 0.28), robot.position.z);
    } else if (p.n === 'deliver') {
      robot.scale.set(1, 1, 1); robot.rotation.y = faceCam;
      var hx = HUMAN.x, hz = HUMAN.z;
      crate.position.set(robot.position.x + (hx - robot.position.x) * e, 1.55 - e * 0.9, robot.position.z + (hz - robot.position.z) * e);
      hArmL.rotation.x = -e * 1.0; hArmR.rotation.x = -e * 1.0;
    } else if (p.n === 'pay') {
      robot.rotation.y = faceCam;
      rArmL.rotation.x = -0.35; rArmR.rotation.x = -0.35;                         // reach to receive the coin
      hArmL.rotation.x = 0; hArmR.rotation.x = -0.5 * (1 - e);                    // human's toss arm returns
      robot.position.y = 0; robot.scale.set(1, 1, 1);
    } else if (p.n === 'celebrate') {
      robot.rotation.y = faceCam;
      rArmL.rotation.x = 0; rArmR.rotation.x = 0; hArmL.rotation.x = 0; hArmR.rotation.x = 0;
      if (k < 0.62) {                                                             // two hops in place
        var jj = (k / 0.62) * Math.PI * 2, hop = Math.abs(Math.sin(jj));
        robot.position.y = hop * 0.42;
        robot.scale.set(1 - hop * 0.06, 1 + hop * 0.12, 1 - hop * 0.06);
      } else {                                                                    // brief pose, then loop
        robot.position.y = 0; robot.scale.set(1, 1, 1);
      }
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
    d = frame(W); look = d < 3 ? 1.0 : 0.75; camera.lookAt(0, look, 0);
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
      // AI core hovering above the robot (guides it)
      '<line x1="101" y1="86" x2="101" y2="106" stroke="' + t + '" stroke-width="2" stroke-dasharray="3 3" opacity="0.5"/>' +
      '<g class="vx-h"><circle cx="101" cy="66" r="20" fill="' + t + '" opacity="0.14"/>' +
      '<circle cx="101" cy="66" r="11" fill="none" stroke="' + t + '" stroke-width="3"/>' +
      '<circle cx="101" cy="66" r="4" fill="' + t + '"/>' +
      '<circle cx="123" cy="66" r="3" fill="' + t + '"/><circle cx="79" cy="66" r="3" fill="' + t + '"/><circle cx="101" cy="44" r="3" fill="' + t + '"/></g>' +
      // small heart (robot happy) + "!" over human
      '<g class="vx-h"><path d="M156 150c-5-9-19-4-19 6 0 8 10 13 19 20 9-7 19-12 19-20 0-10-14-15-19-6z" fill="' + p + '"/></g>' +
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
