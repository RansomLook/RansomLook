/* notesdetails.js — copy-to-clipboard for ransom notes */
(function(){
  function copyText(txt){
    if (navigator.clipboard && navigator.clipboard.writeText){
      return navigator.clipboard.writeText(txt);
    }
    var ta = document.createElement('textarea');
    ta.value = txt;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch(e){}
    document.body.removeChild(ta);
    return Promise.resolve();
  }

  document.addEventListener('click', function(e){
    var btn = e.target.closest('[data-copy]');
    if (!btn) return;
    var tr = btn.closest('tr');
    var pre = tr ? tr.querySelector('[data-note]') : null;
    if (!pre) return;

    var txt = pre.textContent || '';
    copyText(txt).then(function(){
      var orig = btn.textContent;
      btn.textContent = 'Copied!';
      setTimeout(function(){ btn.textContent = orig; }, 1200);
    });
  });
})();
