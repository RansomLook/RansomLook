document.addEventListener('DOMContentLoaded', () => {
  /* Relative time */
  const renderDates = () => {
    const now = Date.now();
    for (const $t of document.querySelectorAll('.rl-table--hot time[data-ts]')) {
      const raw = $t.dataset.ts;
      const iso = raw.includes('T') ? raw : raw.replace(' ', 'T') + 'Z';
      const d = new Date(iso);
      if (isNaN(d)) continue;
      const HH = String(d.getHours()).padStart(2, '0');
      const MM = String(d.getMinutes()).padStart(2, '0');
      const sameDay = new Date(now).toDateString() === d.toDateString();
      const primary = sameDay
        ? `${HH}:${MM}`
        : `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${HH}:${MM}`;
      $t.innerHTML = `<span class="t-primary">${primary}</span><span class="t-rel">${RL.fmtRel(now - d.getTime())}</span>`;
    }
  };
  renderDates();
  setInterval(renderDates, 60000);

  /* Group color dots */
  RL.colorDots();

  /* Client-side filter on group name */
  const $q = document.getElementById('hot-q');
  const $clear = document.querySelector('.hot-search .input-clear');
  const $rows = document.getElementById('hot-rows');
  const $count = document.getElementById('hot-count');
  const $empty = document.getElementById('hot-empty');
  const rows = $rows ? Array.from($rows.querySelectorAll('tr')) : [];
  const total = rows.length;

  const apply = () => {
    const q = ($q?.value || '').toLowerCase().trim();
    let shown = 0;
    for (const tr of rows) {
      const vis = !q || tr.dataset.group.includes(q);
      tr.style.display = vis ? '' : 'none';
      if (vis) shown++;
    }
    if ($count) $count.textContent = q ? `${shown} of ${total}` : '';
    if ($empty) $empty.style.display = shown ? 'none' : '';
  };

  let timer = null;
  $q?.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(apply, 60); });
  $clear?.addEventListener('click', () => { if ($q) { $q.value = ''; apply(); $q.focus(); } });
});
