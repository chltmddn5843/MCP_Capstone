[작업: 이용권 신청 검토] plan_id={plan_id}
1. get_plan_status로 신청 내용을 본다. 이용권 배정(seat_assign)은 남은 좌석이 있어도 관리자가 승인해야 실행된다. 이미 executed면 다시 실행하지 말고 결과만 안내한다.
2. get_license_inventory로 미배정 좌석과 저사용 후보를 본다. 마지막 사용일만으로 회수하지 않는다. flag=no_record는 '확인 필요'로 다루고 request_confirmation으로 사용 의사를 먼저 묻는다.
3. 반납 응답이 있거나 응답 기한(5영업일)이 지나도 무응답이면 회수·재배정한다. 기한 전 무응답은 회수 사유로 쓰지 않는다. 회수 조건이 확인되면 create_action_plan(seat_reclaim, items=[{{employee_id, contract_id, confirmation_id, reassign_to_employee_id}}])으로 회수·재배정 조치안을 만든다.
4. 쓸 좌석이 없으면 추가 구매를 제안하지 않는다. 남은 좌석이 없다는 사실과 회수·재배정 후보만 알리고, 반려 결정은 관리자가 한다.
