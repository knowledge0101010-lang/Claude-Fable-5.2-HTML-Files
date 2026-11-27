#!/usr/bin/env node
// Runtime capture over the Chrome DevTools Protocol.
//   node harness/runtime.mjs [--limit N] [--only 030] [--out reports/runtime.json]
// For every study it records console errors, uncaught exceptions, frame rate,
// desktop/mobile horizontal overflow, canvas/svg counts and a 1440x1000 PNG.
// No npm dependencies: node 22's fetch + WebSocket drive the protocol directly.
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = dirname(HERE);
const CHROME = process.env.CHROME_BIN || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PORT = Number(process.env.CDP_PORT || 9333);
const PROFILE = '/tmp/dsh-fable52-chrome';

const argv = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = argv.indexOf(`--${name}`);
  return i < 0 ? fallback : argv[i + 1];
};
const OUT = opt('out', join(ROOT, 'reports', 'runtime.json'));
const SHOTS = opt('shots', join(ROOT, 'reports', 'shots'));
const LIMIT = Number(opt('limit', 0));
const ONLY = opt('only', '').split(',').filter(Boolean);
const CONCURRENCY = Number(opt('concurrency', 2));
const SETTLE = Number(opt('settle', 1200));
const MEASURE_FPS = argv.includes('--fps');
const PAGE_TIMEOUT = Number(opt('timeout', 30000));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function endpoint(path) {
  const res = await fetch(`http://127.0.0.1:${PORT}${path}`, { method: path.startsWith('/json/new') ? 'PUT' : 'GET' });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

async function launch() {
  // A cold profile costs ~25s on macOS, so the profile is reused across runs;
  // --fresh-profile restores the clean-room behaviour when that matters.
  if (process.env.FRESH_PROFILE === '1') rmSync(PROFILE, { recursive: true, force: true });
  mkdirSync(PROFILE, { recursive: true });
  const child = spawn(CHROME, [
    '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
    '--no-first-run', '--no-default-browser-check', '--disable-extensions',
    '--mute-audio', '--disable-background-timer-throttling',
    '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows',
    `--user-data-dir=${PROFILE}`, `--remote-debugging-port=${PORT}`,
    '--window-size=1440,1000', 'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] });
  let lastErr = '';
  child.stderr.on('data', (b) => { lastErr = b.toString().trim().split('\n').pop() || lastErr; });
  for (let i = 0; i < 100; i++) {
    try { await endpoint('/json/version'); return child; } catch { await sleep(150); }
  }
  child.kill('SIGKILL');
  throw new Error(`chrome did not expose CDP on ${PORT}: ${lastErr}`);
}

function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  const pending = new Map();
  const events = [];
  let seq = 0;
  const ready = new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { res, rej } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result);
    } else if (msg.method) {
      events.push(msg);
    }
  };
  const send = (method, params = {}) => new Promise((res, rej) => {
    const id = ++seq;
    pending.set(id, { res, rej });
    ws.send(JSON.stringify({ id, method, params }));
  });
  return { ws, ready, send, events };
}

const OVERFLOW_PROBE = `(() => {
  const d = document.documentElement, b = document.body;
  const w = Math.max(d.scrollWidth, b ? b.scrollWidth : 0);
  const over = [];
  if (w > innerWidth + 1) {
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.right > innerWidth + 2) {
        over.push((el.tagName + '.' + (el.className || '')).slice(0, 60));
        if (over.length > 5) break;
      }
    }
  }
  return { scrollWidth: w, innerWidth, overflow: w > innerWidth + 1, offenders: over };
})()`;

const FPS_PROBE = `new Promise((resolve) => {
  let n = 0; const t0 = performance.now();
  const step = () => { n++; performance.now() - t0 < 1000 ? requestAnimationFrame(step) : resolve(n); };
  requestAnimationFrame(step);
  setTimeout(() => resolve(n), 1600);
})`;

const METRICS_PROBE = `(() => ({
  title: document.title,
  canvases: document.querySelectorAll('canvas').length,
  svgs: document.querySelectorAll('svg').length,
  buttons: document.querySelectorAll('button,[role=button]').length,
  audio: typeof AudioContext !== 'undefined',
  reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
  scrollHeight: document.documentElement.scrollHeight,
  lang: document.documentElement.lang || '',
  nodes: document.querySelectorAll('*').length,
}))()`;

