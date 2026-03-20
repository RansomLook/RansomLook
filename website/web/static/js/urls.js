document.addEventListener('DOMContentLoaded', () => {
  const data = JSON.parse(document.getElementById('urls-data').textContent);
  const dbSelect = document.getElementById('database');
  const searchInput = document.getElementById('name-search');
  const hiddenInput = document.getElementById('name');
  const dropdown = document.getElementById('name-dropdown');
  const resultsDiv = document.getElementById('name-results');
  const selectedDiv = document.getElementById('name-selected');
  const urlsArea = document.getElementById('urls');
  const urlCount = document.getElementById('url-count');

  function getNames() {
    return dbSelect.value === '3' ? data.markets : data.groups;
  }

  function render(filter) {
    const names = getNames();
    const q = (filter || '').toLowerCase();
    const matches = q ? names.filter(n => n.toLowerCase().includes(q)) : names;
    resultsDiv.innerHTML = '';

    if (matches.length === 0) {
      resultsDiv.innerHTML = '<div class="search-dropdown-empty">No match</div>';
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
      resultsDiv.appendChild(div);
    });

    if (matches.length > max) {
      const more = document.createElement('div');
      more.className = 'search-dropdown-empty';
      more.textContent = `${matches.length - max} more — refine your search`;
      resultsDiv.appendChild(more);
    }
  }

  function select(name) {
    hiddenInput.value = name;
    searchInput.value = name;
    selectedDiv.textContent = '';
    close();
  }

  function open() { dropdown.removeAttribute('hidden'); }
  function close() { dropdown.setAttribute('hidden', ''); }

  searchInput.addEventListener('focus', () => {
    render(searchInput.value);
    open();
  });

  searchInput.addEventListener('input', () => {
    hiddenInput.value = '';
    selectedDiv.textContent = '';
    render(searchInput.value);
    open();
  });

  searchInput.addEventListener('blur', () => {
    setTimeout(close, 150);
  });

  // Keyboard nav
  searchInput.addEventListener('keydown', (e) => {
    const items = [...resultsDiv.querySelectorAll('.search-dropdown-item')];
    const active = resultsDiv.querySelector('.search-dropdown-item.active');
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
      e.preventDefault();
      if (active) { select(active.textContent); }
    } else if (e.key === 'Escape') {
      close();
    }
  });

  // Reset when DB changes
  dbSelect.addEventListener('change', () => {
    searchInput.value = '';
    hiddenInput.value = '';
    selectedDiv.textContent = '';
    render('');
  });

  // URL counter
  function updateCount() {
    const lines = (urlsArea.value || '').split(/\r?\n/).filter(l => l.trim()).length;
    urlCount.textContent = lines + ' URL' + (lines !== 1 ? 's' : '');
  }
  urlsArea.addEventListener('input', updateCount);
  updateCount();
});
