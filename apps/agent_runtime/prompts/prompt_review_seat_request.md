[작업: 이용권 신청 검토] plan_id={plan_id}
1. get_plan_status로 신청 내용을 본다.
2. get_license_inventory로 미배정 좌석과 저사용 후보를 본다. flag=no_record는 '확인 필요'이고, 무응답은 회수 사유가 아니다.
3. 미배정 좌석이 있으면 배정(seat_assign)을, 없으면 본인 확인 응답이 있는 저사용 좌석의 재배정(seat_reclaim, confirmation_id 포함)을, 그것도 없으면 추가 구매 검토(purchase_review)를 제안한다.
