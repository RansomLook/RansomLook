/* tokens.js — reusable token/chip widget for relation fields
 *
 * Usage: add a JSON config block:
 *   <script type="application/json" id="tokens-config">[
 *     {"hiddenId":"groups-hidden","addId":"groups-add","tokensId":"groups-tokens"},
 *     {"hiddenId":"markets-hidden","addId":"markets-add","tokensId":"markets-tokens"}
 *   ]</script>
 */
(function(){
  var cfgEl = document.getElementById('tokens-config');
  if (!cfgEl) return;
  var cfgs;
  try { cfgs = JSON.parse(cfgEl.textContent); } catch(e){ return; }

  function initTokens(hiddenId, addId, tokensId){
    var hidden = document.getElementById(hiddenId);
    var add = document.getElementById(addId);
    var wrap = document.getElementById(tokensId);
    if (!hidden || !add || !wrap) return;

    function setCSV(arr){ hidden.value = arr.join(', '); }
    function getCSV(){ return (hidden.value || '').split(',').map(function(s){ return s.trim(); }).filter(Boolean); }

    function render(){
      wrap.innerHTML = '';
      getCSV().forEach(function(val){
        var b = document.createElement('span');
        b.className = 'token';
        b.innerHTML = '<span>'+val+'</span><span class="x" title="Remove">\u00d7</span>';
        b.querySelector('.x').addEventListener('click', function(){
          var arr = getCSV().filter(function(x){ return x.toLowerCase() !== val.toLowerCase(); });
          setCSV(arr); render();
        });
        wrap.appendChild(b);
      });
    }

    function addToken(v){
      v = (v || '').trim();
      if(!v) return;
      var arr = getCSV();
      if(arr.map(function(x){ return x.toLowerCase(); }).indexOf(v.toLowerCase()) === -1){ arr.push(v); setCSV(arr); }
      add.value = ''; render();
    }

    add.addEventListener('keydown', function(e){
      if(e.key === 'Enter'){ e.preventDefault(); addToken(add.value); }
      if(e.key === ','){ e.preventDefault(); addToken(add.value.replace(/,$/,'')); }
      if(e.key === 'Backspace' && !add.value){
        var arr = getCSV(); arr.pop(); setCSV(arr); render();
      }
    });

    add.addEventListener('change', function(){ addToken(add.value); });
    render();
  }

  cfgs.forEach(function(c){ initTokens(c.hiddenId, c.addId, c.tokensId); });
})();
