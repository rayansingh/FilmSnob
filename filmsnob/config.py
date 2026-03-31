"""Config values from .env."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_BASE_URL = "https://api.themoviedb.org/3"

LETTERBOXD_BASE_URL = "https://letterboxd.com"

REQUEST_DELAY = 1.0
REQUEST_TIMEOUT = 15
