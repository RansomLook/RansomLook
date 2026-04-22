document.addEventListener('DOMContentLoaded', () => {
  /* ====================================================================
   *  DOM refs
   * ==================================================================== */
  const $ = id => document.getElementById(id);
  const $period  = $('period'),   $custom  = $('custom-range');
  const $from    = $('from'),     $to      = $('to');
  const $bucket  = $('bucket'),   $roll    = $('roll');
  const $topn    = $('topn'),     $norm    = $('normalize');
  const $search  = $('group-search'), $chips = $('group-list');
  const $count   = $('picker-count');
  const $status  = $('stats-status');
  const $btnAll  = $('select-all'),  $btnNone  = $('select-none');
  const $refresh = $('refresh'),     $csv      = $('exportcsv'), $share = $('shareurl');

  // Modal
  const $modal     = $('chart-modal');
  const $modalPlot = $('chart-modal-plot');

  /* ====================================================================
   *  State
   * ==================================================================== */
  const state = {
    raw: [],                // [{g, ts}]
    filtered: [],           // after group selection
    allGroups: new Set(),
    selected:  new Set()
  };

  /* ====================================================================
   *  Helpers
   * ==================================================================== */
  const fmtDay  = d => d.toISOString().slice(0, 10);
  const toUTC   = d => new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));

  function weekKey(d) {
    const dt  = toUTC(d);
    const day = dt.getUTCDay() || 7;
    dt.setUTCDate(dt.getUTCDate() - day + 1);
    return fmtDay(dt);
  }

  function rolling(arr, w) {
    if (!w || w <= 1) return arr;
    const out = [];
    let sum = 0;
    for (let i = 0; i < arr.length; i++) {
      sum += arr[i];
      if (i >= w) sum -= arr[i - w];
      out.push(i >= w - 1 ? +(sum / w).toFixed(3) : null);
    }
    return out;
  }

  /* Deep-merge Plotly layout: base + extra, with nested object merge for axes */
  function baseLayout(extra) {
    const css = (v, fb) => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || fb;
    const text   = css('--text', '#e5e7eb');
    const border = css('--border', 'rgba(255,255,255,.12)');
    const paper  = css('--fg', css('--card', '#111827'));
    const grid   = border.replace(/[\d.]+\)$/, '0.35)');

    const axis = { tickfont:{color:text}, titlefont:{color:text}, gridcolor:grid, zerolinecolor:border };
    const base = {
      font:       { family:'Roboto,system-ui,sans-serif', color:text },
      paper_bgcolor: paper,
      plot_bgcolor:  paper,
      legend:     { font:{color:text} },
      hoverlabel: { font:{color:text}, bordercolor:border, bgcolor:'rgba(0,0,0,.65)' },
      xaxis: {...axis},
      yaxis: {...axis}
    };

    if (!extra) return base;

    // Deep merge: for xaxis/yaxis/legend/font, merge nested props instead of replacing
    const out = {...base};
    for (const [k, v] of Object.entries(extra)) {
      if (v && typeof v === 'object' && !Array.isArray(v) && base[k] && typeof base[k] === 'object') {
        out[k] = {...base[k], ...v};
        // Also merge nested objects one level deeper (e.g. xaxis.tickfont)
        for (const [sk, sv] of Object.entries(base[k])) {
          if (sv && typeof sv === 'object' && !Array.isArray(sv) && v[sk] && typeof v[sk] === 'object') {
            out[k][sk] = {...sv, ...v[sk]};
          }
        }
      } else {
        out[k] = v;
      }
    }
    return out;
  }

  /* Sort legend traces by total descending */
  function orderLegend(traces, desc) {
    traces.forEach(t => {
      const total = (t.y || []).reduce((s, v) => s + (Number.isFinite(v) ? v : 0), 0);
      t.legendrank = desc ? -total : total;
    });
  }

  /* ====================================================================
   *  URL <-> UI sync
   * ==================================================================== */
  function readURL() {
    const p = Object.fromEntries(new URL(location.href).searchParams);
    if (p.days)   $period.value = p.days;
    if (p.from)   { $period.value = 'custom'; $from.value = p.from; }
    if (p.to)     $to.value = p.to;
    if (p.bucket) $bucket.value = p.bucket;
    if (p.roll)   $roll.value   = p.roll;
    if (p.topn)   $topn.value   = p.topn;
    if (p.norm)   $norm.checked = (p.norm === '1');
    toggleCustom();
    return p;
  }

  function writeURL() {
    const u = new URL(location.href);
    const s = u.searchParams;
    const set = (k, v) => { if (v && v !== '0') s.set(k, v); else s.delete(k); };

    if ($period.value === 'custom') {
      s.delete('days'); set('from', $from.value); set('to', $to.value);
    } else {
      set('days', $period.value); s.delete('from'); s.delete('to');
    }
    set('bucket', $bucket.value);
    set('roll',   $roll.value);
    set('topn',   $topn.value);
    set('norm',   $norm.checked ? '1' : '');
    set('groups', [...state.selected].join(','));
    history.replaceState(null, '', u.toString());
  }

  /* ====================================================================
   *  Data fetching
   * ==================================================================== */
  async function fetchPosts() {
    const p = new URLSearchParams();
    if ($period.value === 'custom' && $from.value && $to.value) {
      p.set('from', $from.value);
      p.set('to',   $to.value);
    } else {
      p.set('days', $period.value);
    }

    const res = await fetch('/api/posts?' + p, { headers: { Accept: 'application/json' } });
    if (!res.ok) throw new Error('fetch failed: ' + res.status);
    const json = await res.json();
    const posts = json.posts || json.data || json || [];

    state.raw = posts
      .map(x => ({ g: x.group_name, ts: x.discovered }))
      .filter(x => x.ts);

    // Fetch the first-post-ever timestamp per group so we can tell truly
    // new groups (first post inside the window) apart from groups merely
    // resuming activity. Best-effort — if the endpoint is unavailable we
    // just won't flag anything as NEW (safer than a false positive).
    if (!state.groupFirstSeen) {
      try {
        const r = await fetch('/api/group-first-seen', { headers: { Accept: 'application/json' } });
        state.groupFirstSeen = r.ok ? await r.json() : {};
      } catch {
        state.groupFirstSeen = {};
      }
    }
  }

  /* ====================================================================
   *  Group picker
   * ==================================================================== */
  function rebuildGroups(urlGroups) {
    const prev = state.selected;
    state.allGroups = new Set(state.raw.map(x => x.g));

    if (urlGroups) {
      const want = new Set(urlGroups.split(',').filter(Boolean));
      state.selected = new Set([...state.allGroups].filter(g => want.has(g)));
    } else if (prev.size) {
      state.selected = new Set([...state.allGroups].filter(g => prev.has(g)));
    } else {
      state.selected = new Set(state.allGroups);
    }
    renderChips();
  }

  function renderChips() {
    const q = ($search.value || '').trim().toLowerCase();
    $chips.innerHTML = '';

    const sorted = [...state.allGroups].sort((a, b) => a.localeCompare(b));
    for (const g of sorted) {
      if (q && !g.toLowerCase().includes(q)) continue;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-secondary' + (state.selected.has(g) ? ' active' : '');
      btn.textContent = g;
      btn.addEventListener('click', () => {
        if (state.selected.has(g)) state.selected.delete(g); else state.selected.add(g);
        btn.classList.toggle('active');
        updateCharts();
        writeURL();
      });
      $chips.appendChild(btn);
    }
    $count.textContent = '(' + state.selected.size + '/' + state.allGroups.size + ' selected)';
  }

  $btnAll.addEventListener('click', () => {
    state.selected = new Set(state.allGroups);
    renderChips(); updateCharts(); writeURL();
  });
  $btnNone.addEventListener('click', () => {
    state.selected.clear();
    renderChips(); updateCharts(); writeURL();
  });
  $search.addEventListener('input', renderChips);

  /* ====================================================================
   *  Filtering & bucketing
   * ==================================================================== */
  function applyFilters() {
    const sel = state.selected;
    state.filtered = state.raw
      .filter(x => sel.size === 0 || sel.has(x.g))
      .map(x => ({ g: x.g, ts: new Date(x.ts) }))
      .filter(x => !isNaN(x.ts));
  }

  function bucketize() {
    const bk = $bucket.value;
    const keyOf = d => bk === 'hour' ? d.toISOString().slice(0, 13) + ':00'
                     : bk === 'week' ? weekKey(d)
                     : fmtDay(d);

    const groups  = [...new Set(state.filtered.map(r => r.g))].sort();
    const counts  = new Map();
    const timeSet = new Set();

    for (const r of state.filtered) {
      const k = keyOf(r.ts);
      timeSet.add(k);
      const mk = k + '|' + r.g;
      counts.set(mk, (counts.get(mk) || 0) + 1);
    }

    const keys   = [...timeSet].sort();
    const matrix = groups.map(g => keys.map(k => counts.get(k + '|' + g) || 0));

    // Rolling average
    const w = +$roll.value || 0;
    if (w > 0 && bk !== 'week') {
      for (let i = 0; i < matrix.length; i++) matrix[i] = rolling(matrix[i], w);
    }

    // Normalize %
    if ($norm.checked) {
      for (let t = 0; t < keys.length; t++) {
        let col = 0;
        for (let r = 0; r < matrix.length; r++) col += (matrix[r][t] || 0);
        if (col > 0) {
          for (let r = 0; r < matrix.length; r++) matrix[r][t] = +((matrix[r][t] || 0) * 100 / col).toFixed(2);
        }
      }
    }

    return { keys, groups, matrix };
  }

  function countsByGroup() {
    const c = new Map();
    for (const r of state.filtered) c.set(r.g, (c.get(r.g) || 0) + 1);
    return [...c.entries()]
      .map(([group, count]) => ({ group, count }))
      .sort((a, b) => b.count - a.count);
  }

  /* ====================================================================
   *  Status bar
   * ==================================================================== */
  function updateStatus(counts, topN) {
    if (!$status) return;
    const total  = state.filtered.length;
    const nGroups = counts.length;
    const shown  = topN > 0 ? Math.min(topN, nGroups) : nGroups;

    if (topN > 0 && nGroups > topN) {
      const topNames = counts.slice(0, topN).map(d => d.group).join(', ');
      $status.textContent = 'Showing top ' + shown + ' groups by post count (out of ' + nGroups + ') — ' + total + ' posts total. Groups: ' + topNames;
    } else {
      $status.textContent = 'Showing all ' + nGroups + ' groups — ' + total + ' posts total.';
    }
  }

  /* ====================================================================
   *  Color palette — uses shared RL.PALETTE / RL.colorFor from rl-common.js
   * ==================================================================== */
  const PALETTE = RL.PALETTE;
  function paletteIndex(s) {
    let h = 0;
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    return h % PALETTE.length;
  }
  const hexToRgba = (hex, a) => {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  };

  /* Build a "visible set" color map where every shown group has a
     distinct palette colour, even when their hashes collide.
     Each call returns a Map<groupName, hex>. */
  let _visibleColors = new Map();
  function assignVisibleColors(groups) {
    const map = new Map();
    const used = new Set();
    for (const g of groups) {
      let i = paletteIndex(g);
      let tries = 0;
      while (used.has(i) && tries < PALETTE.length) {
        i = (i + 1) % PALETTE.length;
        tries++;
      }
      used.add(i);
      map.set(g, PALETTE[i]);
    }
    _visibleColors = map;
    return map;
  }
  const colorFor      = (g) => _visibleColors.get(g) || PALETTE[paletteIndex(g)];
  const colorForAlpha = (g, a) => hexToRgba(colorFor(g), a);

  /* ====================================================================
   *  Summary + movers
   * ==================================================================== */
  const $kpi = (name) => document.querySelector(`[data-kpi="${name}"]`);
  const $movers = document.getElementById('movers-list');

  function computeSummary() {
    const total = state.filtered.length;
    const counts = new Map();
    for (const r of state.filtered) counts.set(r.g, (counts.get(r.g) || 0) + 1);
    const activeGroups = counts.size;

    let topGroup = null, topCount = 0;
    for (const [g, c] of counts) if (c > topCount) { topGroup = g; topCount = c; }
    const topShare = total > 0 ? ((topCount / total) * 100).toFixed(1) : '0';

    // Split-half trend (2nd half vs 1st half of the current window)
    const sorted = [...state.filtered].sort((a, b) => a.ts - b.ts);
    const mid = Math.floor(sorted.length / 2);
    const first  = sorted.slice(0, mid);
    const second = sorted.slice(mid);
    const firstN = first.length, secondN = second.length;
    const trendPct = firstN > 0 ? ((secondN - firstN) / firstN) * 100 : null;

    // First-post-ever per group — fetched once from /api/group-first-seen
    // so we can reliably flag truly new groups (not just ones that resumed
    // activity after a lull). Falls back to never flagging NEW if the
    // endpoint is unreachable.
    const globalFirst = state.groupFirstSeen || {};
    const windowStart = sorted.length > 0 ? sorted[0].ts : null;

    // Per-group movers
    const firstG = new Map(), secondG = new Map();
    for (const r of first)  firstG.set(r.g,  (firstG.get(r.g)  || 0) + 1);
    for (const r of second) secondG.set(r.g, (secondG.get(r.g) || 0) + 1);
    const all = new Set([...firstG.keys(), ...secondG.keys()]);
    const movers = [];
    for (const g of all) {
      const p = firstG.get(g) || 0;
      const c = secondG.get(g) || 0;
      const raw = c - p;
      const pct = p > 0 ? (raw / p) * 100 : null;
      // Truly new: group's first ever post (across the whole DB) is at or
      // after the start of the current window. Without this global source
      // we cannot distinguish "new group" from "group that resumed", so
      // we stay silent rather than mislabel.
      let trulyNew = false;
      if (windowStart !== null && globalFirst[g]) {
        const fs = new Date(globalFirst[g]).getTime();
        trulyNew = fs >= windowStart;
      }
      const isNew  = p === 0 && c > 0 && trulyNew;
      const isGone = c === 0 && p > 0;
      movers.push({ g, p, c, raw, pct, isNew, isGone });
    }
    movers.sort((a, b) => Math.abs(b.raw) - Math.abs(a.raw));
    return { total, activeGroups, topGroup, topCount, topShare, trendPct, movers };
  }

  function renderSummary() {
    const s = computeSummary();
    $kpi('posts').textContent  = s.total.toLocaleString();
    $kpi('groups').textContent = s.activeGroups;
    $kpi('top').textContent    = s.topGroup ? s.topGroup.replace(/\b\w/g, c => c.toUpperCase()) : '—';
    $kpi('top_sub').textContent= s.topGroup ? `${s.topCount} posts · ${s.topShare}%` : '';

    const $trend = $kpi('trend');
    if ($trend) {
      if (s.trendPct === null) {
        $trend.textContent = '—';
        $trend.className = 'movers-trend delta-flat';
      } else {
        const v = Math.round(s.trendPct * 10) / 10;
        $trend.textContent = (v > 0 ? '▲ +' : v < 0 ? '▼ ' : '= ') + v + '%';
        $trend.className = 'movers-trend ' + (v > 0 ? 'delta-up-strong' : v < 0 ? 'delta-down-strong' : 'delta-flat');
      }
    }

    // Movers list — top 5 by |raw|
    if ($movers) {
      $movers.innerHTML = '';
      const top = s.movers.slice(0, 5);
      if (top.length === 0) {
        $movers.innerHTML = '<li class="muted">No data</li>';
      } else {
        for (const m of top) {
          const li = document.createElement('li');
          // Consistent formatting: always show a delta with % when possible,
          // so positive and negative values have the same unit (matches the
          // "movers-trend" indicator right above this list).
          const pct = m.pct === null ? null : Math.round(m.pct * 10) / 10;
          let tag;
          if (m.isNew) {
            tag = '<span class="delta-badge delta-new" title="First posts ever observed for this group (not seen before the current window).">NEW</span>';
          } else if (m.isGone) {
            tag = '<span class="delta-badge delta-down-strong">GONE</span>';
          } else if (m.raw > 0) {
            const pctTxt = pct !== null ? ' +' + pct + '%' : ' +' + m.raw;
            tag = '<span class="delta-badge delta-up-strong" title="' + m.raw + ' posts">▲' + pctTxt + '</span>';
          } else if (m.raw < 0) {
            const pctTxt = pct !== null ? ' ' + pct + '%' : ' ' + m.raw;
            tag = '<span class="delta-badge delta-down-strong" title="' + m.raw + ' posts">▼' + pctTxt + '</span>';
          } else {
            tag = '<span class="delta-badge delta-flat">= 0%</span>';
          }
          li.innerHTML = `
            <span class="mover-dot" style="background:${colorFor(m.g)}"></span>
            <span class="mover-name" title="${m.g}">${m.g.replace(/\b\w/g, c => c.toUpperCase())}</span>
            ${tag}`;
          $movers.appendChild(li);
        }
      }
    }
  }

  /* ====================================================================
   *  Chart rendering
   * ==================================================================== */
  const plotOpts = { displayModeBar: false, responsive: true };
  const valLabel = () => $norm.checked ? 'Share' : 'Posts';

  function updateCharts() {
    applyFilters();
    const agg    = bucketize();
    const counts = countsByGroup();
    const topN   = +$topn.value || 0;
    const top    = topN > 0 ? counts.slice(0, topN).map(d => d.group) : counts.map(d => d.group);

    // Assign distinct palette colours to every visible group (hash-first with
    // collision fallback) so the N visible series are guaranteed unique.
    assignVisibleColors(top);

    renderSummary();
    updateStatus(counts, topN);

    // --- Bar (per-bar colors, consistent with dots across the site) ---
    const barData = topN > 0 ? counts.slice(0, topN) : counts;
    Plotly.react('chart-bar', [{
      type: 'bar',
      x: barData.map(d => d.group),
      y: barData.map(d => d.count),
      marker: { color: barData.map(d => colorFor(d.group)) },
      hovertemplate: '%{x}: %{y} posts<extra></extra>'
    }], baseLayout({
      margin: { l:60, r:10, t:10, b:80 },
      xaxis: { tickangle:-35, automargin:true }
    }), plotOpts);

    // --- Stacked area ---
    const areaTraces = top.map(g => {
      const idx = agg.groups.indexOf(g);
      const row = idx >= 0 ? agg.matrix[idx] : [];
      return {
        type: 'scatter', mode: 'lines', name: g,
        x: agg.keys, y: row, stackgroup: 'one',
        line:      { color: colorFor(g), width: 1 },
        fillcolor: colorForAlpha(g, 0.55),
        hovertemplate: $bucket.value + ': %{x}<br>' + valLabel() + ': %{y}<extra>' + g + '</extra>'
      };
    });
    orderLegend(areaTraces, false);
    Plotly.react('chart-area', areaTraces, baseLayout({
      margin: { l:60, r:10, t:10, b:50 },
      xaxis: { tickangle:-20, automargin:true }
    }), plotOpts);

    // --- Scatter timeline ---
    const scatterTraces = top.map(g => {
      const pts = state.filtered.filter(x => x.g === g).sort((a, b) => a.ts - b.ts);
      return {
        type: 'scatter', mode: 'markers', name: g,
        x: pts.map(p => p.ts), y: pts.map(() => g),
        marker: { color: colorFor(g), size: 8 },
        hovertemplate: '%{x|%Y-%m-%d %H:%M:%S}<extra>' + g + '</extra>'
      };
    });
    Plotly.react('chart-scatter', scatterTraces, baseLayout({
      margin: { l:80, r:10, t:10, b:40 },
      yaxis: { type:'category', automargin:true }
    }), plotOpts);
  }

  /* ====================================================================
   *  CSV export
   * ==================================================================== */
  function downloadBlob(name, blob) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1500);
  }

  $csv.addEventListener('click', () => {
    const agg = bucketize();
    const header = ['time', ...agg.groups];
    const rows = agg.keys.map((k, i) =>
      [k, ...agg.groups.map((_, r) => agg.matrix[r][i] ?? '')].join(',')
    );
    const csv = [header.join(','), ...rows].join('\n');
    downloadBlob('ransomlook_stats_' + Date.now() + '.csv', new Blob([csv], { type: 'text/csv' }));
  });

  /* ====================================================================
   *  PNG export (per chart)
   * ==================================================================== */
  document.addEventListener('click', async e => {
    const btn = e.target.closest('[data-dl]');
    if (!btn) return;
    const node = $(btn.dataset.dl);
    if (!node) return;
    try {
      const url  = await Plotly.toImage(node, { format:'png', width:1200, height:700 });
      const res  = await fetch(url);
      const blob = await res.blob();
      downloadBlob(btn.dataset.dl + '_' + Date.now() + '.png', blob);
    } catch (err) { console.error('PNG export failed', err); }
  });

  /* ====================================================================
   *  Share URL
   * ==================================================================== */
  $share.addEventListener('click', async () => {
    writeURL();
    try { await navigator.clipboard.writeText(location.href); } catch (e) { /* noop */ }
    $share.textContent = 'Copied!';
    setTimeout(() => { $share.textContent = 'Share URL'; }, 1200);
  });

  /* ====================================================================
   *  Chart modal (click expand button to enlarge)
   * ==================================================================== */
  function openModal(chartId) {
    const src = $(chartId);
    if (!src || !src.data) return;

    const data   = JSON.parse(JSON.stringify(src.data));
    const layout = JSON.parse(JSON.stringify(src.layout || {}));

    $modal.setAttribute('aria-hidden', 'false');

    layout.autosize = true;
    layout.margin   = layout.margin || { l:60, r:20, t:30, b:60 };

    const dialog = $modal.querySelector('.chart-modal__dialog');
    const rect   = dialog.getBoundingClientRect();
    const w = Math.floor(rect.width - 4);
    const h = Math.floor(window.innerHeight * 0.88 - 48);

    Plotly.newPlot($modalPlot, data, layout, { responsive:true, displayModeBar:true })
      .then(() => Plotly.relayout($modalPlot, { width:w, height:h }))
      .then(() => requestAnimationFrame(() => Plotly.Plots.resize($modalPlot)));
  }

  function closeModal() {
    $modal.setAttribute('aria-hidden', 'true');
    if ($modalPlot && $modalPlot.data) Plotly.purge($modalPlot);
  }

  // Expand button opens modal
  document.addEventListener('click', e => {
    const btn = e.target.closest('[data-expand]');
    if (!btn) return;
    const card = btn.closest('.table-card');
    if (!card) return;
    const chart = card.querySelector('div[id^="chart-"]');
    if (chart) openModal(chart.id);
  });

  // Close modal
  document.addEventListener('click', e => {
    if (e.target.matches('[data-close-modal]')) closeModal();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && $modal.getAttribute('aria-hidden') === 'false') closeModal();
  });
  window.addEventListener('resize', () => {
    if ($modal.getAttribute('aria-hidden') === 'false' && $modalPlot && $modalPlot.data) {
      Plotly.relayout($modalPlot, {
        height: Math.round(window.innerHeight * 0.78),
        width:  Math.round(window.innerWidth  * 0.90)
      });
    }
  });

  /* ====================================================================
   *  Controls wiring
   * ==================================================================== */
  function toggleCustom() {
    $custom.style.display = $period.value === 'custom' ? 'flex' : 'none';
    $custom.classList.toggle('d-none', $period.value !== 'custom');
  }

  $period.addEventListener('change', toggleCustom);
  [$period, $from, $to, $bucket, $roll, $topn, $norm].forEach(el => {
    el.addEventListener('change', () => { updateCharts(); writeURL(); });
  });

  /* ====================================================================
   *  Init
   * ==================================================================== */
  const saved = readURL();

  $refresh.addEventListener('click', () => reload());

  async function reload() {
    try {
      await fetchPosts();
      rebuildGroups(saved.groups);
      updateCharts();
      writeURL();
    } catch (err) {
      console.error('Stats load error:', err);
      updateCharts();
    }
  }

  reload();
});
