import os

class Config:
    # ─── polza.ai (OpenAI-совместимый) ────────────────────────
    CSGPT_API_URL = os.environ.get("CSGPT_API_URL", "https://polza.ai/api/v1")
    CSGPT_MODEL   = os.environ.get("CSGPT_MODEL",   "google/gemma-3-27b-it")
    CSGPT_API_KEY = os.environ.get(
        "CSGPT_API_KEY",
        "pza_6rJ6NHqhojNveT_HxnQD_fVQfiMUXZKb",
    )

    # ─── База данных ──────────────────────────────────────────
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), "transservice.db")

    # ─── Сессия ───────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "transservice-super-secret-2024")
    DEBUG = True

    # ─── Модерация ────────────────────────────────────────────
    TOXICITY_THRESHOLD = float(os.environ.get("TOXICITY_THRESHOLD", "0.6"))
    POSTS_PER_PAGE     = int(os.environ.get("POSTS_PER_PAGE", "10"))

    # Прогрессивные блокировки (в минутах)
    AI_BAN_STEPS = [10, 30, 60]

    # ─── Загрузка файлов ──────────────────────────────────────
    MAX_UPLOAD_MB   = 10
    UPLOAD_FOLDER   = os.path.join(os.path.dirname(__file__), "static", "uploads")
    ALLOWED_EXTENSIONS = {
        "pdf", "doc", "docx", "xls", "xlsx",
        "png", "jpg", "jpeg", "gif", "webp",
        "zip", "rar", "txt", "csv",
    }
