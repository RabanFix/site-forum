"""
Точка входа приложения.
Flask-маршруты, сессии, логика представлений.
"""
import uuid
import re
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, flash, abort
)

from config import Config
from models import (
    init_db,
    create_user, verify_user, get_user_by_id, get_all_users,
    get_all_categories, get_category_by_id,
    create_topic, get_topics_by_category, get_topic_by_id,
    increment_topic_views, toggle_pin_topic, toggle_close_topic, delete_topic,
    create_post, get_posts_by_topic, get_post_by_id,
    get_pending_posts, moderate_post, delete_post,
    toggle_like,
    save_chat_message, get_chat_history,
    get_stats,

    # NEW:
    register_user_violation,
    set_user_restriction, clear_user_restriction,
    ban_user, unban_user, delete_user,
)
from ai_service import (
    moderate_content, chat_with_assistant,
    generate_topic_summary, suggest_reply
)

# ─── Локальный фильтр (RU+EN) ───────────────────────────────────────────────
_BAD_WORDS = [
    # RU
    "пиздец", "хуй", "ебать", "блять", "сука", "пизда", "хуйня",
    "ёбаный", "ёб", "еба", "пздц", "пизд", "хуе", "хую", "бля",
    "дебил", "идиот", "мудак", "пидор", "залупа", "блядь", "шлюха",
    "мразь", "урод", "нахуй", "нахуя", "похуй", "долбоёб", "долбоеб",
    # EN (не добавляйте короткое "ass", иначе будет много ложных срабатываний)
    "fuck", "fucking", "shit", "bitch", "asshole", "bastard", "motherfucker",
    "moron", "retard", "idiot",
]

def _normalize_for_filter(text: str) -> str:
    t = text.lower()
    t = t.replace("@", "a").replace("$", "s").replace("0", "o").replace("1", "i").replace("3", "e")
    t = re.sub(r"[\s\*\.\-_!@#$%^&()0-9\[\]{}<>/\\|+=~`'\";,?:]", "", t)
    return t

def is_toxic_local(text: str) -> bool:
    cleaned = _normalize_for_filter(text)
    for word in _BAD_WORDS:
        w = _normalize_for_filter(word)
        if w and w in cleaned:
            return True
    return False

# ─── Инициализация ───────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config["DEBUG"] = Config.DEBUG

with app.app_context():
    init_db()

# ─── Утилиты ограничений/банов ──────────────────────────────────────────────
def _parse_iso(dt_str: str | None):
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None

def user_access_state(user_id: int) -> tuple[bool, str]:
    """
    True = можно писать/пользоваться форумом.
    False = нельзя + текст причины.
    """
    u = get_user_by_id(user_id)
    if not u:
        return False, "Пользователь не найден."

    # Бан
    if int(u.get("is_banned") or 0) == 1:
        until = _parse_iso(u.get("banned_until"))
        reason = (u.get("ban_reason") or "").strip()
        if until and until > datetime.now():
            return False, f"Доступ заблокирован до {until:%d.%m.%Y %H:%M}. {reason}".strip()
        if until is None:
            return False, f"Доступ заблокирован. {reason}".strip()

    # Ограничение (тайм-аут на публикации)
    r_until = _parse_iso(u.get("restricted_until"))
    if r_until and r_until > datetime.now():
        return False, f"Вам временно ограничены публикации до {r_until:%d.%m.%Y %H:%M}."

    return True, ""

def enforce_can_post():
    if "user_id" not in session:
        flash("Для доступа необходимо войти.", "warning")
        return redirect(url_for("login", next=request.url))
    ok, msg = user_access_state(session["user_id"])
    if not ok:
        flash(msg, "danger")
        return redirect(request.referrer or url_for("index"))
    return None

def enforce_can_chat():
    if "user_id" not in session:
        return True, ""  # гость может чатиться (если хотите — запретите)
    ok, msg = user_access_state(session["user_id"])
    return ok, msg

# ─── Декораторы ──────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Для доступа необходимо войти.", "warning")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        user = get_user_by_id(session["user_id"])
        if not user or user["role"] != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated

