import os
from pathlib import Path
from typing import Literal
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, HttpUrl, ValidationError, UUID4

class GameConfig(BaseModel):
    scenario: Literal[1, 2, 3]  # only 3 scenarios
    url: HttpUrl
    playerId: UUID4

class UIConfig(BaseModel):
    enabled: bool

class AppConfig(BaseModel):
    game: GameConfig
    ui: UIConfig

def load_config(path: Path = Path("config.yaml")) -> AppConfig:
    load_dotenv()

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    raw["game"]["playerId"] = os.environ["PLAYER_ID"]
    try:
        return AppConfig(**raw)
    except ValidationError as e:
        raise SystemExit(f"Invalid config: {e}")
