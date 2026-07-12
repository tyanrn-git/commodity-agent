from app.services.formatting import format_amount, format_percent, format_quantity


def test_format_amount():
    assert format_amount("92000.000000") == "92 000"
    assert format_amount(850) == "850"
    assert format_amount("5000") == "5 000"


def test_format_percent():
    assert format_percent("7.6087") == "7,61"
    assert format_percent(100) == "100,00"


def test_format_quantity():
    assert format_quantity("100.000000", "MT") == "100 MT"
    assert format_quantity(100, "MT") == "100 MT"
