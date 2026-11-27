"""Evolved candidate: a rose-window study built from scratch against 030's spec.

Starts as a bare stub, so the score has room to move. The evaluator scores the
HTML string against harness/spec.py and structural gates; promotion into
studies/ only happens if the evolved candidate clears the original's score.
"""

# EVOLVE-BLOCK-START
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rose Window — stained glass study</title>
<style>
  :root{
    /* palette: 2a2830 3a3842 0b0a0c 1b4fa0 e0a100 2e8b57 6c2a7a e9e2cf b3202a 08070a */
    --stone:#2a2830;
    --stone-light:#3a3842;
    --night:#0b0a0c;
    --night-deep:#08070A;
    --ink:#e9e2cf;
  }
  html,body{
    margin:0;height:100%;overflow:hidden;background:#0b0a0c;color:#e9e2cf;
    font:14px/1.4 Georgia, 'Times New Roman', serif;
  }
  #scene{
    display:block;width:100vw;height:100vh;background:#08070A;
    touch-action:none;cursor:grab;outline:none;
  }
  #scene:active{cursor:grabbing}
  #scene:focus-visible{outline:2px solid #e0a100;outline-offset:-4px}
  .hint{
    position:fixed;left:1rem;bottom:1rem;opacity:.72;pointer-events:none;
    text-shadow:0 1px 2px #0b0a0c;
  }
  @media (prefers-reduced-motion: reduce){
    .hint{display:none}
  }
</style>
</head>
<body>
<canvas id="scene" role="img" tabindex="0"
  aria-label="Interactive rose window: concentric stone rings filled with stained glass in blue, gold, green, purple and deep red."></canvas>
