/* Kirchhoff video scenes: a tiny deterministic timeline.
 *
 * A scene is a pure function of time: render(t) sets every style from t alone (no CSS transitions,
 * no requestAnimationFrame state, no clocks, no Math.random). render.py calls
 * window.__scene.setTime(t) for t = i / fps and screenshots each frame, so a re-run gives the same
 * pixels. Open a scene in a browser with ?play to preview it in real time, or ?t=3.5 to hold a frame.
 */
(function () {
  'use strict';
  const K = {};
  K.W = 1920;
  K.H = 1080;
  K.FPS = 30;

  K.clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  K.lerp = (a, b, p) => a + (b - a) * p;
  K.ease = {
    lin: (x) => x,
    out2: (x) => 1 - (1 - x) * (1 - x),
    out3: (x) => 1 - Math.pow(1 - x, 3),
    out4: (x) => 1 - Math.pow(1 - x, 4),
    out5: (x) => 1 - Math.pow(1 - x, 5),
    in2: (x) => x * x,
    in3: (x) => x * x * x,
    inOut3: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
    inOut2: (x) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2),
    outExpo: (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x)),
    outBack: (x) => {
      const c1 = 1.3, c3 = c1 + 1;
      return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
    },
  };
  /** progress of a segment that starts at `start` and lasts `dur`, eased */
  K.p = (t, start, dur, e = K.ease.out4) => e(K.clamp((t - start) / dur));
  /** in → hold → out envelope (1 while visible) */
  K.inout = (t, a, b, din = 0.5, dout = 0.4, e = K.ease.out4) =>
    Math.min(K.p(t, a, din, e), 1 - K.p(t, b - dout, dout, K.ease.in2));

  /** seeded PRNG (mulberry32) for any jitter that must repeat */
  K.rand = (seed) => () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let r = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };

  K.$ = (sel, root = document) => root.querySelector(sel);
  K.$$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  K.el = (tag, cls, html, parent) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined && html !== null) e.innerHTML = html;
    if (parent) parent.appendChild(e);
    return e;
  };
  K.esc = (s) => String(s ?? '–').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

  /** split an element's text into word spans (keeps inner <b>/<em> as single words) */
  K.words = (el) => {
    const parts = [];
    const nodes = Array.from(el.childNodes);
    el.innerHTML = '';
    nodes.forEach((n) => {
      if (n.nodeType === 3) {
        n.textContent.split(/(\s+)/).forEach((w) => {
          if (!w) return;
          if (/^\s+$/.test(w)) { el.appendChild(document.createTextNode(w)); return; }
          const s = K.el('span', 'word', K.esc(w), el);
          parts.push(s);
        });
      } else {
        const s = K.el('span', 'word', '', el);
        s.appendChild(n);
        parts.push(s);
      }
    });
    return parts;
  };

  /** the house reveal: rise + fade + de-blur */
  K.rise = (el, p, o = {}) => {
    const y = o.y ?? 28, blur = o.blur ?? 10, x = o.x ?? 0, s0 = o.s ?? 1;
    el.style.opacity = K.clamp(p).toFixed(4);
    const s = K.lerp(s0, 1, p);
    el.style.transform = `translate3d(${((1 - p) * x).toFixed(2)}px, ${((1 - p) * y).toFixed(2)}px, 0) scale(${s.toFixed(4)})`;
    el.style.filter = blur && p < 1 ? `blur(${((1 - p) * blur).toFixed(2)}px)` : 'none';
  };
  K.fade = (el, p) => { el.style.opacity = K.clamp(p).toFixed(4); };
  K.tf = (el, { x = 0, y = 0, s = 1, r = 0, o } = {}) => {
    el.style.transform = `translate3d(${x.toFixed(2)}px, ${y.toFixed(2)}px, 0) scale(${s.toFixed(4)}) rotate(${r.toFixed(3)}deg)`;
    if (o !== undefined) el.style.opacity = K.clamp(o).toFixed(4);
  };
  /** staggered word reveal */
  K.stagger = (els, t, start, step, dur, opts) => {
    els.forEach((e, i) => K.rise(e, K.p(t, start + i * step, dur), opts));
  };
  /** count a number up; keeps the final string exactly as the data wrote it */
  K.count = (finalStr, p) => {
    const m = String(finalStr).match(/^([^\d−-]*)([−-]?[\d,]*\.?\d+)(.*)$/);
    if (!m || p >= 1) return String(finalStr);
    const raw = parseFloat(m[2].replace(/,/g, '').replace('−', '-'));
    const dec = (m[2].split('.')[1] || '').length;
    const v = raw * p;
    const s = v.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
    return m[1] + s + m[3];
  };

  K.logo = (name) => `assets/logos/${name}.svg`;
  K.mark = (size = 40, dark = true) =>
    `<svg class="node-mark" width="${size}" height="${size}" viewBox="0 0 32 32" aria-hidden="true">` +
    `<rect width="32" height="32" rx="8" fill="${dark ? '#0b0b0f' : '#f4f4f5'}"/>` +
    `<g fill="none" stroke="${dark ? '#ffffff' : '#0b0b0f'}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round">` +
    `<path d="M10 7v18"/><path d="M22.5 7.5 13.5 16l9 8.5"/></g><circle cx="13.5" cy="16" r="3" fill="#0ea5e9"/></svg>`;
  K.wordmark = (parent) =>
    K.el('div', 'wordmark-sm', `${K.mark(30)}<span>Kirchhoff</span>`, parent);
  K.sandbox = (text = 'connector · sandbox') => `<span class="sandbox">${K.esc(text)}</span>`;

  K.D = window.KDATA || {};

  /** wait for fonts and every <img> before the first frame */
  K.ready = async () => {
    if (document.fonts) {
      await Promise.all(['400 40px "Inter K"', '650 40px "Inter K"', '500 20px "Mono K"']
        .map((f) => document.fonts.load(f).catch(() => {})));
      await document.fonts.ready;
    }
    const imgs = K.$$('img');
    await Promise.all(imgs.map((im) => (im.complete && im.naturalWidth ? Promise.resolve() : im.decode().catch(() => {}))));
    await Promise.all(imgs.map((im) => im.decode().catch(() => {})));
  };

  /**
   * Register the scene. render(t) must set every animated style from t alone.
   * hero: the time render.py uses for the preview still.
   */
  K.scene = (def) => {
    const fps = def.fps || K.FPS;
    let duration = def.duration;
    const api = {
      fps,
      get duration() { return duration; },
      set duration(v) { duration = v; },
      hero: def.hero ?? duration * 0.6,
      setTime: async (t) => {
        const r = def.render(K.clamp(t, 0, duration));
        if (r && typeof r.then === 'function') await r;
      },
    };
    window.__scene = api;
    window.__sceneReady = (async () => {
      await K.ready(); // fonts first, so setup() can measure laid-out text
      if (def.setup) await def.setup();
      await K.ready();
      await api.setTime(0);
      return { duration: api.duration, fps, hero: api.hero };
    })();
    // Browser preview helpers (not used by the renderer).
    const q = new URLSearchParams(location.search);
    if (!q.has('render')) {
      window.__sceneReady.then(() => {
        if (q.has('t')) { api.setTime(parseFloat(q.get('t'))); return; }
        if (q.has('play')) {
          const t0 = performance.now();
          const loop = (now) => {
            api.setTime(((now - t0) / 1000) % (api.duration + 0.8));
            requestAnimationFrame(loop);
          };
          requestAnimationFrame(loop);
        } else {
          api.setTime(api.hero);
        }
      });
    }
    return api;
  };

  window.K = K;
})();
