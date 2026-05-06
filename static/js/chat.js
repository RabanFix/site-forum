/* ═══════════════════════════════════════════════════════════
   ТРАНССЕРВИС — ИИ-чат виджет
   ═══════════════════════════════════════════════════════════ */

'use strict';

(function () {
  const toggle    = document.getElementById('ai-toggle');
  const panel     = document.getElementById('ai-panel');
  const closeBtn  = document.getElementById('ai-close');
  const messages  = document.getElementById('ai-messages');
  const input     = document.getElementById('ai-input');
  const sendBtn   = document.getElementById('ai-send');

  if (!toggle || !panel) return;

  // Открыть/закрыть панель
  toggle.addEventListener('click', () => {
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) {
      input && input.focus();
      scrollToBottom();
    }
  });

  closeBtn && closeBtn.addEventListener('click', () => {
    panel.classList.remove('open');
  });

  // Отправка по кнопке
  sendBtn && sendBtn.addEventListener('click', sendMessage);

  // Отправка по Enter (Shift+Enter — перенос строки)
  input && input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  async function sendMessage() {
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    appendMessage('user', text);
    input.value = '';
    input.style.height = 'auto';

    const typingId = appendTyping();

    try {
      const resp = await fetch('/api/chat', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ message: text }),
      });

      removeTyping(typingId);

      if (!resp.ok) {
        appendMessage('bot', '⚠️ Ошибка сервера. Попробуйте позже.');
        return;
      }

      const data = await resp.json();
      if (data.error) {
        appendMessage('bot', '⚠️ ' + data.error);
      } else {
        appendMessage('bot', data.answer);
      }
    } catch (err) {
      removeTyping(typingId);
      appendMessage('bot', '⚠️ Нет соединения с сервером.');
      console.error('Chat error:', err);
    }
  }

  function appendMessage(type, text) {
    const isBot  = type === 'bot';
    const div    = document.createElement('div');
    div.className = `ai-msg ai-msg--${isBot ? 'bot' : 'user'}`;

    const avatar = document.createElement('span');
    avatar.className = 'msg-avatar';
    avatar.textContent = isBot ? '🤖' : '👤';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    bubble.textContent = text;   // textContent — защита от XSS

    div.appendChild(avatar);
    div.appendChild(bubble);
    messages.appendChild(div);
    scrollToBottom();
    return div;
  }

  function appendTyping() {
    const id  = 'typing-' + Date.now();
    const div = document.createElement('div');
    div.className = 'ai-msg ai-msg--bot';
    div.id = id;

    const avatar = document.createElement('span');
    avatar.className = 'msg-avatar';
    avatar.textContent = '🤖';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble msg-typing';
    bubble.innerHTML = '<span></span><span></span><span></span>';

    div.appendChild(avatar);
    div.appendChild(bubble);
    messages.appendChild(div);
    scrollToBottom();
    return id;
  }

  function removeTyping(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function scrollToBottom() {
    if (messages) {
      messages.scrollTop = messages.scrollHeight;
    }
  }
})();