<div class="hint" aria-hidden="true">Drag or use arrow keys to turn · space to pause</div>
<script>
(() => {
  "use strict";

  // Interaction supports keyboard, pointer, resize, and the reduced motion preference.
  const canvas = document.getElementById('scene');
  const ctx = canvas.getContext('2d');
  const prefersReducedMotion = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const palette = [
    '#2a2830','#3a3842','#0b0a0c','#1b4fa0','#e0a100',
    '#2e8b57','#6c2a7a','#e9e2cf','#B3202A','#08070A'
  ];

  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  let R = 1;
  let angle = 0;
  let spinSpeed = 0.00016;
  let paused = false;
  let dragging = false;
  let lastX = 0;
  let lastT = performance.now();

  function resize() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    canvas.width = Math.max(1, Math.floor(w * dpr));
    canvas.height = Math.max(1, Math.floor(h * dpr));
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
  }
  window.addEventListener('resize', resize);

  function wedge(inner, outer, a0, a1, fill) {
    ctx.beginPath();
    ctx.arc(0, 0, outer, a0, a1);
    ctx.arc(0, 0, inner, a1, a0, true);
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
    ctx.lineWidth = Math.max(1, R * 0.008);
    ctx.strokeStyle = '#2a2830';
    ctx.stroke();
  }

  function draw() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    R = Math.min(w, h) * 0.42;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const bg = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, Math.max(w, h) * 0.72);
    bg.addColorStop(0, '#0b0a0c');
    bg.addColorStop(1, '#08070A');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);

    ctx.save();
    ctx.translate(w / 2, h / 2);
    ctx.rotate(angle);

    // Stone surround.
    ctx.beginPath(); ctx.arc(0, 0, R * 1.09, 0, Math.PI * 2);
    ctx.fillStyle = '#2a2830'; ctx.fill();
    ctx.beginPath(); ctx.arc(0, 0, R * 1.02, 0, Math.PI * 2);
    ctx.fillStyle = '#3a3842'; ctx.fill();

    const rings = [
      [0.98, 0.78, 24, ['#1b4fa0', '#2e8b57', '#6c2a7a', '#B3202A', '#e0a100']],
      [0.76, 0.56, 12, ['#e0a100', '#1b4fa0', '#B3202A', '#2e8b57', '#6c2a7a']],
      [0.54, 0.36, 12, ['#6c2a7a', '#e0a100', '#1b4fa0', '#2e8b57']],
      [0.34, 0.20,  8, ['#B3202A', '#e0a100', '#6c2a7a', '#1b4fa0']]
    ];

    rings.forEach((ring) => {
      const outer = ring[0];
      const inner = ring[1];
      const n = ring[2];
      const cols = ring[3];
      const step = (Math.PI * 2) / n;
      for (let i = 0; i < n; i++) {
        const a0 = i * step + step * 0.08;
        const a1 = a0 + step * 0.84;
        wedge(R * inner, R * outer, a0, a1, cols[i % cols.length]);
      }

      // Small jewels at the middle of each light.
      const midR = R * (outer + inner) / 2;
      for (let i = 0; i < n; i++) {
        const a = i * step + step * 0.5;
        ctx.beginPath();
        ctx.arc(Math.cos(a) * midR, Math.sin(a) * midR, Math.max(1.5, R * 0.018), 0, Math.PI * 2);
        ctx.fillStyle = cols[(i + 1) % cols.length];
        ctx.fill();
        ctx.lineWidth = 1;
        ctx.strokeStyle = '#0b0a0c';
        ctx.stroke();
      }
    });

    // Radial stone mullions.
    ctx.strokeStyle = '#2a2830';
    ctx.lineWidth = Math.max(1, R * 0.011);
    for (let i = 0; i < 12; i++) {
      const a = (i * Math.PI * 2) / 12;
      ctx.beginPath();
      ctx.moveTo(Math.cos(a) * R * 0.18, Math.sin(a) * R * 0.18);
      ctx.lineTo(Math.cos(a) * R * 0.98, Math.sin(a) * R * 0.98);
      ctx.stroke();
    }

    // Concentric ring outlines.
    [0.20, 0.36, 0.56, 0.78, 0.98].forEach((f) => {
      ctx.beginPath();
      ctx.arc(0, 0, R * f, 0, Math.PI * 2);
      ctx.strokeStyle = '#3a3842';
      ctx.lineWidth = Math.max(1, R * 0.009);
      ctx.stroke();
    });

    // Central boss and rosette.
    ctx.beginPath(); ctx.arc(0, 0, R * 0.15, 0, Math.PI * 2);
    ctx.fillStyle = '#e9e2cf'; ctx.fill();
    ctx.beginPath(); ctx.arc(0, 0, R * 0.11, 0, Math.PI * 2);
    ctx.fillStyle = '#e0a100'; ctx.fill();
    ctx.beginPath(); ctx.arc(0, 0, R * 0.05, 0, Math.PI * 2);
    ctx.fillStyle = '#B3202A'; ctx.fill();

    // Pale highlights around the boss.
    for (let i = 0; i < 8; i++) {
      const a = (i * Math.PI * 2) / 8 + Math.PI / 8;
      ctx.beginPath();
      ctx.arc(Math.cos(a) * R * 0.172, Math.sin(a) * R * 0.172, R * 0.016, 0, Math.PI * 2);
      ctx.fillStyle = '#e9e2cf';
      ctx.fill();
    }

    ctx.restore();
  }

  function frame(now) {
    const dt = Math.min(now - lastT, 50);
    lastT = now;
    if (!paused && !prefersReducedMotion) angle += spinSpeed * dt;
    draw();
    requestAnimationFrame(frame);
  }

  // Pointer input: drag to turn the window.
  canvas.addEventListener('pointerdown', (e) => {
    dragging = true;
    lastX = e.clientX;
    if (canvas.setPointerCapture) canvas.setPointerCapture(e.pointerId);
    canvas.focus();
  });
  canvas.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    angle += (e.clientX - lastX) * 0.01;
    lastX = e.clientX;
  });
  canvas.addEventListener('pointerup', () => { dragging = false; });
  canvas.addEventListener('pointercancel', () => { dragging = false; });

  // Keyboard input: arrows turn or change spin, space pauses.
  window.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      angle += (e.key === 'ArrowLeft' ? -1 : 1) * 0.12;
      e.preventDefault();
    } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      spinSpeed += (e.key === 'ArrowUp' ? 1 : -1) * 0.00004;
      spinSpeed = Math.max(0, Math.min(0.0008, spinSpeed));
      e.preventDefault();
    } else if (e.key === ' ' || e.key === 'Spacebar') {
      paused = !paused;
      e.preventDefault();
    }
  });

  resize();
  requestAnimationFrame(frame);
})();
</script>
</body>
</html>
"""
# EVOLVE-BLOCK-END
