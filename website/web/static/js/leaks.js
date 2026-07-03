/* leaks.js — modal + table filter for leaks page */
(function(){
  /* ---- Modal ---- */
  var modal = document.getElementById('leak-modal');
  var tbody = document.getElementById('leak-modal-tbody');
  var foot  = document.getElementById('leak-modal-footnote');

  function esc(val){
    if (val === null || val === undefined) return '';
    return String(val).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  function openModal(){
    modal.setAttribute('aria-hidden','false');
    document.body.classList.add('modal-open');
  }
  function closeModal(){
    modal.setAttribute('aria-hidden','true');
    document.body.classList.remove('modal-open');
    tbody.innerHTML = '';
    foot.textContent = '';
  }

  modal.addEventListener('click', function(e){
    if (e.target.matches('[data-dismiss="modal"]')){ e.preventDefault(); closeModal(); }
  });
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape') closeModal();
  });

  function withJsonParam(url){
    return url + (url.indexOf('?') !== -1 ? '&' : '?') + 'format=json';
  }

  function renderRow(group){
    var size = group.size != null ? group.size : '';
    var records = group.records != null ? group.records : '';
    var indexed = group.indexed != null ? group.indexed : '';
    var cols = group.columns != null ? group.columns : '';
    if (Array.isArray(cols)) cols = cols.join(', ');
    var tr = document.createElement('tr');
    tr.innerHTML =
      '<td><center>'+esc(size)+'</center></td>'+
      '<td>'+esc(records)+'</td>'+
      '<td>'+esc(indexed)+'</td>'+
      '<td style="word-break:break-all">'+esc(cols)+'</td>';
    return tr;
  }

  document.addEventListener('click', function(e){
    var a = e.target.closest('a.leak-link');
    if (!a) return;
    e.preventDefault();
    var url = a.getAttribute('href');

    fetch(withJsonParam(url), { headers: { 'Accept': 'application/json' } })
      .then(function(res){
        if (!res.ok) throw new Error('not ok');
        var ct = (res.headers.get('content-type') || '').toLowerCase();
        if (ct.indexOf('application/json') === -1) throw new Error('not json');
        return res.json();
      })
      .then(function(payload){
        var g = payload.group || payload.data || payload;
        if (!g || typeof g !== 'object') throw new Error('bad payload');
        tbody.innerHTML = '';
        tbody.appendChild(renderRow(g));
        foot.textContent = payload.name ? 'Source: ' + payload.name : '';
        openModal();
      })
      .catch(function(){
        window.location.href = url;
      });
  });

  /* ---- Table filter ---- */
  var qInput   = document.getElementById('flt-q');
  var clearBtn = document.querySelector('.input-clear');
  var table    = document.getElementById('leaks-table');
  if (!table) return;
  var trows    = Array.from(table.querySelector('tbody').querySelectorAll('tr'));
  var countEl  = document.getElementById('flt-count');

  function apply(){
    var q = (qInput ? qInput.value : '').trim().toLowerCase();
    var visible = 0;
    trows.forEach(function(tr){
      var show = !q || tr.textContent.toLowerCase().indexOf(q) !== -1;
      tr.style.display = show ? '' : 'none';
      if (show) visible++;
    });
    if (countEl) countEl.textContent = visible + ' leaks';
  }

  var t;
  if (qInput) qInput.addEventListener('input', function(){ clearTimeout(t); t = setTimeout(apply, 120); });
  if (clearBtn) clearBtn.addEventListener('click', function(){ qInput.value = ''; apply(); qInput.focus(); });

  /* ---- Table sort ---- */
  var tbodyEl = table.querySelector('tbody');
  var headers = Array.from(table.querySelectorAll('thead th.sortable'));

  function cellText(tr, idx){
    var td = tr.children[idx];
    return td ? td.textContent.trim() : '';
  }

  function sortBy(th){
    var idx  = th.cellIndex;
    var type = th.getAttribute('data-type') || 'text';
    // Toggle: same column flips direction, else start descending.
    var cur  = th.getAttribute('aria-sort');
    var asc  = cur === 'ascending' ? false : (cur === 'descending' ? true : false);
    var dir  = asc ? 1 : -1;

    trows.sort(function(a, b){
      var va = cellText(a, idx), vb = cellText(b, idx);
      if (type === 'num'){
        return ((parseFloat(va.replace(/[^0-9.\-]/g, '')) || 0) -
                (parseFloat(vb.replace(/[^0-9.\-]/g, '')) || 0)) * dir;
      }
      // 'text' and 'date' (ISO date strings sort lexicographically = chronologically)
      return va.localeCompare(vb, undefined, { numeric: true }) * dir;
    });

    trows.forEach(function(tr){ tbodyEl.appendChild(tr); });

    headers.forEach(function(h){ h.setAttribute('aria-sort', 'none'); });
    th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
  }

  headers.forEach(function(th){
    th.addEventListener('click', function(){ sortBy(th); });
  });

  // Default: newest detections first (Detection column, descending).
  var dateHeader = headers.find(function(h){ return h.getAttribute('data-type') === 'date'; });
  if (dateHeader) sortBy(dateHeader);

  apply();
})();
