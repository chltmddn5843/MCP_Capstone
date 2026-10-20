[작업: 사용량 경보 조사] anomaly_id={anomaly_id}
1. get_anomalies로 경보를 확인하고, get_anomaly_detail로 프로젝트의 등록 목적·모델·예산과 최근 추이를 본다.
2. get_usage_breakdown을 by=model, by=input_length, by=api_key로 본다.
3. 원인 후보를 근거와 함께 제시한다: 요청 수 증가, 평균 입력 길이 증가, 모델 변경. 단정하지 않는다.
4. 선택 가능한 조치안을 제시한다: 예산 증액 검토(budget_review), 반복 요청 점검, 품질 평가 후 모델 검토(model_change, test), 부서에 사용 목적 확인 요청. 담당자가 고르면 create_action_plan으로 만든다.
