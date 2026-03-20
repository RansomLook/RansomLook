document.addEventListener('DOMContentLoaded', () => {
  const $tbody  = document.getElementById('log-body');
  const $search = document.getElementById('log-search');
  const $action = document.getElementById('action-filter');
  const $user   = document.getElementById('user-filter');
  const $from   = document.getElementById('from-date');
  const $to     = document.getElementById('to-date');
  const $reset  = document.getElementById('reset-filters');

  const rows = [...$tbody.querySelectorAll('tr')];

  // Convert all UTC timestamps to local timezone
  document.querySelectorAll('.utc-time').forEach(el => {
    const iso = el.getAttribute('datetime');
    if (!iso) return;
    const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
    if (isNaN(d)) return;
    el.textContent = d.toLocaleString(undefined, {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
  });

  function parseDateOnly(s) {
    if (!s) return null;
    const m = String(s).trim().match(/^(\d{4}-\d{2}-\d{2})/);
    if (!m) return null;
    const d = new Date(m[1] + 'T00:00:00Z');
    return isNaN(d) ? null : d;
  }

  function update() {
    const q      = ($search.value || '').toLowerCase();
    const wantA  = ($action.value || '');
    const wantU  = ($user.value || '');
    const dFrom  = $from.value ? new Date($from.value + 'T00:00:00Z') : null;
    const dTo    = $to.value   ? new Date($to.value   + 'T23:59:59Z') : null;

    rows.forEach(tr => {
      const action  = tr.dataset.action || '';
      const user    = tr.dataset.user || '';
      const ts      = parseDateOnly(tr.dataset.ts);
      const text    = (tr.querySelector('.log-details')?.textContent || '').toLowerCase()
                    + ' ' + (tr.querySelector('.monospace')?.textContent || '').toLowerCase();

      let ok = true;
      if (q && !text.includes(q) && !action.toLowerCase().includes(q)) ok = false;
      if (ok && wantA && action !== wantA) ok = false;
      if (ok && wantU && user !== wantU) ok = false;
      if (ok && dFrom && ts && ts < dFrom) ok = false;
      if (ok && dTo   && ts && ts > dTo)   ok = false;

      tr.style.display = ok ? '' : 'none';
    });
  }

  [$search, $action, $user].forEach(el => el.addEventListener('input', update));
  [$from, $to].forEach(el => el.addEventListener('change', update));

  // Export visible rows as CSV (US format: comma-separated, MM/DD/YYYY dates)
  document.getElementById('export-csv').addEventListener('click', () => {
    const csvEscape = s => '"' + String(s).replace(/"/g, '""') + '"';
    const header = ['Date (UTC)','User','Action','Target','Details'];
    const lines = [header.map(csvEscape).join(',')];

    rows.forEach(tr => {
      if (tr.style.display === 'none') return;
      const ts = tr.dataset.ts || '';
      // Format as MM/DD/YYYY HH:MM:SS for US locale
      let dateFmt = ts;
      const m = ts.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}:\d{2}:\d{2})/);
      if (m) dateFmt = m[2] + '/' + m[3] + '/' + m[1] + ' ' + m[4];

      const user   = tr.dataset.user || '';
      const action = tr.dataset.action || '';
      const target = tr.querySelector('.monospace')?.textContent.trim() || '';
      const details = tr.querySelector('.log-details')?.textContent.trim() || '';
      lines.push([dateFmt, user, action, target, details].map(csvEscape).join(','));
    });

    const blob = new Blob([lines.join('\r\n')], {type: 'text/csv;charset=utf-8'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'audit_log.csv';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1200);
  });

  $reset.addEventListener('click', () => {
    $search.value = '';
    $action.value = '';
    $user.value   = '';
    $from.value   = '';
    $to.value     = '';
    rows.forEach(r => r.style.display = '');
  });

  update();
});
