"""Sequential public codes like RPT-000123 / PRB-000123 / ACT-000123."""
from sqlalchemy.orm import Session

from app.models.system import SimulationParameter

_PREFIXES = {"report": "RPT", "cluster": "PRB", "action": "ACT", "evidence": "EVD"}


def next_code(db: Session, kind: str) -> str:
    key = f"seq.{kind}"
    prefix = _PREFIXES[kind]
    row = db.get(SimulationParameter, key)
    n = int((row.value_json or {}).get("n", 0)) + 1 if row else 1
    if row:
        row.value_json = {"n": n}
    else:
        db.add(SimulationParameter(key=key, value_json={"n": n}, description="internal counter"))
    return f"{prefix}-{n:06d}"
