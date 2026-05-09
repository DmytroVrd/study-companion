from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class SM2State:
    easiness: float = 2.5
    interval: int = 1
    repetitions: int = 0


def sm2_update(state: SM2State, quality: int) -> tuple[SM2State, datetime]:
    """Update SM-2 state. quality: 0-5, where 0 is blackout and 5 is perfect."""
    if not 0 <= quality <= 5:
        raise ValueError("quality must be in range 0..5")

    if quality < 3:
        state.repetitions = 0
        state.interval = 1
    else:
        if state.repetitions == 0:
            state.interval = 1
        elif state.repetitions == 1:
            state.interval = 6
        else:
            state.interval = round(state.interval * state.easiness)
        state.repetitions += 1

    state.easiness = max(
        1.3,
        state.easiness + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02),
    )
    next_review = datetime.utcnow() + timedelta(days=state.interval)
    return state, next_review
