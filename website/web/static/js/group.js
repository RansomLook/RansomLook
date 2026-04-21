document.addEventListener('DOMContentLoaded', () => {
  /* ====================================================================
   *  Spark health mini-charts
   * ==================================================================== */
  document.querySelectorAll('.spark[data-health]').forEach(el => {
    let series = [];
    try { series = JSON.parse(el.getAttribute('data-health') || '[]'); } catch (e) { series = []; }
    if (!series || !series.length) { el.textContent = '\u2014'; return; }

    const x = series.map((v, i) => i);
    const colors = series.map(v => v ? '#10b981' : '#ef4444');  // green=up, red=down
    const data = [{
      x, y: series.map(() => 1),  // all bars same height, color encodes status
      type: 'bar',
      marker: { color: colors },
      hoverinfo: 'skip',
    }];
    const layout = {
      margin: { l:2, r:2, t:2, b:2 }, height: 28, width: Math.max(series.length * 6, 40),
      paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
      xaxis: { visible: false }, yaxis: { visible: false, range: [0, 1.2] },
      bargap: 0.15,
    };
    if (window.Plotly) Plotly.newPlot(el, data, layout, { displayModeBar: false, staticPlot: true });
    else el.textContent = '\u2014';
  });

  /* ====================================================================
   *  Activity chart (bar + optional rolling avg)
   *  Reads posts data from <script type="application/json" id="posts-data">
   * ==================================================================== */
  const postsEl = document.getElementById('posts-data');
  if (postsEl && window.Plotly) {
    const POSTS = JSON.parse(postsEl.textContent);
    const groupName = postsEl.dataset.groupName || 'group';
    const COLOR_TEXT = '#e5e7eb';

    const fmtDay   = d => d.toISOString().slice(0, 10);
    const toMonday = d => {
      const x = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
      const w = x.getUTCDay() || 7;
      x.setUTCDate(x.getUTCDate() - w + 1);
      return x;
    };

    const $bucket = document.getElementById('grp-bucket');
    const $roll   = document.getElementById('grp-roll');

    function grpBaseLayout(extra) {
      const base = {
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: COLOR_TEXT }, margin: { l:60, r:10, t:10, b:60 },
        xaxis: { tickfont: { color: COLOR_TEXT }, titlefont: { color: COLOR_TEXT } },
        yaxis: { tickfont: { color: COLOR_TEXT }, titlefont: { color: COLOR_TEXT } },
        legend: { font: { color: COLOR_TEXT } }
      };
      if (!extra) return base;
      for (const [k, v] of Object.entries(extra)) {
        if (v && typeof v === 'object' && !Array.isArray(v) && base[k] && typeof base[k] === 'object') {
          base[k] = { ...base[k], ...v };
        } else {
          base[k] = v;
        }
      }
      return base;
    }

    function bucketize() {
      const bucket = $bucket.value;
      const map = new Map();
      POSTS.forEach(p => {
        const ts = new Date(p.discovered || p.timestamp || p.time);
        if (isNaN(ts)) return;
        const k = bucket === 'week' ? fmtDay(toMonday(ts)) : fmtDay(ts);
        map.set(k, (map.get(k) || 0) + 1);
      });
      const keys = [...map.keys()].sort();
      const counts = keys.map(k => map.get(k) || 0);

      const w = +$roll.value || 0;
      let roll = counts;
      if (w > 1) {
        roll = [];
        let sum = 0;
        for (let i = 0; i < counts.length; i++) {
          sum += counts[i];
          if (i >= w) sum -= counts[i - w];
          roll.push(i >= w - 1 ? +(sum / w).toFixed(3) : null);
        }
      }
      return { keys, counts, roll };
    }

    function draw() {
      const { keys, counts, roll } = bucketize();
      const traces = [{ type: 'bar', x: keys, y: counts, name: 'Posts', hovertemplate: '%{x}: %{y}<extra></extra>' }];
      if (+($roll.value || 0) > 0) {
        traces.push({ type: 'scatter', mode: 'lines', name: 'Rolling ' + $roll.value, x: keys, y: roll });
      }
      Plotly.react('grp-bar', traces, grpBaseLayout({ xaxis: { tickangle: -25, automargin: true } }), { displayModeBar: false });
    }

    [$bucket, $roll].forEach(el => el.addEventListener('change', draw));
    draw();

    // PNG export for activity chart
    document.addEventListener('click', async e => {
      const btn = e.target.closest('[data-dl="grp-bar"]');
      if (!btn) return;
      try {
        const dataUrl = await Plotly.toImage('grp-bar', { format: 'png', width: 1200, height: 700 });
        const res = await fetch(dataUrl);
        const blob = await res.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = groupName + '_activity.png';
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 1500);
      } catch (err) { console.error('PNG export failed', err); }
    });
  }

  /* ====================================================================
   *  Chart enlarge modal
   * ==================================================================== */
  const chartModal = document.getElementById('chart-modal');
  if (chartModal && window.Plotly) {
    const dialog    = chartModal.querySelector('.chart-modal__dialog');
    const modalPlot = document.getElementById('chart-modal-plot');

    function closeChart() {
      chartModal.setAttribute('aria-hidden', 'true');
      if (modalPlot && modalPlot.data) Plotly.purge(modalPlot);
    }

    async function openChartModal(chartId) {
      const src = document.getElementById(chartId);
      if (!src || !src.data) return;
      const data   = JSON.parse(JSON.stringify(src.data));
      const layout = JSON.parse(JSON.stringify(src.layout || {}));

      layout.font   = Object.assign({ color: '#e5e7eb' }, layout.font || {});
      layout.xaxis  = Object.assign({ tickfont: { color: '#e5e7eb' }, titlefont: { color: '#e5e7eb' } }, layout.xaxis || {});
      layout.yaxis  = Object.assign({ tickfont: { color: '#e5e7eb' }, titlefont: { color: '#e5e7eb' } }, layout.yaxis || {});
      layout.legend  = Object.assign({ font: { color: '#e5e7eb' } }, layout.legend || {});

      chartModal.setAttribute('aria-hidden', 'false');
      const rect = dialog.getBoundingClientRect();
      const w = Math.floor(rect.width - 4);
      const h = Math.floor(window.innerHeight * 0.90 - 48);

      await Plotly.newPlot(modalPlot, data, layout, { responsive: true, displayModeBar: true });
      await Plotly.relayout(modalPlot, { width: w, height: h });
      requestAnimationFrame(() => Plotly.Plots.resize(modalPlot));
    }

    // Expand button
    document.addEventListener('click', e => {
      const expand = e.target.closest('[data-expand]');
      if (expand) {
        const card = expand.closest('.table-card');
        if (card) {
          const chart = card.querySelector('div[id^="grp-"]');
          if (chart) openChartModal(chart.id);
        }
        return;
      }
      // Also support clicking on card-title
      const title = e.target.closest('.card-title');
      if (title) { openChartModal('grp-bar'); return; }

      if (e.target.matches('[data-close-modal]')) closeChart();
    });

    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && chartModal.getAttribute('aria-hidden') === 'false') closeChart();
    });
    window.addEventListener('resize', () => {
      if (chartModal.getAttribute('aria-hidden') === 'false' && modalPlot && modalPlot.data) {
        Plotly.relayout(modalPlot, {
          height: Math.round(window.innerHeight * 0.90 - 48),
          width:  Math.round(dialog.getBoundingClientRect().width - 4)
        });
      }
    });
  }

  /* ====================================================================
   *  Compare link rewrite (pre-fill source A with current group)
   * ==================================================================== */
  const pathMatch = location.pathname.match(/^\/(group|market)\/([^/]+)\/?$/);
  if (pathMatch) {
    const kind = pathMatch[1] === 'group' ? 'group' : 'market';
    const name = decodeURIComponent(pathMatch[2]);
    document.querySelectorAll('a[href="/compare"], a[href^="/compare?"]').forEach(a => {
      const url = new URL(a.getAttribute('href'), location.origin);
      if (!url.searchParams.get('a')) url.searchParams.set('a', name);
      if (!url.searchParams.get('kind')) url.searchParams.set('kind', kind);
      a.setAttribute('href', url.pathname + '?' + url.searchParams.toString());
    });
  }

  /* ====================================================================
   *  Note overlay (ransom notes in-page viewer)
   * ==================================================================== */
  const noteLayer = document.getElementById('noteLayer');
  if (noteLayer) {
    const titleEl = document.getElementById('noteLayerTitle');
    const textEl  = document.getElementById('noteLayerText');
    const htmlEl  = document.getElementById('noteLayerHtml');

    function openOverlay()  { noteLayer.setAttribute('data-open', '1'); document.body.style.overflow = 'hidden'; }
    function closeOverlay() {
      noteLayer.removeAttribute('data-open');
      document.body.style.overflow = '';
      textEl.textContent = '';
      htmlEl.innerHTML = '';
      textEl.hidden = false;
      htmlEl.hidden = true;
      titleEl.textContent = 'Note';
    }

    noteLayer.addEventListener('click', e => {
      if (e.target.matches('[data-close]') || e.target.closest('[data-close]')) {
        e.preventDefault();
        closeOverlay();
      }
    });
    document.addEventListener('keydown', e => {
      if (noteLayer.style.display !== 'none' && e.key === 'Escape') { e.preventDefault(); closeOverlay(); }
    });

    async function openNote(id) {
      try {
        const res = await fetch('/api/notes/' + encodeURIComponent(id), { headers: { Accept: 'application/json' } });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const n = await res.json();

        titleEl.textContent = n.title || 'Note';
        htmlEl.hidden = true;
        textEl.hidden = false;
        textEl.textContent = n.content || '';
        openOverlay();
      } catch (err) {
        console.error('[note overlay] error:', err);
        alert("Impossible d'ouvrir la note.");
      }
    }

    // Bind triggers inside #ransom-notes
    const scope = document.getElementById('ransom-notes');
    if (scope) {
      scope.querySelectorAll('a.js-open-note[data-note-id]').forEach(el => {
        el.addEventListener('click', ev => {
          ev.preventDefault();
          ev.stopPropagation();
          const id = el.getAttribute('data-note-id');
          if (id) openNote(id);
        });
      });
    }
  }
});
