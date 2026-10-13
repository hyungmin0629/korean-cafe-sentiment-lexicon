# 네이버 플레이스 리뷰를 각자 수집해 분석하기

`tools/crawl_naver_place.py`는 사용자가 자기 컴퓨터에서 실행하는 Python 코드입니다. **매장 URL → 방문자 리뷰 CSV → 감성분석 보고서**로 연결합니다. 카페 이름은 결과 표시용이며, 대상 지점은 URL의 플레이스 ID로 정합니다. 공개 고객 본문을 대상으로 하며 작성자·프로필·사진·매장 답글·선택 키워드를 수집 필드에 넣지 않습니다.

**현재 검증 상태 (2026-10-13):** 사용자 링크는 스타벅스 타임스퀘어R점이며, 네이버 지도와 데스크톱 방문자 리뷰 탭은 정상적으로 열렸습니다. 이미 열린 화면에서 카드 10개·본문 10개의 구조를 확인해 선택자와 본문 더보기 처리를 수정했습니다. 크롤러의 실제 실행은 `robots.txt`의 429 응답으로 **0건에서 중단**됐습니다. 기본 대상인 모바일 화면과 실제 수집·목록 추가 로딩은 아직 미확인입니다. Python 검사 59개와 외부 요청을 자체 작성 HTML로 대체한 Chrome 시험은 통과했습니다. 상세한 확인 범위와 미지원 동작은 [실수집 검증 기록](naver_live_validation.md)에 있습니다.

## 설치

저장소를 내려받고 그 폴더에서 Python 3.10 이상으로 실행합니다. 분석기 자체에는 추가 라이브러리가 필요 없지만 네이버 수집에는 Playwright와 Beautiful Soup가 필요합니다.

```powershell
python -m pip install -r requirements-naver.txt
python -m playwright install chromium
```

