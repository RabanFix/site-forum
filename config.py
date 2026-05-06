import os

class Config:
    CSGPT_API_KEY = os.environ.get(
        "CSGPT_API_KEY",
        "csk-ekjctwk8h6xcpdty63nrpxrpmpk9cxfpdfcvcf3vjkjnt8x2"
    )
    CSGPT_API_URL = "https://api.csGPT.ru/v1/chat/completions"
    CSGPT_MODEL   = "gpt-4o-mini"

    DATABASE_PATH = os.path.join(os.path.dirname(__file__), "transservice.db")

    SECRET_KEY = os.environ.get("SECRET_KEY", "transservice-super-secret-2024")
    DEBUG = True

    TOXICITY_THRESHOLD = 0.6
    POSTS_PER_PAGE     = 10

    # Прогрессивные блокировки (в минутах)
    AI_BAN_STEPS = [10, 30, 60]