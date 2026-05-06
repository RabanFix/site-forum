/* ═══════════════════════════════════════════════════════════
   ТРАНССЕРВИС — Страница темы (ИИ-инструменты)
   ═══════════════════════════════════════════════════════════ */

'use strict';

(function () {
  const resultPanel = document.getElementById('ai-result-panel');
  const resultBody  = document.getElementById('ai-result-body');
  const btnSummary  = document.getElementById('btn-summary');
  const btnSuggest  = document.getElementById('btn-suggest');
  const suggestion  = document.getElementById('ai-suggestion');
  const suggestText = document.getElementById('suggestion-text');
  const useSuggest  = document.getElementById('use-suggestion');
  const replyArea   = document.getElementById('reply-content');

  // ─── Резюме темы ───────────────────────────────────────
  if (btnSummary) {
    btnSummary.addEventListener('click', async () => {
      const topicId = btnSummary.dataset.topic;
      if (!topicId) return;

      showPanel('Загружаю резюме...');
      btnSummary.disabled = true;

      try {
        const resp = await fetch(`/api/summary/${topicId}`);
        const data = await resp.json();
        showPanel(data.summary || data.error || 'Нет данных');
      } catch (e) {
        showPanel('⚠️ Не удалось получить резюме.');
      } finally {
        btnSummary.disabled = false;
      }
    });
  }

  // ─── Подсказка ответа ─────────────────────────────────
  if (btnSuggest) {
    btnSuggest.addEventListener('click', async () => {
      const topicId = btnSuggest.dataset.topic;
      if (!topicId) return;

      btnSuggest.disabled = true;
      btnSuggest.textContent = '💡 Генерирую...';

      try {
        const resp = await fetch('/api/suggest', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ topic_id: parseInt(topicId) }),
        });
        const data = await resp.json();

        if (data.suggestion && suggestion && suggestText) {
          suggestText.textContent = data.suggestion;
          suggestion.style.display = 'block';
          // Прокрутить к форме ответа
          suggestion.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      } catch (e) {
        alert('⚠️ Не удалось получить подсказку.');
      } finally {
        btnSuggest.disabled = false;
        btnSuggest.innerHTML = '💡 Подсказка';
      }
    });
  }

  // Вставить подсказку в форму ответа
  if (useSuggest && suggestText && replyArea) {
    useSuggest.addEventListener('click', () => {
      replyArea.value = suggestText.textContent;
      replyArea.focus();
      // Авто-высота
      replyArea.style.height = 'auto';
      replyArea.style.height = Math.min(replyArea.scrollHeight, 400) + 'px';
    });
  }

  // ─── Хелперы ───────────────────────────────────────────
  function showPanel(text) {
    if (!resultPanel || !resultBody) return;
    resultBody.textContent = text;
    resultPanel.style.display = 'block';
    resultPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // Кнопка закрытия панели результата
  const closeResult = resultPanel && resultPanel.querySelector('button');
  if (closeResult) {
    closeResult.addEventListener('click', () => {
      resultPanel.style.display = 'none';
    });
  }
})();