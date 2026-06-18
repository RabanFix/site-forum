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
      if (target === 'toxicity') loadToxicityStats();
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

  // ─── Авто-обновление счётчика (каждые 60 сек) ─────────
  const pendingBadge = document.getElementById('pending-badge');
  if (pendingBadge) {
    setInterval(async () => {
      try {
        const resp = await fetch('/api/admin/pending-count');
        if (!resp.ok) return;
        const data = await resp.json();
        if (typeof data.count === 'number') {
          pendingBadge.textContent = data.count;
          pendingBadge.style.display = data.count === 0 ? 'none' : '';
        }
      } catch (_) {}
    }, 60000);
  }

  // ─── Закрытие модального при клике на фон ─────────────
  document.querySelectorAll('.modal-backdrop').forEach((el) => {
    el.addEventListener('click', (e) => {
      if (e.target === el) closeModal(el.id);
    });
  });
})();

// ─── Модальное окно: Ограничение (своё время) ─────────
function openRestrictModal(userId, username) {
  document.getElementById('restrict-username').textContent = username;
  document.getElementById('restrict-form').action =
    `/admin/user/${userId}/restrict-custom`;
  openModal('restrict-modal');
}

// ─── Модальное окно: Бан ──────────────────────────────
function openBanModal(userId, username) {
  document.getElementById('ban-username').textContent = username;

  const timedForm = document.getElementById('ban-timed-form');
  const permForm  = document.getElementById('ban-perm-form');

  timedForm.action = `/admin/user/${userId}/ban-timed`;
  timedForm.style.display = 'block';
  permForm.action  = `/admin/user/${userId}/ban`;
  permForm.style.display  = 'none';

  document.getElementById('ban-minutes-input').value = '';
  openModal('ban-modal');
}

function setBanMinutes(minutes) {
  document.getElementById('ban-minutes-input').value = minutes;
  document.getElementById('ban-timed-form').style.display = 'block';
  document.getElementById('ban-perm-form').style.display  = 'none';
}

function setBanPermanent() {
  document.getElementById('ban-timed-form').style.display = 'none';
  document.getElementById('ban-perm-form').style.display  = 'block';
}

// ─── Дашборд токсичности ──────────────────────────────
let _toxTimer = null;

