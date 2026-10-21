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
Claude Opus 5.5는 복잡한 추론과 긴 문서 분석에 적합하고, 입력 100만 토큰당 4달러·출력 20달러를 기준으로 계산한다.
분류처럼 짧은 작업은 Sonnet 5.5나 Haiku 5.5로 바꿔 비용을 줄일 수 있다.
원문: https://platform.claude.com/docs/en/about-claude/pricing

## 모델별 단가
Claude Opus 5.5 (anthropic:claude-opus-5-5): 입력 100만 토큰당 4달러, 출력 20달러. 복잡한 추론과 긴 문서 분석에 적합하다.
Claude Sonnet 5.5 (anthropic:claude-sonnet-5-5): 입력 2달러, 출력 10달러. 범용 추론·분류·요약에 적합하다.
Claude Haiku 5.5 (anthropic:claude-haiku-5-5): 입력 0.10달러, 출력 0.50달러(입력 10만 토큰 이하). 빠른 단순 분류에 적합하다.

## 긴 입력 줄이기
보고서 전체를 넣으면 입력 토큰이 크게 늘어난다. 필요한 장만 잘라 넣거나 장별 요약을 먼저 만든 뒤 합친다.
입력 길이 상위 구간(8k 이상)의 비중이 커졌다면 일부 요청에 긴 문서가 들어오고 있다는 신호다.
