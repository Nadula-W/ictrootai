from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator, field_validator, SecretStr, Field
from urllib.parse import urlparse
from pathlib import Path
from typing import Literal
from .db_url import validate_database_url

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[1]/'.env', extra='ignore', hide_input_in_errors=True)
    database_url: SecretStr = SecretStr('')
    database_transport: Literal['direct','supabase_websocket'] = 'direct'
    database_pool_size: int = Field(default=5,ge=1,le=50)
    database_max_overflow: int = Field(default=5,ge=0,le=50)
    database_pool_timeout: int = Field(default=10,ge=1,le=120)
    database_pool_recycle: int = Field(default=1800,ge=60)
    environment: str = 'development'
    ollama_url: str = 'http://127.0.0.1:11434'
    ollama_model: str = 'qwen3:4b-instruct'
    embedding_model: str = 'embeddinggemma'
    ollama_timeout: int = 120
    secure_cookies: bool = False

    @field_validator('database_url',mode='before')
    @classmethod
    def postgres_database(cls,value):
        raw=value.get_secret_value() if isinstance(value,SecretStr) else value
        return SecretStr(validate_database_url(raw)) if raw else SecretStr('')

    @model_validator(mode='after')
    def local_ai_only(self):
        parsed=urlparse(self.ollama_url)
        if parsed.hostname not in ('localhost','127.0.0.1','::1') or parsed.scheme not in ('http','https') or parsed.username or parsed.password:
            raise ValueError('Ollama must use a loopback URL with no embedded credentials')
        if self.environment!='development' and not self.secure_cookies:
            raise ValueError('Non-development deployments require SECURE_COOKIES=true and HTTPS')
        return self

settings = Settings()
