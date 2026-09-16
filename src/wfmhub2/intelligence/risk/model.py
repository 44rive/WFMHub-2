from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IntervalRisk:
    interval_start: datetime
    service_scope: str
    staffing_gap: float
    risk_score: float
    severity: str


def classify_risk(staffing_gap: float) -> tuple[float, str]:
    if staffing_gap >= 0:
        return 0.0, "safe"
    magnitude = min(abs(staffing_gap) / 5.0, 1.0)
    if magnitude >= 0.6:
        return magnitude, "critical"
    if magnitude >= 0.3:
        return magnitude, "risk"
    return magnitude, "watch"
