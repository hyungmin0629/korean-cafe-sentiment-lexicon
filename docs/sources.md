# 출처와 공개 범위

기준일: 2026-10-13.

| 자료 | 출처·확인 방법 | 사용 |
|---|---|---|
| 프로젝트 목표 | 사용자 요청, 상위 감정분석 계획 문서 | 설계 기준 |
| 카페 표현 후보 420개 | Codex 자체 작성, 2026-10-12. 기존 124개에 도메인 보완 가설 291개와 개발 오류 유형 보완 5개 추가, 사람 검증 전 | candidate 사전, MIT |
| 기능 예제 18건 | Codex 자체 작성 | synthetic 예제, MIT |
| 참고 감성사전 | https://github.com/park1200656/KnuSentiLex README | 구조 참고. 원문 사전 복제 없음 |
| 테라로사 강릉본점 리뷰 | https://www.diningcode.com/profile.php?rid=wDkXSfj2qk2T | 로컬 분석, 원문 비공개 |
| 어니언 안국점 리뷰 | https://www.diningcode.com/profile.php?rid=vVFyXDEBVFu0 | 로컬 분석, 원문 비공개 |
| 레이어드 안국점 리뷰 | https://www.diningcode.com/profile.php?rid=DUzvoAT8FEUU | 개발 오류 점검, 원문 비공개 |
| 프릳츠 도화점 리뷰 | https://www.diningcode.com/profile.php?rid=BHt96vm9RXTN | 확장 개발, 원문 비공개 |
| 대림창고 성수 리뷰 | https://www.diningcode.com/profile.php?rid=TpMlBoL70Tge | 개발 오류 점검, 원문 비공개 |
| 카페나리나무 리뷰 | https://www.diningcode.com/profile.php?rid=ekLKGpK4p3Rc | 고정 사전 적용, 원문 비공개 |
| 모모스커피 부산본점 | https://www.diningcode.com/profile.php?rid=yxzkcEWHCAUB | 이번 분류기 수정 미사용, 원문 비공개 |
| 앤트러사이트 합정점 | https://www.diningcode.com/profile.php?rid=BkLmmTum9h3V | 이번 분류기 수정 미사용, 원문 비공개 |
| 보고서 예제 250건 | Codex 자체 작성 | synthetic 입력·HTML, MIT |
| 수집 허용 경로 확인 | https://www.diningcode.com/robots.txt | 수집 도구에 경로 검사 적용 |

실제 수집 건수·캐시·날짜 누락은 `data_private/crawl_manifest.json`에 기록합니다. 수집일은 Asia/Seoul 기준입니다. 원문 연도가 빠진 표시일을 임의로 작성일로 변환하지 않습니다.

네이버 플레이스 직접 요청은 429 응답을 받아 추가 수집을 중단했습니다. 다이닝코드의 공개 페이지와 페이지 자체가 사용하는 공개 더보기 요청으로 출처를 전환했습니다. 로그인·제한 우회·작성자 프로필·사진 수집은 수행하지 않습니다.

웹에 공개된 리뷰라도 재배포 조건은 별도입니다. 이번 공개 묶음에는 원문 리뷰, 캐시 페이지, 작성자 정보가 포함되지 않습니다. 외부 자료에 프로젝트 MIT 라이선스를 적용하지 않습니다.

추가 수집 기록은 `data_private/reviews.expansion.manifest.json`, `data_private/reviews.narinamu.manifest.json`에 있습니다. 공개 통계에는 원문·작성자·카페 감성 점수를 포함하지 않습니다.

새 카페 수집 기록은 `data_private/reviews.holdout_v03.manifest.json`에 있습니다. 실제 보고서의 발췌는 외부 원문이므로 공개 대상에 포함하지 않습니다.

2026-10-13에는 각자 실행하는 네이버 수집 코드를 추가했습니다. 사용자 지도 링크의 플레이스 ID는 `1649277590`이며 일반 브라우저에서 확인한 지점은 스타벅스 타임스퀘어R점입니다. 지도·데스크톱 리뷰 탭이 열려 카드 10개의 DOM 구조를 확인하고 선택자를 보완했습니다. 크롤러의 `https://m.place.naver.com/robots.txt` 요청은 429를 반환해 본문 0건에서 중단했습니다. 이 지점의 실제 리뷰 원문은 저장하거나 공개하지 않았으며 모바일 실제 수집·추가 로딩은 미확인입니다. 공개 `tests/fixtures/naver_reviews.synthetic.html`(5건)과 `naver_reviews.dom20261013.synthetic.html`(3건)은 Codex가 직접 작성한 테스트 문장입니다. 후자는 확인한 태그 구조를 재현하지만 실제 리뷰·작성자·HTML 전체를 복제하지 않았습니다. 설치·브라우저 API는 [Playwright 공식 문서](https://playwright.dev/python/docs/library)를 참고했습니다. [검증 기록](naver_live_validation.md)과 [실행 안내](naver_crawling.md)에 확인 범위를 기록했습니다.
