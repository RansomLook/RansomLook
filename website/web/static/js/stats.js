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

    updateStatus(counts, topN);

    // --- Bar ---
    const barData = topN > 0 ? counts.slice(0, topN) : counts;
    Plotly.react('chart-bar', [{
      type: 'bar',
      x: barData.map(d => d.group),
      y: barData.map(d => d.count),
      hovertemplate: '%{x}: %{y} posts<extra></extra>'
    }], baseLayout({
      margin: { l:60, r:10, t:10, b:80 },
      xaxis: { tickangle:-35, automargin:true }
    }), plotOpts);

    // --- Pie ---
    const pieData = topN > 0 ? counts.slice(0, topN) : counts;
    Plotly.react('chart-pie', [{
      type: 'pie',
      labels: pieData.map(d => d.group),
      values: pieData.map(d => d.count),
      textinfo: 'label+percent',
      hovertemplate: '%{label}: %{value} posts<extra></extra>'
    }], baseLayout({
      margin: { l:10, r:10, t:10, b:10 }
    }), plotOpts);

    // --- Stacked area ---
    const areaTraces = top.map(g => {
      const idx = agg.groups.indexOf(g);
      const row = idx >= 0 ? agg.matrix[idx] : [];
      return {
        type: 'scatter', mode: 'lines', name: g,
        x: agg.keys, y: row, stackgroup: 'one',
        hovertemplate: $bucket.value + ': %{x}<br>' + valLabel() + ': %{y}<extra>' + g + '</extra>'
      };
    });
    orderLegend(areaTraces, false);
    Plotly.react('chart-area', areaTraces, baseLayout({
      margin: { l:60, r:10, t:10, b:50 },
      xaxis: { tickangle:-20, automargin:true }
    }), plotOpts);

    // --- Heatmap ---
    const hmY = [...top].reverse();
    const hmZ = hmY.map(g => {
      const idx = agg.groups.indexOf(g);
      return idx >= 0 ? agg.matrix[idx] : [];
    });
    Plotly.react('chart-heatmap', [{
      type: 'heatmap',
      x: agg.keys, y: hmY, z: hmZ,
      colorscale: 'Portland',
      hovertemplate: $bucket.value + ': %{x}<br>Group: %{y}<br>' + valLabel() + ': %{z}<extra></extra>'
    }], baseLayout({
      margin: { l:90, r:10, t:10, b:40 },
      yaxis: { automargin:true }
    }), plotOpts);

    // --- Scatter timeline ---
    const scatterTraces = top.map(g => {
      const pts = state.filtered.filter(x => x.g === g).sort((a, b) => a.ts - b.ts);
      return {
        type: 'scatter', mode: 'markers', name: g,
        x: pts.map(p => p.ts), y: pts.map(() => g),
        hovertemplate: '%{x|%Y-%m-%d %H:%M:%S}<extra>' + g + '</extra>'
      };
    });
    Plotly.react('chart-scatter', scatterTraces, baseLayout({
      margin: { l:80, r:10, t:10, b:40 },
      yaxis: { type:'category', automargin:true }
    }), plotOpts);

    // --- Sparklines ---
    const sparkTraces = top.map(g => {
      const idx = agg.groups.indexOf(g);
      const row = idx >= 0 ? agg.matrix[idx] : [];
      return {
        type: 'scatter', mode: 'lines', name: g,
        x: agg.keys, y: row,
        hovertemplate: '%{x}<br>' + g + ': %{y}<extra></extra>'
      };
    });
    Plotly.react('chart-sparks', sparkTraces, baseLayout({
      margin: { l:60, r:10, t:10, b:50 },
      xaxis: { tickangle:-20, automargin:true }
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
