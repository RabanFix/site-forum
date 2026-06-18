import sqlite3
import hashlib
import re
from datetime import datetime
from config import Config


def get_connection():
    """Возвращает соединение с БД."""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ─────────────────────────────────────────────
# Инициализация
# ─────────────────────────────────────────────


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        avatar TEXT DEFAULT 'default.png',
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        icon TEXT DEFAULT ' '
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL REFERENCES categories(id),
        user_id INTEGER NOT NULL REFERENCES users(id),
        title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        views INTEGER DEFAULT 0,
        is_pinned INTEGER DEFAULT 0,
        is_closed INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id),
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        is_moderated INTEGER DEFAULT 0,
        toxicity_score REAL DEFAULT 0.0,
        ai_comment TEXT DEFAULT ''
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ai_chat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id),
        UNIQUE(post_id, user_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS topic_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL,
        UNIQUE(topic_id, user_id)
    )
    """)

    conn.commit()

    # добавление новых колонок в users и topics
    _ensure_user_columns(conn)
    _ensure_topic_columns(conn)
    conn.commit()

    _seed_data(conn)
    conn.commit()
    conn.close()


from datetime import datetime, timedelta


def _ensure_user_columns(conn):
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}

    def add_col(sql):
        conn.execute(sql)

    if "warnings_count" not in cols:
        add_col(
            "ALTER TABLE users ADD COLUMN warnings_count INTEGER NOT NULL DEFAULT 0"
        )
    if "penalty_level" not in cols:
        add_col("ALTER TABLE users ADD COLUMN penalty_level INTEGER NOT NULL DEFAULT 0")
    if "restricted_until" not in cols:
        add_col("ALTER TABLE users ADD COLUMN restricted_until TEXT")
    if "is_banned" not in cols:
        add_col("ALTER TABLE users ADD COLUMN is_banned INTEGER NOT NULL DEFAULT 0")
    if "banned_until" not in cols:
        add_col("ALTER TABLE users ADD COLUMN banned_until TEXT")
    if "ban_reason" not in cols:
        add_col("ALTER TABLE users ADD COLUMN ban_reason TEXT DEFAULT ''")


def _ensure_topic_columns(conn):
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(topics)").fetchall()}
    if "report_count" not in cols:
        conn.execute(
            "ALTER TABLE topics ADD COLUMN report_count INTEGER NOT NULL DEFAULT 0"
        )
    if "is_reported" not in cols:
        conn.execute(
            "ALTER TABLE topics ADD COLUMN is_reported INTEGER NOT NULL DEFAULT 0"
        )
    if "addressed_to_user_id" not in cols:
        conn.execute(
            "ALTER TABLE topics ADD COLUMN addressed_to_user_id INTEGER REFERENCES users(id)"
        )
    if "attachment_path" not in cols:
        conn.execute("ALTER TABLE topics ADD COLUMN attachment_path TEXT")
    if "attachment_filename" not in cols:
        conn.execute("ALTER TABLE topics ADD COLUMN attachment_filename TEXT")


def register_user_violation(user_id: int) -> dict:
    """
    +1 предупреждение. Каждые 3 предупреждения -> ограничение:
    10 мин, потом 30, потом 60 (максимум).
    Администраторы имеют иммунитет — функция пропускается.
    """
    conn = get_connection()
    role_row = conn.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
    if role_row and role_row["role"] == "admin":
        conn.close()
        return {"ok": True, "skipped": True}

    u = conn.execute(
        "SELECT warnings_count, penalty_level FROM users WHERE id=?", (user_id,)
    ).fetchone()
    if not u:
        conn.close()
        return {"ok": False}

    warnings = int(u["warnings_count"] or 0) + 1
    penalty_level = int(u["penalty_level"] or 0)

    restricted_until = None
    applied_minutes = None

    if warnings >= 3:
        warnings = 0
        penalty_level += 1
        minutes = [10, 30, 60][min(penalty_level - 1, 2)]
        restricted_until = (datetime.now() + timedelta(minutes=minutes)).isoformat()
        applied_minutes = minutes

        conn.execute(
            "UPDATE users SET warnings_count=?, penalty_level=?, restricted_until=? WHERE id=?",
            (warnings, penalty_level, restricted_until, user_id),
        )
    else:
        conn.execute(
            "UPDATE users SET warnings_count=? WHERE id=?", (warnings, user_id)
        )

    conn.commit()
    conn.close()
    return {
        "ok": True,
        "warnings_count": warnings,
        "penalty_level": penalty_level,
        "restricted_until": restricted_until,
        "applied_minutes": applied_minutes,
    }


def set_user_restriction(user_id: int, minutes: int, reason: str = ""):
    until = (datetime.now() + timedelta(minutes=minutes)).isoformat()
    conn = get_connection()
    conn.execute("UPDATE users SET restricted_until=? WHERE id=?", (until, user_id))
    conn.commit()
    conn.close()
    return until


def clear_user_restriction(user_id: int):
    conn = get_connection()
    conn.execute("UPDATE users SET restricted_until=NULL WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def ban_user(user_id: int, until_iso: str | None = None, reason: str = ""):
    conn = get_connection()
    role_row = conn.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
    if role_row and role_row["role"] == "admin":
        conn.close()
        return
    conn.execute(
        "UPDATE users SET is_banned=1, banned_until=?, ban_reason=? WHERE id=?",
        (until_iso, reason, user_id),
    )
    conn.commit()
    conn.close()


def unban_user(user_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE users SET is_banned=0, banned_until=NULL, ban_reason='' WHERE id=?",
        (user_id,),
    )
    conn.commit()
    conn.close()


def delete_user(user_id: int):
    """
    Удаление пользователя и его контента (аккуратно под вашу схему FK).
    """
    conn = get_connection()
    # удалим темы пользователя (каскадно удалятся посты, и лайки к постам тоже)
    conn.execute("DELETE FROM topics WHERE user_id=?", (user_id,))
    # удалим оставшиеся посты пользователя в чужих темах (лайки к ним каскадом)
    conn.execute("DELETE FROM posts WHERE user_id=?", (user_id,))
    # удалим лайки пользователя
    conn.execute("DELETE FROM likes WHERE user_id=?", (user_id,))
    # удалим историю чата
    conn.execute("DELETE FROM ai_chat WHERE user_id=?", (user_id,))
    # удалим самого пользователя
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def add_warning(user_id):
    conn = get_connection()
    user = conn.execute(
        "SELECT warnings, role FROM users WHERE id=?", (user_id,)
    ).fetchone()
    if not user:
        conn.close()
        return
    if user["role"] == "admin":
        conn.close()
        return

    warnings = user["warnings"] + 1

    block_minutes = 0
    if warnings == 3:
        block_minutes = 10
    elif warnings == 4:
        block_minutes = 30
    elif warnings >= 5:
        block_minutes = 60

    blocked_until = None
    if block_minutes:
        blocked_until = (datetime.now() + timedelta(minutes=block_minutes)).isoformat()

    conn.execute(
        """
        UPDATE users
        SET warnings=?, blocked_until=?
        WHERE id=?
    """,
        (warnings, blocked_until, user_id),
    )

    conn.commit()
    conn.close()


def is_user_blocked(user_id):
    conn = get_connection()
    user = conn.execute(
        "SELECT blocked_until, is_banned FROM users WHERE id=?", (user_id,)
    ).fetchone()
    conn.close()

    if not user:
        return False, None

    if user["is_banned"]:
        return True, "Пользователь заблокирован администратором."

    if user["blocked_until"]:
        blocked_time = datetime.fromisoformat(user["blocked_until"])
        if datetime.now() < blocked_time:
            return True, f"Временная блокировка до {blocked_time.strftime('%H:%M')}"

    return False, None


def _migrate_categories(conn):
    """Переименовывает старые категории форума в новые (для существующих БД)."""
    rename_map = {
        "Общие вопросы": (
            "Объявления руководства",
            "Официальные сообщения и обновления от руководителей",
            "📢",
        ),
        "Грузоперевозки": (
            "Статусы заказов",
            "Информация о ходе выполнения заказов",
            "📦",
        ),
        "Логистика и маршруты": (
            "Вопросы и заявки",
            "Задайте вопрос руководителю или подайте заявку",
            "❓",
        ),
        "Техническое обслуживание": (
            "Транспортные услуги",
            "Информация об услугах и условиях перевозки",
            "🚛",
        ),
        "Нормативная база": (
            "Документы и договоры",
            "Образцы, шаблоны, требования к документам",
            "📋",
        ),
    }
    for old_name, (new_name, new_desc, new_icon) in rename_map.items():
        conn.execute(
            """
            UPDATE categories SET name=?, description=?, icon=?
            WHERE name=?
              AND NOT EXISTS (SELECT 1 FROM categories WHERE name=?)
        """,
            (new_name, new_desc, new_icon, old_name, new_name),
        )


def _seed_data(conn):
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE username='admin'")
    if not cur.fetchone():
        cur.execute(
            """
            INSERT INTO users (username, password_hash, role, created_at)
            VALUES (?, ?, 'admin', ?)
        """,
            ("admin", _hash("admin123"), datetime.now().isoformat()),
        )

    cur.execute("SELECT id FROM users WHERE username='ivanov'")
    if not cur.fetchone():
        cur.execute(
            """
            INSERT INTO users (username, password_hash, role, created_at)
            VALUES (?, ?, 'user', ?)
        """,
            ("ivanov", _hash("pass123"), datetime.now().isoformat()),
        )

    # Сначала мигрируем старые названия (если существуют)
    _migrate_categories(conn)

    # Затем вставляем новые категории (INSERT OR IGNORE — безопасно для существующих)
    categories = [
        (
            "Объявления руководства",
            "Официальные сообщения и обновления от руководителей",
            "📢",
        ),
        ("Статусы заказов", "Информация о ходе выполнения заказов", "📦"),
        ("Вопросы и заявки", "Задайте вопрос руководителю или подайте заявку", "❓"),
        ("Транспортные услуги", "Информация об услугах и условиях перевозки", "🚛"),
        ("Документы и договоры", "Образцы, шаблоны, требования к документам", "📋"),
    ]
    for name, desc, icon in categories:
        cur.execute(
            "INSERT OR IGNORE INTO categories (name, description, icon) VALUES (?,?,?)",
            (name, desc, icon),
        )

    conn.commit()


# ─────────────────────────────────────────────
# Вспомогательные
# ─────────────────────────────────────────────


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ─────────────────────────────────────────────
# Пользователи
# ─────────────────────────────────────────────


def create_user(username, password, role="user"):
    try:
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO users (username, password_hash, role, created_at)
            VALUES (?, ?, ?, ?)
        """,
            (username, _hash(password), role, datetime.now().isoformat()),
        )
        conn.commit()
        result = get_user_by_username(username)
        conn.close()
        return result
    except sqlite3.IntegrityError:
        return None


