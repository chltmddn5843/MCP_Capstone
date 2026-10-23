"""의도 분류와 의도별 절차·도구 집합. classify_intent 노드가 쓴다.

의도는 다섯 가지 + 시스템. 신청 의도는 반드시 처리 요청(create_action_plan)으로 끝나거나, 제품을 하나만 되묻고 끝난다.
"""

from __future__ import annotations

import re

INTENTS = ["access_request", "release_request", "recommendation", "policy_question", "off_topic", "status_or_other"]

LABEL = {"off_topic": "기능 밖 요청", "access_request": "사용 신청", "release_request": "반납·중단", "recommendation": "제품·모델 추천", "policy_question": "사용 가능 여부·정책", "status_or_other": "상태 문의·기타", "system": "시스템 작업"}

CLASSIFY_PROMPT = """다음 요청의 의도를 아래 여섯 가지 중 하나의 영어 코드로만 답하라. 설명 없이 코드만.
- access_request: 어떤 제품(AI 채팅, API, 소프트웨어)을 쓰고 싶다 / 사용 신청·권한·이용권을 달라 / 사용할 수 있게 해달라
- release_request: 더 안 쓴다 / 반납 / 해지 / 중단
- recommendation: 어떤 제품·모델을 쓰는 게 좋은지, 비용을 줄일 수 있는지, 조건 비교
- policy_question: 이 기능·제품을 써도 되는지, 정책·보안 규정, 데이터 넣어도 되는지
- off_topic: 업무용 AI·소프트웨어 제품, 모델, 이용권, 사용량·비용, 사내 AI 정책과 관계없는 요청 (잡담, 장난, 인사만, 맛집·날씨·뉴스, 일반 상식, 업무 자체를 대신 해 달라는 요청)
- status_or_other: 내 요청·업무 상태 확인, 업무 등록·수정, 이 서비스 사용법

직전 대화 맥락이 있으면 참고하되, 이번 메시지의 요구가 우선이다. "사용할 수 있게 해달라", "써야 한다", "요청 보내줘"는 질문이 아니라 access_request다.

요청: {text}
코드:"""

# 의도별 도구 부분집합 (직원 기준. 역할에 없는 도구는 서버가 이미 걸러 준다)
TOOLS_BY_INTENT = {
    "access_request": ["get_my_profile", "list_approved_tools", "list_approved_models", "create_action_plan", "request_unlisted_product", "get_plan_status"],
    "release_request": ["get_my_profile", "list_approved_tools", "create_action_plan", "get_plan_status"],
    "recommendation": ["get_my_profile", "list_approved_tools", "list_approved_models", "get_eval_results", "estimate_task_cost", "get_usage_summary", "search_vendor_docs", "create_action_plan"],
    "policy_question": ["get_my_profile", "list_approved_tools", "search_internal_policy", "search_vendor_docs", "get_vendor_update"],
    "status_or_other": ["get_my_profile", "upsert_my_task", "get_plan_status", "list_approved_tools"],
}

PROCEDURE = {
    "access_request": """[이번 요청의 의도: 사용 신청] 반드시 아래 순서로 행동한다. 상담으로 빠지지 않는다.
1. get_my_profile로 본인 정보(employee_id)와 이미 쓰는 제품을 본다. list_approved_tools로 승인 제품 목록을 본다.
2. 요청한 제품이 승인 제품 목록에 없으면(사내 미도입) request_unlisted_product(product_name: 요청한 제품 이름, purpose: 한 줄 용도)를 부르고, 결과(status=rejected, reject_reason=사내 미도입)가 오면 "이 요청은 미도입 제품 신청입니다. [제품명]은 현재 사내 제공 대상이 아니에요. 신청 내용은 기록했고, 결과는 DM으로 안내해 드릴게요."라고만 답한다. 도구를 부르지 않고 "승인된 제품으로는 어렵다"고만 답하지 않는다. 결과가 conflict(등록 제품)면 아래 사용 신청 절차로 간다. 구매·도입 예정을 약속하지 않는다. 목록에 있는 제품이면 아래로.
   어떤 제품인지 분명하면 바로 처리 요청을 만든다. 분명하지 않으면 승인 제품 이름을 2~3개 보여 주고 "어느 것을 쓰고 싶은지" 딱 하나만 묻고 끝낸다 (조건·용도를 더 묻지 않는다).
3. 처리 요청 만들기:
   - 좌석형 제품(채팅, 소프트웨어): create_action_plan(type=seat_assign, items=[{employee_id: 본인, contract_id: 그 제품의 계약 id}])
   - 사용량 과금 제품(API): create_action_plan(type=api_access, items=[{tool_id, purpose: 한 줄 용도, model_id?, expected_requests_per_day?}]). 용도를 모르면 요청 문장에서 추정해 한 줄로 쓴다.
   - 좌석형 제품을 본인이 이미 배정받아 쓰고 있을 때만(get_my_profile의 등록 업무·이용권 기준) 요청을 만들지 말고 "이미 쓸 수 있어요"라고 답한다.
   - API 제품은 회사 승인 목록에 있어도 개인 권한(프로젝트)이 따로 필요하므로 **항상** api_access 요청을 만든다. "이미 쓸 수 있어요"라고 답하지 않는다.
4. create_action_plan 결과의 status로 답한다. 요청을 만들지 못했으면 절대 전달됐다고 말하지 않는다.
   - pending_approval이고 좌석형: "관리자에게 신청을 전달했어요. 승인되면 로그인 방법을 DM으로 보내드릴게요." 근거(evidence)에 남은 좌석 없음(shortage)이 있으면 "지금 남은 좌석이 없어 관리자가 확인한 뒤 결과를 알려드릴게요."
   - pending_approval이고 API: "관리자에게 전달했어요. 승인되면 키를 받을 수 있는 링크를 DM으로 보내드릴게요."
비용 추정·모델 비교는 이 의도에서 하지 않는다.""",
    "release_request": """[이번 요청의 의도: 반납·중단] 1) get_my_profile로 쓰는 제품을 확인한다. 2) 어느 제품인지 분명하면 create_action_plan(type=seat_reclaim, items=[{employee_id: 본인, contract_id}], rationale: "본인 반납 요청")을 만든다. 여러 개면 어느 것인지 하나만 묻는다. 3) 본인 반납은 관리자 승인 없이 바로 처리된다. 결과 status가 executed면 "반납 처리됐어요. 다시 필요해지면 저에게 말씀해 주세요."라고 답한다. 요청을 만들지 못했으면 처리됐다고 말하지 않는다.""",
    "recommendation": """[이번 요청의 의도: 제품·모델 추천] 업무 조건(하루 건수, 입력 길이, 정확도 기준, 응답 시간, 채팅인지 API인지)이 부족하면 한 번에 묶어 묻는다. 승인 제품·모델 중에서 평가 결과와 비용으로 비교해 추천한다. 승인 제품 어느 것도 그 기능을 제공하지 않으면 "지금 승인된 제품으로는 어렵습니다"라고 솔직히 답한다. 추천 뒤 사용자가 쓰겠다고 하면 사용 신청 절차로 넘어간다고 안내한다 ("쓰고 싶다고 말씀해 주시면 관리자에게 전달할게요").""",
    "policy_question": """[이번 요청의 의도: 사용 가능 여부·정책] search_internal_policy와 list_approved_tools로 확인해 "돼요/안 돼요"와 조건을 짧게 답한다. 해당 기능이 승인 제품 플랜에 있는지도 본다.""",
    "status_or_other": """[이번 요청의 의도: 상태 문의·기타] 내 요청 상태는 get_plan_status, 업무 등록은 upsert_my_task를 쓴다. 인사·잡담은 짧게 답한다.""",
    "system": "",
}

