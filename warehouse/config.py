"""Configuration loaded from the environment (.env)."""

import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/marketdata"
)

# TSE daily price limit, used by the quality check for implausible jumps.
TSE_DAILY_LIMIT = 0.05
