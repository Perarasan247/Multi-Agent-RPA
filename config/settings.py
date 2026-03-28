"""Application settings loaded from .env file using pydantic-settings."""

from pathlib import Path
from pydantic_settings import BaseSettings


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

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    model_config = {
        "env_file": str(Path(__file__).resolve().parent.parent / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
