from ai_marketplace_monitor.ai import AIResponse, parse_ai_rating_response


def test_parse_rating_zero_missing_vram() -> None:
    answer = (
        "The listing does not state VRAM.\n"
        "Rating 0: VRAM (GB) not stated in title or description; cannot verify 16 GB requirement."
    )
    parsed = parse_ai_rating_response(answer)
    assert parsed is not None
    score, comment, listing_kind = parsed
    assert score == 0
    assert "VRAM" in comment
    assert listing_kind == "unknown"
    res = AIResponse(score=score, comment=comment)
    assert res.conclusion == "Missing required data"


def test_parse_rating_three_unchanged() -> None:
    answer = "Rating 3: Adequate but vague on condition."
    parsed = parse_ai_rating_response(answer)
    assert parsed is not None
    score, comment, listing_kind = parsed
    assert score == 3
    assert "vague" in comment.lower()
    assert listing_kind == "unknown"


def test_parse_with_form_line_gpu_only() -> None:
    answer = (
        "Looks like a bare card.\n" "Rating 4: RTX 5060 Ti 16 GB standalone GPU.\n" "Form: gpu_only"
    )
    parsed = parse_ai_rating_response(answer)
    assert parsed is not None
    score, comment, listing_kind = parsed
    assert score == 4
    assert listing_kind == "gpu_only"
    assert "Form" not in comment


def test_parse_with_form_line_complete_pc() -> None:
    answer = "Rating 1: Full PC, not card-only.\nForm: complete_pc"
    parsed = parse_ai_rating_response(answer)
    assert parsed is not None
    score, _, listing_kind = parsed
    assert score == 1
    assert listing_kind == "complete_pc"


def test_parse_invalid_no_rating_digit() -> None:
    assert parse_ai_rating_response("Looks fine, no rating line.") is None
    assert parse_ai_rating_response("") is None


def test_ai_response_conclusion_unknown_score() -> None:
    res = AIResponse(score=9, comment="broken")
    assert res.conclusion == "Unknown rating"