async function capturePage(page, sem) {
  const release = await sem();
  try {
    return await captureBody(page);
  } finally {
    release();
  }
}

async function captureBody(page) {
  let target;
  try {
    target = await endpoint(`/json/new?${encodeURIComponent(page.url)}`);
  } catch (err) {
    return { ...page.meta, status: 'open-failed', error: String(err) };
  }
  const { ws, ready, send, events } = connect(target.webSocketDebuggerUrl);
  const out = { ...page.meta, status: 'ok', errors: [], warnings: [], timing: {} };
  const mark = (name, t) => { out.timing[name] = Math.round(performance.now() - t); };
  try {
    let t = performance.now();
    await ready;
    mark('open', t); t = performance.now();
    await send('Runtime.enable');
    await send('Log.enable');
    await send('Page.enable');
    mark('enable', t); t = performance.now();
    await sleep(SETTLE);
    const evalJs = async (expression, awaitPromise = false) => {
      const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise });
      if (r.exceptionDetails) throw new Error(r.exceptionDetails.text || 'eval failed');
      return r.result.value;
    };
    out.metrics = await evalJs(METRICS_PROBE);
    mark('metrics', t); t = performance.now();
    if (MEASURE_FPS) {
      out.fps = await evalJs(FPS_PROBE, true);
      mark('fps', t); t = performance.now();
    }
    out.desktop = await evalJs(OVERFLOW_PROBE);
    mark('desktop', t); t = performance.now();
    if (page.meta.file === 'index.html' || page.meta.reimpl) {
      const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
      writeFileSync(join(SHOTS, `${page.meta.stem}.png`), Buffer.from(shot.data, 'base64'));
      out.shot = `shots/${page.meta.stem}.png`;
    }
    await send('Emulation.setDeviceMetricsOverride', { width: 360, height: 780, deviceScaleFactor: 2, mobile: true });
    await sleep(350);
    out.mobile = await evalJs(OVERFLOW_PROBE);
    mark('mobile', t); t = performance.now();
    if (page.meta.stem === 'index') {
      const mshot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
      writeFileSync(join(SHOTS, 'index-mobile.png'), Buffer.from(mshot.data, 'base64'));
      out.mobileShot = 'shots/index-mobile.png';
      mark('mobileShot', t);
    }
  } catch (err) {
    out.status = 'capture-failed';
    out.error = String(err);
  } finally {
    for (const ev of events) {
      if (ev.method === 'Runtime.exceptionThrown') {
        const d = ev.params.exceptionDetails;
        out.errors.push((d.exception && d.exception.description || d.text || 'exception').split('\n')[0].slice(0, 200));
      } else if (ev.method === 'Runtime.consoleAPICalled' && ev.params.type === 'error') {
        out.errors.push((ev.params.args || []).map((a) => a.value ?? a.description ?? '').join(' ').slice(0, 200));
      } else if (ev.method === 'Log.entryAdded' && ev.params.entry.level === 'error') {
        out.errors.push(String(ev.params.entry.text).slice(0, 200));
      }
    }
    out.errors = [...new Set(out.errors)].slice(0, 8);
    try { ws.close(); } catch {}
    try { await fetch(`http://127.0.0.1:${PORT}/json/close/${target.id}`); } catch {}
  }
  return out;
}

function pool(n) {
  let live = 0;
  const queue = [];
  return () => new Promise((resolve) => {
    const run = () => { live++; resolve(() => { live--; const next = queue.shift(); if (next) next(); }); };
    live < n ? run() : queue.push(run);
  });
}

const pages = (await import('node:fs')).readdirSync(ROOT)
  .filter((f) => /^\d{3}-.*\.html$/.test(f))
  .sort()
  .filter((f) => !ONLY.length || ONLY.some((o) => f.includes(o)))
  .slice(0, LIMIT || undefined)
  .map((f) => ({ url: `file://${join(ROOT, f)}`, meta: { file: f, stem: f.replace(/\.html$/, ''), number: f.slice(0, 3) } }));

