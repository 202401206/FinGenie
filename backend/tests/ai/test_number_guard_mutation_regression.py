"""Boundary regression discovered by the NG07 mutation campaign."""

from decimal import Decimal

from app.ai.number_guard import verify_numbers_in_text


def test_numeric_token_limit_accepts_128_digits_and_rejects_129():
    for length, expected in [(128, True), (129, False)]:
        digits = "1" * length
        assert (
            verify_numbers_in_text(f"Credits: {digits}.", [Decimal(digits)]) is expected
        )
