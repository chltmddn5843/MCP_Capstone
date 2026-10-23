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


def test_off_topic_rule_blocks_small_talk_without_model():
    """하네스 입력 경계 1차: 업무 단어 없는 짧은 말·이모지는 모델을 부르지 않고 기능 밖으로 본다."""
    from apps.agent_runtime.harness.intents import off_topic_by_rule
    for text in ("메롱", "메롱메롱", "ㅋㅋㅋㅋ", "🙂", "?!", "하이", "뭐해"):
        assert off_topic_by_rule(text), text
    for text in ("이용권 신청할래요", "캔바 반납", "ChatGPT", "메뉴", "보고서 요약에 맞는 모델 추천해줘", "도와줘", "이제 안써"):
        assert not off_topic_by_rule(text), text
    assert not off_topic_by_rule("판교 맛집 추천해줘")  # 짧지 않으면 규칙으로 단정하지 않고 의도 분류(모델)에 넘긴다
    assert not off_topic_by_rule("네", last_ai="어느 제품을 쓰고 싶으세요?")  # 되물음에 대한 짧은 답은 통과
    assert off_topic_by_rule("메롱", last_ai="반납 처리됐어요.")


def test_parse_intent_knows_off_topic():
    assert parse_intent("off_topic", "") == "off_topic"
