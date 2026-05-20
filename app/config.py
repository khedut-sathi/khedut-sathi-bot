from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    gemini_api_key: str
    supabase_url: str
    supabase_key: str
    openai_api_key: str = ""
    r2_account_id: str = ""
    r2_access_key: str = ""
    r2_secret_key: str = ""
    r2_bucket_name: str = "farmer-copilot-images"
    weather_api_key: str = ""
    data_gov_api_key: str = ""
    app_env: str = "development"
    webhook_url: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
