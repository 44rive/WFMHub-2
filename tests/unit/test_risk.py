from wfmhub2.intelligence.risk.model import classify_risk


def test_safe_when_not_understaffed() -> None:
    score, severity = classify_risk(0.5)
    assert score == 0.0
    assert severity == "safe"


def test_critical_shortage() -> None:
    score, severity = classify_risk(-4.0)
    assert score > 0.6
    assert severity == "critical"
