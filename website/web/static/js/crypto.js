/* ====================================================================
 *  Crypto detail page — sorting, filtering, CSV export
 * ==================================================================== */

/* ── CSV helpers ── */
function csvEscape(val) {
  if (val == null) return '';
  const s = String(val);
  return s.includes(',') || s.includes('"') || s.includes('\n') ? '"' + s.replace(/"/g, '""') + '"' : s;
}

function buildCSV(rows) {
  const header = 'blockchain,address,direction,counterpart,counterpart_group,tx_hash,amount,amountUSD,time,source\n';
  return header + rows.join('\n');
}

function downloadCSV(content, filename) {
  const blob = new Blob([content], {type: 'text/csv;charset=utf-8;'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

function tableToRows(table, chain, address) {
  const rows = [];
  table.querySelectorAll('tbody tr').forEach(tr => {
    if (tr.style.display === 'none') return;
    const cells = tr.querySelectorAll('td');
    if (cells.length < 7) return;
    const txLink = cells[0].querySelector('a, span[title]');
    const fullHash = txLink && txLink.getAttribute('title') ? txLink.getAttribute('title') : cells[0].textContent.trim();
    const date = cells[1].textContent.trim().replace(/\s+/g, ' ');
    const dir = cells[2].textContent.trim();
    const cpEl = cells[3];
    const cpAddr = (cpEl.querySelector('a') || cpEl).textContent.trim();
    const cpGroup = cpEl.querySelector('.link-tag') ? cpEl.querySelector('.link-tag').textContent.trim() : '';
    const amount = cells[4].textContent.trim();
    const usd = cells[5].textContent.trim().replace('$', '');
    const source = cells[6].textContent.trim();
    rows.push([chain, address, dir, cpAddr, cpGroup, fullHash, amount, usd, date, source].map(csvEscape).join(','));
  });
  return rows;
}

/* ── Export per wallet ── */
function exportWalletCSV(chain, address) {
  const group = (document.querySelector('[data-crypto-group]') || {}).dataset?.cryptoGroup || 'export';
  const details = document.querySelectorAll('.level-2');
  for (const d of details) {
    const code = d.querySelector('code.mono');
    if (code && code.textContent.trim() === address) {
      const table = d.querySelector('table');
      if (!table) return;
      const rows = tableToRows(table, chain, address);
      downloadCSV(buildCSV(rows), group + '_' + address.substring(0, 12) + '.csv');
      return;
    }
  }
}

/* ── Export all group ── */
function exportGroupCSV() {
  const group = (document.querySelector('[data-crypto-group]') || {}).dataset?.cryptoGroup || 'export';
  const allRows = [];
  document.querySelectorAll('.level-1').forEach(l1 => {
    const chain = l1.querySelector('.mono') ? l1.querySelector('.mono').textContent.trim() : '';
    l1.querySelectorAll('.level-2').forEach(l2 => {
      const code = l2.querySelector('code.mono');
      const address = code ? code.textContent.trim() : '';
      const table = l2.querySelector('table');
      if (table) {
        allRows.push(...tableToRows(table, chain, address));
      }
    });
  });
  downloadCSV(buildCSV(allRows), group + '_all_transactions.csv');
}

/* ── Sorting ── */
document.addEventListener('click', function(e) {
  const th = e.target.closest('.sortable');
  if (!th) return;
  const table = th.closest('table');
  const tbody = table.querySelector('tbody');
  const col = parseInt(th.dataset.col);
  const type = th.dataset.type;
  const rows = Array.from(tbody.querySelectorAll('tr'));

  const cur = th.dataset.sort || '';
  const dir = cur === 'asc' ? 'desc' : 'asc';
  table.querySelectorAll('.sortable').forEach(s => { s.dataset.sort = ''; s.querySelector('.sort-arrow').textContent = ''; });
  th.dataset.sort = dir;
  th.querySelector('.sort-arrow').textContent = dir === 'asc' ? ' \u25B2' : ' \u25BC';

  rows.sort((a, b) => {
    const cellA = a.querySelectorAll('td')[col];
    const cellB = b.querySelectorAll('td')[col];
    if (!cellA || !cellB) return 0;
    let va = cellA.textContent.trim().replace(/[$,]/g, '');
    let vb = cellB.textContent.trim().replace(/[$,]/g, '');
    if (type === 'number') {
      va = parseFloat(va) || 0;
      vb = parseFloat(vb) || 0;
    }
    if (va < vb) return dir === 'asc' ? -1 : 1;
    if (va > vb) return dir === 'asc' ? 1 : -1;
    return 0;
  });
  rows.forEach(r => tbody.appendChild(r));
});

/* Wallet CSV buttons: the address is read from data-* instead of being
   interpolated into an inline handler, so it is never parsed as code. */
document.addEventListener('click', function(e) {
  const btn = e.target.closest('.export-wallet');
  if (!btn) return;
  e.stopPropagation();
  exportWalletCSV(btn.dataset.chain || '', btn.dataset.address || '');
});

/* ── Filters ── */
function applyFilters(btn) {
  const card = btn.closest('.table-card');
  const from = card.querySelector('.filter-from').value;
  const to = card.querySelector('.filter-to').value;
  const min = parseFloat(card.querySelector('.filter-min').value);
  const max = parseFloat(card.querySelector('.filter-max').value);
  const dirVal = card.querySelector('.filter-dir').value;
  const rows = card.querySelectorAll('tbody tr');

  rows.forEach(tr => {
    const cells = tr.querySelectorAll('td');
    if (cells.length < 7) return;
    const date = cells[1].textContent.trim().replace(/\s+/g, ' ').substring(0, 10);
    const dir = cells[2].textContent.trim();
    const amt = parseFloat(cells[4].textContent.trim()) || 0;
    let show = true;
    if (from && date < from) show = false;
    if (to && date > to) show = false;
    if (!isNaN(min) && amt < min) show = false;
    if (!isNaN(max) && amt > max) show = false;
    if (dirVal && dir !== dirVal) show = false;
    tr.style.display = show ? '' : 'none';
  });
}

function clearFilters(btn) {
  const card = btn.closest('.table-card');
  card.querySelectorAll('.tx-filters input, .tx-filters select').forEach(el => el.value = '');
  card.querySelectorAll('tbody tr').forEach(tr => tr.style.display = '');
}