# ─── Контекст ────────────────────────────────────────────────────────────────
@app.context_processor
def inject_globals():
    user = None
    if "user_id" in session:
        user = get_user_by_id(session["user_id"])
    return {"current_user": user}

# ─── Главная ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    categories = get_all_categories()
    stats = get_stats()
    return render_template("index.html", categories=categories, stats=stats)

# ─── Аутентификация ──────────────────────────────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not username or not password:
            flash("Заполните все поля.", "danger")
        elif len(username) < 3:
            flash("Имя пользователя — минимум 3 символа.", "danger")
        elif len(password) < 6:
            flash("Пароль — минимум 6 символов.", "danger")
        elif password != confirm:
            flash("Пароли не совпадают.", "danger")
        else:
            user = create_user(username, password)
            if user:
                session["user_id"] = user["id"]
                flash(f"Добро пожаловать, {username}!", "success")
                return redirect(url_for("index"))
            flash("Пользователь с таким именем уже существует.", "danger")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = verify_user(username, password)

        if user:
            # запрет входа забаненным
            if int(user.get("is_banned") or 0) == 1:
                ok, msg = user_access_state(user["id"])
                flash(msg or "Доступ заблокирован.", "danger")
                return render_template("login.html")

            session["user_id"] = user["id"]
            flash(f"С возвращением, {username}!", "success")
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)

        flash("Неверное имя пользователя или пароль.", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("index"))

# ─── Форум ───────────────────────────────────────────────────────────────────
@app.route("/forum")
def forum():
    categories = get_all_categories()
    return render_template("forum.html", categories=categories)

