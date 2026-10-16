/* Draw the hall plan from the captured design model (racks, busways, feeders, pipes, CDUs).
 * Geometry comes straight from lib/data.js; nothing here is hand-placed. */
(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const mk = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    Object.entries(attrs || {}).forEach(([k, v]) => e.setAttribute(k, v));
    if (parent) parent.appendChild(e);
    return e;
  };
  /**
   * K.plan(svg, plan, {width, height, pad}) → handles
   * Plan units are metres; the view fits the hall plus the electrical rooms.
   */
  K.plan = (svg, plan, o = {}) => {
    const W = o.width || 840, H = o.height || 520, pad = o.pad ?? 16;
    const rooms = Object.values(plan.rooms || {});
    const xs = [0, plan.hall[0], ...rooms.flatMap((r) => [r[0], r[2]])];
    const ys = [0, plan.hall[1], ...rooms.flatMap((r) => [r[1], r[3]])];
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const s = Math.min((W - 2 * pad) / (maxX - minX), (H - 2 * pad) / (maxY - minY));
    const ox = pad + ((W - 2 * pad) - (maxX - minX) * s) / 2 - minX * s;
    const oy = pad + ((H - 2 * pad) - (maxY - minY) * s) / 2 - minY * s;
    const X = (x) => ox + x * s, Y = (y) => oy + y * s;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    const g = (id) => mk('g', { id }, svg);
    const base = g('pl-base'), gRooms = g('pl-rooms'), gRack = g('pl-racks'), gFeed = g('pl-feeders'),
      gBus = g('pl-busways'), gPipe = g('pl-pipes'), gCdu = g('pl-cdus'), gTop = g('pl-top');

    // hall shell, grid columns, rooms
    mk('rect', { x: X(0), y: Y(0), width: plan.hall[0] * s, height: plan.hall[1] * s, rx: 6, fill: '#fbfbfc',
      stroke: '#c9c9d1', 'stroke-width': 2 }, base);
    (plan.columns || []).forEach(([x, y]) =>
      mk('rect', { x: X(x) - 3.5, y: Y(y) - 3.5, width: 7, height: 7, fill: '#c9c9d1' }, base));
    const roomEls = Object.entries(plan.rooms || {}).map(([name, r]) => {
      const gallery = name === 'gallery' || name.startsWith('bay');
      const e = mk('rect', { x: X(r[0]), y: Y(r[1]), width: (r[2] - r[0]) * s, height: (r[3] - r[1]) * s, rx: 4,
        fill: gallery ? 'rgba(29,78,216,0.035)' : '#f4f4f6', stroke: gallery ? '#b8c7f0' : '#c9c9d1',
        'stroke-width': 1.5, 'stroke-dasharray': gallery ? '5 5' : '0' }, gRooms);
      if (!name.startsWith('bay')) {
        const label = name === 'gallery' ? 'CDU gallery' : `Room ${name}`;
        mk('text', { x: X(r[0]) + 8, y: Y(r[1]) + 18, 'font-family': 'Mono K', 'font-size': 13, fill: '#8a8a95' }, gRooms)
          .textContent = label;
      }
      return e;
    });
    // racks: d along x, w along y, centred on (x, y)
    const racks = (plan.racks || []).map(([x, y, w, d]) =>
      mk('rect', { x: X(x - d / 2), y: Y(y - w / 2), width: Math.max(2, d * s), height: Math.max(2, w * s - 1), rx: 1.5,
        fill: '#0b0b0f' }, gRack));
    const line = (pts, attrs, parent) => {
      const d = pts.map(([x, y], i) => `${i ? 'L' : 'M'} ${X(x).toFixed(1)} ${Y(y).toFixed(1)}`).join(' ');
      const e = mk('path', { d, fill: 'none', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', ...attrs }, parent);
      e._len = e.getTotalLength();
      e.style.strokeDasharray = `${e._len} ${e._len}`;
      return e;
    };
    const feeders = (plan.feeders || []).map(([id, pts]) => {
      const e = line(pts, { stroke: '#c2410c', 'stroke-width': 3, opacity: 0.85 }, gFeed);
      e._id = id;
      return e;
    });
    const busways = (plan.busways || []).map(([id, x0, y0, x1, y1]) => {
      const e = line([[x0, y0], [x1, y1]], { stroke: '#c2410c', 'stroke-width': 2.5, opacity: 0.9 }, gBus);
      e._id = id;
      return e;
    });
    const pipes = (plan.pipes || []).map(([id, kind, pts]) => {
      const e = line(pts, { stroke: '#1d4ed8', 'stroke-width': kind === 'header' ? 5 : 3.2 }, gPipe);
      e._id = id;
      return e;
    });
    const cdus = (plan.cdus || []).map(([id, x, y]) =>
      mk('rect', { x: X(x) - 7, y: Y(y) - 7, width: 14, height: 14, rx: 3, fill: '#fff', stroke: '#1d4ed8', 'stroke-width': 2.5 }, gCdu));
    return { svg, s, X, Y, racks, feeders, busways, pipes, cdus, rooms: roomEls, top: gTop, mk: (t, a) => mk(t, a, gTop) };
  };
  /** draw a path to fraction p (0..1) */
  K.drawTo = (e, p) => { e.style.strokeDashoffset = (e._len * (1 - K.clamp(p))).toFixed(2); };
})();
