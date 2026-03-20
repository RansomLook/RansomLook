document.addEventListener('DOMContentLoaded', () => {
  // Collapsible sections
  document.querySelectorAll('.js-collapse-toggle').forEach(hd => {
    hd.addEventListener('click', () => {
      const body = hd.nextElementSibling;
      if (!body || !body.classList.contains('collapse-body')) return;
      const hidden = body.hasAttribute('hidden');
      body.toggleAttribute('hidden');
      const arrow = hd.querySelector('.collapse-arrow');
      if (arrow) arrow.textContent = hidden ? '▾' : '▸';
    });
  });

  // Toggle password visibility
  document.querySelectorAll('.js-toggle-pw').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = document.getElementById(btn.dataset.target);
      if (!input) return;
      const isPw = input.type === 'password';
      input.type = isPw ? 'text' : 'password';
      btn.textContent = isPw ? 'Hide' : 'Show';
    });
  });
});
