from companion.quiz.spaced import SM2State, sm2_update


def test_sm2_resets_after_failed_answer() -> None:
    state = SM2State(easiness=2.5, interval=6, repetitions=2)

    updated, next_review = sm2_update(state, quality=2)

    assert updated.repetitions == 0
    assert updated.interval == 1
    assert updated.easiness < 2.5
    assert next_review is not None


def test_sm2_grows_interval_after_repeated_success() -> None:
    state = SM2State(easiness=2.5, interval=6, repetitions=2)

    updated, _ = sm2_update(state, quality=5)

    assert updated.repetitions == 3
    assert updated.interval == 15
    assert updated.easiness >= 2.5


def test_sm2_rejects_invalid_quality() -> None:
    try:
        sm2_update(SM2State(), quality=6)
    except ValueError as exc:
        assert "quality" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
