import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

PRESETS_PATH = Path(__file__).resolve().parent.parent / "presets" / "sport_presets.json"


class EventModulesConfig(BaseModel):
    """
    Pluggable module toggles for the Universal Parameterized Event Engine.
    Allows the same core engine to power Football, Trips (Prague->Dresden), Book Clubs, and Pub Quizzes.
    """

    roles_enabled: bool = True
    team_draft_enabled: bool = True
    score_tracking_enabled: bool = True
    mvp_voting_enabled: bool = True
    inventory_enabled: bool = True
    billing_enabled: bool = True
    late_tracking_enabled: bool = True


class SportPreset(BaseModel):
    code: str
    category: str = "sport"  # "sport" | "trip" | "club" | "social" | "custom"
    icon: str = "⚽"
    name: Dict[str, str] = Field(default_factory=dict)
    terminology: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    modules: EventModulesConfig = Field(default_factory=EventModulesConfig)
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

    def localized_terminology(self, locale: str = "en") -> Dict[str, str]:
        loc = (locale or "en").lower()
        if loc == "cz":
            loc = "cs"
        default_terms = {
            "event_noun": "Event",
            "participant_noun": "Participant",
            "venue_noun": "Location",
            "grouping_noun": "Groups",
        }
        terms = self.terminology.get(loc) or self.terminology.get("en") or {}
        return {**default_terms, **terms}

    def resolve_modules(self, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        base = self.modules.model_dump()
        if isinstance(overrides, dict):
            for k in base:
                if k in overrides and overrides[k] is not None:
                    base[k] = bool(overrides[k])
        return base


EventPreset = SportPreset


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


get_event_preset = get_sport_preset
list_event_presets = list_sport_presets