def get_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_username(username):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def verify_user(username, password):
    user = get_user_by_username(username)
    if user and user["password_hash"] == _hash(password):
        return user
    return None


def get_all_users():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# Категории
# ─────────────────────────────────────────────


def get_all_categories():
    conn = get_connection()
    rows = conn.execute("""
        SELECT c.*,
               COUNT(DISTINCT t.id) as topic_count,
               COUNT(DISTINCT p.id) as post_count
        FROM categories c
        LEFT JOIN topics t ON t.category_id = c.id
        LEFT JOIN posts  p ON p.topic_id = t.id AND p.is_moderated = 1
        GROUP BY c.id
        ORDER BY c.id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_category_by_id(cat_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ─────────────────────────────────────────────
# Темы
# ─────────────────────────────────────────────


def create_topic(
    category_id,
    user_id,
    title,
    addressed_to_user_id=None,
    is_pinned=0,
    attachment_path=None,
    attachment_filename=None,
):
    conn = get_connection()
    cur = conn.execute(
        """
        INSERT INTO topics
            (category_id, user_id, title, created_at,
             addressed_to_user_id, is_pinned, attachment_path, attachment_filename)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            category_id,
            user_id,
            title,
            datetime.now().isoformat(),
            addressed_to_user_id,
            is_pinned,
            attachment_path,
            attachment_filename,
        ),
    )
    topic_id = cur.lastrowid
    conn.commit()
    conn.close()
    return topic_id


