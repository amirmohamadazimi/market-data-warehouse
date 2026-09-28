"""Configuration loaded from the environment (.env)."""

import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/marketdata"
)

# The TSE daily price limit changed over time (3% to 7%), so it is not a constant:
# see tse_price_limits.csv, loaded into the tse_price_limits table by `init`.
