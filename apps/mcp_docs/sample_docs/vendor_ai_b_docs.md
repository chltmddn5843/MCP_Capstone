---
doc_id: vendor-ai-b-docs
title: AI-B API 모델 가격·사용 가이드 (가상 샘플)
doc_type: vendor
vendor: AI-B
kind: pricing
url: https://vendor-b.example/pricing
published_at: 2026-10-15
is_candidate: false
---

> 개발용 가상 샘플이다.

## b-mid 입력 단가 인하 (2026-10-15)
b-mid 입력 토큰 단가를 20% 인하한다. 출력 단가는 그대로다.
원문: https://vendor-b.example/release-notes/2026-10-15

## 모델별 단가
b-large: 입력 100만 토큰당 3.0달러, 출력 15.0달러. 긴 문서 이해와 복잡한 생성에 적합하다.
b-mid: 입력 0.8달러, 출력 4.0달러. 분류, 요약처럼 형식이 정해진 업무에 적합하다.
b-small: 입력 0.25달러, 출력 1.25달러. 짧은 입력의 단순 분류에 적합하지만 품질을 먼저 평가해야 한다.

## 긴 입력 줄이기
보고서 전체를 넣으면 입력 토큰이 크게 늘어난다. 필요한 장만 잘라 넣거나 장별 요약을 먼저 만든 뒤 합친다.
입력 길이 상위 구간(8k 이상)의 비중이 커졌다면 일부 요청에 긴 문서가 들어오고 있다는 신호다.
