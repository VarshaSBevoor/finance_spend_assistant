import os
from pathlib import Path

DEFAULT_MODEL = "qwen2.5:7b-instruct"
DEFAULT_HOST = "http://localhost:11434"
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def read_env_file(path: Path = ENV_FILE) -> dict[str, str]:
    """Read KEY=value lines. Blank lines and lines starting with # are skipped."""
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_setting(name: str, default: str, file_values: dict[str, str]) -> str:
    """A real environment variable wins, then the .env file, then the default."""
    return os.environ.get(name) or file_values.get(name) or default
