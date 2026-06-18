/* ═══════════════════════════════════════════════════════════
   ТРАНССЕРВИС — ИИ-чат виджет
   ═══════════════════════════════════════════════════════════ */

'use strict';

(function () {
  const toggle      = document.getElementById('ai-toggle');
  const panel       = document.getElementById('ai-panel');
  const closeBtn    = document.getElementById('ai-close');
  const messages    = document.getElementById('ai-messages');
  const input       = document.getElementById('ai-input');
  const sendBtn     = document.getElementById('ai-send');
  const suggestions = document.getElementById('ai-suggestions');
  const factBtn     = document.getElementById('ai-fact-btn');

  if (!toggle || !panel) return;

  // ─── Разнообразие: случайные приветствия ──────────────────
  const GREETINGS = [
    { avatar: '🤖', text: 'Здравствуйте! Я ИИ-ассистент форума <strong>Транссервис</strong>. Задайте любой вопрос о грузоперевозках, логистике или работе форума.' },
    { avatar: '🚛', text: 'Добро пожаловать! Я здесь, чтобы помочь вам с вопросами транспорта и логистики. С чего начнём?' },
    { avatar: '📦', text: 'Привет! Спрашивайте всё о грузоперевозках — тарифы, документы, маршруты, законодательство. Я готов помочь!' },
    { avatar: '🗺️', text: 'Здравствуйте! Ваш помощник по логистике на связи. Чем могу быть полезен сегодня?' },
    { avatar: '🧑‍💼', text: 'Добрый день! Я специализируюсь на транспортной логистике. Задайте ваш вопрос — отвечу подробно.' },
    { avatar: '📋', text: 'Здравствуйте! Вопросы о перевозках, документах, тарифах — всё это в моей компетенции. Слушаю вас!' },
  ];

  // ─── Разнообразие: факты о логистике ─────────────────────
  const FACTS = [
    '🚛 В России ежегодно перевозится более 8 млрд тонн грузов автомобильным транспортом.',
    '📦 Около 90% всей мировой торговли осуществляется морским транспортом.',
    '📋 CMR-накладная была введена Женевской конвенцией 1956 года и действует в 55 странах.',
    '⚖️ Максимально допустимая нагрузка на ось грузовика в России составляет 10 тонн.',
    '🌐 TIR-карнет позволяет перевезти груз через несколько стран без таможенного досмотра на каждой границе.',
    '☢️ Более 50% всех опасных грузов в мире перевозится автомобильным транспортом.',
    '📍 Современные GPS-трекеры для грузов обновляют координаты каждые 30–60 секунд.',
    '🔗 Мультимодальные перевозки снижают стоимость доставки в среднем на 15–25% по сравнению с одним видом транспорта.',
    '🏭 Самый длинный автопоезд в мире — 1474 метра — был собран в Австралии в 2006 году.',
    '🛣️ Общая протяжённость федеральных автодорог России превышает 61 000 км.',
    '📊 Стоимость фрахта морского контейнера может отличаться в 5–10 раз в зависимости от сезона.',
    '🤝 Договор транспортной экспедиции регулируется главой 41 Гражданского кодекса РФ.',
  ];

  // ─── Инициализация разнообразия при первой загрузке ──────
  (function initVariety() {
    const g = GREETINGS[Math.floor(Math.random() * GREETINGS.length)];
    const avatarEl   = document.getElementById('ai-bot-avatar');
    const bubbleEl   = document.getElementById('ai-greeting-bubble');
    const headerAvatar = document.querySelector('.ai-avatar');
    if (avatarEl)   avatarEl.textContent = g.avatar;
    if (bubbleEl)   bubbleEl.innerHTML   = g.text;
    if (headerAvatar) headerAvatar.textContent = g.avatar;

    // Случайный placeholder в поле ввода
    const PLACEHOLDERS = [
      'Ваш вопрос о перевозках…',
      'Спрашивайте о логистике…',
      'Что вас интересует?',
      'Вопрос по документам?',
      'Узнайте о тарифах…',
    ];
    if (input) {
      input.placeholder = PLACEHOLDERS[Math.floor(Math.random() * PLACEHOLDERS.length)];
    }

    // Перемешиваем чипы-вопросы (кроме кнопки факта и разделителя)
    shuffleChips();
  })();

  function shuffleChips() {
    if (!suggestions) return;
    const chipNodes = Array.from(suggestions.querySelectorAll('.ai-chip[data-q]'));
    for (let i = chipNodes.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      suggestions.appendChild(chipNodes[j]);
      chipNodes.splice(j, 1);
      chipNodes.splice(i > j ? i - 1 : i, 0, chipNodes[j] || chipNodes[chipNodes.length - 1]);
    }
    // Простой перемешиватель: добавить все в случайном порядке
    const allChips = Array.from(suggestions.querySelectorAll('.ai-chip[data-q]'));
    allChips.sort(() => Math.random() - 0.5);
    allChips.forEach(c => suggestions.appendChild(c));
  }

  // ─── Кнопка «Факт» ────────────────────────────────────────
  if (factBtn) {
    factBtn.addEventListener('click', () => {
      const fact = FACTS[Math.floor(Math.random() * FACTS.length)];
      hideSuggestions();
      appendFactMessage(fact);
    });
  }

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

  // Подсказки: клик по чипу отправляет вопрос и скрывает панель подсказок
  if (suggestions) {
    suggestions.querySelectorAll('.ai-chip[data-q]').forEach(chip => {
      chip.addEventListener('click', () => {
        const q = chip.dataset.q;
        if (!q) return;
        hideSuggestions();
        if (input) { input.value = q; }
        sendMessage();
      });
    });
  }

  function hideSuggestions() {
    if (suggestions) {
      suggestions.style.display = 'none';
    }
  }

  // Отправка по кнопке
  sendBtn && sendBtn.addEventListener('click', () => { hideSuggestions(); sendMessage(); });

  // Отправка по Enter (Shift+Enter — перенос строки)
  input && input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      hideSuggestions();
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

    const avatarEl = document.getElementById('ai-bot-avatar');
    const botEmoji = avatarEl ? avatarEl.textContent : '🤖';

    const avatar = document.createElement('span');
    avatar.className = 'msg-avatar';
    avatar.textContent = isBot ? botEmoji : '👤';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    bubble.textContent = text;

    div.appendChild(avatar);
    div.appendChild(bubble);
    messages.appendChild(div);
    scrollToBottom();
    return div;
  }

  function appendFactMessage(text) {
    const div = document.createElement('div');
    div.className = 'ai-msg ai-msg--bot ai-msg--fact';

    const avatar = document.createElement('span');
    avatar.className = 'msg-avatar';
    avatar.textContent = '💡';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble msg-bubble--fact';
    bubble.textContent = text;

    div.appendChild(avatar);
    div.appendChild(bubble);
    messages.appendChild(div);
    scrollToBottom();
  }

  function appendTyping() {
    const id  = 'typing-' + Date.now();
    const div = document.createElement('div');
    div.className = 'ai-msg ai-msg--bot';
    div.id = id;

    const avatarEl = document.getElementById('ai-bot-avatar');
    const botEmoji = avatarEl ? avatarEl.textContent : '🤖';

    const avatar = document.createElement('span');
    avatar.className = 'msg-avatar';
    avatar.textContent = botEmoji;

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
