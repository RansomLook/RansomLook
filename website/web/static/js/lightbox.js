/* lightbox.js — image gallery lightbox with keyboard & touch navigation */
(function(){
  var lb   = document.getElementById('ta-lightbox');
  if (!lb) return;
  var img  = document.getElementById('lb-img');
  var cap  = document.getElementById('lb-cap');
  var cnt  = document.getElementById('lb-count');
  var btnN = lb.querySelector('.lb-next');
  var btnP = lb.querySelector('.lb-prev');

  var thumbs = Array.from(document.querySelectorAll('.thumb-link'));
  var idx = -1;

  function srcFor(a){ return a.dataset.img || a.getAttribute('href'); }
  function capFor(a){
    return a.getAttribute('aria-label')
        || (a.querySelector('img') ? a.querySelector('img').alt : '')
        || '';
  }

  function preload(i){
    if(!thumbs.length) return;
    if(i < 0) i = thumbs.length - 1;
    if(i >= thumbs.length) i = 0;
    var pre = new Image();
    pre.src = srcFor(thumbs[i]);
  }

  function openAt(i){
    if(!thumbs.length) return;
    if(i < 0) i = thumbs.length - 1;
    if(i >= thumbs.length) i = 0;
    idx = i;

    var t = thumbs[idx];
    img.src = srcFor(t);
    cap.textContent = capFor(t);
    cnt.textContent = (idx+1) + ' / ' + thumbs.length;

    lb.hidden = false;
    document.addEventListener('keydown', onKey);
    preload(idx+1);
  }

  function close(){
    lb.hidden = true;
    img.src = ''; cap.textContent = ''; cnt.textContent = '';
    document.removeEventListener('keydown', onKey);
  }

  function next(){ openAt(idx+1); }
  function prev(){ openAt(idx-1); }

  function onKey(e){
    if(e.key === 'Escape') close();
    else if(e.key === 'ArrowRight') next();
    else if(e.key === 'ArrowLeft')  prev();
  }

  document.addEventListener('click', function(e){
    var a = e.target.closest('a.thumb-link');
    if(a){
      e.preventDefault();
      var i = thumbs.indexOf(a);
      openAt(i >= 0 ? i : 0);
      return;
    }
    if(e.target.hasAttribute('data-close')) close();
  });

  btnN.addEventListener('click', next);
  btnP.addEventListener('click', prev);

  var touchX = null;
  lb.addEventListener('touchstart', function(e){ touchX = e.changedTouches[0].clientX; }, {passive:true});
  lb.addEventListener('touchend', function(e){
    if(touchX == null) return;
    var dx = e.changedTouches[0].clientX - touchX;
    touchX = null;
    if(Math.abs(dx) > 30){ dx < 0 ? next() : prev(); }
  }, {passive:true});
})();
