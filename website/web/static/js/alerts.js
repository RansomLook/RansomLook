document.addEventListener('DOMContentLoaded', () => {
  const ta = document.getElementById('kw');
  const lineCount = document.getElementById('line-count');

  function lines() {
    return (ta.value || '')
      .split(/\r?\n/)
      .map(s => s.trim())
      .filter(Boolean);
  }
  function updateCount() { lineCount.textContent = String(lines().length); }
  function setLines(arr) { ta.value = arr.join('\n'); updateCount(); }

  // Tools
  document.getElementById('btn-trim').addEventListener('click', () => {
    setLines(lines().map(s => s.trim()));
  });
  document.getElementById('btn-dedupe').addEventListener('click', () => {
    const seen = new Set(); const out = [];
    for (const s of lines()) { const k = s.toLowerCase(); if (!seen.has(k)) { seen.add(k); out.push(s); } }
    setLines(out);
  });
  document.getElementById('btn-sort').addEventListener('click', () => {
    setLines(lines().sort((a,b)=> a.localeCompare(b)));
  });
  document.getElementById('btn-lower').addEventListener('click', () => {
    setLines(lines().map(s => s.toLowerCase()));
  });
  document.getElementById('btn-upper').addEventListener('click', () => {
    setLines(lines().map(s => s.toUpperCase()));
  });

  // Import / Export
  document.getElementById('btn-export').addEventListener('click', () => {
    const blob = new Blob([ta.value || ''], {type:'text/plain'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'keywords.txt';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(()=>URL.revokeObjectURL(a.href), 1200);
  });

  document.getElementById('btn-import').addEventListener('click', () => {
    const inp = document.createElement('input');
    inp.type = 'file'; inp.accept = '.txt,text/plain';
    inp.addEventListener('change', () => {
      const f = inp.files && inp.files[0]; if (!f) return;
      const r = new FileReader();
      r.onload = () => { ta.value = String(r.result || ''); updateCount(); };
      r.readAsText(f);
    });
    inp.click();
  });

  // Counter live update
  ta.addEventListener('input', updateCount);
  updateCount();

  // Tester
  const tInput = document.getElementById('t-input');
  const tMatches = document.getElementById('t-matches');
  const tCase = document.getElementById('t-case');

  function runTest(){
    const text = tInput.value || '';
    const kws = lines();
    if (!text || kws.length === 0) { tMatches.textContent = '—'; return; }

    const hay = tCase.checked ? text : text.toLowerCase();
    const hits = [];
    for (const k of kws) {
      const needle = tCase.checked ? k : k.toLowerCase();
      if (needle && hay.includes(needle)) hits.push(k);
    }
    if (hits.length === 0) { tMatches.textContent = 'No match'; return; }
    tMatches.innerHTML = hits.map(h => `<span class="kw-badge">${h.replace(/[&<>"]/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[s]))}</span>`).join(' ');
  }

  document.getElementById('t-run').addEventListener('click', runTest);
  document.getElementById('t-clear').addEventListener('click', () => { tInput.value=''; tMatches.textContent='—'; });
});
