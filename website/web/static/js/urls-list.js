(() => {
  'use strict';

  const $q = document.getElementById('urls-q');
  const $clear = document.querySelector('#urls-q ~ .input-clear');
  const $typeBtns = document.querySelectorAll('.browse-tabs [data-type]');
  const $statusBtns = document.querySelectorAll('.browse-tabs [data-status]');
  const $rows = document.querySelectorAll('#urls-table .url-row');
  const $count = document.getElementById('urls-count');
  const $empty = document.getElementById('urls-empty');
  const $csv = document.getElementById('urls-csv');
  const csvBase = $csv ? $csv.getAttribute('href') : '';

  const boot = (() => {
    try { return JSON.parse(document.getElementById('urls-bootstrap').textContent); }
    catch (e) { return { activeType: 'all', activeStatus: 'all', query: '' }; }
  })();

  const state = {
    type: boot.activeType || 'all',
    status: boot.activeStatus || 'all',
    q: (boot.query || '').toLowerCase().trim(),
  };

  function apply() {
    let shown = 0;
    const q = state.q;
    $rows.forEach(row => {
      const okType = state.type === 'all' || row.dataset.type === state.type;
      const okStatus = state.status === 'all' || row.dataset.status === state.status;
      const okQ = !q ||
                  row.dataset.name.indexOf(q) !== -1 ||
                  row.dataset.slug.indexOf(q) !== -1;
      const visible = okType && okStatus && okQ;
      row.hidden = !visible;
      if (visible) shown++;
    });
    if ($count) $count.textContent = shown + ' row' + (shown === 1 ? '' : 's');
    if ($empty) $empty.style.display = shown === 0 ? '' : 'none';
    if ($csv) {
      const params = new URLSearchParams();
      if (state.type !== 'all') params.set('type', state.type);
      if (state.status !== 'all') params.set('status', state.status);
      if (state.q) params.set('q', state.q);
      const qs = params.toString();
      $csv.href = csvBase + (qs ? '?' + qs : '');
    }
  }

  function setPressed(btns, key, value) {
    btns.forEach(b => b.setAttribute('aria-selected', b.dataset[key] === value ? 'true' : 'false'));
  }

  $typeBtns.forEach(b => b.addEventListener('click', () => {
    state.type = b.dataset.type;
    setPressed($typeBtns, 'type', state.type);
    apply();
  }));

  $statusBtns.forEach(b => b.addEventListener('click', () => {
    state.status = b.dataset.status;
    setPressed($statusBtns, 'status', state.status);
    apply();
  }));

  if ($q) {
    $q.addEventListener('input', () => {
      state.q = $q.value.toLowerCase().trim();
      apply();
    });
  }

  if ($clear && $q) {
    $clear.addEventListener('click', () => {
      $q.value = '';
      state.q = '';
      apply();
      $q.focus();
    });
  }

  setPressed($typeBtns, 'type', state.type);
  setPressed($statusBtns, 'status', state.status);
  apply();
})();
