/* 写作模式动画层：雨、星空、池塘、远海、夜车、水墨、梦境、沙丘、花园、窗岛
   纯 canvas，无第三方依赖；打字时在光标附近激起涟漪 / 星屑。 */
(function () {
  const MODES = ['bamboo', 'starfield', 'pond', 'ocean', 'night-train', 'ink', 'dream', 'dunes', 'monet', 'island'];
  let scene = 'none';
  let cv = null;
  let ctx = null;
  let W = 0;
  let H = 0;
  let dpr = 1;
  let raf = 0;
  let last = 0;
  let clock = 0;
  let parts = [];
  let pulses = [];
  const reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const rnd = (a, b) => a + Math.random() * (b - a);

  function resize() {
    if (!cv) return;
    dpr = Math.min(2, window.devicePixelRatio || 1);
    W = window.innerWidth;
    H = window.innerHeight;
    cv.width = Math.round(W * dpr);
    cv.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    build();
  }

  function ensure() {
    if (cv) return true;
    const host = document.getElementById('sceneBg');
    if (!host) return false;
    cv = document.createElement('canvas');
    cv.id = 'ambient';
    cv.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none';
    host.appendChild(cv);
    ctx = cv.getContext('2d');
    resize();
    window.addEventListener('resize', resize);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) stop(); else if (scene !== 'none') start();
    });
    return true;
  }

  function build() {
    parts = [];
    pulses = [];
    const n = { bamboo: 150, starfield: 120, pond: 60, ocean: 46, 'night-train': 34, ink: 22, dream: 44, dunes: 70, monet: 40, island: 50 }[scene] || 0;
    for (let i = 0; i < n; i++) parts.push(spawn(true));
  }

  function spawn(init) {
    const x = rnd(0, W);
    const y = rnd(0, H);
    switch (scene) {
      case 'bamboo':
        return { x, y: init ? y : rnd(-H, -10), len: rnd(12, 34), sp: rnd(420, 780), a: rnd(.12, .38) };
      case 'starfield':
        return { x, y, r: rnd(.5, 1.9), ph: rnd(0, 6.28), tw: rnd(.5, 1.6) };
      case 'pond':
        return { x, y: rnd(H * .25, H), r: rnd(2, 7), sp: rnd(.12, .5), ph: rnd(0, 6.28) };
      case 'ocean':
        return { y: rnd(H * .18, H * .95), off: rnd(0, 6.28), amp: rnd(4, 16), sp: rnd(.12, .34), a: rnd(.05, .14) };
      case 'night-train':
        return { x: init ? x : rnd(W, W + 240), y: rnd(H * .1, H * .85), w: rnd(60, 220), sp: rnd(90, 320), a: rnd(.06, .2), warm: Math.random() > .45 };
      case 'ink':
        return { x, y: init ? y : H + rnd(20, 120), r: rnd(18, 70), sp: rnd(6, 22), a: rnd(.03, .1), ph: rnd(0, 6.28) };
      case 'dream':
        return { x, y: init ? y : H + rnd(10, 80), r: rnd(1.4, 4.6), sp: rnd(8, 26), a: rnd(.15, .5), ph: rnd(0, 6.28) };
      case 'dunes':
        return { x: init ? x : -20, y: rnd(H * .2, H), r: rnd(.6, 2.2), sp: rnd(20, 70), a: rnd(.05, .2) };
      case 'monet':
        return { x, y: init ? y : rnd(-H, -10), r: rnd(2, 5), sp: rnd(14, 40), rot: rnd(0, 6.28), vr: rnd(-.6, .6), a: rnd(.2, .55), hue: rnd(330, 360) };
      case 'island':
      default:
        return { x, y, r: rnd(.6, 2), sp: rnd(3, 12), ph: rnd(0, 6.28), a: rnd(.1, .3) };
    }
  }

  function draw(dt) {
    ctx.clearRect(0, 0, W, H);
    const t = clock;
    if (scene === 'bamboo') {
      ctx.lineWidth = 1;
      for (const p of parts) {
        p.y += p.sp * dt;
        if (p.y > H + 40) Object.assign(p, spawn(false));
        ctx.strokeStyle = 'rgba(198,222,208,' + p.a + ')';
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(p.x - 3, p.y + p.len);
        ctx.stroke();
      }
    } else if (scene === 'starfield') {
      for (const p of parts) {
        const a = p.a = .25 + Math.abs(Math.sin(t * p.tw + p.ph)) * .55;
        ctx.fillStyle = 'rgba(240,244,255,' + a.toFixed(3) + ')';
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, 6.283);
        ctx.fill();
      }
    } else if (scene === 'pond') {
      ctx.lineWidth = 1;
      for (const p of parts) {
        p.y -= p.sp * dt;
        if (p.y < H * .2) Object.assign(p, spawn(false));
        const r = p.r + Math.sin(t * .8 + p.ph) * 1.6;
        ctx.strokeStyle = 'rgba(214,236,226,.16)';
        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.max(1, r), 0, 6.283);
        ctx.stroke();
      }
    } else if (scene === 'ocean') {
      for (const p of parts) {
        ctx.strokeStyle = 'rgba(226,244,242,' + p.a + ')';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        for (let x = 0; x <= W; x += 12) {
          const y = p.y + Math.sin(x * .006 + t * p.sp + p.off) * p.amp;
          if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
    } else if (scene === 'night-train') {
      for (const p of parts) {
        p.x -= p.sp * dt;
        if (p.x + p.w < -40) Object.assign(p, spawn(false));
        const g = ctx.createLinearGradient(p.x, 0, p.x + p.w, 0);
        const c = p.warm ? '229,184,92' : '146,190,214';
        g.addColorStop(0, 'rgba(' + c + ',0)');
        g.addColorStop(.5, 'rgba(' + c + ',' + p.a + ')');
        g.addColorStop(1, 'rgba(' + c + ',0)');
        ctx.fillStyle = g;
        ctx.fillRect(p.x, p.y, p.w, 1.6);
      }
    } else if (scene === 'ink') {
      for (const p of parts) {
        p.y -= p.sp * dt;
        const r = p.r * (1 + Math.sin(t * .5 + p.ph) * .08);
        if (p.y + r < -20) Object.assign(p, spawn(false));
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r);
        g.addColorStop(0, 'rgba(28,30,32,' + p.a + ')');
        g.addColorStop(1, 'rgba(28,30,32,0)');
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, 6.283);
        ctx.fill();
      }
    } else if (scene === 'dream') {
      for (const p of parts) {
        p.y -= p.sp * dt;
        p.x += Math.sin(t * .7 + p.ph) * .18;
        if (p.y < -20) Object.assign(p, spawn(false));
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 4);
        g.addColorStop(0, 'rgba(236,226,255,' + p.a + ')');
        g.addColorStop(1, 'rgba(236,226,255,0)');
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r * 4, 0, 6.283);
        ctx.fill();
      }
    } else if (scene === 'dunes') {
      for (const p of parts) {
        p.x += p.sp * dt;
        p.y += Math.sin(t + p.r * 9) * .12;
        if (p.x > W + 20) Object.assign(p, spawn(false));
        ctx.fillStyle = 'rgba(214,192,152,' + p.a + ')';
        ctx.fillRect(p.x, p.y, p.r * 2.4, p.r * .8);
      }
    } else if (scene === 'monet') {
      for (const p of parts) {
        p.y += p.sp * dt;
        p.x += Math.sin(t * .5 + p.rot) * .3;
        p.rot += p.vr * dt;
        if (p.y > H + 10) Object.assign(p, spawn(false));
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillStyle = 'hsla(' + p.hue + ',72%,76%,' + p.a + ')';
        ctx.beginPath();
        ctx.ellipse(0, 0, p.r * 1.9, p.r, 0, 0, 6.283);
        ctx.fill();
        ctx.restore();
      }
    } else if (scene === 'island') {
      for (const p of parts) {
        p.x += Math.sin(t * .3 + p.ph) * .12;
        p.y -= p.sp * dt;
        if (p.y < -10) Object.assign(p, spawn(false));
        ctx.fillStyle = 'rgba(248,242,226,' + p.a + ')';
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, 6.283);
        ctx.fill();
      }
    }

    // 打字涟漪
    for (let i = pulses.length - 1; i >= 0; i--) {
      const q = pulses[i];
      q.age += dt;
      if (q.age > q.ttl) { pulses.splice(i, 1); continue; }
      const k = q.age / q.ttl;
      const r = 6 + k * 46;
      const a = (1 - k) * .4;
      ctx.strokeStyle = 'rgba(255,255,255,' + a.toFixed(3) + ')';
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.arc(q.x, q.y, r, 0, 6.283);
      ctx.stroke();
      if (scene === 'starfield') {
        ctx.fillStyle = 'rgba(255,255,255,' + (a * .8).toFixed(3) + ')';
        for (let j = 0; j < 4; j++) {
          const ang = q.age * 6 + j * 1.57;
          ctx.beginPath();
          ctx.arc(q.x + Math.cos(ang) * r * .6, q.y + Math.sin(ang) * r * .6, 1.2, 0, 6.283);
          ctx.fill();
        }
      }
    }
  }

  function tick(now) {
    raf = requestAnimationFrame(tick);
    if (!last) last = now;
    const dt = Math.min(.05, (now - last) / 1000);
    if (now - (tick.prev || 0) < 33) { last = now; return; }
    tick.prev = now;
    last = now;
    clock += dt;
    draw(dt);
  }

  function start() {
    if (reduced || !ensure()) return;
    if (raf) return;
    last = 0;
    raf = requestAnimationFrame(tick);
  }

  function stop() {
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    if (ctx) ctx.clearRect(0, 0, W, H);
  }

  window.Ambient = {
    set(name) {
      const next = MODES.includes(name) ? name : 'none';
      if (next === scene) return;
      scene = next;
      if (!ensure()) return;
      build();
      if (scene === 'none') stop(); else start();
    },
    pulse() {
      if (scene === 'none' || !ctx || reduced) return;
      const now = Date.now();
      if (now - (pulse.prev || 0) < 90) return;
      pulse.prev = now;
      const paper = document.querySelector('.paper');
      const r = paper ? paper.getBoundingClientRect() : { left: W * .3, right: W * .7, top: H * .3, bottom: H * .8 };
      const x = rnd(r.left + 40, Math.max(r.left + 60, r.right - 40));
      const y = rnd(r.top + 60, Math.max(r.top + 80, Math.min(r.bottom, H - 120)));
      pulses.push({ x, y, age: 0, ttl: .9 });
      if (pulses.length > 12) pulses.shift();
    },
  };
})();