def get_topics_by_category(cat_id, page=1):
    limit = Config.POSTS_PER_PAGE
    offset = (page - 1) * limit
    conn = get_connection()

    total = conn.execute(
        "SELECT COUNT(*) FROM topics WHERE category_id=?", (cat_id,)
    ).fetchone()[0]

    rows = conn.execute(
        """
        SELECT t.*,
               u.username,
               u2.username as addressed_to_username,
               COUNT(p.id) as reply_count,
               MAX(p.created_at) as last_post_at
        FROM topics t
        JOIN users u ON u.id = t.user_id
        LEFT JOIN users u2 ON u2.id = t.addressed_to_user_id
        LEFT JOIN posts p ON p.topic_id = t.id AND p.is_moderated = 1
        WHERE t.category_id = ?
        GROUP BY t.id
        ORDER BY t.is_pinned DESC, COALESCE(MAX(p.created_at), t.created_at) DESC
        LIMIT ? OFFSET ?
    """,
        (cat_id, limit, offset),
    ).fetchall()

    conn.close()
    return [dict(r) for r in rows], total


def get_topic_by_id(topic_id):
    conn = get_connection()
    row = conn.execute(
        """
        SELECT t.*, u.username, c.name as category_name,
               u2.username as addressed_to_username
        FROM topics t
        JOIN users u ON u.id = t.user_id
        JOIN categories c ON c.id = t.category_id
        LEFT JOIN users u2 ON u2.id = t.addressed_to_user_id
        WHERE t.id = ?
    """,
        (topic_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None



def increment_topic_views(topic_id):
    conn = get_connection()
    conn.execute("UPDATE topics SET views = views + 1 WHERE id=?", (topic_id,))
    conn.commit()
    conn.close()


def toggle_pin_topic(topic_id):
    conn = get_connection()
    conn.execute("UPDATE topics SET is_pinned = 1 - is_pinned WHERE id=?", (topic_id,))
    conn.commit()
    conn.close()


def toggle_close_topic(topic_id):
    conn = get_connection()
    conn.execute("UPDATE topics SET is_closed = 1 - is_closed WHERE id=?", (topic_id,))
    conn.commit()
    conn.close()


def delete_topic(topic_id):
    """Удаляет тему со ВСЕМИ постами и лайками."""
    conn = get_connection()
    conn.execute(
        """
        DELETE FROM likes WHERE post_id IN (
            SELECT id FROM posts WHERE topic_id = ?
        )
    """,
        (topic_id,),
    )
    conn.execute("DELETE FROM posts WHERE topic_id = ?", (topic_id,))
    conn.execute("DELETE FROM topic_reports WHERE topic_id = ?", (topic_id,))
    conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
    conn.commit()
    conn.close()


def get_all_topics(limit=200):
    """Возвращает все темы для панели администратора."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT t.*, u.username, c.name as category_name,
               COUNT(DISTINCT p.id) as reply_count
        FROM topics t
        JOIN users u ON u.id = t.user_id
        JOIN categories c ON c.id = t.category_id
        LEFT JOIN posts p ON p.topic_id = t.id AND p.is_moderated = 1
        GROUP BY t.id
        ORDER BY t.is_reported DESC, t.report_count DESC, t.created_at DESC
        LIMIT ?
    """,
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def report_topic(topic_id: int, user_id: int, threshold: int = 3) -> dict:
    """
    Пользователь жалуется на тему.
    Возвращает {'already': True} если уже жаловался,
    {'reported': True, 'count': n, 'flagged': bool} иначе.
    """
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO topic_reports (topic_id, user_id, created_at) VALUES (?,?,?)",
            (topic_id, user_id, datetime.now().isoformat()),
        )
        conn.commit()
    except Exception:
        conn.close()
        return {"already": True}

    count = conn.execute(
        "SELECT COUNT(*) FROM topic_reports WHERE topic_id=?", (topic_id,)
    ).fetchone()[0]

    flagged = count >= threshold
    conn.execute(
        "UPDATE topics SET report_count=?, is_reported=? WHERE id=?",
        (count, 1 if flagged else 0, topic_id),
    )
    conn.commit()
    conn.close()
    return {"already": False, "count": count, "flagged": flagged}


def dismiss_topic_report(topic_id: int):
    """Сбросить все жалобы на тему (администратор)."""
    conn = get_connection()
    conn.execute("DELETE FROM topic_reports WHERE topic_id=?", (topic_id,))
    conn.execute(
        "UPDATE topics SET report_count=0, is_reported=0 WHERE id=?", (topic_id,)
    )
    conn.commit()
    conn.close()


def get_reported_topics():
    """Возвращает темы с is_reported=1 для очереди администратора."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.*, u.username, c.name as category_name,
               COUNT(DISTINCT p.id) as reply_count
        FROM topics t
        JOIN users u ON u.id = t.user_id
        JOIN categories c ON c.id = t.category_id
        LEFT JOIN posts p ON p.topic_id = t.id AND p.is_moderated = 1
        WHERE t.is_reported = 1
        GROUP BY t.id
        ORDER BY t.report_count DESC, t.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# Посты
# ─────────────────────────────────────────────


def create_post(
    topic_id, user_id, content, is_moderated=0, toxicity_score=0.0, ai_comment=""
):
    conn = get_connection()
    cur = conn.execute(
        """
        INSERT INTO posts
            (topic_id, user_id, content, created_at,
             is_moderated, toxicity_score, ai_comment)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            topic_id,
            user_id,
            content,
            datetime.now().isoformat(),
            is_moderated,
            toxicity_score,
            ai_comment,
        ),
    )
    post_id = cur.lastrowid
    conn.commit()
    conn.close()
    return post_id


