[작업: 모델 추천] 업무 설명: {task_description}
1. 조건이 부족하면 묻는다: 하루 건수, 건당 입력 길이, 정확도 기준, 허용 응답 시간, 채팅 좌석인지 API 업무인지.
2. 채팅 좌석이면 list_approved_tools로 플랜 유형을 본다. seat_flat이면 비용 대신 품질·속도 기준으로 안내한다.
3. API 업무면 list_approved_models, get_usage_summary, get_eval_results(task_type)를 본다. 평가 결과가 없으면 추천하지 않고 평가가 필요하다고 답한다.
4. 품질 기준(threshold)을 통과한 후보만 남기고 estimate_task_cost로 월 예상 비용을 비교한다.
5. 추천 모델, 선정 이유, 예상 비용, 품질 확인 필요 사항을 답한다. "간단한 업무라 저렴한 모델"로 단정하지 않는다.
