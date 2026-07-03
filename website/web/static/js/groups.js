document.addEventListener('DOMContentLoaded', () => {
  const qInput   = document.getElementById('flt-q');
  const clearBtn = document.querySelector('.input-clear');
  const alphaBtns = [...document.querySelectorAll('.alpha-btn')];
  const articles = [...document.querySelectorAll('article.profile')];
  const countEl  = document.getElementById('flt-count');
  const topAnchor = document.getElementById('filters-top');

  if (!articles.length) return;

  function norm(s) { return (s || '').toLowerCase(); }
  function initialOf(s) {
    const ch = (s || '').trim().charAt(0).toUpperCase();
    return /[A-Z]/.test(ch) ? ch : '#';
  }

  const cache = articles.map(art => {
    const id   = art.getAttribute('id') || '';
    const name = (art.querySelector('.profile-title')?.textContent || '').trim();
    const desc = (art.querySelector('.profile-desc')?.textContent || '').trim();
    const rows = [...art.querySelectorAll('table[data-links-table] tbody tr')];
    const titles = rows.map(r => (r.querySelector('td:nth-child(1)')?.textContent || '').trim()).join(' ');
    const urls   = rows.map(r => (r.querySelector('td:nth-child(4) a')?.getAttribute('href') || r.querySelector('td:nth-child(4)')?.textContent || '').trim()).join(' ');
    const searchable = norm([name, desc, titles, urls].join(' '));
    return { art, id, name, searchable, initial: initialOf(name), visible: true };
  });

  // Sticky header offset
  const siteHeader = document.querySelector('.site-header');
  function stickyOffset() {
    return siteHeader ? (siteHeader.getBoundingClientRect().height + 8) : 0;
  }

  function jumpToTop() {
    const top = (topAnchor?.getBoundingClientRect().top || 0) + window.pageYOffset - stickyOffset();
    window.scrollTo({ top, behavior: 'smooth' });
  }

  function jumpToLetter(L) {
    const target = cache.find(x => x.visible && x.initial === L);
    if (target) {
      const y = target.art.getBoundingClientRect().top + window.pageYOffset - stickyOffset();
      window.scrollTo({ top: y, behavior: 'smooth' });
      if (target.id) history.replaceState(null, '', '#' + encodeURIComponent(target.id));
      target.art.classList.add('flash-border');
      setTimeout(() => target.art.classList.remove('flash-border'), 900);
    }
  }

  function renderAlpha() {
    const available = new Set(cache.filter(x => x.visible).map(x => x.initial));
    alphaBtns.forEach(btn => { btn.disabled = !available.has(btn.dataset.letter); });
  }

  function updateCount() {
    const n = cache.filter(x => x.visible).length;
    if (countEl) countEl.textContent = n + ' groups visible';
  }

  function applyFilter() {
    const q = norm(qInput?.value || '');
    cache.forEach(obj => {
      const match = !q || obj.searchable.includes(q);
      obj.visible = match;
      obj.art.style.display = match ? '' : 'none';
    });
    renderAlpha();
    updateCount();
  }

  alphaBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      alphaBtns.forEach(b => b.classList.toggle('is-active', b === btn));
      jumpToLetter(btn.dataset.letter);
    });
  });

  clearBtn?.addEventListener('click', () => { qInput.value = ''; applyFilter(); qInput.focus(); });
  let t;
  qInput?.addEventListener('input', () => { clearTimeout(t); t = setTimeout(applyFilter, 120); });

  // Anchor-list clicks with sticky offset
  document.querySelectorAll('.anchor-list a').forEach(a => {
    a.addEventListener('click', e => {
      const href = a.getAttribute('href') || '';
      if (!href.startsWith('#')) return;
      e.preventDefault();
      const id = decodeURIComponent(href.slice(1));
      const el = document.getElementById(id);
      if (el) {
        const y = el.getBoundingClientRect().top + window.pageYOffset - stickyOffset();
        window.scrollTo({ top: y, behavior: 'smooth' });
        history.replaceState(null, '', href);
        el.classList.add('flash-border');
        setTimeout(() => el.classList.remove('flash-border'), 900);
      }
    });
  });

  // Scroll-to-top button
  const topBtn = document.createElement('button');
  topBtn.className = 'scroll-top';
  topBtn.type = 'button';
  topBtn.setAttribute('aria-label', 'Back to top');
  topBtn.innerHTML = '&uarr;';
  document.body.appendChild(topBtn);
  topBtn.addEventListener('click', jumpToTop);
  const onScroll = () => { topBtn.classList.toggle('is-visible', window.pageYOffset > 140); };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  // Initial
  applyFilter();
});
