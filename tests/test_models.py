from polymarket_bot.models import Market, Outcome


def test_from_api_parses_json_string_fields():
    raw = {
        "id": "1",
        "slug": "m",
        "question": "Will X win?",
        "status": "MARKET_STATUS_OPEN",
        "closed": False,
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.60", "0.45"]',
    }
    m = Market.from_api(raw)
    assert m.outcomes == ["Yes", "No"]
    assert m.outcome_prices == [0.60, 0.45]
    assert m.price(Outcome.YES) == 0.60
    assert m.price(Outcome.NO) == 0.45


def test_price_falls_back_to_one_minus_yes_for_no():
    m = Market(
        id="1", slug="m", question="q", status="open", closed=False,
        outcomes=["Yes"], outcome_prices=[0.7],
    )
    assert abs(m.price(Outcome.NO) - 0.3) < 1e-9


def test_price_returns_zero_when_missing():
    m = Market(
        id="1", slug="m", question="q", status="open", closed=False,
        outcomes=["Yes"], outcome_prices=[],
    )
    assert m.price(Outcome.YES) == 0.0
