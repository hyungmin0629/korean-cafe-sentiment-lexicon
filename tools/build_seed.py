"""Create the initial authored candidates once; edit CSV thereafter."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# expression | regex stem/phrase | category | polarity
SEEDS = r"""
맛있다|맛있|menu|2
맛없다|맛없|menu|-2
맛이 좋다|맛[이가은는]*\s*좋|menu|2
맛이 없다|맛[이가은는]*\s*없|menu|-2
맛이 별로다|맛[이가은는]*\s*별로|menu|-1
맛이 아쉽다|맛[이가은는]*\s*아쉽|menu|-1
맛집|맛집|menu|1
향긋하다|향긋|menu|1
고소하다|고소|menu|1
풍미가 좋다|풍미[가도는]*\s*좋|menu|2
향이 좋다|향[이가은는]*\s*좋|menu|1
잡내|잡내|menu|-1
비린내|비린내|menu|-2
눅눅하다|눅눅|menu|-1
퍽퍽하다|퍽퍽|menu|-1
촉촉하다|촉촉|menu|1
바삭하다|바삭|menu|1
신선하다|신선|menu|1
상했다|상했|menu|-2
밍밍하다|밍밍|menu|-1
탄 맛|탄\s*맛|menu|-1
취향에 맞다|취향[에이가]*\s*(?:잘\s*)?맞|menu|1
입맛에 맞다|입맛[에이가]*\s*(?:잘\s*)?맞|menu|1
입에 맞다|입에\s*(?:잘\s*)?맞|menu|1
취향이 아니다|취향[이가은는]*\s*아니|menu|-1
너무 달다|너무\s*달|menu|-1
너무 쓰다|너무\s*쓰|menu|-1
너무 시다|너무\s*시(?:다|고|네|어요|었)|menu|-1
산미가 너무 강하다|산미[가은는]*\s*너무\s*강|menu|-1
친절하다|친절|service|2
불친절하다|불친절|service|-2
상냥하다|상냥|service|1
다정하다|다정|service|1
퉁명스럽다|퉁명|service|-1
무례하다|무례|service|-2
응대가 좋다|응대[가도는]*\s*좋|service|1
응대가 별로다|응대[가도는]*\s*별로|service|-1
설명을 잘 해주다|설명[을도]*\s*잘\s*해|service|1
주문을 잘못 받다|주문[을도]*\s*잘못\s*받|service|-2
주문 누락|주문\s*누락|service|-2
인사를 안 하다|인사[를도]*\s*안\s*하|service|-1
아늑하다|아늑|space|1
쾌적하다|쾌적|space|1
답답하다|답답|space|-1
시끄럽다|시끄[러럽]|space|-1
소음이 심하다|소음[이가]*\s*심|space|-2
의자가 불편하다|의자[가도는]*\s*불편|space|-1
좌석이 편하다|좌석[이가도은는]*\s*편|space|1
인테리어가 예쁘다|인테리어[가도는]*\s*예[쁘뻐쁜뻤]|space|1
분위기가 좋다|분위기[가도는]*\s*좋|space|2
분위기 맛집|분위기\s*맛집|space|2
사진 찍기 좋다|사진\s*찍기\s*좋|space|1
공부하기 좋다|공부하기\s*좋|space|1
작업하기 좋다|작업하기\s*좋|space|1
콘센트가 부족하다|콘센트[가도는]*\s*부족|space|-1
좌석이 좁다|좌석[이가도은는]*\s*좁|space|-1
공간이 넓다|공간[이가도은는]*\s*넓|space|1
찾기 쉽다|찾기\s*쉽|location|1
찾기 어렵다|찾기\s*어[렵려]|location|-1
접근성이 좋다|접근성[이가도은는]*\s*좋|location|1
역에서 가깝다|역에서\s*가[깝까]|location|1
주차가 편하다|주차[가도는]*\s*편|location|1
주차가 어렵다|주차[가도는]*\s*어[렵려]|location|-1
주차가 불편하다|주차[가도는]*\s*불편|location|-1
주차 공간이 없다|주차\s*(?:공간|자리)[이가도은는]*\s*없|location|-1
가성비가 좋다|가성비[가도는]*\s*좋|value|2
가성비가 나쁘다|가성비[가도는]*\s*나[쁘빠]|value|-2
비싸다|비[싸싼쌌]|value|-1
저렴하다|저렴|value|1
합리적인 가격|합리적[인으로]*\s*가격|value|1
양이 적다|양[이가은는]*\s*적|value|-1
가격이 부담스럽다|가격[이가은는]*\s*부담|value|-1
돈이 아깝다|돈[이가은는]*\s*아[깝까]|value|-2
깨끗하다|깨끗|hygiene|1
지저분하다|지저분|hygiene|-2
청결하다|청결|hygiene|1
더럽다|더[럽러]|hygiene|-2
위생이 좋다|위생[이가은는]*\s*좋|hygiene|1
위생이 아쉽다|위생[이가은는]*\s*아쉽|hygiene|-1
먼지가 많다|먼지[가은는]*\s*많|hygiene|-1
설거지가 안 되다|설거지[가은는]*\s*안\s*되|hygiene|-2
대기가 길다|대기[가은는]*\s*길|operation|-1
웨이팅이 길다|웨이팅[이가은는]*\s*길|operation|-1
자주 품절|자주\s*품절|operation|-1
품절이라 아쉽다|품절[이라서]*\s*아쉽|operation|-1
오래 기다리다|오래\s*기다|operation|-1
빨리 나오다|빨리\s*나[오왔]|operation|1
대기 없이|대기\s*없이|operation|1
웨이팅 없이|웨이팅\s*없이|operation|1
재방문하고 싶다|재방문[을]*\s*하고\s*싶|overall|2
또 오고 싶다|또\s*오고\s*싶|overall|2
다시 방문하고 싶다|다시\s*방문하고\s*싶|overall|2
다신 안 오다|다신\s*안\s*[오올]|overall|-2
재방문 의사 없다|재방문\s*의사[가은는]*\s*없|overall|-2
추천한다|추천|auto|1
만족한다|만족|auto|1
실망한다|실망|auto|-2
별로다|별로|auto|-1
아쉽다|아[쉽쉬]|auto|-1
괜찮다|괜찮|auto|1
좋다|좋|auto|1
나쁘다|나[쁘빠]|auto|-1
편하다|편[하한해했]|auto|1
불편하다|불편|auto|-1
예쁘다|예[쁘뻐쁜뻤]|auto|1
깔끔하다|깔끔|auto|1
그저 그렇다|그저\s*그[렇래런]|auto|0
보통이다|보통|auto|0
평범하다|평범|auto|0
"""


def main():
    entries = []
    for index, line in enumerate(SEEDS.strip().splitlines(), 1):
        expression, rest = line.split("|", 1)
        pattern, category, polarity = rest.rsplit("|", 2)
        entries.append({"entry_id": f"CAFE{index:04d}", "expression": expression,
                        "variants": [], "pattern": r"(?<![가-힣])(?:" + pattern + ")",
                        "category": category, "subcategory": "", "polarity": int(polarity),
                        "match_type": "regex", "target_terms": [], "context_rule_id": "default",
                        "provenance": "authored_by_codex_2026-10-12", "status": "candidate",
                        "notes": "자체 작성 초안. 실제 리뷰·사람 평가로 검증 전."})
    lexicon_dir = ROOT / "lexicon"
    lexicon_dir.mkdir(parents=True, exist_ok=True)
    path = lexicon_dir / "cafe_sentiment.csv"
    if path.exists():
        raise SystemExit("Seed CSV exists; edit the CSV, do not regenerate it")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(entries[0]))
        writer.writeheader()
        for entry in entries:
            row = dict(entry)
            for field in ("variants", "target_terms"):
                row[field] = json.dumps(row[field], ensure_ascii=False)
            writer.writerow(row)
    print(f"Created {len(entries)} candidate entries")


if __name__ == "__main__":
    main()
