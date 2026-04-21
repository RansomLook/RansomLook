document.addEventListener('DOMContentLoaded', () => {
  /* ----------------------------------------------------------------
   * Relative time ("4 min ago", "2h ago", "yesterday")
   * ---------------------------------------------------------------- */
  RL.renderDates('time');
  setInterval(() => RL.renderDates('time'), 60000);

  /* ----------------------------------------------------------------
   * Group color dots — stable palette indexed by name hash
   * ---------------------------------------------------------------- */
  RL.colorDots();

  /* ----------------------------------------------------------------
   * Live filter: title search + group dropdown
   * ---------------------------------------------------------------- */
  const $q       = document.getElementById('recent-q');
  const $clear   = document.querySelector('.recent-search .input-clear');
  const $group   = document.getElementById('recent-group');
  const $rows    = document.getElementById('recent-rows');
  const $count   = document.getElementById('recent-count');
  const $empty   = document.getElementById('recent-empty');
  const rows     = $rows ? Array.from($rows.querySelectorAll('tr')) : [];
  const total    = rows.length;

  const apply = () => {
    const q = ($q?.value || '').toLowerCase().trim();
    const g = ($group?.value || '').toLowerCase();
    let shown = 0;
    for (const tr of rows) {
      const okQ = !q || tr.dataset.title.includes(q) || tr.dataset.group.includes(q);
      const okG = !g || tr.dataset.group === g;
      const vis = okQ && okG;
      tr.style.display = vis ? '' : 'none';
      if (vis) shown++;
    }
    if ($count) {
      $count.textContent = (q || g)
        ? `${shown} of ${total}`
        : '';
    }
    if ($empty) $empty.style.display = shown ? 'none' : '';
  };

  let qTimer = null;
  $q?.addEventListener('input', () => {
    clearTimeout(qTimer);
    qTimer = setTimeout(apply, 60);
  });
  $clear?.addEventListener('click', () => { if ($q) { $q.value = ''; apply(); $q.focus(); } });
  $group?.addEventListener('change', apply);
});
