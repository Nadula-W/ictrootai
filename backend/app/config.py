from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from urllib.parse import urlparse

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'sqlite:///./ictroot.db'
    environment: str = 'development'
    ollama_url: str = 'http://127.0.0.1:11434'
    ollama_model: str = 'qwen3:4b-instruct'
    embedding_model: str = 'embeddinggemma'
    ollama_timeout: int = 120
    secure_cookies: bool = False

    @model_validator(mode='after')
    def local_ai_only(self):
        parsed=urlparse(self.ollama_url)
        if parsed.hostname not in ('localhost','127.0.0.1','::1') or parsed.scheme not in ('http','https') or parsed.username or parsed.password:
            raise ValueError('Ollama must use a loopback URL with no embedded credentials')
        if self.environment!='development' and not self.secure_cookies:
            raise ValueError('Non-development deployments require SECURE_COOKIES=true and HTTPS')
        return self

settings = Settings()
