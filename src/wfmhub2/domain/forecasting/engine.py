from dataclasses import dataclass


@dataclass(frozen=True)
class ForecastCandidateScore:
    model_id: str
    bias: float
    wape: float
    mae: float


def choose_lowest_wape(scores: list[ForecastCandidateScore]) -> ForecastCandidateScore:
    """Seed deterministic selector before richer service/horizon policies land."""
    if not scores:
        raise ValueError("At least one forecast candidate is required")
    return min(scores, key=lambda score: (score.wape, abs(score.bias), score.mae, score.model_id))
