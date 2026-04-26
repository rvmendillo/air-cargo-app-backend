import os
import warnings
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    warnings.warn("Missing GEMINI_API_KEY in .env – AI features will be unavailable")
else:
    genai.configure(api_key=API_KEY)
