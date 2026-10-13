# 한국어 카페 리뷰 감성사전

저장소: [korean-cafe-sentiment-lexicon](https://github.com/hyungmin0629/korean-cafe-sentiment-lexicon)

리뷰 CSV를 넣으면 메뉴·친절·공간·입지·가격·청결·운영·전반 만족의 감성 점수를 기간별로 계산합니다. 표현별 근거를 저장하며, 분석 실행에는 외부 AI API나 추가 Python 라이브러리가 필요하지 않습니다.

버전 0.4.0은 자체 작성한 **420개 후보 표현**과 **오프라인 HTML 진단 보고서**를 제공합니다. 실제 카페 8곳의 본문 624건에 실행했고, 나리나무 2건도 포함했습니다. 개발 본문 221건에서 관찰된 후보는 95개, 미관찰 후보는 325개입니다. 모든 항목은 `candidate`이며 **사람 정답 기반 정확도는 아직 측정하지 않았습니다.**

보고서 상단에서 최근 6개월의 점수 변화, 전월 대비 차이, 가장 큰 월간 변화와 월별 리뷰 수를 봅니다. 항목별 월간 점수표와 기간 합산, 근거·반복 표현도 함께 제공합니다. [자체 작성 예제 보고서](examples/report.synthetic.html)를 내려받아 브라우저에서 열어보세요. 사용법은 [보고서 안내](docs/owner_report.md)에 있습니다.

## 원문 검토 화면

사전 예측을 숨긴 화면에서 사람이 8개 항목의 정답·근거·보류 이유를 입력합니다. 검토자별 자동 저장, JSON 백업·복구, 평가용 CSV 출력을 제공합니다. [자체 작성 검토 예제](examples/annotation.synthetic.html)를 내려받아 열어보세요. 실제 검토 자료 60리뷰·480항목은 비공개이며 정답은 아직 비어 있습니다.

```powershell
python tools/build_annotation_ui.py --input examples/annotations.synthetic.blank.csv --output outputs_private/review_demo.html
```

작성 기준·저장·평가 방법은 [검토 화면 안내](docs/annotation_workspace.md)에 있습니다. 화면 생성만으로 사람 정확도가 측정되지는 않습니다.

## 바로 실행

Python 3.10 이상에서 내려받은 저장소 폴더를 작업 위치로 사용합니다.

```powershell
git clone https://github.com/hyungmin0629/korean-cafe-sentiment-lexicon.git
cd korean-cafe-sentiment-lexicon
```

### CSV를 올리는 분석 화면

```powershell
python tools/serve_app.py
```

[http://127.0.0.1:8766/](http://127.0.0.1:8766/)에서 **CSV 선택 → 입력 확인 → 보고서 생성**을 실행합니다. 크롤러 CSV와 본문·작성일 두 열 CSV를 받고, 중복·날짜 미상·방문일만 있는 자료를 안내합니다. 파일이 없으면 자체 작성 예제 250건을 선택해 볼 수 있습니다. 결과는 이 PC의 비공개 실행 폴더에 저장합니다. 서버가 실행 중이어야 새로 접속하거나 분석할 수 있습니다. [설치·입력·산출물 안내](docs/upload_app.md)를 참고하세요.

이 화면은 사람 정답을 입력하는 `review.html`과 별도이며 네이버 자동 수집은 별도 코드로 실행합니다.

### 명령으로 실행

```powershell
python run.py --input examples/reviews.synthetic.csv --output outputs_private/demo --period month --start 2026-01-01 --end 2026-03-31
```

예제는 실제 고객 리뷰가 아닌 자체 작성 문장 18건입니다. 기존 결과를 실수로 덮어쓰지 않도록 새 폴더 또는 빈 폴더로 출력해야 합니다.

보고서를 포함한 생성 예제 250건 실행:

```powershell
python run.py --input examples/reviews.report.synthetic.csv --output outputs_private/report_demo
```

결과 폴더의 `report.html`을 엽니다. `--report-examples 0`은 발췌를 제외하며 `--no-report`는 HTML 출력을 생략합니다. 실제 보고서는 일부 원문 발췌가 있으므로 비공개로 관리합니다.

실제 리뷰 분석:

```powershell
python run.py --input data_private/reviews.csv --output outputs_private/actual_all --period all
python run.py --input data_private/reviews.csv --output outputs_private/actual_month --period month
```

분기 집계는 `--period quarter`, 전체 기간은 `--period all`입니다. `--start`·`--end`는 양 끝 날짜를 포함합니다. 날짜 필터가 있으면 날짜 미상 리뷰는 전체 기간 집계에서도 제외됩니다.

설치해서 쓰는 경우:

```powershell
python -m pip install .
cafe-sentiment --input examples/reviews.synthetic.csv --output outputs_private/installed_demo
```

## 리뷰 준비

네이버 플레이스는 각자 자기 컴퓨터에서 실행하는 [수집 코드와 설치 안내](docs/naver_crawling.md)를 제공합니다. 지도·플레이스 URL로 방문자 리뷰 CSV를 만들고 기존 감성분석 보고서에 연결합니다.

```powershell
python -m pip install -r requirements-naver.txt
python -m playwright install chromium
python tools/crawl_naver_place.py --url "https://map.naver.com/p/entry/place/1649277590" --cafe-name "스타벅스 타임스퀘어R점" --output data_private/naver_01 --report-output outputs_private/naver_01
```

**네이버 실수집은 429 응답으로 0건에서 중단됐습니다.** 일반 브라우저에서는 매장·방문자 리뷰 탭이 열렸고, 데스크톱 화면의 카드 10개 구조를 확인해 선택자를 수정했습니다. 모바일 화면의 실제 수집·목록 추가 로딩은 미확인입니다. 자동 스크롤 로딩은 현재 미지원이며 전체 리뷰 수집을 보장하지 않습니다. 작성일을 확인할 수 없는 리뷰는 월별 집계에서 제외하고 방문일은 별도로 보존합니다. [사이트 접속·실수집 검증 기록](docs/naver_live_validation.md)에서 확인 범위를 보세요.

CSV를 이미 가지고 있거나 두 열로 준비한 경우 [CSV 분석 화면](docs/upload_app.md)을 사용합니다. 명령으로 변환하려면 [수동 리뷰 준비·변환 안내](docs/review_preparation.md)를 참고하세요.

UTF-8 또는 UTF-8 BOM CSV를 사용합니다. 입력 양식은 `examples/reviews.template.csv`에 있습니다.

| 필드 | 내용 |
|---|---|
| review_id | 출처·카페 내 고유 리뷰 ID, 필수 |
| cafe_id | 카페 ID, 필수 |
| cafe_name | 표시용 이름 |
| review_date | YYYY-MM-DD 작성일, 기간 분석 시 필요 |
| text | 리뷰 본문, 필수 |
| source | 출처, 필수. 생성 예제는 synthetic |
| rating | 별점, 선택. 텍스트 점수 계산에 사용하지 않음 |
| collected_at | 수집일, 선택 |

쉼표나 줄바꿈이 있는 본문은 CSV 규칙에 따라 따옴표로 감싸야 합니다. 원문에 작성 연도가 없으면 임의로 연도를 넣지 않습니다. 본문이 같은 독립 리뷰는 유지하고, 출처·카페 ID·리뷰 ID가 같은 중복은 첫 행만 처리합니다.

## 결과 파일

| 파일 | 읽는 방법 |
|---|---|
| report.html | 카페·월 범위 필터, 8개 항목, 월별 추세, 근거 발췌, CSV 미리보기·저장, 인쇄 |
| summary.csv | 카페·기간·카테고리별 점수, 건수, 비율, 표본 상태 |
| reviews.jsonl | 리뷰별 원문·정제문·카테고리 점수·근거 표현·정제문 위치 |
| input_issues.csv | 중복·빈 필드·날짜 누락 등과 처리 방식 |
| run_metadata.json | 입력·사전·규칙 해시, 버전, 집계 설정, 처리 건수 |

점수 범위는 0~100입니다. 해당 항목의 감성 근거가 없으면 빈칸이며, 중립과 긍부정 혼합은 구분해 집계합니다. **75점은 고객 75%가 만족했다는 뜻이 아닙니다.** 관련 리뷰가 10건 미만이면 임시 기준으로 ‘표본 부족’을 표시합니다.

`reviews.jsonl`은 날짜 필터 밖 리뷰도 포함하는 전체 입력의 상세 분석입니다. `summary.csv`에만 기간 필터가 적용됩니다. 상세 파일에는 리뷰 원문이 있으므로 비공개 폴더에서 관리합니다.

## 사전 수정과 카페 설정

`lexicon/cafe_sentiment.csv`가 편집 기준입니다. `polarity`는 -2~-1~0~1~2이며, `pattern`은 매칭 정규식입니다. 단어 변형은 `pattern`에 반영합니다. `variants`, `subcategory`는 기록용입니다. `target_terms`가 비어 있지 않으면 해당 절에 그 단서 중 하나가 있어야 매칭합니다. 대상 연결은 `context_rules.json`의 공통 단서와 카페별 설정을 사용합니다.

붙여 쓴 `빵도맛있어요` 등을 위해 자체 작성 정규식의 맨 앞 `(?<![가-힣])` 경계는 대상·조사·강조·앞 부정 단서가 있을 때 완화합니다. 무조건 부분 문자열을 허용하지는 않습니다. `lexicon/development_coverage.csv`에는 후보별 개발 자료 선택 근거 건수가 있습니다. 0건은 틀린 표현이라는 뜻도, 검증된 표현이라는 뜻도 아닙니다.

```powershell
python tools/export_lexicon.py
python -m unittest discover -s tests -v
```

변환 도구는 배포용 JSON과 설치 패키지 안의 사전도 동기화합니다. 사전·규칙을 바꾸면 버전과 변경 이력을 갱신합니다.

카페별 메뉴명은 `configs/cafe_aliases.example.json` 구조로 작성하여 `--aliases 파일경로`를 지정합니다. 그 설정의 단어 자체에는 감성 점수를 부여하지 않습니다.

## 실제 리뷰 수집

수집 도구는 분석기와 별도이며 `beautifulsoup4`가 필요합니다. 공개 페이지의 리뷰만 요청하며 닉네임·사용자 프로필·사진을 결과 CSV로 저장하지 않습니다. 요청 간격은 최소 1초이고, 접근 제한 응답을 받으면 중단합니다.

```powershell
python -m pip install -r requirements-crawl.txt
python tools/crawl_diningcode.py --max-pages 40 --delay 1.5
python tools/crawl_diningcode.py --cafes configs/collection.expansion.json --output data_private/reviews.expansion.csv --max-pages 70 --delay 1.5
python tools/crawl_diningcode.py --cafes configs/collection.narinamu.json --output data_private/reviews.narinamu.csv --max-pages 5 --delay 1.5
```

기본 대상은 테라로사 강릉본점·어니언 안국점·레이어드 안국점이며 설정으로 프릳츠·대림창고·나리나무를 추가합니다. `--cafes`는 `[카페 ID, 이름, 다이닝코드 rid]` 배열의 JSON입니다. 추천순 표본이며 화면 전체 리뷰의 완전 수집을 보장하지 않습니다. 원문 CSV·캐시·수집 기록은 `data_private`에 저장하며 GitHub 공개 대상에서 제외합니다. 작성 연도가 빠지면 `source_date_text`를 보존하고 `review_date`를 빈칸으로 둡니다. 캐시를 읽은 수집 시각은 캐시 파일 생성·저장 시점입니다.

## 검증과 문서

```powershell
python -m unittest discover -s tests -v
python tools/benchmark.py
python tools/benchmark_cli.py
```

- `docs/taxonomy.md`: 분류 기준.
- `docs/scoring.md`: 점수, 비율 분모, 날짜와 표본 처리.
- `docs/annotation_guide.md`: 실제 리뷰 정답 작성 방법.
- `docs/annotation_workspace.md`: 예측을 숨긴 검토 화면·저장·복구·CSV 평가 연결.
- `docs/evaluation.md`: 검증 결과와 미지원 문맥.
- `docs/provisional_review.md`: v0.2의 고정 사전 12본문 잠정 점검(과거 기록).
- `docs/provisional_review.v03.md`: 새 카페 10본문 잠정 점검과 남은 누락·오판.
- `docs/dataset.v03.json`, `docs/coverage.v03.json`: 데이터 역할·해시·후보 출현·판정 범위.
- `docs/data_status.md`: 확보 자료와 작업 상태.
- `docs/sources.md`: 출처와 공개 범위.

반어, 복잡한 대명사, 붙여 쓴 긴 문장, 인용과 직접 평가가 섞인 절은 오판 또는 누락이 생길 수 있습니다. 현재는 형태소 분석기 없이 어간 정규식과 가까운 대상 단서를 사용합니다. 판정 범위는 정확도가 아닙니다. 나리나무 2건으로 카테고리별 운영 판단을 내릴 수는 없습니다.

실제 정답 작성·평가는 `docs/annotation_guide.md`를 따릅니다. 정답이 비어 있으면 평가 도구는 정확도를 계산하지 않습니다. 사람 라벨 없이 자동 판정을 정답으로 채우지 않습니다.

## 공개와 기여

코드와 자체 작성 사전·예제는 MIT 라이선스로 제공합니다. 외부 원문 리뷰는 이 라이선스에 포함하지 않습니다. KNU 사전 데이터는 복제하지 않았습니다. 신규 표현을 제안할 때는 카테고리, 감성 강도, 판단 이유, 자체 작성 예문을 함께 제출해주세요.

GitHub 공개용 묶음은 `python tools/package_public.py`로 생성합니다. 공개 묶음에는 허용된 코드·문서·사전·생성 예제와 원문 없는 실행 통계만 포함합니다. 카페별 감성 점수·실제 상세 결과는 로컬에 보관합니다.