설치 방법은 [Playwright 공식 문서](https://playwright.dev/python/docs/library)를 기준으로 합니다. 새 임시 브라우저를 사용하며 기존 Chrome의 로그인 정보·쿠키·프로필을 가져오지 않습니다.

## URL을 넣어 수집과 보고서 생성

사용자가 제공한 지도 URL의 매장 ID와 화면에서 확인한 지점명을 사용한 예제입니다. 다른 카페에서는 `--cafe-name`을 해당 지점명으로 바꾸세요.

```powershell
python tools/crawl_naver_place.py --url "https://map.naver.com/p/entry/place/1649277590" --cafe-name "스타벅스 타임스퀘어R점" --max-reviews 200 --max-pages 20 --delay 2 --output data_private/naver_starbucks_01 --report-output outputs_private/naver_starbucks_01
```

카페를 바꿀 때는 URL·표시명·출력 폴더를 바꿉니다. 지도 검색 결과의 `/place/숫자ID` URL과 모바일 플레이스의 `/restaurant/숫자ID` URL도 받습니다. 검색 문구·추적 쿼리는 제거하고 같은 ID의 방문자 리뷰 페이지를 엽니다. `naver.me` 공유 단축 주소는 브라우저에서 매장 페이지로 연 뒤 전체 URL을 복사합니다. 카페 이름만으로 지점을 자동 선택하지 않습니다.

화면을 보며 실행하려면 `--headed`를 추가합니다. 기본은 브라우저 창을 띄우지 않습니다. `--report-output`을 생략하면 CSV만 만듭니다. 결과를 덮어쓰지 않으므로 매번 새 폴더를 사용하세요.

정상적으로 본문이 확보되면 `outputs_private/naver_starbucks_01/report.html`을 브라우저로 엽니다. 메뉴·친절·공간·입지 등 8항목 점수와 근거가 나오며, 확인된 작성일이 있어야 월별 추세에 포함됩니다. 보고서의 점수는 후보 사전의 분석 결과이고 사람 정확도는 아직 미측정입니다.

CSV만 수집한 경우 [CSV 분석 화면](upload_app.md)에 `reviews.csv`를 올려 입력을 확인하고 기간을 선택할 수 있습니다. 화면 자체에서 네이버를 수집하지는 않습니다.

## 수집 결과와 범위

| 파일 | 내용 |
|---|---|
| `reviews.csv` | 분석기 필수 열과 본문, 작성일, 별도 방문일, 원본 날짜 표시, 출처 URL, ID 생성 기준 |
| `collection_manifest.json` | 매장 ID, 수집 시각(UTC), 시도한 화면 수, 상한, 종료 이유, 확보 건수, 작성일 확인 건수, 선택자 해시 |
| 보고서 출력 폴더 | `report.html`, `summary.csv`, `reviews.jsonl`, `input_issues.csv`, `run_metadata.json` |

화면 기본 정렬을 사용하고 설정한 목록 더보기가 있을 때 누르며 수집합니다. 사진·차트·본문의 일반 더보기는 목록 더보기로 사용하지 않습니다. `--max-pages`는 웹 주소의 페이지 번호가 아니라 읽은 화면 스냅샷 수의 상한입니다. 최대 리뷰 수·화면 수에 도달하거나 목록 더보기 버튼이 없거나 새 카드가 늘지 않으면 종료합니다. **전체 리뷰의 완전 수집과 최신순·무작위 표본을 보장하지 않습니다.** 자동 스크롤 로딩·기존 카드 교체 방식은 현재 지원하지 않아 해당 화면에서는 이미 로드된 표본만 저장합니다. 종료 이유를 확인하고 같은 표본 범위로 비교하세요.

가능하면 출처의 리뷰 ID를 사용합니다. ID가 보이지 않으면 본문·원본 날짜·같은 화면 내 발생 순서로 임시 ID를 만듭니다. 같은 문장의 독립 리뷰는 유지하고 반복 스냅샷은 중복 제거합니다. 임시 ID는 화면 순서나 본문 수정 시 변할 수 있어 다른 실행의 자료를 합칠 때 별도 확인해야 합니다. `fallback_id_count`로 사용 건수를 확인할 수 있습니다.

작성일이 명시되고 연월일이 완전할 때만 `review_date`에 넣습니다. 방문일은 `visit_date`로 따로 저장합니다. `9.15`, `어제`, 날짜의 의미가 불명확한 표시에서 작성일을 추측하지 않습니다. 작성일이 없는 본문은 기간 합산 분석에는 사용할 수 있지만 월별 집계에서는 제외됩니다. 따라서 네이버 화면이 방문일만 제공하면 이 코드만으로 작성일 기준 시계열을 만들 수 없습니다.

실제 CSV·발췌가 있는 보고서는 `data_private/`·`outputs_private/`에서 비공개로 관리합니다. 공개 코드에 실제 리뷰 원문은 포함하지 않습니다.

## 접근 제한과 선택자 변경

먼저 `robots.txt`의 경로 규칙과 간격을 확인합니다. 403·429, CAPTCHA, 로그인/다른 호스트 이동, 확인할 수 없는 robots 응답이면 중단합니다. 제한 응답에 자동 재시도·IP 교체·CAPTCHA 해제·로그인 자동화를 하지 않습니다. 요청 간격은 화면 조작 사이 최소 1초이고 robots 간격이 더 길면 따릅니다. 브라우저가 페이지를 렌더링하는 데 필요한 여러 리소스를 요청하므로 모든 개별 리소스의 요청 간격을 통제하는 방식은 아닙니다. 자료 수집 권한과 이용 조건은 실행자가 확인해야 하며, 코드가 자동 수집에 대한 네이버의 허가를 대신하지 않습니다. [네이버 이용약관](https://policy.naver.com/policy/service.html)

중단 시 종료 코드 `1`과 `status: stopped`를 기록하고 이미 확보한 행은 CSV로 보존합니다. 자동 보고서 생성은 생략합니다. 0행 CSV는 성공 결과가 아닙니다. 입력 오류는 종료 코드 `2`이며, 정상적으로 제한 범위의 표본을 저장한 경우 `0`입니다. 정상 코드도 전체 수집 완료를 뜻하지 않습니다.

페이지를 열었는데 `review_layout_unrecognized_or_unavailable` 또는 `no_nonempty_review_bodies`가 나오면 [선택자 설정](../configs/naver_place_selectors.json)을 확인합니다. `card`는 리뷰 한 장, `body`는 고객 본문, `written_date`는 명시된 작성일, `visit_date`는 명시된 방문일, `generic_date`는 기타 날짜 표시, `load_more`는 목록 더보기, `expand_body`는 본문 펼치기 버튼입니다. 날짜와 본문 선택자는 카드 안에서 조회합니다. 클래스가 바뀔 수 있으며 선택자를 아무 텍스트 전체로 넓히면 닉네임·답글·메뉴 안내가 섞입니다. 기본의 명시 작성일/방문일 속성은 실제 화면에서 확인되지 않은 확장용 선택자입니다. 확인한 화면의 방문일은 `.pui__gfuUIT`에서 읽습니다.

```powershell
python tools/crawl_naver_place.py --url "https://map.naver.com/p/entry/place/1649277590" --cafe-name "스타벅스 타임스퀘어R점" --selectors configs/naver_place_selectors.json --output data_private/naver_starbucks_02
```

접근이 허용된 화면의 렌더링된 HTML을 이미 가지고 있다면 `--html 파일.html`로 네트워크 요청 없이 추출을 점검할 수 있습니다. 웹페이지 저장 파일은 JavaScript로 생성된 리뷰 DOM을 포함하지 않을 수도 있습니다. 실제 저장 화면은 개인정보가 있을 수 있으므로 비공개 경로에 두세요.

## 네트워크 없는 기능 예제

아래 입력은 실제 네이버 화면을 복제한 자료가 아닌 **자체 작성 HTML 5건**입니다. 추출기·CSV·보고서 연결을 확인하는 용도이며 네이버 실수집을 검증하지 않습니다.

```powershell
python tools/crawl_naver_place.py --url "https://map.naver.com/p/entry/place/1649277590" --cafe-name "자체 작성 기능 예제" --html tests/fixtures/naver_reviews.synthetic.html --synthetic --output outputs_private/naver_fixture_01 --report-output outputs_private/naver_fixture_report_01
python -m unittest discover -s tests -v
```

직접 CSV를 이미 보유한 경우에는 [수동 리뷰 준비·변환 안내](review_preparation.md)를 대안으로 사용할 수 있습니다.
