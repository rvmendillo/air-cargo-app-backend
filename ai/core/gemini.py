import os
import warnings
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

# Ensure .env is loaded from the backend directory
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    warnings.warn("Missing GEMINI_API_KEY in .env – AI features will be unavailable")
else:
    genai.configure(api_key=API_KEY)
