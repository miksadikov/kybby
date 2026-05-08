from pathlib import Path

from app.core.settings import settings


APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR.parent / 'data'
PROJECT_ROOT = settings.project_root
PROVIDERS_DIR = settings.providers_dir
OUT_DIR = settings.output_dir
RECRAFT_DIR = settings.recraft_dir
SEEDREAM_DIR = settings.seedream_dir
FLUX_DIR = settings.flux_dir
FIGMA_PLUGIN_DIR = settings.figma_plugin_dir
LEGACY_FLASK_DIR = settings.legacy_flask_dir
