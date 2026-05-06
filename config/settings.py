"""Application settings loaded from .env file using pydantic-settings."""

import sys
from pathlib import Path
from pydantic_settings import BaseSettings

# When running as a PyInstaller exe, look in the current working directory
# for .env, and inside the bundled temp folder for .secrets (hidden from client).
# When running as a script, look relative to this file.
if getattr(sys, "frozen", False):
    _BASE_DIR = Path.cwd()
    _BUNDLE_DIR = Path(sys._MEIPASS)
else:
    _BASE_DIR = Path(__file__).resolve().parent.parent
    _BUNDLE_DIR = _BASE_DIR


class Settings(BaseSettings):
    """Excellon RPA system configuration.

    All values are loaded from .env file in project root automatically.
    """

    # Application
    app_exe_path: str = r"C:\Excellon\Excellon.exe"
    app_window_title: str = "Excellon 5.0"

    # Agent 1: Login
    excellon_username: str = ""
    excellon_password: str = ""

    # Agent 2: Navigation
    report_key: str = "spareparts_sales_statement"

    # Agent 3: Filter
    filter_from_date: str = "01/03/2026"
    filter_to_date: str = "31/03/2026"

    # Agent 4: Download
    dealer_code: str = "D10836"
    branch_code: str = "BR001"
    save_path: str = r"C:\Reports\Downloads"
    download_format: str = "xlsx"

    # Vision
    gemini_api_key: str = ""
    anthropic_api_key: str = ""

    # License
    license_secret: str = ""

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    model_config = {
        "env_file": [
            str(_BASE_DIR / ".env"),
            str(_BUNDLE_DIR / ".secrets"),
        ],
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
