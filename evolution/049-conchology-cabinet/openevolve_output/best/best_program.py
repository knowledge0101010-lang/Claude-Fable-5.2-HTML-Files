"""Evolved candidate for 049-conchology-cabinet — built from scratch against its spec."""
# EVOLVE-BLOCK-START
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A Cabinet of Computed Shells</title>
<style>
  html, body { margin: 0; height: 100%; overflow: hidden; background: #fbf5ec; color: #2d2424;
    font: 14px/1.45 ui-serif, Georgia, "Times New Roman", serif; }
  #scene { display: block; width: 100vw; height: 100vh; touch-action: none; background: #fbf5ec; }
  .grain { position: fixed; inset: 0; pointer-events: none; opacity: 0.3;
    mix-blend-mode: multiply; filter: url(#cabinet-grain); }
  .hud { position: fixed; left: 16px; bottom: 14px; padding: 9px 13px; border-radius: 10px;
    background: rgba(251, 245, 236, 0.86); border: 1px solid #d9a38f; max-width: min(48ch, 82vw); }
  .hud b { color: #6a3b2b; letter-spacing: 0.02em; }
  .hud kbd { background: #f3e9e2; border: 1px solid #7c5c4d; border-radius: 4px;
    padding: 0 4px; font: inherit; font-size: 12px; }
  #status { color: #7c5c4d; }
  @media (prefers-reduced-motion: reduce) { .grain { opacity: 0.15; } }
</style>
</head>
<body>
<canvas id="scene" role="img" aria-label="A cabinet of computed logarithmic spiral shells"></canvas>
<div class="grain" id="grain" aria-hidden="true"></div>
<div class="hud">
  <b>A Cabinet of Computed Shells</b><br>
  <span id="status" role="status" aria-live="polite">warming the cabinet</span><br>
  <kbd>&larr;</kbd><kbd>&rarr;</kbd> tightness &middot; <kbd>&uarr;</kbd><kbd>&darr;</kbd> whorls
  &middot; <kbd>space</kbd> add &middot; <kbd>g</kbd> grain &middot; <kbd>r</kbd> reset
</div>
<svg width="0" height="0" aria-hidden="true" focusable="false" style="position:absolute">
  <filter id="cabinet-grain" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="3" seed="7" result="noise"/>
    <feColorMatrix in="noise" type="saturate" values="0" result="flat"/>
    <feComponentTransfer in="flat"><feFuncA type="linear" slope="0.4"/></feComponentTransfer>
  </filter>
</svg>
<script>
(function () {
  'use strict';

  var PALETTE = ['#f3e9e2', '#d9a38f', '#7c5c4d', '#2d2424', '#9fb8b3', '#fbf5ec', '#6a3b2b'];
  var RGB = new Uint8ClampedArray(21);
  for (var i = 0; i < 7; i++) {
    RGB[i * 3] = parseInt(PALETTE[i].substr(1, 2), 16);
    RGB[i * 3 + 1] = parseInt(PALETTE[i].substr(3, 2), 16);
    RGB[i * 3 + 2] = parseInt(PALETTE[i].substr(5, 2), 16);
  }
  var ORDER = [3, 6, 2, 1, 4, 0, 5];   // nucleus -> lip
  var STEPS = 120;
  var samples = new Float32Array((STEPS + 1) * 2);

  var canvas = document.getElementById('scene');
  var ctx = canvas.getContext('2d', { alpha: false });
  var statusEl = document.getElementById('status');
  var grainEl = document.getElementById('grain');
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');

  var W = 1, H = 1, DPR = 1;
  var whorls = 3.2, tightness = 0.17;
  var clock = 0, raf = 0, last = 0;
  var seed = 20240217;

  function rnd() {
    seed = (seed * 16807) % 2147483647;
    return seed / 2147483647;
  }

  function colorAt(t) {
    if (t < 0) t = 0; else if (t > 0.999) t = 0.999;
    var f = t * 6, k = Math.floor(f), m = f - k;
    var a = ORDER[k] * 3, b = ORDER[k + 1] * 3;
    return 'rgb(' + Math.round(RGB[a] + (RGB[b] - RGB[a]) * m) + ',' +
      Math.round(RGB[a + 1] + (RGB[b + 1] - RGB[a + 1]) * m) + ',' +
      Math.round(RGB[a + 2] + (RGB[b + 2] - RGB[a + 2]) * m) + ')';
  }

  var shells = [], MAX = 18;

  function addShell(x, y) {
    shells.push({
      x: x, y: y,
      r: 32 + rnd() * 86,
      rot: rnd() * 6.2832,
      spin: (rnd() - 0.5) * 0.22,
      mix: rnd(),
      phase: rnd() * 6.2832,
      ink: rnd()
    });
    while (shells.length > MAX) shells.shift();
    paint();
  }

  function drawShell(s) {
    var time = reduce.matches ? 0 : clock;
    var turns = Math.max(1.2, whorls + Math.sin(time * 0.5 + s.phase) * 0.22);
    var b = tightness * (0.55 + 0.9 * s.ink);
    var total = turns * 6.2832;
    var i, u, th, r, x, y, px, py, dx, dy, d, rr;

    for (i = 0; i <= STEPS; i++) {
      u = i / STEPS;
      th = total * u;
      r = s.r * Math.exp(b * (th - total));
      samples[i * 2] = Math.cos(th) * r;
      samples[i * 2 + 1] = Math.sin(th) * r;
    }

    ctx.save();
    ctx.translate(s.x, s.y);
    ctx.rotate(s.rot + (reduce.matches ? 0 : time * s.spin));
    ctx.lineCap = 'round';

    ctx.lineWidth = 1;
    for (i = 8; i < STEPS; i += 9) {
      x = samples[i * 2]; y = samples[i * 2 + 1];
      px = samples[(i - 8) * 2]; py = samples[(i - 8) * 2 + 1];
      dx = x - px; dy = y - py; d = Math.sqrt(dx * dx + dy * dy) || 1;
      ctx.strokeStyle = colorAt(0.3 + 0.4 * s.mix);
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + dx / d * 7, y + dy / d * 7);
      ctx.stroke();
    }

    for (i = 1; i <= STEPS; i++) {
      x = samples[i * 2]; y = samples[i * 2 + 1];
      px = samples[(i - 1) * 2]; py = samples[(i - 1) * 2 + 1];
      rr = Math.sqrt(x * x + y * y);
      ctx.strokeStyle = colorAt(0.04 + 0.36 * s.mix + 0.34 * (i / STEPS));
      ctx.lineWidth = Math.max(0.7, rr * 0.3);
      ctx.beginPath();
      ctx.moveTo(px, py);
      ctx.lineTo(x, y);
      ctx.stroke();
    }
    ctx.restore();
  }

  function paint() {
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.fillStyle = '#fbf5ec';
    ctx.fillRect(0, 0, W, H);

    ctx.strokeStyle = '#d9a38f';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, H * 0.79);
    ctx.lineTo(W, H * 0.79);
    ctx.stroke();

    for (var i = 0; i < shells.length; i++) drawShell(shells[i]);
  }

  function updateStatus() {
    statusEl.textContent = 'tightness ' + tightness.toFixed(3) +
      ' \u00b7 whorls ' + whorls.toFixed(1) + ' \u00b7 ' + shells.length + ' shells';
  }

  function reset() {
    shells.length = 0;
    seed = 20240217;
    for (var i = 0; i < 6; i++) {
      addShell(W * (0.16 + 0.68 * (i / 5)), H * (0.52 + 0.15 * Math.sin(i * 1.7)));
    }
    updateStatus();
  }

  function frame(now) {
    raf = 0;
    if (reduce.matches) return;
    if (!last) last = now;
    clock += Math.min(0.05, (now - last) / 1000);
    last = now;
    paint();
    raf = requestAnimationFrame(frame);
  }

  function start() {
    if (raf || reduce.matches) return;
    last = 0;
    raf = requestAnimationFrame(frame);
  }

  function onMotion() {
    if (reduce.matches) {
      if (raf) { cancelAnimationFrame(raf); raf = 0; }
      clock = 0;
      paint();
    } else {
      start();
    }
  }

  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    W = Math.max(1, canvas.clientWidth);
    H = Math.max(1, canvas.clientHeight);
    canvas.width = Math.round(W * DPR);
    canvas.height = Math.round(H * DPR);
    paint();
  }

  window.addEventListener('resize', resize);

  window.addEventListener('keydown', function (e) {
    var k = e.key;
    if (k === 'ArrowLeft') tightness = Math.max(0.05, tightness - 0.015);
    else if (k === 'ArrowRight') tightness = Math.min(0.4, tightness + 0.015);
    else if (k === 'ArrowUp') whorls = Math.min(6, whorls + 0.2);
    else if (k === 'ArrowDown') whorls = Math.max(1.2, whorls - 0.2);
    else if (k === ' ' || k === 'Spacebar') addShell(W * (0.14 + rnd() * 0.72), H * (0.4 + rnd() * 0.36));
    else if (k === 'r' || k === 'R') reset();
    else if (k === 'g' || k === 'G') grainEl.style.display = grainEl.style.display === 'none' ? '' : 'none';
    else return;
    e.preventDefault();
    updateStatus();
    paint();
  });

  var dragAt = 0;
  canvas.addEventListener('pointerdown', function (e) {
    if (canvas.setPointerCapture) canvas.setPointerCapture(e.pointerId);
    addShell(e.clientX, e.clientY);
    updateStatus();
  });
  canvas.addEventListener('pointermove', function (e) {
    if (!e.buttons) return;
    var t = e.timeStamp || performance.now();
    if (t - dragAt < 150) return;
    dragAt = t;
    addShell(e.clientX, e.clientY);
    updateStatus();
  });

  if (reduce.addEventListener) reduce.addEventListener('change', onMotion);
  else if (reduce.addListener) reduce.addListener(onMotion);

  resize();
  reset();
  start();
})();
</script>
</body>
</html>
"""
# EVOLVE-BLOCK-END
