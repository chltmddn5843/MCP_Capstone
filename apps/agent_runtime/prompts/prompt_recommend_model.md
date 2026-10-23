[작업: 모델 추천] 업무 설명: {task_description}
1. 조건이 부족하면 묻는다: 하루 건수, 건당 입력 길이, 정확도 기준, 허용 응답 시간, 채팅 좌석인지 API 업무인지.
2. 채팅 좌석이면 list_approved_tools로 플랜 유형을 본다. seat_flat이면 비용 대신 품질·속도 기준으로 안내한다.
3. API 업무면 list_approved_models, get_usage_summary, get_eval_results(task_type)를 본다. 평가 결과가 없으면 추천하지 말고 샘플 평가를 제안한다.
4. get_eval_results 결과에서 eligible=true인 모델만 후보로 쓴다(품질 기준 통과 + 사내 승인, 시스템이 판정). 직접 다시 거르지 않는다. 후보마다 estimate_task_cost로 월 예상 비용을 비교한다. 권한 때문에 프로젝트 사용량을 볼 수 없으면(forbidden) 하루 건수와 건당 토큰을 물어 현재 모델도 estimate_task_cost로 계산해 같은 기준으로 비교한다.
5. 추천 모델, 선정 이유, 예상 비용, 품질 확인 필요 사항을 답한다. "간단한 업무라 저렴한 모델"로 단정하지 않는다.
