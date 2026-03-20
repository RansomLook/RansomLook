/* ====================================================================
 *  Theme toggle (dark / light) — runs immediately to avoid FOUC
 * ==================================================================== */
(function() {
  const html = document.documentElement;
  const stored = document.cookie.replace(/(?:(?:^|.*;\s*)theme\s*=\s*([^;]*).*$)|^.*$/, '$1');
  if (stored) html.className = html.className.replace(/\b(dark|light)\b/, stored);

  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.querySelector('.theme-toggle');
    if (!btn) return;
    btn.addEventListener('click', () => {
      const next = html.classList.contains('light') ? 'dark' : 'light';
      html.classList.remove('dark', 'light');
      html.classList.add(next);
      document.cookie = 'theme=' + next + ';path=/;max-age=31536000;SameSite=Strict';
    });
  });
})();

document.addEventListener('DOMContentLoaded', () => {
  /* ====================================================================
   *  Nav toggle (burger menu)
   * ==================================================================== */
  const toggle   = document.querySelector('.nav-toggle');
  const navLinks = document.querySelector('.nav-links');

  if (toggle && navLinks) {
    const openNav  = () => { navLinks.classList.add('active'); document.body.classList.add('menu-open'); toggle.setAttribute('aria-expanded','true'); };
    const closeNav = () => { navLinks.classList.remove('active'); document.body.classList.remove('menu-open'); toggle.setAttribute('aria-expanded','false'); };

    toggle.addEventListener('click', e => {
      e.stopPropagation();
      navLinks.classList.contains('active') ? closeNav() : openNav();
    });

    document.addEventListener('click', e => {
      if (navLinks.classList.contains('active') && !navLinks.contains(e.target) && e.target !== toggle) closeNav();
    });
  }

  /* ====================================================================
   *  Language dropdown
   * ==================================================================== */
  const langBtn  = document.querySelector('.lang-btn');
  const langMenu = document.querySelector('.lang-menu');

  if (langBtn && langMenu) {
    const closeLang = () => { langMenu.classList.remove('open'); langBtn.setAttribute('aria-expanded','false'); };

    langBtn.addEventListener('click', e => {
      e.stopPropagation();
      const open = !langMenu.classList.contains('open');
      langMenu.classList.toggle('open', open);
      langBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });

    document.addEventListener('click', e => {
      if (langMenu.classList.contains('open') && !langMenu.contains(e.target) && e.target !== langBtn) closeLang();
    });
  }

  /* ====================================================================
   *  Search modal (Ctrl/Cmd + K)
   * ==================================================================== */
  const searchModal = document.getElementById('searchModal');
  if (searchModal) {
    const openBtns = document.querySelectorAll('.search-open');
    const closers  = searchModal.querySelectorAll('[data-close]');
    const input    = searchModal.querySelector('.rl-search-input');

    function openSearch() {
      searchModal.hidden = false;
      document.body.style.overflow = 'hidden';
      openBtns.forEach(b => b.setAttribute('aria-expanded', 'true'));
      setTimeout(() => input && input.focus(), 0);
    }
    function closeSearch() {
      searchModal.hidden = true;
      document.body.style.overflow = '';
      openBtns.forEach(b => b.setAttribute('aria-expanded', 'false'));
    }

    openBtns.forEach(b => b.addEventListener('click', openSearch));
    closers.forEach(el => el.addEventListener('click', closeSearch));
    searchModal.addEventListener('keydown', e => { if (e.key === 'Escape') closeSearch(); });
    searchModal.addEventListener('click', e => { if (e.target.classList.contains('rl-modal__backdrop')) closeSearch(); });

    document.addEventListener('keydown', e => {
      const isMac = navigator.platform.toUpperCase().includes('MAC');
      if ((isMac && e.metaKey && e.key.toLowerCase() === 'k') || (!isMac && e.ctrlKey && e.key.toLowerCase() === 'k')) {
        e.preventDefault();
        if (searchModal.hidden) openSearch(); else closeSearch();
      }
    });
  }

  /* ====================================================================
   *  Shared lightbox (for pages with #imgModal + .open-shot links)
   * ==================================================================== */
  const imgModal = document.getElementById('imgModal');
  const shotLinks = Array.from(document.querySelectorAll('a.open-shot'));

  if (imgModal && shotLinks.length) {
    const img     = document.getElementById('imgModalImg');
    const caption = document.getElementById('imgModalCaption');
    const closeEls = imgModal.querySelectorAll('[data-close], .rl-modal__backdrop');
    const prevBtn = imgModal.querySelector('.img-prev');
    const nextBtn = imgModal.querySelector('.img-next');
    let index = 0;

    function openAt(i) {
      index = (i + shotLinks.length) % shotLinks.length;
      const a = shotLinks[index];
      img.src = a.getAttribute('href');
      img.alt = (a.querySelector('img') && a.querySelector('img').alt) || a.getAttribute('data-caption') || '';
      caption.textContent = a.getAttribute('data-caption') || img.alt || '';
      imgModal.hidden = false;
      document.body.style.overflow = 'hidden';
      imgModal.setAttribute('tabindex', '-1');
      imgModal.focus();
    }
    function closeLB() {
      imgModal.hidden = true;
      document.body.style.overflow = '';
      img.src = '';
    }
    function next() { openAt(index + 1); }
    function prev() { openAt(index - 1); }

    shotLinks.forEach((a, i) => a.addEventListener('click', e => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
      e.preventDefault();
      openAt(i);
    }));
    closeEls.forEach(el => el.addEventListener('click', closeLB));
    if (nextBtn) nextBtn.addEventListener('click', next);
    if (prevBtn) prevBtn.addEventListener('click', prev);
    imgModal.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeLB();
      if (e.key === 'ArrowRight') next();
      if (e.key === 'ArrowLeft') prev();
    });
  }
});