_KW = [
    ("release_request", r"안\s*써|반납|해지|중단|그만|필요\s*없"),
    ("access_request", r"사용\s*(신청|요청|하고\s*싶|할\s*수\s*있게|해야)|쓰고\s*싶|써야|이용권|권한|열어\s*줘|신청"),
    ("policy_question", r"써도\s*되|사용해도\s*되|정책|보안|규정|넣어도\s*되"),
    ("recommendation", r"추천|비용|줄일|어떤\s*모델|어떤\s*제품|뭐가\s*좋|비교"),
]


# 하네스 입력 경계: 기능과 무관한 요청은 본 AI(도구를 쓰는 답변 루프)를 돌리지 않고 이 문구로 거부한다
OFF_TOPIC_ANSWER = ("저는 업무용 AI·소프트웨어 이용권과 사용 관리를 돕는 비서예요. 이 요청은 도와드릴 수 없어요.\n"
                    "이런 걸 말씀해 주세요: '이용권 신청할래요', '캔바 반납할게요', '보고서 요약에 맞는 모델 추천해줘', '메뉴'")
# 업무 단어: 하나라도 있으면 규칙으로 거부하지 않고 의도 분류에 맡긴다
_DOMAIN = re.compile(r"ai|gpt|챗|chat|claude|클로드|canva|캔바|adobe|어도비|acrobat|아크로뱃|grok|api|모델|제품|이용권|좌석|라이선스|라이센스|구독|"
                     r"신청|반납|비용|요금|사용량|토큰|정책|보안|승인|키|업무|요약|번역|분석|보고서|문서|메뉴|도와|도움|사용법|help", re.IGNORECASE)
_ASKED = re.compile(r"\?|알려\s*주|어느|어떤 것|골라|말씀해")


def off_topic_by_rule(text: str, last_ai: str | None = None) -> bool:
    """모델을 부르지 않는 1차 필터. 이모지·기호뿐이거나, 업무 단어 없이 아주 짧은 말(메롱, ㅋㅋ, 하이)이면 기능 밖.
    직전 AI 답이 되물음이면 짧은 대답(네, 그거요, 2번)일 수 있으므로 거르지 않는다. 애매하면 의도 분류(모델)에 넘긴다."""
    if last_ai and _ASKED.search(last_ai):
        return False
    core = re.sub(r"[\W_]+", "", text or "")
    if not core:
        return True
    if _DOMAIN.search(text) or any(re.search(pat, text) for _, pat in _KW):
        return False
    return len(core) <= 6


def classify_by_keywords(text: str) -> str:
    """모델 없이(fake 모드) 또는 모델 응답을 못 읽었을 때 쓰는 보조 분류."""
    for intent, pat in _KW:
        if re.search(pat, text):
            return intent
    return "status_or_other"


def parse_intent(raw: str, fallback_text: str) -> str:
    code = (raw or "").strip().strip('"\'`.').lower()
    for i in INTENTS:
        if i in code:
            return i
    return classify_by_keywords(fallback_text)


CLAIM_WORDS = re.compile(r"(전달했|배정됐|배정되었|접수됐|접수되었|신청했|요청했|처리됐|처리되었)")
