# 관리자 화면 (담당: Agent+프론트)

Streamlit, 포트 8501. 화면 3개: 메인(활용 지표·미충족 수요), 자산 관리(이용권·사용량·경보), 승인함.
조회·승인은 백엔드 REST 직접 호출, 경보 조사만 에이전트(`POST /agent/runs`, prompt_name=investigate_anomaly).
만들 파일: `app.py`. 실행: `uv run streamlit run apps/admin_ui/app.py`
