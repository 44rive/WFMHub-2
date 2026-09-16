from wfmhub2.domain.forecasting.engine import ForecastCandidateScore, choose_lowest_wape


def test_forecast_selector_prefers_lowest_wape() -> None:
    candidates = [
        ForecastCandidateScore("seasonal-naive", bias=0.02, wape=0.12, mae=10.0),
        ForecastCandidateScore("xgboost", bias=-0.01, wape=0.09, mae=9.0),
    ]
    assert choose_lowest_wape(candidates).model_id == "xgboost"
