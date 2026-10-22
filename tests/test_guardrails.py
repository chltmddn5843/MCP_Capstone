from apps.agent_runtime.harness.guardrails import public_channel, sanitize_public_answer


def test_public_channel_rule():
    assert public_channel("employee", "admin_ui") and public_channel("admin", "slack")
    assert not public_channel("admin", "admin_ui") and not public_channel("system", "system")


def test_sanitize_strips_ids_tools_and_evidence():
    raw = "배정됐어요 (plan_ab12, emp_mkt_01). `execute_approved_plan` 결과 status=executed. 오류 코드 forbidden 아님.\n\n근거: get_my_profile(emp_mkt_01), ctr_chatgpt_2026"
    out = sanitize_public_answer(raw)
    assert "근거" not in out and "plan_" not in out and "emp_" not in out and "execute_approved_plan" not in out and "forbidden" not in out
    assert out.startswith("배정됐어요.")


def test_sanitize_keeps_plain_text():
    s = "지금은 빈 자리가 없어 관리자가 검토합니다. 결과가 나오면 알려드릴게요."
    assert sanitize_public_answer(s) == s
