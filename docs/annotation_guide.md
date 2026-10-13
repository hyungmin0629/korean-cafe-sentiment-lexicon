# 실제 리뷰 평가 자료 작성

기능 시험과 실제 리뷰 정확도 평가는 구분합니다. 생성 예제와 사전을 만든 Codex의 자동 판정을 사람 정답으로 간주하지 않습니다.

1. 개발은 테라로사·프릳츠, 개발 검토는 어니언, v0.3 분류기 수정 미사용 카페는 모모스·앤트러사이트입니다. 레이어드·대림창고는 오류 점검을 개발에 참고하여 개발 검토 자료로 변경했습니다. 나리나무는 적용 사례입니다.
2. 두 사람이 독립적으로 원문을 읽고 카테고리·평가 구절·감성 방향을 표시하는 방식을 권장합니다. 사전 예측을 먼저 보여 주지 않습니다.
3. `gold_label`은 positive(긍정), negative(부정), neutral(명시적 중립), mixed(긍부정 혼합), unscored(해당 항목에 평가 없음)입니다. 단순 메뉴 주문·특징·맛 취향 서술을 긍정으로 채우지 않습니다.
4. 사람이 판단할 수 없는 행은 gold_label을 비워 두고 notes에 이유를 씁니다. 빈 라벨은 평가 대상에서 빠지며 라벨 완료율로 별도 보고합니다. 판단 불가와 평가 없음은 다릅니다.
5. 다른 카페 비교·과거 경험·전언·희망은 현재 카페의 직접 평가와 구별합니다. 의견 차이를 기록하고 합의한 자료를 만듭니다.
6. 보류 자료의 원문이나 오류를 보고 후보를 수정했다면 새 최종 평가 자료가 필요합니다.

정답 작성에는 [원문 검토 화면](annotation_workspace.md)을 사용할 수 있습니다. CSV 원문 열을 비우고 원문 해시로 연결하는 출력도 지원하며, 평가 도구가 해시 일치를 확인합니다.

v0.3 새 카페 양식은 `data_private/annotations.v03.holdout.blank.csv`입니다. 두 카페에서 각각 30본문을 ID 해시 순서로 선택해 8개 항목씩 480행을 만들었습니다. 모두 비어 있습니다. 이전 v0.2 양식 1,216행은 과거 기록입니다. 예측 라벨은 넣지 않았습니다. `source, review_id, cafe_id, split, text, category, gold_label, evidence_text, reviewer, notes` 열을 사용합니다. reviewer는 필수이며 사람 검토자나 Codex 등 실제 작성자를 기록합니다. 합의한 파일은 별도 이름으로 저장합니다.

```powershell
python tools/evaluate.py --predictions outputs_private/actual_all_v03_final/reviews.jsonl --annotations data_private/annotations.v03.human.csv --kind human --split holdout --output outputs_private/evaluation.human.json
```

`--kind`는 실제 라벨 작성 방식을 선언합니다. `human`, `codex_provisional`, `synthetic` 중 선택하며, 도구가 작성자 신원을 검증해 주지는 않습니다. 사람이 확인하지 않은 파일을 human으로 지정하지 않습니다. Codex 임시 라벨이나 생성 예제 결과는 실제 사람 정답 기반 정확도로 보고하지 않습니다.

정답이 모두 비어 있으면 도구는 종료하고 정확도를 계산하지 않습니다. 일부만 채웠으면 완료율과 평가 행 수를 보고합니다. 분류별 정밀도·재현율·F1·혼동표를 출력합니다. 정답에 감성이 있는데 예측이 unscored인 경우는 누락으로 계산하며 제외하지 않습니다. mixed와 neutral도 구별합니다. Macro F1은 정답 표본이 있는 라벨만 평균하므로 평가 파일 간 라벨 구성도 확인합니다.

원문·정답 구절·상세 예측·오류 예시는 비공개 폴더에서 관리합니다. 품질 결과를 공개할 때 작성 방법·카페 분리·라벨 완료율·표본 수를 함께 보고합니다.