function loadToxicityStats() {
  const loading  = document.getElementById('tox-loading');
  const empty    = document.getElementById('tox-empty');
  const wrap     = document.getElementById('tox-table-wrap');
  const tbody    = document.getElementById('tox-tbody');
  const nextNote = document.getElementById('tox-next-refresh');

  if (!loading || !tbody) return;

  loading.style.display = 'block';
  empty.style.display   = 'none';
  wrap.style.display    = 'none';

  fetch('/api/admin/toxicity-stats')
    .then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(rows => {
      loading.style.display = 'none';
      if (!rows.length) { empty.style.display = 'block'; return; }

      tbody.innerHTML = '';
      rows.forEach((u, i) => {
        const avg   = u.avg_toxicity  || 0;
        const max   = u.max_toxicity  || 0;
        const pct   = Math.round(avg * 100);
        const cls   = avg >= 0.6 ? 'tox-danger' : avg >= 0.4 ? 'tox-warn' : 'tox-ok';
        const rowCls = avg >= 0.6 ? 'tox-row-danger' : avg >= 0.4 ? 'tox-row-warn' : '';

        let statusBadge;
        if (u.is_banned)         statusBadge = '<span class="tox-badge-danger">🚫 Бан</span>';
        else if (u.restricted_until) statusBadge = '<span class="tox-badge-warn">⏳ Огр.</span>';
        else                     statusBadge = '<span class="tox-badge-ok">✅ Активен</span>';

        const warningBadge = u.warnings_count > 0
          ? `<span class="tox-badge-${u.warnings_count >= 3 ? 'danger' : 'warn'}">${u.warnings_count}</span>`
          : `<span style="color:var(--text-muted)">0</span>`;

        const flagged = u.flagged_posts || 0;
        const flagCell = flagged > 0
          ? `<span class="tox-badge-${flagged >= 3 ? 'danger' : 'warn'}">${flagged}</span>`
          : `<span style="color:var(--text-muted)">0</span>`;

        const tr = document.createElement('tr');
        if (rowCls) tr.className = rowCls;
        tr.innerHTML = `
          <td style="color:var(--text-muted);font-size:.8rem;">${i + 1}</td>
          <td style="font-weight:600;">${escHtml(u.username)}</td>
          <td>${u.total_posts || 0}</td>
          <td>${flagCell}</td>
          <td>
            <div class="tox-bar-wrap">
              <div class="tox-bar-fill ${cls}" style="width:${pct}%"></div>
            </div>
            <span class="tox-bar-label">${(avg * 100).toFixed(1)}%</span>
          </td>
          <td style="font-size:.8rem;color:var(--text-muted);">${(max * 100).toFixed(1)}%</td>
          <td>${warningBadge}</td>
          <td style="font-size:.8rem;color:var(--text-muted);">${u.penalty_level || 0}</td>
          <td>${statusBadge}</td>
          <td>
            <button class="btn btn-outline btn-xs tox-chart-btn"
                    onclick="showUserHistory(${u.id}, '${escHtml(u.username)}', ${avg})">
              📈
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });

      wrap.style.display = 'block';

      // Показываем время следующего автообновления
      const next = new Date(Date.now() + 30000);
      nextNote.textContent = `Авто-обновление в ${next.getHours()}:${String(next.getMinutes()).padStart(2,'0')}:${String(next.getSeconds()).padStart(2,'0')}`;
    })
    .catch(() => {
      loading.textContent = '⚠️ Не удалось загрузить данные.';
    });
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─── График истории токсичности ───────────────────────
function showUserHistory(userId, username, avgTox) {
  document.getElementById('tox-hist-name').textContent = username;
  document.getElementById('tox-hist-loading').style.display = 'block';
  document.getElementById('tox-hist-chart-wrap').style.display = 'none';
  document.getElementById('tox-hist-empty').style.display = 'none';
  document.getElementById('tox-hist-summary').innerHTML = '';
  openModal('tox-history-modal');

  fetch(`/api/admin/user-toxicity-history/${userId}`)
    .then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(posts => {
      document.getElementById('tox-hist-loading').style.display = 'none';

      if (!posts.length) {
        document.getElementById('tox-hist-empty').style.display = 'block';
        return;
      }

      // ── Статистика-шапка ──
      const scores = posts.map(p => p.toxicity_score || 0);
      const avg    = scores.reduce((a, b) => a + b, 0) / scores.length;
      const max    = Math.max(...scores);
      const trend  = scores.length >= 4
        ? scores.slice(-3).reduce((a, b) => a + b, 0) / 3 - scores.slice(0, 3).reduce((a, b) => a + b, 0) / 3
        : 0;
      const trendIcon = trend > 0.05 ? '📈 Рост' : trend < -0.05 ? '📉 Снижение' : '➡️ Стабильно';
      const trendCls  = trend > 0.05 ? 'tox-badge-danger' : trend < -0.05 ? 'tox-badge-ok' : 'tox-badge-warn';

      document.getElementById('tox-hist-summary').innerHTML = `
        <div class="tox-hist-stats">
          <div class="tox-hist-stat"><strong>${posts.length}</strong><small>постов</small></div>
          <div class="tox-hist-stat"><strong>${(avg * 100).toFixed(1)}%</strong><small>среднее</small></div>
          <div class="tox-hist-stat"><strong>${(max * 100).toFixed(1)}%</strong><small>максимум</small></div>
          <div class="tox-hist-stat"><span class="${trendCls}">${trendIcon}</span><small>тенденция</small></div>
        </div>
      `;

      // ── SVG-график ──
      drawToxicityChart(posts, avg);
      document.getElementById('tox-hist-chart-wrap').style.display = 'block';
    })
    .catch(() => {
      document.getElementById('tox-hist-loading').textContent = '⚠️ Ошибка загрузки.';
    });
}

function drawToxicityChart(posts, avg) {
  const svg    = document.getElementById('tox-hist-svg');
  const W = 520, H = 180;
  const pad = { top: 16, right: 20, bottom: 32, left: 40 };
  const cW = W - pad.left - pad.right;
  const cH = H - pad.top  - pad.bottom;

  svg.innerHTML = '';

  const n = posts.length;
  const xStep = n > 1 ? cW / (n - 1) : cW;

  function xPos(i) { return pad.left + (n > 1 ? i * xStep : cW / 2); }
  function yPos(v) { return pad.top + cH - v * cH; }

  function mkEl(tag, attrs) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
    return el;
  }

  // Grid lines
  [0, 0.25, 0.5, 0.75, 1.0].forEach(v => {
    svg.appendChild(mkEl('line', {
      x1: pad.left, y1: yPos(v), x2: pad.left + cW, y2: yPos(v),
      stroke: '#e8e0d8', 'stroke-width': 1
    }));
    const lbl = mkEl('text', {
      x: pad.left - 5, y: yPos(v) + 4,
      'text-anchor': 'end', fill: '#aaa', 'font-size': '9'
    });
    lbl.textContent = Math.round(v * 100) + '%';
    svg.appendChild(lbl);
  });

  // Threshold line (60%)
  const thY = yPos(0.6);
  svg.appendChild(mkEl('line', {
    x1: pad.left, y1: thY, x2: pad.left + cW, y2: thY,
    stroke: '#d94f4f', 'stroke-width': 1.2, 'stroke-dasharray': '4,3', opacity: 0.8
  }));

  // Average line
  const avgY = yPos(avg);
  svg.appendChild(mkEl('line', {
    x1: pad.left, y1: avgY, x2: pad.left + cW, y2: avgY,
    stroke: '#5b8dee', 'stroke-width': 1.2, 'stroke-dasharray': '4,3', opacity: 0.8
  }));

  // Area fill under curve
  const areaPoints = posts.map((p, i) => `${xPos(i)},${yPos(p.toxicity_score || 0)}`);
  const areaPath   = `M${pad.left},${yPos(0)} L${areaPoints.join(' L')} L${xPos(n - 1)},${yPos(0)} Z`;
  const areaPoly   = mkEl('path', {
    d: areaPath, fill: 'url(#toxGrad)', opacity: 0.18
  });

  // Gradient def
  const defs = mkEl('defs', {});
  const grad = mkEl('linearGradient', { id: 'toxGrad', x1: 0, y1: 0, x2: 0, y2: 1 });
  const s0   = mkEl('stop', { offset: '0%',   'stop-color': '#d94f4f' });
  const s1   = mkEl('stop', { offset: '100%', 'stop-color': '#4caf7d' });
  grad.appendChild(s0); grad.appendChild(s1);
  defs.appendChild(grad);
  svg.appendChild(defs);
  svg.appendChild(areaPoly);

  // Polyline
  const linePoints = posts.map((p, i) => `${xPos(i)},${yPos(p.toxicity_score || 0)}`).join(' ');
  svg.appendChild(mkEl('polyline', {
    points: linePoints, fill: 'none',
    stroke: '#e6a817', 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round'
  }));

  // X-axis labels (post number) + circles
  posts.forEach((p, i) => {
    const score = p.toxicity_score || 0;
    const cx = xPos(i), cy = yPos(score);
    const color = score >= 0.6 ? '#d94f4f' : score >= 0.4 ? '#e6a817' : '#4caf7d';

    // Dot
    const circle = mkEl('circle', {
      cx, cy, r: 4.5, fill: color, stroke: '#fff', 'stroke-width': 1.5,
      style: 'cursor:pointer'
    });

    // Tooltip via title
    const titleEl = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    const date = p.created_at ? p.created_at.slice(0, 10) : '';
    titleEl.textContent = `Пост #${i + 1} (${date})\nТоксичность: ${(score * 100).toFixed(1)}%\n${p.snippet || ''}`;
    circle.appendChild(titleEl);
    svg.appendChild(circle);

    // X tick
    if (n <= 10 || i % Math.ceil(n / 8) === 0) {
      const lbl = mkEl('text', {
        x: cx, y: H - pad.bottom + 14,
        'text-anchor': 'middle', fill: '#aaa', 'font-size': '9'
      });
      lbl.textContent = i + 1;
      svg.appendChild(lbl);
    }
  });

  // X-axis line
  svg.appendChild(mkEl('line', {
    x1: pad.left, y1: pad.top + cH, x2: pad.left + cW, y2: pad.top + cH,
    stroke: '#ccc', 'stroke-width': 1
  }));
}

// Авто-обновление дашборда каждые 30 сек когда вкладка открыта
document.addEventListener('visibilitychange', () => {
  const toxPanel = document.getElementById('tab-toxicity');
  if (document.hidden || !toxPanel || toxPanel.style.display === 'none') {
    clearInterval(_toxTimer);
    _toxTimer = null;
  }
});

// Следим за активной вкладкой (запускаем/останавливаем таймер)
(function watchToxTab() {
  const tabs = document.querySelectorAll('.admin-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      clearInterval(_toxTimer);
      _toxTimer = null;
      if (tab.dataset.tab === 'toxicity') {
        _toxTimer = setInterval(loadToxicityStats, 30000);
      }
    });
  });
})();

// ─── Helpers ──────────────────────────────────────────
function openModal(id) {
  document.getElementById(id).style.display = 'flex';
  document.body.style.overflow = 'hidden';
}

function closeModal(id) {
  document.getElementById(id).style.display = 'none';
  document.body.style.overflow = '';
}
