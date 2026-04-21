document.addEventListener('DOMContentLoaded', () => {
  const $q           = document.getElementById('browse-q');
  const $clear       = document.querySelector('.field--search .input-clear');
  const $grid        = document.getElementById('browse-grid');
  const $cards       = $grid ? Array.from($grid.querySelectorAll('.item-card')) : [];
  const $tabs        = Array.from(document.querySelectorAll('.browse-tabs .tab-btn'));
  const $alpha       = Array.from(document.querySelectorAll('.alpha-bar .alpha-btn'));
  const $healthWrap  = document.querySelector('.health-chips');
  const $healthChips = Array.from(document.querySelectorAll('.health-chip'));
  const $count       = document.getElementById('browse-count');
  const $empty       = document.getElementById('browse-empty');

  const bootEl = document.getElementById('browse-bootstrap');
  const boot   = bootEl ? JSON.parse(bootEl.textContent || '{}') : {};

  const state = {
    tab: (boot.activeTab || 'all').toLowerCase(),
    q:   (boot.query || '').toLowerCase(),
    letter: '',
    health: new Set()   // subset of {'healthy','degraded','offline'} — empty = no filter
  };

  /* ----------------------------------------------------------------
   * URL sync (replaceState — no history spam on each keystroke)
   * ---------------------------------------------------------------- */
  const syncUrl = () => {
    const url = new URL(window.location.href);
    if (state.tab && state.tab !== 'all') url.searchParams.set('tab', state.tab);
    else url.searchParams.delete('tab');
    if (state.q) url.searchParams.set('q', state.q);
    else url.searchParams.delete('q');
    history.replaceState(null, '', url);
  };

  /* ----------------------------------------------------------------
   * Filtering
   * ---------------------------------------------------------------- */
  const applyFilter = () => {
    const q = state.q.trim();
    const hasQ = q.length > 0;
    const healthActive = state.health.size > 0;

    // Live per-type counts (after search+health but before tab restriction)
    const perType = { all: 0, group: 0, market: 0, actor: 0 };
    let visibleTotal = 0;

    for (const card of $cards) {
      const type    = card.dataset.type;
      const name    = card.dataset.name || '';
      const aliases = card.dataset.aliases || '';
      const letter  = card.dataset.letter || '';
      const health  = card.dataset.health || '';

      const matchQ = !hasQ || name.includes(q) || aliases.includes(q);
      const matchLetter = !state.letter || letter === state.letter;
      const matchTab = state.tab === 'all' || type === state.tab;
      // Health filter: actors (no health) are hidden when any chip is active.
      const matchHealth = !healthActive || (health && state.health.has(health));

      if (matchQ && matchLetter && matchHealth) {
        perType.all++;
        perType[type] = (perType[type] || 0) + 1;
      }

      const visible = matchQ && matchLetter && matchTab && matchHealth;
      card.style.display = visible ? '' : 'none';
      if (visible) visibleTotal++;
    }

    // Update tab counts
    for (const $t of $tabs) {
      const key = $t.dataset.tab;
      const el = $t.querySelector('.tab-count');
      if (el) el.textContent = perType[key] ?? 0;
      $t.setAttribute('aria-selected', $t.dataset.tab === state.tab ? 'true' : 'false');
      $t.classList.toggle('is-active', $t.dataset.tab === state.tab);
    }

    // Active letter highlight
    for (const $l of $alpha) {
      $l.classList.toggle('is-active', ($l.dataset.letter || '') === state.letter);
    }

    // Health chips: update active state and hide whole bar on actor-only tab
    for (const $c of $healthChips) {
      $c.classList.toggle('is-active', state.health.has($c.dataset.health));
      $c.setAttribute('aria-pressed', state.health.has($c.dataset.health) ? 'true' : 'false');
    }
    if ($healthWrap) $healthWrap.hidden = (state.tab === 'actor');

    if ($count) {
      $count.textContent = visibleTotal
        ? `${visibleTotal} result${visibleTotal > 1 ? 's' : ''}`
        : '';
    }
    if ($empty) $empty.style.display = visibleTotal ? 'none' : '';
  };

  /* ----------------------------------------------------------------
   * Events
   * ---------------------------------------------------------------- */
  let qTimer = null;
  $q?.addEventListener('input', () => {
    const prev = state.q;
    state.q = $q.value.toLowerCase();

    // Auto-switch to "All" the first time a user starts typing,
    // so they don't miss results that live in another tab.
    if (!prev && state.q) state.tab = 'all';

    clearTimeout(qTimer);
    qTimer = setTimeout(() => { syncUrl(); applyFilter(); }, 60);
  });

  $clear?.addEventListener('click', () => {
    if (!$q) return;
    $q.value = '';
    state.q = '';
    syncUrl();
    applyFilter();
    $q.focus();
  });

  for (const $t of $tabs) {
    $t.addEventListener('click', () => {
      state.tab = $t.dataset.tab;
      syncUrl();
      applyFilter();
    });
  }

  for (const $l of $alpha) {
    $l.addEventListener('click', () => {
      const letter = $l.dataset.letter || '';
      state.letter = (state.letter === letter) ? '' : letter;
      applyFilter();
    });
  }

  for (const $c of $healthChips) {
    $c.addEventListener('click', () => {
      const h = $c.dataset.health;
      if (state.health.has(h)) state.health.delete(h);
      else state.health.add(h);
      applyFilter();
    });
  }

  // Ctrl/Cmd+K focuses the in-page search bar. Uses the capture phase and
  // stopImmediatePropagation to beat base.html/main.js's global modal handler.
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      e.stopImmediatePropagation();
      $q?.focus();
      $q?.select();
    }
  }, { capture: true });

  // Replace broken logos with their text-initial placeholder (CSP-friendly,
  // no inline onerror handlers). Uses capture phase because 'error' does not
  // bubble.
  $grid?.addEventListener('error', (e) => {
    const img = e.target;
    if (!(img instanceof HTMLImageElement)) return;
    const slot = img.closest('.card-logo');
    if (!slot) return;
    const initial = slot.dataset.initial || '?';
    const ph = document.createElement('div');
    ph.className = 'card-logo-placeholder';
    ph.textContent = initial;
    slot.replaceChildren(ph);
  }, { capture: true });

  applyFilter();
});
