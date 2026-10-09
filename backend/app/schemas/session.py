"""Identity responses. MeOut is the base later slices extend (streak, XP, settings...)."""
from pydantic import BaseModel

from .common import ConfigOut


class UserOut(BaseModel):
    id: str
    kind: str
    nickname: str | None
    avatar_key: str | None
    cefr_level: str | None
    hide_timer: bool
    streak: int = 0
    xp: int = 0
    level: int = 1
    level_progress: float = 0.0
    reflex_level_unlocked: int = 1


class GateOut(BaseModel):
    reason: str
    mandatory: bool = True


class MeOut(BaseModel):
    user: UserOut
    is_guest: bool
    gate: GateOut | None

    @classmethod
    def from_row(cls, row: dict, stats: dict | None = None) -> "MeOut":
        """Build from a users row (+ optional computed stats: streak/xp/level/level_progress).

        Whitelists fields: hashes, tokens, guardian data never leave."""
        user = UserOut(id=row["id"], kind=row["kind"], nickname=row["nickname"], avatar_key=row["avatar_key"],
                       cefr_level=row["cefr_level"], hide_timer=bool(row["hide_timer"]),
                       reflex_level_unlocked=row["reflex_level_unlocked"], **(stats or {}))
        gate = GateOut(reason="second_visit") if row["kind"] == "guest" and row["gate_required_at"] else None
        return cls(user=user, is_guest=row["kind"] == "guest", gate=gate)


class BootstrapOut(MeOut):
    csrf_token: str
    config: ConfigOut


class HeartbeatOut(BaseModel):
    gate: GateOut | None
