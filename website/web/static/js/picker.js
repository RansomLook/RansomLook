/**
 * Shared picker logic for admin pages with type-toggle + search filter.
 * Works with: edit.html, addpost.html, logo.html
 *
 * Expects DOM elements:
 *   - Radio inputs with name="type" (id="t-groups", "t-markets", optionally "t-actors")
 *   - Forms with id="form-groups", "form-markets", optionally "form-actors"
 *   - Search input with id="picker-search"
 */
document.addEventListener('DOMContentLoaded', () => {
  const searchBox = document.getElementById('picker-search');
  if (!searchBox) return;

  // Discover tabs and forms dynamically
  const tabs = [...document.querySelectorAll('input[name="type"]')];
  const forms = tabs.map(t => document.getElementById('form-' + t.id.replace('t-', '')));

  function applyToggle() {
    tabs.forEach((t, i) => {
      if (forms[i]) forms[i].style.display = t.checked ? '' : 'none';
    });
    searchBox.value = '';
    filterSelect('');
  }

  tabs.forEach(t => t.addEventListener('change', applyToggle));
  applyToggle();

  function filterSelect(q) {
    q = (q || '').toLowerCase().trim();
    const visibleForm = forms.find(f => f && f.style.display !== 'none');
    if (!visibleForm) return;
    const select = visibleForm.querySelector('select');
    if (!select) return;

    for (const opt of select.options) {
      const txt = (opt.textContent || '').toLowerCase();
      opt.hidden = q && !txt.includes(q);
    }

    if (select.selectedOptions.length && select.selectedOptions[0].hidden) {
      const firstVisible = [...select.options].find(o => !o.hidden);
      if (firstVisible) firstVisible.selected = true;
    }
  }

  searchBox.addEventListener('input', e => filterSelect(e.target.value));
});
