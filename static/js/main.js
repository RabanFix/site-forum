/* ═══════════════════════════════════════════════════════════
   ТРАНССЕРВИС — Главный JavaScript
   ═══════════════════════════════════════════════════════════ */

'use strict';

// ─── Бургер-меню ─────────────────────────────────────────
(function () {
  const btn  = document.getElementById('burger-btn');
  const menu = document.getElementById('mobile-menu');
  if (!btn || !menu) return;

  btn.addEventListener('click', () => {
    menu.classList.toggle('open');
    btn.setAttribute('aria-expanded', menu.classList.contains('open'));
  });

  // Закрыть при клике вне
  document.addEventListener('click', (e) => {
    if (!btn.contains(e.target) && !menu.contains(e.target)) {
      menu.classList.remove('open');
    }
  });
})();

// ─── Авто-скрытие flash-сообщений ────────────────────────
(function () {
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach((el) => {
    setTimeout(() => {
      el.style.transition = 'opacity .4s ease, transform .4s ease';
      el.style.opacity = '0';
      el.style.transform = 'translateY(-8px)';
      setTimeout(() => el.remove(), 400);
    }, 5000);
  });
})();

// ─── Лайки (AJAX) ────────────────────────────────────────
(function () {
  document.querySelectorAll('.like-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const postId = btn.dataset.post;
      if (!postId) return;

      try {
        const resp = await fetch(`/api/like/${postId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });
        if (resp.status === 302 || resp.redirected) {
          window.location.href = '/login';
          return;
        }
        if (!resp.ok) return;
        const data = await resp.json();
        const counter = btn.querySelector('.like-count');
        if (counter) counter.textContent = data.likes;
        btn.classList.toggle('liked');
      } catch (err) {
        console.error('Like error:', err);
      }
    });
  });
})();

// ─── Авто-рост textarea ───────────────────────────────────
(function () {
  document.querySelectorAll('textarea').forEach((ta) => {
    ta.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 400) + 'px';
    });
  });
})();

// ─── Шкала токсичности (цвет) ────────────────────────────
(function () {
  document.querySelectorAll('.toxicity-fill').forEach((el) => {
    const score = parseFloat(el.dataset.score) || 0;
    const pct   = Math.round(score * 100);
    el.style.width = pct + '%';

    let color;
    if (score < 0.3)       color = '#16a34a';
    else if (score < 0.6)  color = '#d97706';
    else                   color = '#dc2626';

    el.style.background = color;
  });
})();