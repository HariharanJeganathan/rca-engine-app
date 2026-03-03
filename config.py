import os

# =========================
# Azure OpenAI Configuration
# =========================

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# =========================
# Model Configuration
# =========================

# Keep same logical structure in case you reference these elsewhere
FAST_MODEL = AZURE_OPENAI_DEPLOYMENT
SMART_MODEL = AZURE_OPENAI_DEPLOYMENT

# =========================
# Processing Configuration
# =========================

CHUNK_MAX_CHARS = 8000
MAX_FILE_SIZE_MB = 10
MAX_EXCEL_ROWS = 1000

# =========================
# Database Configuration
# =========================

DB_NAME = os.getenv("DB_NAME", "/home/rca_store.db")