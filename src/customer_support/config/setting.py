from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    GROQ_API_KEY: str
    BRAND_ID: str = "AmazonHelp"
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    DATASET_PATH: str = "data/raw/twcs.csv"
    GOLDEN_SET_PATH: str = "data/schemas/golden_set_final.jsonl"
    INTENT_CONFIDENCE_THRESHOLD: float = 0.7
    EVIDENCE_THRESHOLD: float = 0.6
    RETRIEVAL_TOP_K: int = 3

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
    )


settings = Settings()