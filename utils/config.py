import os
from typing import Final
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

DB_PORT: Final[str] = str(os.getenv("PGPORT"))
DB_HOST: Final[str] = os.getenv("PGHOST")
DB_NAME: Final[str] = os.getenv("PGDATABASE")
DB_USER: Final[str] = os.getenv("PGUSER")
DB_PASSWORD: Final[str] = os.getenv("PGPASSWORD")

REDIS_URL = os.getenv("REDIS_URL", default="")

WEBHOOK_PATH: Final[str] = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL: Final[str] = os.getenv("WEBHOOK_URL")
WEBAPP_HOST: Final[str] = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT: Final[int] = int(os.getenv("PORT", "8000"))
