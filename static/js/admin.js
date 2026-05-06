/* ═══════════════════════════════════════════════════════════
   ТРАНССЕРВИС — Панель администратора
   ═══════════════════════════════════════════════════════════ */

'use strict';

(function () {
  // ─── Переключение вкладок ─────────────────────────────
  const tabs   = document.querySelectorAll('.admin-tab');
  const panels = document.querySelectorAll('.admin-panel');

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;

      tabs.forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');

      panels.forEach((p) => {
        p.style.display = p.id === `tab-${target}` ? 'block' : 'none';
      });
    });
  });

  // ─── Цвет шкалы токсичности ───────────────────────────
  document.querySelectorAll('.toxicity-fill').forEach((el) => {
    const score = parseFloat(el.dataset.score) || 0;
    el.style.width = Math.round(score * 100) + '%';

    if (score < 0.3)       el.style.background = '#16a34a';
    else if (score < 0.6)  el.style.background = '#d97706';
    else                   el.style.background = '#dc2626';
  });

  // ─── Подтверждение критических действий ───────────────
  document.querySelectorAll('[data-confirm]').forEach((el) => {
    el.addEventListener('click', (e) => {
      if (!confirm(el.dataset.confirm)) {
        e.preventDefault();
      }
    });
  });

  // ─── Авто-обновление счётчика (каждые 60 сек) ─────────
  // Только если есть ожидающие посты
  const pendingBadge = document.querySelector('.tab-badge');
  if (pendingBadge) {
    setInterval(async () => {
      try {
        const resp = await fetch('/api/admin/pending-count', { method: 'GET' });
        if (!resp.ok) return;
        const data = await resp.json();
        if (typeof data.count === 'number') {
          pendingBadge.textContent = data.count;
          if (data.count === 0) pendingBadge.style.display = 'none';
        }
      } catch (_) { /* silent */ }
    }, 60000);
  }
})();