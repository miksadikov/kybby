from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = 'KitYourBrand'
    debug: bool = True
    app_host: str = '127.0.0.1'
    app_port: int = 8000
    secret_key: str = 'change-me'

    project_root: Path = BASE_DIR
    providers_dir: Path = BASE_DIR / 'providers'
    output_dir: Path = BASE_DIR / 'out'
    recraft_dir: Path = BASE_DIR / 'providers' / 'brandkit_recraft'
    seedream_dir: Path = BASE_DIR / 'providers' / 'brandkit_seedream'
    flux_dir: Path = BASE_DIR / 'providers' / 'brandkit_flux2'
    figma_plugin_dir: Path = BASE_DIR.parent / 'brandkit_figma_plugin_provider'
    legacy_flask_dir: Path = BASE_DIR.parent / 'brandkit_tokens_ui_three_providers'
    data_dir: Path = BASE_DIR / 'data'

    # HTTP к внешним провайдерам (таймауты / повторы при 429 и 5xx).
    provider_http_timeout_seconds: float = 120.0
    provider_http_max_retries: int = 3
    provider_http_retry_backoff_base: float = 1.0

    # Дубли .env; явно прокидываются в env подпроцессов brandkit_* при генерации.
    recraft_api_key: str | None = None
    openrouter_api_key: str | None = None
    openrouter_referer: str | None = None
    openrouter_title: str | None = None

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')


settings = Settings()
