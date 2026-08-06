document.addEventListener('DOMContentLoaded', () => {
  const $search = document.getElementById('log-search');
  const $action = document.getElementById('action-filter');
  const $user   = document.getElementById('user-filter');
  const $from   = document.getElementById('from-date');
  const $to     = document.getElementById('to-date');

  // Convert all UTC timestamps to local timezone (filtering/pagination is server-side)
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

  // Export the full audit log matching current filters (server-side, all pages)
  document.getElementById('export-csv').addEventListener('click', () => {
    const params = new URLSearchParams();
    if ($search.value) params.set('q', $search.value);
    if ($action.value) params.set('action', $action.value);
    if ($user.value)   params.set('user', $user.value);
    if ($from.value)   params.set('from', $from.value);
    if ($to.value)     params.set('to', $to.value);
    window.location.href = exportUrl + (params.toString() ? '?' + params.toString() : '');
  });
});
