/* compare.js — toggle, search, swap, charts for compare page */
(function(){
  var rGroups  = document.getElementById('t-groups');
  var rMarkets = document.getElementById('t-markets');
  var fGroups  = document.getElementById('form-groups');
  var fMarkets = document.getElementById('form-markets');

  function applyToggle(){
    var gOn = rGroups.checked;
    fGroups.style.display  = gOn ? '' : 'none';
    fMarkets.style.display = gOn ? 'none' : '';
    ['gsearchA','gsearchB','msearchA','msearchB'].forEach(function(id){
      var el = document.getElementById(id); if(el) el.value = '';
    });
    [fGroups, fMarkets].forEach(function(form){
      form.querySelectorAll('select').forEach(function(sel){
        Array.from(sel.options).forEach(function(o){ o.hidden = false; });
      });
    });
  }
  rGroups.addEventListener('change', applyToggle);
  rMarkets.addEventListener('change', applyToggle);
  applyToggle();

  function wireSearch(inputId, selectId){
    var input = document.getElementById(inputId);
    var select = document.getElementById(selectId);
    if(!input || !select) return;
    input.addEventListener('input', function(){
      var q = (input.value || '').toLowerCase().trim();
      for(var i = 0; i < select.options.length; i++){
        var opt = select.options[i];
        var txt = (opt.textContent || '').toLowerCase();
        opt.hidden = q ? txt.indexOf(q) === -1 : false;
      }
      if (select.selectedOptions.length && select.selectedOptions[0].hidden){
        var first = Array.from(select.options).find(function(o){ return !o.hidden && !o.disabled; });
        if (first) first.selected = true;
      }
    });
  }

  wireSearch('gsearchA','ga'); wireSearch('gsearchB','gb');
  wireSearch('msearchA','ma'); wireSearch('msearchB','mb');

  function hookSwap(btnId, aId, bId){
    var btn = document.getElementById(btnId);
    var aSel = document.getElementById(aId);
    var bSel = document.getElementById(bId);
    if (!btn || !aSel || !bSel) return;
    btn.addEventListener('click', function(){
      var va = aSel.value, vb = bSel.value;
      aSel.value = vb || '';
      bSel.value = va || '';
    });
  }
  hookSwap('swap-g', 'ga', 'gb');
  hookSwap('swap-m', 'ma', 'mb');

  /* Charts — read data from JSON block if present */
  var dataEl = document.getElementById('compare-data');
  if (!dataEl) return;
  var d;
  try { d = JSON.parse(dataEl.textContent); } catch(e){ return; }

  function bars(){
    if (!window.Plotly) return;
    Plotly.newPlot('posts-bars', [
      { name: d.a.name, y: [d.a.posts7, d.a.posts30, d.a.posts365], x: ['7d','30d','365d'], type:'bar' },
      { name: d.b.name, y: [d.b.posts7, d.b.posts30, d.b.posts365], x: ['7d','30d','365d'], type:'bar' }
    ], { barmode:'group', paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
         font:{color:'#e5e7eb'}, margin:{l:48,r:18,t:18,b:48} }, {displayModeBar:false});
  }
  function gauges(){
    if (!window.Plotly) return;
    Plotly.newPlot('mirrors-gauges', [
      { type:'indicator', mode:'gauge+number', value:d.a.uptime,
        gauge:{axis:{range:[0,100]}}, domain:{x:[0,0.48],y:[0,1]}, title:{text:d.a.name+' UP %'} },
      { type:'indicator', mode:'gauge+number', value:d.b.uptime,
        gauge:{axis:{range:[0,100]}}, domain:{x:[0.52,1],y:[0,1]}, title:{text:d.b.name+' UP %'} }
    ], { paper_bgcolor:'rgba(0,0,0,0)', font:{color:'#e5e7eb'}, margin:{l:40,r:40,t:24,b:16} }, {displayModeBar:false});
  }

  if (document.readyState === 'complete'){ bars(); gauges(); }
  else window.addEventListener('load', function(){ bars(); gauges(); });
})();
