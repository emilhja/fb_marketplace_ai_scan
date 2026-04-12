"""Keyword / SERP title matching helpers."""

from ai_marketplace_monitor.utils import is_substring


def test_digit_token_boundary_rejects_substring_of_longer_number() -> None:
    assert not is_substring("5060", "item 15060 kr", digit_token_boundary=True)
    assert is_substring("5060", "RTX 5060 16GB", digit_token_boundary=True)
    assert is_substring("5060", "rtx5060", digit_token_boundary=True)


def test_digit_boundary_with_logical_and() -> None:
    expr = "(RTX OR NVIDIA) AND 5060"
    assert is_substring(expr, "NVIDIA 5060 16GB", digit_token_boundary=True)
    assert not is_substring(expr, "NVIDIA 15060", digit_token_boundary=True)
