import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("Missing GEMINI_API_KEY in .env")

genai.configure(api_key=API_KEY)