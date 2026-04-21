/*  rl-common.js — shared helpers used across RansomLook pages
 *  Exposes everything on window.RL so page-specific scripts can
 *  use RL.PALETTE, RL.colorFor(), RL.fmtRel(), etc.
 */
(function () {
  'use strict';

  const PALETTE = [
    '#60a5fa', '#ef4444', '#10b981', '#f59e0b', '#a855f7',
    '#ec4899', '#22d3ee', '#84cc16', '#f97316', '#14b8a6',
    '#e11d48', '#6366f1', '#65a30d', '#d946ef', '#eab308',
    '#0ea5e9', '#be123c', '#7c3aed', '#059669', '#c2410c',
  ];

  function colorFor(s) {
    let h = 0;
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    return PALETTE[h % PALETTE.length];
  }

  function fmtRel(ms) {
    const s = Math.max(0, ms / 1000);
    if (s < 60)     return 'just now';
    if (s < 3600)   return Math.floor(s / 60) + ' min ago';
    if (s < 86400)  return Math.floor(s / 3600) + 'h ago';
    if (s < 172800) return 'yesterday';
    return Math.floor(s / 86400) + 'd ago';
  }

  function renderDates(selector) {
    const now = Date.now();
    for (const $t of document.querySelectorAll(selector + '[data-ts]')) {
      const raw = $t.dataset.ts;
      const iso = raw.includes('T') ? raw : raw.replace(' ', 'T') + 'Z';
      const d = new Date(iso);
      if (isNaN(d)) continue;
      const ms = now - d.getTime();
      const sameDay = new Date(now).toDateString() === d.toDateString();
      const HH = String(d.getHours()).padStart(2, '0');
      const MM = String(d.getMinutes()).padStart(2, '0');
      const primary = sameDay
        ? HH + ':' + MM
        : String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0') + ' ' + HH + ':' + MM;
      $t.innerHTML = '<span class="t-primary">' + primary + '</span><span class="t-rel">' + fmtRel(ms) + '</span>';
    }
  }

  function colorDots() {
    for (const $d of document.querySelectorAll('[data-group-dot]')) {
      $d.style.backgroundColor = colorFor($d.dataset.groupDot);
    }
  }

  window.RL = {
    PALETTE:     PALETTE,
    colorFor:    colorFor,
    fmtRel:      fmtRel,
    renderDates: renderDates,
    colorDots:   colorDots
  };
})();
