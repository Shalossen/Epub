from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    base_url: str = Field(default="https://japscan.si")
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    )
    concurrency: int = Field(default=5)
    request_timeout_seconds: float = Field(default=20.0)
    rate_limit_rps: float = Field(default=1.0)
    data_dir: Path = Field(default=Path("data"))
    images_dir_name: str = Field(default="images")

    class Config:
        env_prefix = "SCRAPER_"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
(settings.data_dir / settings.images_dir_name).mkdir(parents=True, exist_ok=True)