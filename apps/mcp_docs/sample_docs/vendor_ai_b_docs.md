---
doc_id: vendor-ai-b-docs
title: AI 모델 가격·사용 가이드 (개발용 카탈로그)
doc_type: vendor
vendor: Anthropic
kind: pricing
url: https://platform.claude.com/docs/en/about-claude/pricing
published_at: 2026-10-15
is_candidate: false
---

> 가격은 2026-10-21에 공식 가격 문서를 확인해 기록한 데모용 기준값이며, 실제 계약·할인·배치 요금은 별도 확인이 필요하다.

## Claude 모델 선택 기준
Claude Opus 4.7은 복잡한 추론과 긴 문서 분석에 적합하고, 입력 100만 토큰당 5달러·출력 25달러를 기준으로 계산한다.
원문: https://platform.claude.com/docs/en/about-claude/pricing

## 모델별 단가
Claude Opus 4.7: 입력 100만 토큰당 5달러, 출력 25달러. 복잡한 추론과 긴 문서 분석에 적합하다.
GPT-5.2: 입력 1.75달러, 출력 14달러. 범용 추론·분류·요약에 적합하다.
Grok 4.7: 입력 2달러, 출력 6달러. 빠른 응답과 검색 도구 연동에 적합하다.

## 긴 입력 줄이기
보고서 전체를 넣으면 입력 토큰이 크게 늘어난다. 필요한 장만 잘라 넣거나 장별 요약을 먼저 만든 뒤 합친다.
입력 길이 상위 구간(8k 이상)의 비중이 커졌다면 일부 요청에 긴 문서가 들어오고 있다는 신호다.
