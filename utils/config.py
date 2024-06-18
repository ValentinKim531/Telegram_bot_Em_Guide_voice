import os
from typing import Final
from dotenv import load_dotenv

load_dotenv()


DB_PORT: Final[str] = str(os.getenv("PGPORT"))
DB_HOST: Final[str] = os.getenv("PGHOST")
DB_NAME: Final[str] = os.getenv("PGDATABASE")
DB_USER: Final[str] = os.getenv("POSTGRES_USER")
DB_PASSWORD: Final[str] = os.getenv("POSTGRES_PASSWORD")
