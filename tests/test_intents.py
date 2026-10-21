from apps.agent_runtime.harness.intents import classify_by_keywords, parse_intent


def test_keyword_classifier_separates_requests_from_questions():
    assert classify_by_keywords("ai a 사용하고싶어") == "access_request"
    assert classify_by_keywords("내가 사용할 수 있게 해달라고") == "access_request"
    assert classify_by_keywords("b api도 사용해야해") == "access_request"
    assert classify_by_keywords("이제 안써") == "release_request"
    assert classify_by_keywords("문서 비교 기능 써도 되나요?") == "policy_question"
    assert classify_by_keywords("고객 문의 분류 비용을 줄일 수 있을까요?") == "recommendation"
    assert classify_by_keywords("안녕하세요") == "status_or_other"


def test_parse_intent_accepts_model_output_or_falls_back():
    assert parse_intent("access_request", "") == "access_request"
    assert parse_intent("`recommendation`.", "") == "recommendation"
    assert parse_intent("잘 모르겠어요", "이제 안써") == "release_request"
