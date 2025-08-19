from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env if present (local development)
load_dotenv()


@dataclass(frozen=True)
class AppConfig:
	port: int = int(os.getenv("APP_PORT", "8080"))
	db_host: str = os.getenv("DB_HOST", "localhost")
	db_port: int = int(os.getenv("DB_PORT", "5432"))
	db_name: str = os.getenv("DB_NAME", "configs")
	db_user: str = os.getenv("DB_USER", "configs")
	db_password: str = os.getenv("DB_PASSWORD", "configs")


def load_config() -> AppConfig:
	return AppConfig()
