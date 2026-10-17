from typing import Any, Dict, List

import yaml
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow the grader page to call this service directly from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Layer 1: hardcoded defaults (lowest precedence)
# ---------------------------------------------------------------------------
DEFAULTS: Dict[str, Any] = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

# ---------------------------------------------------------------------------
# Layer 2: config.development.yaml
# ---------------------------------------------------------------------------
YAML_TEXT = """
port: 8969
workers: 6
debug: true
log_level: warning
api_key: key-izjrski36l
"""

# ---------------------------------------------------------------------------
# Layer 3: .env file
# ---------------------------------------------------------------------------
DOTENV_TEXT = """
APP_DEBUG=false
APP_LOG_LEVEL=error
APP_API_KEY=key-94yptip8um
"""

# ---------------------------------------------------------------------------
# Layer 4: OS environment variables (APP_* prefix)
# ---------------------------------------------------------------------------
OS_ENV: Dict[str, str] = {
    "APP_PORT": "8479",
    "APP_LOG_LEVEL": "info",
}

ALIASES = {"num_workers": "workers"}
INT_KEYS = {"port", "workers"}
BOOL_KEYS = {"debug"}
TRUTHY = {"true", "1", "yes", "on"}


def normalize_key(raw: str) -> str:
    """APP_NUM_WORKERS / NUM_WORKERS / num_workers -> workers, APP_PORT -> port."""
    key = raw.strip().lower()
    if key.startswith("app_"):
        key = key[4:]
    return ALIASES.get(key, key)


def coerce(key: str, value: Any) -> Any:
    if key in INT_KEYS:
        return int(str(value).strip())
    if key in BOOL_KEYS:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in TRUTHY
    return str(value)


def parse_dotenv(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip("'\"")
    return out


def apply_layer(config: Dict[str, Any], layer: Dict[str, Any]) -> None:
    for raw_key, raw_val in layer.items():
        key = normalize_key(str(raw_key))
        try:
            config[key] = coerce(key, raw_val)
        except (ValueError, TypeError):
            continue  # ignore values that cannot be coerced


def build_config(overrides: List[str]) -> Dict[str, Any]:
    config: Dict[str, Any] = {}
    apply_layer(config, DEFAULTS)                              # 1 (lowest)
    apply_layer(config, yaml.safe_load(YAML_TEXT) or {})       # 2
    apply_layer(config, parse_dotenv(DOTENV_TEXT))             # 3
    apply_layer(config, {k: v for k, v in OS_ENV.items()
                         if k.upper().startswith("APP_")})     # 4

    cli: Dict[str, str] = {}
    for item in overrides:                                     # CLI (highest)
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        cli[k] = v
    apply_layer(config, cli)

    config["api_key"] = "****"  # never expose the real secret
    return config


@app.get("/effective-config")
def effective_config(set: List[str] = Query(default=[])):
    return build_config(set)


@app.get("/")
def root():
    return {"status": "ok", "endpoint": "/effective-config"}
