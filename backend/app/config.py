import os
from dotenv import load_dotenv
load_dotenv()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").strip().lower()
if not LLM_PROVIDER:
	if OPENROUTER_API_KEY and OPENROUTER_API_KEY.strip() != "change-me":
		LLM_PROVIDER = "openrouter"
	elif ANTHROPIC_API_KEY.startswith("sk-or-"):
		# Be forgiving when an OpenRouter key was entered in the old key setting.
		OPENROUTER_API_KEY = ANTHROPIC_API_KEY
		LLM_PROVIDER = "openrouter"
	else:
		LLM_PROVIDER = "anthropic"
MODEL = os.getenv("OPENROUTER_MODEL" if LLM_PROVIDER == "openrouter" else "ANTHROPIC_MODEL", "openrouter/free" if LLM_PROVIDER == "openrouter" else "claude-sonnet-5-5")
SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./careerlens.db")
