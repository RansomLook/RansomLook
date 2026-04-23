document.addEventListener('DOMContentLoaded', () => {
  const groups = JSON.parse(document.getElementById('th-groups-data').textContent);

  document.querySelectorAll('.th-group-search').forEach(search => {
    const hidden = document.getElementById(search.dataset.target);
    const wrap = search.closest('div');
    const dropdown = wrap.querySelector('.th-group-dropdown');
    const results = wrap.querySelector('.th-group-results');
    if (!hidden || !dropdown || !results) return;

    function render(filter) {
      const q = (filter || '').toLowerCase();
      const matches = q ? groups.filter(n => n.toLowerCase().includes(q)) : groups;
      results.innerHTML = '';

      if (matches.length === 0) {
        results.innerHTML = '<div class="search-dropdown-empty">No match</div>';
        return;
      }
      const max = 50;
      matches.slice(0, max).forEach(name => {
        const div = document.createElement('div');
        div.className = 'search-dropdown-item';
        div.textContent = name;
        div.addEventListener('mousedown', (e) => {
          e.preventDefault();
          select(name);
        });
        results.appendChild(div);
      });
      if (matches.length > max) {
        const more = document.createElement('div');
        more.className = 'search-dropdown-empty';
        more.textContent = `${matches.length - max} more — refine your search`;
        results.appendChild(more);
      }
    }

    function select(name) {
      hidden.value = name;
      search.value = name;
      dropdown.setAttribute('hidden', '');
    }

    search.addEventListener('focus', () => { render(search.value); dropdown.removeAttribute('hidden'); });
    search.addEventListener('input', () => {
      hidden.value = '';
      render(search.value);
      dropdown.removeAttribute('hidden');
    });
    search.addEventListener('blur', () => setTimeout(() => dropdown.setAttribute('hidden', ''), 150));

    search.addEventListener('keydown', (e) => {
      const items = [...results.querySelectorAll('.search-dropdown-item')];
      const active = results.querySelector('.search-dropdown-item.active');
      let idx = items.indexOf(active);

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (active) active.classList.remove('active');
        idx = Math.min(idx + 1, items.length - 1);
        if (items[idx]) { items[idx].classList.add('active'); items[idx].scrollIntoView({block:'nearest'}); }
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (active) active.classList.remove('active');
        idx = Math.max(idx - 1, 0);
        if (items[idx]) { items[idx].classList.add('active'); items[idx].scrollIntoView({block:'nearest'}); }
      } else if (e.key === 'Enter') {
        if (active) { e.preventDefault(); select(active.textContent); }
      } else if (e.key === 'Escape') {
        dropdown.setAttribute('hidden', '');
      }
    });
  });
});
