"""의도 분류와 F2 조건 확인 (설계 문서 12절 classify_intent·collect_conditions).

ponytail: 키워드·정규식 규칙이다. 모델 호출 없이 빠르고 결과가 예측 가능하지만, 돌려 말한 요청은 general로 빠진다.
분류가 틀려도 general은 기존 루프(call_model)로 가므로 답이 막히지는 않는다. 오분류가 잦으면 작은 모델 분류로 바꾼다.
"""

from __future__ import annotations

import re

# 시스템 작업은 prompt_name으로 의도가 정해진다
PROMPT_INTENT = {"review_update": "update_review", "investigate_anomaly": "anomaly", "review_seat_request": "license",
                 "recommend_model": "recommend", "compare_candidates": "recommend"}
RULES = [  # 위에서부터 먼저 맞는 것
    ("anomaly", r"급증|경보|비용\s*(알림|증가|폭증)|원인\s*조사"),
    ("license", r"이용권|좌석|라이선스|회수|재배정|배정|plan_\w+"),
    ("recommend", r"추천|어떤\s*(모델|AI|제품|도구)|무슨\s*(모델|AI)|뭘\s*써|무엇을\s*써|어떤 걸\s*써"),
    ("update_review", r"업데이트|새\s*기능|릴리스"),
]

# F2 필수 조건 5개 (prompt_recommend_model.md 1단계와 같은 순서)
CONDITIONS = {
    "daily_volume": ("하루 건수", r"(하루|매일|일\s*평균|일당|/\s*일)\D{0,8}\d[\d,]*\s*(건|회|번|개)|\d[\d,]*\s*(건|회|번)\s*(정도\s*)?(/\s*일|씩\s*매일|하루)"),
    "input_length": ("건당 입력 길이", r"\d[\d,]*\s*(자|글자|토큰|페이지|쪽|장|단어|줄)|짧은|한\s*줄|긴\s*문서|PDF"),
    "accuracy": ("정확도 기준", r"정확도|정확해야|품질|\d+\s*%|틀리면|오류\s*허용"),
    "latency": ("허용 응답 시간", r"\d+\s*(초|분|시간)\s*(이내|안에|내|까지)|실시간|즉시|바로|하루\s*안|응답\s*시간|급하지\s*않"),
    "usage_mode": ("채팅으로 직접 쓰는지, 시스템에 붙여 자동으로 돌리는지(API)", r"좌석|채팅|직접\s*(써|쓰|사용)|ChatGPT|API|자동(화|으로)|연동|배치"),
}


def classify(text: str, prompt_name: str | None) -> str:
    if prompt_name in PROMPT_INTENT:
        return PROMPT_INTENT[prompt_name]
    return next((intent for intent, pat in RULES if re.search(pat, text, re.I)), "general")


def conditions(texts: list[str]) -> dict[str, bool]:
    """대화 전체(같은 thread의 사람 메시지)에서 조건이 언급됐는지. 답을 나눠 해도 모인다."""
    joined = "\n".join(texts)
    return {k: bool(re.search(pat, joined, re.I)) for k, (_, pat) in CONDITIONS.items()}


def question(missing: list[str]) -> str:
    items = "\n".join(f"- {CONDITIONS[k][0]}" for k in missing)
    return ("추천하려면 몇 가지를 더 알아야 해요. 아는 것만 한 번에 알려 주세요.\n" + items +
            "\n(모르면 '모름'이라고 해 주셔도 돼요. 그러면 있는 정보로 추천하고 확인이 필요한 점을 함께 알려드릴게요.)")


if __name__ == "__main__":  # 자체 점검: uv run python -m apps.agent_runtime.harness.intent
    assert classify("고객 문의 분류에 어떤 모델 쓰면 좋을까요?", None) == "recommend"
    assert classify("ChatGPT Enterprise 이용권 신청하고 싶어요", None) == "license"
    assert classify("아무거나", "investigate_anomaly") == "anomaly"
    assert classify("사내 정책 알려줘", None) == "general"
    c = conditions(["하루 1,000건 문의를 분류해요. 건당 300자 정도", "정확도 90% 이상, 1초 이내, API로 자동으로"])
    assert all(c.values()), c
    assert not any(conditions(["모델 추천해줘"]).values())
    print("ok")
