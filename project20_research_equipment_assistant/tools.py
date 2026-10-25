"""LabSlot deterministic scheduling tool.

This module is the *LabSlot validator engine*. It contains no LLM calls: every
decision is made with plain integer arithmetic on minutes-from-midnight so the
same input always produces the same output.

Tool / graph node identifier: ``check_equipment_session``
"""

import re

OPENING_MINUTE = 9 * 60    # 09:00 -> 540
CLOSING_MINUTE = 17 * 60   # 17:00 -> 1020
MINUTES_PER_DAY = 24 * 60  # 1440

# Structured equipment catalogue (mirrors docs/equipment_catalogue.txt).
EQUIPMENT = {
    "MIC-01": {
        "name": "Digital Microscope",
        "required_training": "MIC-BASIC",
        "max_duration_minutes": 120,
    },
    "PRN-01": {
        "name": "3D Printer",
        "required_training": "PRINT-BASIC",
        "max_duration_minutes": 240,
    },
    "SCN-01": {
        "name": "Document Scanner",
        "required_training": None,
        "max_duration_minutes": 60,
    },
}

# Every training module LabSlot knows about.
TRAINING_MODULES = {
    "MIC-BASIC": "Digital microscope basic training",
    "PRINT-BASIC": "3D printer basic training",
}

_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _parse_time(start_time):
    """Parse a strict HH:MM (24-hour) string into minutes from midnight."""
    if not isinstance(start_time, str):
        raise ValueError("start_time must be a string in HH:MM 24-hour format.")
    match = _TIME_PATTERN.match(start_time.strip())
    if not match:
        raise ValueError(
            f"Invalid start_time '{start_time}'. Use HH:MM 24-hour format, e.g. 09:30 or 14:00."
        )
    return int(match.group(1)) * 60 + int(match.group(2))


def _format_minutes(total_minutes):
    """Format minutes-from-midnight as HH:MM, flagging results past midnight."""
    next_day = total_minutes >= MINUTES_PER_DAY
    wrapped = total_minutes % MINUTES_PER_DAY
    text = f"{wrapped // 60:02d}:{wrapped % 60:02d}"
    return f"{text} (next day)" if next_day else text


def _normalise_training(completed_training):
    """Validate and de-duplicate caller-supplied training codes (order preserved)."""
    if completed_training is None:
        return []
    if isinstance(completed_training, (str, bytes)) or not hasattr(completed_training, "__iter__"):
        raise ValueError("completed_training must be a list of training module codes.")
    cleaned = []
    for code in completed_training:
        if not isinstance(code, str):
            raise ValueError("Training codes must be strings.")
        normalised = code.strip().upper()
        if normalised not in TRAINING_MODULES:
            known = ", ".join(sorted(TRAINING_MODULES))
            raise ValueError(f"Unknown training code '{code}'. Known training codes: {known}.")
        if normalised not in cleaned:
            cleaned.append(normalised)
    return cleaned


def check_equipment_session(
    equipment_code: str,
    start_time: str,
    duration_minutes: int,
    completed_training: list[str],
) -> dict:
    """Check whether a research-equipment session satisfies LabSlot booking rules.

    Returns ``{"eligible_to_request": bool, "equipment_name": str,
    "requested_end_time": str, "violations": list[str]}``.

    Raises ``ValueError`` with an explicit message for unknown equipment codes,
    unknown training codes, malformed times, or non-positive / non-integer
    durations. Passing every check does NOT confirm availability.
    """
    if not isinstance(equipment_code, str) or equipment_code.strip().upper() not in EQUIPMENT:
        known = ", ".join(sorted(EQUIPMENT))
        raise ValueError(f"Unknown equipment code '{equipment_code}'. Known equipment codes: {known}.")
    code = equipment_code.strip().upper()
    equipment = EQUIPMENT[code]

    start_minute = _parse_time(start_time)

    if isinstance(duration_minutes, bool) or not isinstance(duration_minutes, int) or duration_minutes <= 0:
        raise ValueError("duration_minutes must be a positive integer.")

    training = _normalise_training(completed_training)

    end_minute = start_minute + duration_minutes  # no midnight wrapping
    violations = []

    required = equipment["required_training"]
    if required and required not in training:
        violations.append(f"Missing required training: {required} is required for {code}.")

    limit = equipment["max_duration_minutes"]
    if duration_minutes > limit:
        violations.append(
            f"Requested duration of {duration_minutes} minutes exceeds the {limit}-minute limit for {code}."
        )

    if start_minute < OPENING_MINUTE:
        violations.append(f"Session starts at {_format_minutes(start_minute)}, before the 09:00 opening time.")

    if end_minute > CLOSING_MINUTE:
        violations.append(
            f"Session ends at {_format_minutes(end_minute)}, which exceeds the 17:00 closing time."
        )

    return {
        "eligible_to_request": not violations,
        "equipment_name": equipment["name"],
        "requested_end_time": _format_minutes(end_minute),
        "violations": violations,
    }


if __name__ == "__main__":
    demo_cases = [
        ("MIC-01", "10:00", 90, ["MIC-BASIC"]),
        ("MIC-01", "10:00", 90, []),
        ("PRN-01", "14:00", 240, ["PRINT-BASIC"]),
        ("SCN-01", "16:00", 60, []),
    ]
    print("LabSlot validator engine - demo cases")
    for case in demo_cases:
        print(case, "->", check_equipment_session(*case))