@app.route("/forum/category/<int:cat_id>")
def category(cat_id):
    cat = get_category_by_id(cat_id)
    if not cat:
        abort(404)

    page = request.args.get("page", 1, type=int)
    topics, total = get_topics_by_category(cat_id, page)
    total_pages = max(1, (total + Config.POSTS_PER_PAGE - 1) // Config.POSTS_PER_PAGE)

    return render_template("category.html", category=cat, topics=topics, page=page, total_pages=total_pages)

# ─── Новая тема ──────────────────────────────────────────────────────────────
@app.route("/forum/topic/new/<int:cat_id>", methods=["GET", "POST"])
@login_required
def new_topic(cat_id):
    block_redirect = enforce_can_post()
    if block_redirect:
        return block_redirect

    cat = get_category_by_id(cat_id)
    if not cat:
        abort(404)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if not title or not content:
            flash("Заполните заголовок и текст.", "danger")
        elif len(title) < 5:
            flash("Заголовок — минимум 5 символов.", "danger")
        elif len(content) < 10:
            flash("Сообщение слишком короткое.", "danger")
        else:
            full_text = f"{title}\n\n{content}"
            mod_result = moderate_content(full_text)

            if is_toxic_local(full_text):
                mod_result["approved"] = False
                mod_result["toxicity_score"] = max(mod_result.get("toxicity_score", 0.0), 0.95)
                mod_result["reason"] = "Сообщение содержит недопустимую лексику/оскорбления."

            if mod_result["approved"]:
                topic_id = create_topic(cat_id, session["user_id"], title)
                create_post(
                    topic_id, session["user_id"], content,
                    is_moderated=1,
                    toxicity_score=mod_result.get("toxicity_score", 0.0),
                    ai_comment=mod_result.get("reason", "")
                )
                flash("Тема успешно создана!", "success")
                return redirect(url_for("topic", topic_id=topic_id))

            # blocked -> warning + possible restriction
            vio = register_user_violation(session["user_id"])
            if vio.get("restricted_until"):
                flash(
                    f"Тема заблокирована: {mod_result.get('reason','')}. "
                    f"У вас 3/3 предупреждения — ограничение публикаций на {vio.get('applied_minutes')} мин.",
                    "danger"
                )
            else:
                flash(
                    f"Тема заблокирована: {mod_result.get('reason','')}. "
                    f"Предупреждение {vio.get('warnings_count', 0)}/3.",
                    "danger"
                )
            return redirect(url_for("category", cat_id=cat_id))

    return render_template("new_topic.html", category=cat)

# ─── Просмотр темы + ответ ───────────────────────────────────────────────────
@app.route("/forum/topic/<int:topic_id>", methods=["GET", "POST"])
def topic(topic_id):
    t = get_topic_by_id(topic_id)
    if not t:
        abort(404)

    increment_topic_views(topic_id)

    page = request.args.get("page", 1, type=int)
    posts, total = get_posts_by_topic(topic_id, page)
    total_pages = max(1, (total + Config.POSTS_PER_PAGE - 1) // Config.POSTS_PER_PAGE)

    if request.method == "POST":
        if "user_id" not in session:
            flash("Войдите, чтобы оставить сообщение.", "warning")
            return redirect(url_for("login"))

        block_redirect = enforce_can_post()
        if block_redirect:
            return block_redirect

        if t["is_closed"]:
            flash("Тема закрыта для новых сообщений.", "warning")
            return redirect(url_for("topic", topic_id=topic_id))

        content = request.form.get("content", "").strip()
        if len(content) < 3:
            flash("Сообщение слишком короткое.", "danger")
        else:
            mod_result = moderate_content(content)

            if is_toxic_local(content):
                mod_result["approved"] = False
                mod_result["toxicity_score"] = max(mod_result.get("toxicity_score", 0.0), 0.95)
                mod_result["reason"] = "Сообщение содержит недопустимую лексику/оскорбления."

            is_moderated = 1 if mod_result["approved"] else 2

            create_post(
                topic_id, session["user_id"], content,
                is_moderated=is_moderated,
                toxicity_score=mod_result.get("toxicity_score", 0.0),
                ai_comment=mod_result.get("reason", "")
            )

            if mod_result["approved"]:
                flash("Сообщение опубликовано!", "success")
            else:
                vio = register_user_violation(session["user_id"])
                if vio.get("restricted_until"):
                    flash(
                        f"Сообщение заблокировано: {mod_result.get('reason','')}. "
                        f"У вас 3/3 предупреждения — ограничение публикаций на {vio.get('applied_minutes')} мин.",
                        "danger"
                    )
                else:
                    flash(
                        f"Сообщение заблокировано: {mod_result.get('reason','')}. "
                        f"Предупреждение {vio.get('warnings_count', 0)}/3.",
                        "danger"
                    )

        return redirect(url_for("topic", topic_id=topic_id, page=total_pages))

    return render_template("topic.html", topic=t, posts=posts, page=page, total_pages=total_pages)

# ─── API: лайки ──────────────────────────────────────────────────────────────
@app.route("/api/like/<int:post_id>", methods=["POST"])
@login_required
def like_post(post_id):
    # по желанию можно запретить лайки при бане/ограничении
    count = toggle_like(post_id, session["user_id"])
    return jsonify({"likes": count})

# ─── API: ИИ-чат ─────────────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Пустое сообщение"}), 400

    ok, msg = enforce_can_chat()
    if not ok:
        return jsonify({"answer": msg}), 403

    if "chat_session" not in session:
        session["chat_session"] = str(uuid.uuid4())
    chat_session = session["chat_session"]
    user_id = session.get("user_id")

    history = get_chat_history(chat_session)
    answer = chat_with_assistant(message, history)

    save_chat_message(chat_session, "user", message, user_id)
    save_chat_message(chat_session, "assistant", answer, user_id)

    return jsonify({"answer": answer})

@app.route("/api/suggest", methods=["POST"])
@login_required
def api_suggest():
    block_redirect = enforce_can_post()
    if block_redirect:
        return jsonify({"error": "Вам ограничены публикации/доступ."}), 403

    data = request.get_json(silent=True) or {}
    topic_id = data.get("topic_id")
    t = get_topic_by_id(topic_id) if topic_id else None
    if not t:
        return jsonify({"error": "Тема не найдена"}), 404

    posts, _ = get_posts_by_topic(topic_id)
    last_text = "\n\n".join(f"[{p['username']}]: {p['content']}" for p in posts[-5:])
    suggestion = suggest_reply(t["title"], last_text)
    return jsonify({"suggestion": suggestion})

@app.route("/api/summary/<int:topic_id>")
def api_summary(topic_id):
    t = get_topic_by_id(topic_id)
    if not t:
        return jsonify({"error": "Тема не найдена"}), 404

    posts, _ = get_posts_by_topic(topic_id)
    if not posts:
        return jsonify({"summary": "В теме пока нет сообщений."})

    text = "\n\n".join(f"[{p['username']}]: {p['content']}" for p in posts)
    summary = generate_topic_summary(text)
    return jsonify({"summary": summary})

# ─── API для admin.js (у вас он дергается, но роут отсутствовал) ────────────
@app.route("/api/admin/pending-count")
@admin_required
def api_admin_pending_count():
    pending = get_pending_posts()
    return jsonify({"count": len(pending)})

# ─── Админ-панель ────────────────────────────────────────────────────────────
@app.route("/admin")
@admin_required
def admin():
    stats = get_stats()
    pending = get_pending_posts()
    users = get_all_users()
    return render_template("admin.html", stats=stats, pending_posts=pending, users=users)

@app.route("/admin/moderate/<int:post_id>/<int:decision>")
@admin_required
def admin_moderate(post_id, decision):
    post = get_post_by_id(post_id)
    if post:
        moderate_post(
            post_id, decision,
            "Одобрено администратором." if decision == 1 else "Отклонено администратором."
        )
    flash("Решение сохранено.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/delete/post/<int:post_id>")
@admin_required
def admin_delete_post(post_id):
    delete_post(post_id)
    flash("Пост удалён.", "info")
    return redirect(request.referrer or url_for("admin"))

@app.route("/admin/pin/<int:topic_id>")
@admin_required
def admin_pin(topic_id):
    toggle_pin_topic(topic_id)
    flash("Статус закрепления изменён.", "info")
    return redirect(request.referrer or url_for("admin"))

@app.route("/admin/close/<int:topic_id>")
@admin_required
def admin_close(topic_id):
    toggle_close_topic(topic_id)
    flash("Статус темы изменён.", "info")
    return redirect(request.referrer or url_for("admin"))

@app.route("/admin/delete/topic/<int:topic_id>")
@admin_required
def admin_delete_topic(topic_id):
    delete_topic(topic_id)
    flash("Тема удалена.", "info")
    return redirect(request.referrer or url_for("admin"))

# ─── Админ: санкции пользователей ───────────────────────────────────────────
@app.route("/admin/user/<int:user_id>/restrict/<int:minutes>")
@admin_required
def admin_user_restrict(user_id, minutes):
    if user_id == session.get("user_id"):
        flash("Нельзя ограничить самого себя.", "danger")
        return redirect(url_for("admin"))
    until = set_user_restriction(user_id, minutes)
    flash(f"Пользователь ограничен на {minutes} мин (до {until[:16].replace('T',' ')}).", "warning")
    return redirect(url_for("admin"))

@app.route("/admin/user/<int:user_id>/unrestrict")
@admin_required
def admin_user_unrestrict(user_id):
    clear_user_restriction(user_id)
    flash("Ограничение снято.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/user/<int:user_id>/ban")
@admin_required
def admin_user_ban(user_id):
    if user_id == session.get("user_id"):
        flash("Нельзя забанить самого себя.", "danger")
        return redirect(url_for("admin"))
    # бан навсегда (можно расширить до бан-до-даты)
    ban_user(user_id, until_iso=None, reason="Блокировка администратором.")
    flash("Пользователь заблокирован.", "danger")
    return redirect(url_for("admin"))

@app.route("/admin/user/<int:user_id>/unban")
@admin_required
def admin_user_unban(user_id):
    unban_user(user_id)
    flash("Пользователь разбанен.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/user/<int:user_id>/delete")
@admin_required
def admin_user_delete(user_id):
    if user_id == session.get("user_id"):
        flash("Нельзя удалить самого себя.", "danger")
        return redirect(url_for("admin"))
    delete_user(user_id)
    flash("Пользователь удалён.", "info")
    return redirect(url_for("admin"))

# ─── Ошибки ──────────────────────────────────────────────────────────────────
@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Доступ запрещён"), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Страница не найдена"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, message="Внутренняя ошибка сервера"), 500

# ─── Запуск ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=Config.DEBUG)