const fs = await import('node:fs');
const derived = (fs.existsSync(join(ROOT, 'studies')) ? fs.readdirSync(join(ROOT, 'studies'), { withFileTypes: true }) : [])
  .filter((d) => d.isDirectory() && fs.existsSync(join(ROOT, 'studies', d.name, 'index.html')))
  .map((d) => ({
    url: `file://${join(ROOT, 'studies', d.name, 'index.html')}`,
    meta: { file: `studies/${d.name}/index.html`, stem: `derived-${d.name}`, number: d.name.slice(0, 3), reimpl: true },
  }))
  .filter((p) => !ONLY.length || ONLY.some((o) => p.meta.file.includes(o)));
const gallery = { url: `file://${join(ROOT, 'index.html')}`, meta: { file: 'index.html', stem: 'index', number: '000' } };
const targets = [gallery, ...pages, ...derived];

mkdirSync(SHOTS, { recursive: true });
const withTimeout = (meta, p, ms = PAGE_TIMEOUT) => {
  let timer;
  const guard = new Promise((res) => { timer = setTimeout(() => res({ ...meta, status: 'timeout' }), ms); });
  return Promise.race([p, guard]).finally(() => clearTimeout(timer));
};
const CHUNK = Number(opt('chunk', 24));
const results = [];
let launchMs = 0;
for (let offset = 0; offset < targets.length; offset += CHUNK) {
  const slice = targets.slice(offset, offset + CHUNK);
  const tLaunch = performance.now();
  const child = await launch();
  launchMs += Math.round(performance.now() - tLaunch);
  const sem = pool(CONCURRENCY);
  try {
    const done = await Promise.all(slice.map((t) => withTimeout(t.meta, capturePage(t, sem))));
    results.push(...done);
    const retry = done.filter((r) => r.status !== 'ok');
    if (retry.length) {
      console.error(`chunk ${offset / CHUNK + 1}: retrying ${retry.length} page(s) sequentially`);
      for (const bad of retry) {
        const t = slice.find((x) => x.meta.file === bad.file);
        if (!t) continue;
        const again = await withTimeout(t.meta, capturePage(t, sem), PAGE_TIMEOUT * 2);
        const at = results.findIndex((r) => r.file === bad.file);
        if (at >= 0) results[at] = again.status === 'ok' ? again : { ...again, firstFailure: bad.status };
      }
    }
  } finally {
    child.kill('SIGKILL');
    await sleep(300);
  }
}

const ok = results.filter((r) => r.status === 'ok');
const fps = ok.map((r) => r.fps).filter((n) => typeof n === 'number');
const q = (arr, p) => arr.length ? arr.slice().sort((a, b) => a - b)[Math.floor(p * (arr.length - 1))] : null;
const report = {
  capturedAt: new Date().toISOString(),
  pages: results,
  summary: {
    chrome_launch_ms: launchMs,
    chunks: Math.ceil(targets.length / CHUNK),
    targets: results.length,
    captured: ok.length,
    failed: results.length - ok.length,
    console_errors: ok.filter((r) => r.errors.length).length,
    desktop_overflow: ok.filter((r) => r.desktop && r.desktop.overflow).length,
    mobile_overflow: ok.filter((r) => r.mobile && r.mobile.overflow).length,
    fps_min: fps.length ? Math.min(...fps) : null,
    fps_p50: q(fps, 0.5),
    fps_mean: fps.length ? Math.round(fps.reduce((a, b) => a + b, 0) / fps.length) : null,
    slow_pages: ok.filter((r) => typeof r.fps === 'number' && r.fps < 30).map((r) => r.file),
    erroring_pages: ok.filter((r) => r.errors.length).map((r) => ({ file: r.file, errors: r.errors })),
    mobile_overflow_pages: ok.filter((r) => r.mobile && r.mobile.overflow).map((r) => ({ file: r.file, offenders: r.mobile.offenders })),
    desktop_overflow_pages: ok.filter((r) => r.desktop && r.desktop.overflow).map((r) => r.file),
    failed_pages: results.filter((r) => r.status !== 'ok').map((r) => ({ file: r.file, status: r.status })),
  },
};
mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 1));
console.log(JSON.stringify(report.summary, null, 1));
console.log(`wrote ${OUT}`);
