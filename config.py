
import os

# API Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Model Configuration
FAST_MODEL = "llama-3.3-70b-versatile"
SMART_MODEL = "llama-3.3-70b-versatile"

# Processing Configuration
CHUNK_MAX_CHARS = 8000
MAX_FILE_SIZE_MB = 10
MAX_EXCEL_ROWS = 1000

# Database Configuration
DB_NAME = os.getenv("DB_NAME", "/home/rca_store.db")