document.addEventListener('DOMContentLoaded', () => {
  RL.colorDots();

  /* Relative time on Latest posts */
  const renderDates = () => {
    const now = Date.now();
    for (const $t of document.querySelectorAll('.insight-time[data-ts]')) {
      const raw = $t.dataset.ts;
      const iso = raw.includes('T') ? raw : raw.replace(' ', 'T') + 'Z';
      const d = new Date(iso);
      if (isNaN(d)) continue;
      $t.textContent = RL.fmtRel(now - d.getTime());
    }
  };
  renderDates();
  setInterval(renderDates, 60000);
});
