/* chips-filter.js — generic chip grid filter
 *
 * Usage: add data attributes to HTML:
 *   <input  id="XXX-filter" …>
 *   <button class="input-clear" …>
 *   <span  id="flt-count"></span>
 *   <div   id="XXX-grid" class="auto-grid"> … .group-chip[data-name] … </div>
 *
 * Then in template:
 *   <script type="application/json" id="chips-config">{"inputId":"XXX-filter","gridId":"XXX-grid","label":"actors"}</script>
 */
(function(){
  var cfgEl = document.getElementById('chips-config');
  if (!cfgEl) return;
  var cfg;
  try { cfg = JSON.parse(cfgEl.textContent); } catch(e){ return; }

  var input    = document.getElementById(cfg.inputId);
  var clearBtn = document.querySelector('.input-clear');
  var countEl  = document.getElementById('flt-count');
  var items    = Array.from(document.querySelectorAll('#' + cfg.gridId + ' .group-chip'));
  var label    = cfg.label || 'items';
  if (!input) return;

  function apply(){
    var q = input.value.trim().toLowerCase();
    var n = 0;
    items.forEach(function(a){
      var tokens = (a.dataset.name || '').toLowerCase();
      var match = !q || tokens.indexOf(q) !== -1;
      a.style.display = match ? '' : 'none';
      if (match) n++;
    });
    if (countEl) countEl.textContent = n + ' ' + label;
  }

  var t;
  input.addEventListener('input', function(){ clearTimeout(t); t = setTimeout(apply, 120); });
  if (clearBtn) clearBtn.addEventListener('click', function(){ input.value = ''; apply(); input.focus(); });
  apply();
})();
