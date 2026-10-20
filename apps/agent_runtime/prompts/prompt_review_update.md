[작업: 업데이트 검토] update_id={update_id}
1. get_vendor_update로 내용을 읽는다.
2. list_approved_tools로 회사 플랜에 해당 기능이 포함되는지 확인한다. 없으면 '보류'라고 답하고 끝낸다.
3. find_relevant_tasks로 후보를 받아 관련성이 분명한 업무만 고른다. 관련성 근거를 한 줄로 쓴다.
4. 고른 업무마다 save_suggestion을 만든다. 근거가 없는 대상에는 보내지 않는다.
