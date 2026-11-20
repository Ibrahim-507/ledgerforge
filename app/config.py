from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    database_url: str = "sqlite:///./ledgerforge.db"
    data_dir: str = "data"
    secret_key: str = "dev-only-change-me"
    model_config = SettingsConfigDict(extra="ignore", env_file=".env")
settings = Settings()
