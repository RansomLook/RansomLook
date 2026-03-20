document.addEventListener('DOMContentLoaded', () => {
  /* ====================================================================
   *  Listing: search + sort + counter
   * ==================================================================== */
  const qInput   = document.getElementById('flt-q');
  const clearBtn = document.querySelector('.input-clear');
  const countEl  = document.getElementById('flt-count');
  const table    = document.querySelector('table[aria-label="RF dumps"]');
  const tbody    = table.querySelector('tbody');
  const rows     = [...tbody.querySelectorAll('tr')];

  let sortKey = 'date';
  let sortDir = -1;
  const collator = new Intl.Collator(undefined, { sensitivity: 'base', numeric: true });

  function getRowData(tr) {
    const nameCell = tr.querySelector('td:nth-child(1)');
    const descCell = tr.querySelector('td:nth-child(2)');
    const dateCell = tr.querySelector('td:nth-child(3)');
    return {
      name:     (nameCell?.textContent || '').trim(),
      desc:     (descCell?.textContent || '').trim(),
      dateText: (dateCell?.textContent || '').trim(),
      dateKey:  (dateCell?.textContent || '').trim(),
      tr
    };
  }

  function updateCount(visible) {
    if (countEl) countEl.textContent = visible + ' dumps';
  }

  function apply() {
    const q = (qInput?.value || '').trim().toLowerCase();
    let list = rows.map(getRowData);

    if (q) {
      list = list.filter(r => r.name.toLowerCase().includes(q) || r.desc.toLowerCase().includes(q));
    }

    if (sortKey) {
      list.sort((a, b) => {
        let cmp = 0;
        if (sortKey === 'name') cmp = collator.compare(a.name, b.name);
        else if (sortKey === 'date') cmp = a.dateKey.localeCompare(b.dateKey);
        return cmp * sortDir;
      });
    }

    const frag = document.createDocumentFragment();
    list.forEach(item => frag.appendChild(item.tr));
    tbody.innerHTML = '';
    tbody.appendChild(frag);
    updateCount(list.length);
  }

  function setSort(key) {
    if (sortKey === key) sortDir *= -1;
    else { sortKey = key; sortDir = 1; }

    document.querySelectorAll('.th-sort').forEach(btn => {
      const state = (btn.dataset.sort === sortKey) ? (sortDir === 1 ? 'ascending' : 'descending') : 'none';
      btn.setAttribute('aria-sort', state);
      const ind = btn.querySelector('.ind');
      if (ind) ind.textContent = state === 'ascending' ? '\u25B2' : state === 'descending' ? '\u25BC' : '\u2195';
    });
    apply();
  }

  document.querySelectorAll('.th-sort').forEach(btn => {
    btn.addEventListener('click', () => setSort(btn.dataset.sort));
    btn.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSort(btn.dataset.sort); } });
  });

  clearBtn?.addEventListener('click', () => { qInput.value = ''; apply(); qInput.focus(); });
  let t;
  qInput?.addEventListener('input', () => { clearTimeout(t); t = setTimeout(apply, 120); });

  apply();

  /* ====================================================================
   *  Modal: fetch & display RF dump details
   * ==================================================================== */
  const modal      = document.getElementById('rf-modal');
  const titleEl    = document.getElementById('rf-modal-title');
  const headBody   = document.getElementById('rf-head-tbody');
  const extraBody  = document.getElementById('rf-extra-tbody');
  const breachBody = document.getElementById('rf-breaches-tbody');

  function esc(val) {
    if (val === null || val === undefined) return '';
    return String(val).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function openModal()  { modal.setAttribute('aria-hidden', 'false'); document.body.classList.add('modal-open'); }
  function closeModal() {
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
    headBody.innerHTML   = '<tr><td colspan="3">Loading\u2026</td></tr>';
    extraBody.innerHTML  = '<tr><td colspan="4">\u2014</td></tr>';
    breachBody.innerHTML = '<tr><td colspan="2">\u2014</td></tr>';
  }

  // Delegated click for rf-link
  document.addEventListener('click', async e => {
    const a = e.target.closest('.rf-link');
    if (!a) return;
    e.preventDefault();

    const url  = a.getAttribute('href');
    const name = a.dataset.rfName || 'RF dump';

    try {
      const res = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!res.ok) throw new Error('Fetch failed');
      const payload = await res.json();
      const g = payload.group || payload.data || payload;

      titleEl.textContent = name;

      headBody.innerHTML =
        '<tr><td>' + esc(g.name ?? name) + '</td>' +
        '<td>' + esc(g.source ?? '\u2014') + '</td>' +
        '<td><center>' + esc((g.downloaded || '').toString().split('T')[0]) + '</center></td></tr>';

      let columns = g.columns ?? '\u2014';
      if (Array.isArray(columns)) columns = columns.join(', ');

      extraBody.innerHTML =
        '<tr><td><center>' + esc(g.size ?? '\u2014') + '</center></td>' +
        '<td>' + esc(g.records ?? '\u2014') + '</td>' +
        '<td>' + esc(g.indexed ?? '\u2014') + '</td>' +
        '<td>' + esc(columns) + '</td></tr>';

      if (Array.isArray(g.breaches) && g.breaches.length && g.breaches[0] && typeof g.breaches[0] === 'object') {
        const obj = g.breaches[0];
        breachBody.innerHTML = Object.keys(obj).map(k =>
          '<tr><td>' + esc(k) + '</td><td>' + esc(String(obj[k])) + '</td></tr>'
        ).join('') || '<tr><td colspan="2">\u2014</td></tr>';
      } else {
        breachBody.innerHTML = '<tr><td colspan="2">\u2014</td></tr>';
      }

      openModal();
    } catch (err) {
      console.error(err);
      headBody.innerHTML = '<tr><td colspan="3" style="color:#fca5a5;">Unable to load details.</td></tr>';
      extraBody.innerHTML  = '<tr><td colspan="4">\u2014</td></tr>';
      breachBody.innerHTML = '<tr><td colspan="2">\u2014</td></tr>';
      window.location.href = url.replace('?format=json', '');
    }
  });

  // Close handlers
  document.addEventListener('click', e => {
    if (e.target.matches('[data-dismiss="modal"], .modal-backdrop')) { e.preventDefault(); closeModal(); }
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
});
