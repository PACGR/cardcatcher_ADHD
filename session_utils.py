# -*- coding: utf-8 -*-
"""Shared validation for participant/session identifiers and random seeds."""


IDENTIFIER_FIELDS = {
    "SubType": "집단 코드",
    "SubIdx": "참가자 번호",
    "SubSes": "세션 번호",
}
MAX_SESSION_SEED = (2 ** 32) - 1


def normalize_session_inputs(subject_info):
    normalized = dict(subject_info)
    for field, label in IDENTIFIER_FIELDS.items():
        value = str(normalized.get(field, "")).strip()
        if not value:
            raise ValueError(f"{label}({field})를 입력해 주세요.")
        if value in {".", ".."} or not all(
            character.isalnum() or character in "_-"
            for character in value
        ):
            raise ValueError(
                f"{label}({field})에는 문자, 숫자, 밑줄(_), "
                "하이픈(-)만 사용할 수 있습니다."
            )
        normalized[field] = value

    seed_text = str(normalized.get("Seed", "")).strip()
    if seed_text:
        if not seed_text.isdecimal():
            raise ValueError("Seed는 비워 두거나 0 이상의 정수로 입력해 주세요.")
        seed_value = int(seed_text)
        if seed_value > MAX_SESSION_SEED:
            raise ValueError(
                f"Seed는 0부터 {MAX_SESSION_SEED} 사이여야 합니다."
            )
    else:
        seed_value = None
    normalized["Seed"] = seed_text
    return normalized, seed_value
