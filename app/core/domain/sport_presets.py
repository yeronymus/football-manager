import json
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field

PRESETS_PATH = Path(__file__).resolve().parent.parent / "presets" / "sport_presets.json"


class SportPreset(BaseModel):
    code: str
    icon: str = "⚽"
    name: Dict[str, str] = Field(default_factory=dict)
    has_goalkeeper: bool = True
    default_team_count: int = 2
    supported_team_counts: List[int] = Field(default_factory=lambda: [2, 3])
    default_main_players_count: int = 22
    default_max_players: int = 26
    default_duration_hours: float = 2.0
    pitch_formats: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    card_system_enabled: bool = True

    def localized_name(self, locale: str = "en") -> str:
        loc = (locale or "en").lower()
        if loc == "cz":
            loc = "cs"
        return self.name.get(loc) or self.name.get("en") or self.code.title()


def load_sport_presets() -> Dict[str, SportPreset]:
    if not PRESETS_PATH.exists():
        return {"football": SportPreset(code="football", name={"en": "Football"})}
    raw = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    return {code: SportPreset.model_validate(spec) for code, spec in raw.items()}


SPORT_PRESETS: Dict[str, SportPreset] = load_sport_presets()


def get_sport_preset(sport_type: str | None) -> SportPreset:
    code = (sport_type or "football").strip().lower()
    return SPORT_PRESETS.get(code) or SPORT_PRESETS["football"]


def list_sport_presets() -> List[SportPreset]:
    return list(SPORT_PRESETS.values())
