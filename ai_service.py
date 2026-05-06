"""
Слой взаимодействия с ИИ.
"""
import re
import json
import requests
from config import Config

# ─── Системные промпты ──────────────────────────────────────────────────────
_SYSTEM_ASSISTANT = """Ты — вежливый и компетентный ИИ-ассистент форума
ООО «Транссервис». Специализируешься на транспортной логистике,
грузоперевозках, техническом обслуживании транспорта и российском
транспортном законодательстве.
Отвечай на русском языке, кратко и по делу.
При необходимости задавай уточняющие вопросы."""

_SYSTEM_MODERATOR = """Ты — строгий модератор русскоязычного профессионального форума
транспортной компании ООО «Транссервис».
Твоя задача: оценить текст пользователя и вернуть JSON-ответ.

КРИТИЧЕСКИ ВАЖНО — ВСЕГДА блокируй (approved=false) если текст содержит:
1) Любую ненормативную лексику и оскорбления на русском ИЛИ английском языке
2) Угрозы и призывы к насилию
3) Спам/рекламу
4) Сексуальный контент
5) Дискриминацию/хейт
6) Заведомо ложную информацию
7) Контент явно не по теме транспортного форума

Верни ТОЛЬКО валидный JSON без markdown:
{"toxicity_score": 0.0, "approved": true, "reason": "Сообщение корректно."}
"""

def _call_api(messages: list[dict], temperature: float = 0.1, max_tokens: int = 256) -> str | None:
    headers = {
        "Authorization": f"Bearer {Config.CSGPT_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": Config.CSGPT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        resp = requests.post(Config.CSGPT_API_URL, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[AI] API error: {e}")
        return None

# ─── Локальный фильтр (резервный) ────────────────────────────────────────────
_BAD_WORDS_SET = {
    # RU
    "пиздец","хуй","ебать","блять","сука","пизда","хуйня","ёбаный","еба","пздц","пизд",
    "хуе","хую","бля","дебил","мудак","пидор","залупа","ёб","блядь","шлюха","мразь",
    "урод","тупица","идиот",
    # EN
    "fuck","fucking","shit","bitch","asshole","bastard","motherfucker","moron","retard","idiot",
}

def _normalize_for_filter(text: str) -> str:
    t = text.lower()
    # простая деобфускация
    t = t.replace("@", "a").replace("$", "s").replace("0", "o").replace("1", "i").replace("3", "e")
    # убираем пробелы/знаки чтобы ловить f*u*c*k
    t = re.sub(r"[\s\*\.\-_!@#$%^&()0-9\[\]{}<>/\\|+=~`'\";,?:]", "", t)
    return t

def _local_toxicity_check(text: str) -> dict | None:
    text_clean = _normalize_for_filter(text)
    for word in _BAD_WORDS_SET:
        w = _normalize_for_filter(word)
        if w and w in text_clean:
            return {
                "approved": False,
                "toxicity_score": 0.95,
                "reason": "Сообщение содержит недопустимую лексику/оскорбления."
            }
    return None

# ─── OFFLINE ассистент (заглушка) ────────────────────────────────────────────
def _offline_assistant(user_message: str) -> str:
    q = user_message.lower()

    base = (
        "Сейчас ИИ-ассистент работает в офлайн-режиме (без доступа к внешнему API).\n\n"
    )

    if re.search(r"маршрут|оптимиз|плечо|пробег|километр", q):
        return base + (
            "По маршрутам: укажите точки А→Б, тип груза, ограничения (вес/габарит), сроки и желаемые дороги (платные/бесплатные). "
            "Я подскажу, как обычно считают маршрут и какие данные нужны для оптимизации."
        )

    if re.search(r"ттн|накладн|документ|путев|заявк", q):
        return base + (
            "По документам: уточните вид перевозки (внутрироссийская/международная), тип договора и кто грузоотправитель/получатель. "
            "Обычно требуют заявку, договор/счет, ТТН/УПД, путевой лист и доверенности (по ситуации)."
        )

    if re.search(r"стоим|тариф|цена|расчет|калькуляц", q):
        return base + (
            "По расчету стоимости: нужны расстояние, тип ТС, масса/объем, класс опасности, погрузка/выгрузка, простои, сезонность, платные дороги. "
            "Напишите параметры — подскажу структуру расчета."
        )

    return base + (
        "Напишите, пожалуйста, что именно интересует: перевозки, логистика/маршруты, документы, ТО транспорта или правила форума? "
        "Уточните город(а), тип груза и сроки — отвечу точнее при подключении к внешнему API."
    )

# ─── Публичные функции ───────────────────────────────────────────────────────
def moderate_content(text: str) -> dict:
    local_result = _local_toxicity_check(text)
    if local_result:
        return local_result

    messages = [
        {"role": "system", "content": _SYSTEM_MODERATOR},
        {"role": "user", "content": f"Оцени следующий текст форума:\n\n{text}"},
    ]
    raw = _call_api(messages, temperature=0.1, max_tokens=256)

    if raw is None:
        # “мягкая политика” — можно оставить, но лучше всё равно ловить мат локально (мы уже ловим)
        return {"approved": True, "toxicity_score": 0.0, "reason": "Модерация API недоступна — опубликовано."}

    match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
    if not match:
        return {"approved": True, "toxicity_score": 0.0, "reason": "Не удалось распознать ответ модератора."}

    try:
        result = json.loads(match.group())
        result.setdefault("approved", True)
        result.setdefault("toxicity_score", 0.0)
        result.setdefault("reason", "")

        if result["toxicity_score"] >= Config.TOXICITY_THRESHOLD:
            result["approved"] = False

        return result
    except json.JSONDecodeError:
        return {"approved": True, "toxicity_score": 0.0, "reason": "Ошибка парсинга ответа модератора."}

def chat_with_assistant(user_message: str, history: list[dict] | None = None) -> str:
    messages = [{"role": "system", "content": _SYSTEM_ASSISTANT}]
    if history:
        for item in history[-10:]:
            messages.append({"role": item["role"], "content": item["message"]})
    messages.append({"role": "user", "content": user_message})

    answer = _call_api(messages, temperature=0.7, max_tokens=1024)
    if answer:
        return answer

    # вот тут главное: вместо вечного “недоступен” — нормальная заглушка
    return _offline_assistant(user_message)

def generate_topic_summary(posts_text: str) -> str:
    messages = [
        {"role": "system", "content": "Ты кратко резюмируешь обсуждения форума. Пиши по-русски, до 3 абзацев."},
        {"role": "user", "content": f"Составь краткое резюме этого обсуждения:\n\n{posts_text}"}
    ]
    result = _call_api(messages, temperature=0.5, max_tokens=512)
    return result if result else "Не удалось сгенерировать резюме (офлайн-режим)."

def suggest_reply(topic_title: str, last_posts: str) -> str:
    messages = [
        {"role": "system", "content": "Пиши вежливый полезный ответ (2–4 предложения) на русском."},
        {"role": "user", "content": f"Тема: «{topic_title}»\n\nПоследние сообщения:\n{last_posts}\n\nПредложи вариант ответа."}
    ]
    result = _call_api(messages, temperature=0.8, max_tokens=512)
    return result if result else "Не удалось сгенерировать подсказку (офлайн-режим)."