def get_posts_by_topic(topic_id, page=1):
    """Возвращает ТОЛЬКО одобренные посты (is_moderated = 1)."""
    limit = Config.POSTS_PER_PAGE
    offset = (page - 1) * limit
    conn = get_connection()

    total = conn.execute(
        "SELECT COUNT(*) FROM posts WHERE topic_id=? AND is_moderated = 1", (topic_id,)
    ).fetchone()[0]

    rows = conn.execute(
        """
        SELECT p.*,
               u.username,
               u.role,
               u.avatar,
               (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id) as like_count
        FROM posts p
        JOIN users u ON u.id = p.user_id
        WHERE p.topic_id = ? AND p.is_moderated = 1
        ORDER BY p.created_at ASC
        LIMIT ? OFFSET ?
    """,
        (topic_id, limit, offset),
    ).fetchall()

    conn.close()
    return [dict(r) for r in rows], total


def get_post_by_id(post_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_pending_posts():
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.*, u.username, t.title as topic_title
        FROM posts p
        JOIN users u ON u.id = p.user_id
        JOIN topics t ON t.id = p.topic_id
        WHERE p.is_moderated = 0
        ORDER BY p.created_at ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def moderate_post(post_id, decision, ai_comment=""):
    conn = get_connection()
    conn.execute(
        """
        UPDATE posts SET is_moderated=?, ai_comment=? WHERE id=?
    """,
        (decision, ai_comment, post_id),
    )
    conn.commit()
    conn.close()


def delete_post(post_id):
    """Удаляет пост и его лайки."""
    conn = get_connection()
    conn.execute("DELETE FROM likes WHERE post_id=?", (post_id,))
    conn.execute("DELETE FROM posts WHERE id=?", (post_id,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# Лайки
# ─────────────────────────────────────────────


def toggle_like(post_id, user_id):
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM likes WHERE post_id=? AND user_id=?", (post_id, user_id)
    ).fetchone()

    if existing:
        conn.execute(
            "DELETE FROM likes WHERE post_id=? AND user_id=?", (post_id, user_id)
        )
    else:
        conn.execute(
            "INSERT INTO likes (post_id, user_id) VALUES (?,?)", (post_id, user_id)
        )

    conn.commit()
    count = conn.execute(
        "SELECT COUNT(*) FROM likes WHERE post_id=?", (post_id,)
    ).fetchone()[0]
    conn.close()
    return count


# ─────────────────────────────────────────────
# AI-чат
# ─────────────────────────────────────────────


def save_chat_message(session_id, role, message, user_id=None):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO ai_chat (user_id, session_id, role, message, created_at)
        VALUES (?, ?, ?, ?, ?)
    """,
        (user_id, session_id, role, message, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_chat_history(session_id, limit=20):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT role, message FROM ai_chat
        WHERE session_id = ?
        ORDER BY created_at DESC
        LIMIT ?
    """,
        (session_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


# ─────────────────────────────────────────────
# Статистика
# ─────────────────────────────────────────────


def search_forum(query: str, limit: int = 40):
    """
    Поиск по темам (заголовок) и постам (содержимое).
    Возвращает (topic_results, post_results).
    """
    q = query.strip()
    if not q or len(q) < 2:
        return [], []
    like = f"%{q}%"
    conn = get_connection()

    topic_rows = conn.execute(
        """
        SELECT t.id, t.title, t.created_at, u.username,
               c.id AS cat_id, c.name AS cat_name, c.icon AS cat_icon
        FROM topics t
        JOIN users u ON u.id = t.user_id
        JOIN categories c ON c.id = t.category_id
        WHERE t.title LIKE ? COLLATE NOCASE
        ORDER BY t.created_at DESC
        LIMIT ?
    """,
        (like, limit),
    ).fetchall()

    post_rows = conn.execute(
        """
        SELECT p.id, p.content, p.created_at, u.username,
               t.id AS topic_id, t.title AS topic_title,
               c.id AS cat_id, c.name AS cat_name
        FROM posts p
        JOIN users u ON u.id = p.user_id
        JOIN topics t ON t.id = p.topic_id
        JOIN categories c ON c.id = t.category_id
        WHERE p.is_moderated = 1 AND p.content LIKE ? COLLATE NOCASE
        ORDER BY p.created_at DESC
        LIMIT ?
    """,
        (like, limit),
    ).fetchall()

    conn.close()
    return [dict(r) for r in topic_rows], [dict(r) for r in post_rows]


def admin_clear_own_restrictions(user_id: int):
    """Снимает все ограничения с администратора (для самого себя)."""
    conn = get_connection()
    conn.execute(
        """
        UPDATE users
        SET is_banned=0, banned_until=NULL, ban_reason='',
            restricted_until=NULL, warnings_count=0
        WHERE id=? AND role='admin'
    """,
        (user_id,),
    )
    conn.commit()
    conn.close()


def get_stats():
    conn = get_connection()
    stats = {
        "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "topics": conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0],
        "posts": conn.execute(
            "SELECT COUNT(*) FROM posts WHERE is_moderated=1"
        ).fetchone()[0],
        "pending": conn.execute(
            "SELECT COUNT(*) FROM posts WHERE is_moderated=0"
        ).fetchone()[0],
        "rejected": conn.execute(
            "SELECT COUNT(*) FROM posts WHERE is_moderated=2"
        ).fetchone()[0],
    }
    conn.close()
    return stats


def get_user_post_toxicity_history(user_id: int, limit: int = 20):
    """Последние N постов пользователя с оценкой токсичности для графика."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            p.id,
            p.toxicity_score,
            p.is_moderated,
            SUBSTR(p.content, 1, 80) AS snippet,
            p.created_at
        FROM posts p
        WHERE p.user_id = ?
        ORDER BY p.created_at DESC
        LIMIT ?
    """,
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_user_toxicity_stats():
    """Статистика токсичности по каждому пользователю для дашборда."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            u.id,
            u.username,
            COALESCE(u.warnings_count, 0)  AS warnings_count,
            COALESCE(u.penalty_level, 0)   AS penalty_level,
            COALESCE(u.is_banned, 0)        AS is_banned,
            u.restricted_until,
            COUNT(p.id)                                               AS total_posts,
            SUM(CASE WHEN p.toxicity_score >= 0.6 THEN 1 ELSE 0 END) AS flagged_posts,
            ROUND(COALESCE(AVG(p.toxicity_score), 0.0), 3)           AS avg_toxicity,
            ROUND(COALESCE(MAX(p.toxicity_score), 0.0), 3)           AS max_toxicity
        FROM users u
        LEFT JOIN posts p ON p.user_id = u.id
        WHERE u.role != 'admin'
        GROUP BY u.id
        ORDER BY avg_toxicity DESC, flagged_posts DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
