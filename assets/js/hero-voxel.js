/* Hero voxel animation — an AI robot moves crates and earns coins.
   Vanilla three.js (r128 UMD global THREE). Editorial dark palette + teal accent. */
(function () {
  var mount = document.getElementById('voxel');
  if (!mount || typeof THREE === 'undefined') return;

  // Respect reduced-motion: render one static frame, no loop.
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function cssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }
  var TEAL = new THREE.Color(cssVar('--accent', '#6ad7c2'));

  var W = mount.clientWidth || 480;
  var H = mount.clientHeight || 460;

  var scene = new THREE.Scene();
  var d = 5.2, aspect = W / H;
  var camera = new THREE.OrthographicCamera(-d * aspect, d * aspect, d, -d, -50, 100);
  camera.position.set(9, 7.5, 9);
  camera.lookAt(0, 1.1, 0);

  var renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  } catch (e) { renderer = null; }
  if (!renderer || !renderer.getContext || !renderer.getContext()) {
    fallback(mount, TEAL);   // no WebGL — show a static themed illustration
    return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(W, H);
  mount.appendChild(renderer.domElement);

  scene.add(new THREE.AmbientLight(0xffffff, 0.78));
  var key = new THREE.DirectionalLight(0xffffff, 0.85);
  key.position.set(6, 12, 4);
  scene.add(key);
  var rim = new THREE.DirectionalLight(TEAL.getHex(), 0.25);
  rim.position.set(-6, 4, -6);
  scene.add(rim);

  var M = {
    tileA: new THREE.MeshLambertMaterial({ color: 0x161820 }),
    tileB: new THREE.MeshLambertMaterial({ color: 0x1e2029 }),
    bot: new THREE.MeshLambertMaterial({ color: 0xd2d5dd }),
    bot2: new THREE.MeshLambertMaterial({ color: 0x9aa0ad }),
    dark: new THREE.MeshLambertMaterial({ color: 0x2a2d36 }),
    teal: new THREE.MeshBasicMaterial({ color: TEAL }),
    tealGlow: new THREE.MeshBasicMaterial({ color: TEAL, transparent: true, opacity: 0.9 }),
    crate: new THREE.MeshLambertMaterial({ color: 0x5f6675 }),
    crateEdge: new THREE.MeshLambertMaterial({ color: 0x767d8d }),
    coin: new THREE.MeshStandardMaterial({ color: TEAL, metalness: 0.55, roughness: 0.3, emissive: TEAL, emissiveIntensity: 0.25 })
  };

  function box(w, h, dp, mat, x, y, z) {
    var m = new THREE.Mesh(new THREE.BoxGeometry(w, h, dp), mat);
    m.position.set(x, y, z);
    return m;
  }

  // ---- ground ----
  var N = 7, ground = new THREE.Group();
  for (var i = 0; i < N; i++) for (var j = 0; j < N; j++) {
    ground.add(box(0.94, 0.4, 0.94, (i + j) % 2 ? M.tileA : M.tileB, i - (N - 1) / 2, -0.22, j - (N - 1) / 2));
  }
  scene.add(ground);

  // ---- robot ----
  var robot = new THREE.Group();
  robot.add(box(1.0, 1.0, 0.8, M.bot, 0, 1.0, 0));           // body
  robot.add(box(0.5, 0.28, 0.3, M.teal, 0, 1.02, 0.28));     // chest light
  var head = box(0.8, 0.6, 0.72, M.bot2, 0, 1.78, 0);
  robot.add(head);
  robot.add(box(0.17, 0.17, 0.06, M.teal, -0.18, 1.83, 0.37)); // eyes
  robot.add(box(0.17, 0.17, 0.06, M.teal, 0.18, 1.83, 0.37));
  var armL = box(0.2, 0.72, 0.2, M.bot2, -0.62, 1.05, 0.1);
  var armR = box(0.2, 0.72, 0.2, M.bot2, 0.62, 1.05, 0.1);
  robot.add(armL); robot.add(armR);
  robot.add(box(0.34, 0.32, 0.34, M.dark, -0.28, 0.32, 0));   // legs
  robot.add(box(0.34, 0.32, 0.34, M.dark, 0.28, 0.32, 0));
  // AI "thinking" ring above head
  var ring = new THREE.Mesh(new THREE.TorusGeometry(0.34, 0.045, 8, 26), M.tealGlow);
  ring.position.set(0, 2.42, 0); ring.rotation.x = Math.PI / 2;
  robot.add(ring);
  scene.add(robot);

  // ---- crate being carried / picked ----
  function makeCrate() {
    var g = new THREE.Group();
    g.add(box(0.78, 0.78, 0.78, M.crate, 0, 0, 0));
    g.add(box(0.84, 0.1, 0.84, M.crateEdge, 0, 0.36, 0));
    g.add(box(0.84, 0.1, 0.84, M.crateEdge, 0, -0.36, 0));
    return g;
  }
  var crate = makeCrate(); scene.add(crate);

  var stack = [];      // delivered crates
  var coins = [];      // flying coins
  var coinGeo = new THREE.CylinderGeometry(0.3, 0.3, 0.08, 20);

  var pickup = new THREE.Vector3(-2.3, 0, 1.3);
  var drop = new THREE.Vector3(2.3, 0, -1.3);
  var botY = 0;

  // ---- coin counter overlay ----
  var counter = document.getElementById('coincount');
  var earned = 0;
  function addCoin() {
    var c = new THREE.Mesh(coinGeo, M.coin);
    var base = drop.clone();
    c.position.set(base.x, 1.2 + stack.length * 0.5, base.z);
    c.rotation.x = Math.PI / 2;
    c.userData.life = 0;
    scene.add(c); coins.push(c);
    earned++;
    if (counter) counter.textContent = earned;
  }

  // ---- state machine ----
  var PHASES = reduce
    ? [{ name: 'idle', dur: 999 }]
    : [
        { name: 'toPickup', dur: 1.5 },
        { name: 'grab', dur: 0.55 },
        { name: 'toDrop', dur: 1.5 },
        { name: 'place', dur: 0.55 },
        { name: 'reward', dur: 0.7 }
      ];
  var phase = 0, pt = 0;
  var fromPos = drop.clone(), toPos = pickup.clone();
  robot.position.copy(pickup);
  crate.position.set(pickup.x, 0.4, pickup.z);
  crate.visible = true;

  function ease(x) { return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; }
  function facePath(from, to) {
    var dx = to.x - from.x, dz = to.z - from.z;
    if (dx || dz) robot.rotation.y = Math.atan2(dx, dz);
  }

  function enter(name) {
    if (name === 'toPickup') { fromPos = drop.clone(); toPos = pickup.clone(); facePath(fromPos, toPos); crate.visible = true; crate.position.set(pickup.x, 0.4, pickup.z); }
    else if (name === 'toDrop') { fromPos = pickup.clone(); toPos = drop.clone(); facePath(fromPos, toPos); }
    else if (name === 'place') { /* lower crate onto stack */ }
    else if (name === 'reward') { addCoin(); }
  }
  enter('toPickup');

  function update(dt, tsec) {
    // ambient life
    ring.rotation.z += dt * 1.4;
    ring.position.y = 2.42 + Math.sin(tsec * 3) * 0.05;
    robot.position.y = botY + Math.abs(Math.sin(tsec * 6)) * 0.0; // reserved

    var ph = PHASES[phase];
    pt += dt;
    var p = Math.min(1, pt / ph.dur);

    if (ph.name === 'toPickup' || ph.name === 'toDrop') {
      var e = ease(p);
      robot.position.x = fromPos.x + (toPos.x - fromPos.x) * e;
      robot.position.z = fromPos.z + (toPos.z - fromPos.z) * e;
      robot.position.y = Math.abs(Math.sin(p * Math.PI * 5)) * 0.12; // walk bob
      var swing = Math.sin(p * Math.PI * 5) * 0.5;
      armL.rotation.x = swing; armR.rotation.x = -swing;
      if (ph.name === 'toDrop') { // carry crate above head
        crate.visible = true;
        crate.position.set(robot.position.x, robot.position.y + 2.5, robot.position.z);
        crate.rotation.y += dt * 0.6;
      }
    } else if (ph.name === 'grab') {
      armL.rotation.x = -0.6; armR.rotation.x = -0.6;
      var y = 0.4 + ease(p) * (2.5 - 0.4);
      crate.position.set(robot.position.x, y, robot.position.z);
    } else if (ph.name === 'place') {
      armL.rotation.x = -0.4; armR.rotation.x = -0.4;
      var targetY = 0.4 + stack.length * 0.82;
      var y2 = 2.5 + ease(p) * (targetY - 2.5);
      crate.position.set(drop.x, y2, drop.z);
      crate.rotation.y = 0;
    } else if (ph.name === 'reward') {
      armL.rotation.x = 0; armR.rotation.x = 0;
    }

    // coins float + fade
    for (var k = coins.length - 1; k >= 0; k--) {
      var c = coins[k];
      c.userData.life += dt;
      c.position.y += dt * 1.4;
      c.rotation.z += dt * 6;
      c.material = c.material; // keep
      if (c.userData.life > 1.1) { scene.remove(c); coins.splice(k, 1); }
    }

    if (p >= 1 && !reduce) {
      // phase transition
      if (ph.name === 'grab') { /* crate now carried */ }
      if (ph.name === 'place') {
        // leave a delivered crate on the stack
        var placed = makeCrate();
        placed.position.set(drop.x, 0.4 + stack.length * 0.82, drop.z);
        scene.add(placed); stack.push(placed);
        crate.visible = false;
        if (stack.length >= 3) { // clear the stack for a clean loop
          for (var s = 0; s < stack.length; s++) scene.remove(stack[s]);
          stack = [];
        }
      }
      phase = (phase + 1) % PHASES.length;
      pt = 0;
      enter(PHASES[phase].name);
    }
  }

  // ---- loop ----
  var clock = new THREE.Clock();
  function frame() {
    if (document.hidden) { requestAnimationFrame(frame); return; }
    var dt = Math.min(clock.getDelta(), 0.05);
    var tsec = clock.elapsedTime;
    if (!reduce) update(dt, tsec);
    // gentle scene sway
    scene.rotation.y = Math.sin(tsec * 0.15) * 0.06;
    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  // ---- resize ----
  function onResize() {
    W = mount.clientWidth || W; H = mount.clientHeight || H;
    aspect = W / H;
    camera.left = -d * aspect; camera.right = d * aspect;
    camera.top = d; camera.bottom = -d;
    camera.updateProjectionMatrix();
    renderer.setSize(W, H);
  }
  window.addEventListener('resize', onResize);

  // ---- static fallback (no WebGL) ----
  function fallback(el, teal) {
    var c = '#' + teal.getHexString();
    el.innerHTML =
      '<style>' +
      '.vx-fb{width:100%;height:100%;display:flex;align-items:center;justify-content:center}' +
      '.vx-bot{animation:vxbob 3.4s ease-in-out infinite}' +
      '.vx-coin{animation:vxfloat 2.6s ease-in-out infinite;transform-origin:center}' +
      '@keyframes vxbob{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}' +
      '@keyframes vxfloat{0%,100%{transform:translateY(0);opacity:.9}50%{transform:translateY(-10px);opacity:1}}' +
      '@media(prefers-reduced-motion:reduce){.vx-bot,.vx-coin{animation:none}}' +
      '</style>' +
      '<div class="vx-fb"><svg viewBox="0 0 320 320" width="86%" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="An AI robot moving a crate and earning a coin">' +
      // ground
      '<ellipse cx="160" cy="270" rx="120" ry="26" fill="' + c + '" opacity="0.08"/>' +
      // coin
      '<g class="vx-coin"><circle cx="235" cy="70" r="26" fill="none" stroke="' + c + '" stroke-width="3"/>' +
      '<circle cx="235" cy="70" r="15" fill="none" stroke="' + c + '" stroke-width="3" opacity="0.7"/></g>' +
      // robot
      '<g class="vx-bot" stroke="#c7cad3" stroke-width="3" stroke-linejoin="round">' +
      '<line x1="160" y1="70" x2="160" y2="92" stroke="' + c + '"/><circle cx="160" cy="64" r="6" fill="' + c + '" stroke="none"/>' +
      '<rect x="120" y="92" width="80" height="60" rx="10" fill="#1b1e26"/>' +
      '<circle cx="145" cy="120" r="7" fill="' + c + '" stroke="none"/><circle cx="175" cy="120" r="7" fill="' + c + '" stroke="none"/>' +
      '<rect x="112" y="158" width="96" height="80" rx="12" fill="#20242e"/>' +
      '<rect x="140" y="176" width="40" height="16" rx="4" fill="' + c + '" stroke="none" opacity="0.85"/>' +
      '<rect x="92" y="168" width="18" height="54" rx="8" fill="#20242e"/>' +
      '<rect x="210" y="168" width="18" height="54" rx="8" fill="#20242e"/>' +
      '</g>' +
      // crate held
      '<g class="vx-bot"><rect x="126" y="212" width="68" height="60" rx="6" fill="#3a3f4c" stroke="#767d8d" stroke-width="3"/>' +
      '<line x1="126" y1="242" x2="194" y2="242" stroke="#767d8d" stroke-width="3"/>' +
      '<line x1="160" y1="212" x2="160" y2="272" stroke="#767d8d" stroke-width="3"/></g>' +
      '</svg></div>';
  }
})();
