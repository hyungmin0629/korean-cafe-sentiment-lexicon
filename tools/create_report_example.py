"""Create explicitly synthetic report examples with a large and sparse cafe."""
import csv
import argparse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TEXTS={
    1:["커피는 맛있어요. 직원은 친절해요. 주차가 편해요.",
       "빵이 촉촉하고 맛있어요. 분위기가 좋아요. 가격이 적당해요.",
       "커피가 고소해요. 주문이 빨리 나와요. 의자가 편해요.",
       "스콘은 맛있어요. 직원이 설명을 잘 해줘요. 화장실은 깨끗해요.",
       "커피는 맛있어요. 공간이 넓어요. 주차장이 넓어요.",
       "라떼는 맛있어요. 직원이 상냥해요. 와이파이가 잘 돼요.",
       "케이크가 맛있어요. 가격이 합리적이에요. 재방문 의사 있어요.",
       "커피는 맛있어요. 직원이 친절해요. 대기 없이 들어왔어요."],
    2:["커피는 맛있어요. 직원은 불친절해요. 주차가 어려워요.",
       "빵은 맛없어요. 분위기는 좋아요. 가격은 비싸요.",
       "커피는 맛있어요. 주문하는데 오래 걸려요. 의자가 불편해요.",
       "스콘은 맛없어요. 직원 설명이 부족해요. 화장실은 깨끗해요.",
       "커피는 맛있어요. 공간은 넓어요. 웨이팅이 길어요.",
       "라떼는 맛없어요. 직원이 불친절해요. 와이파이가 안 돼요.",
       "케이크는 맛있어요. 가격은 비싸요. 재방문 의사 없어요.",
       "커피는 맛없어요. 직원은 친절해요. 대기가 길어요."],
    3:["커피는 맛있어요. 직원은 친절해요. 주차가 편해요.",
       "빵은 맛있어요. 분위기가 좋아요. 가격은 비싸요.",
       "커피는 맛있어요. 주문이 빨리 나와요. 의자가 편해요.",
       "스콘은 맛있어요. 직원이 설명을 잘 해줘요. 화장실은 깨끗해요.",
       "커피는 맛없어요. 공간은 넓어요. 대기 없이 들어왔어요.",
       "라떼는 맛있어요. 직원은 친절해요. 와이파이가 잘 돼요.",
       "케이크는 맛있어요. 가격은 비싸요. 재방문 의사 있어요.",
       "커피는 맛있어요. 직원은 친절해요. 주문이 빨리 나와요."]}
TEXTS[4] = TEXTS[1][:4] + TEXTS[2][4:]
TEXTS[5] = [text.replace("가격은 비싸요", "가격이 합리적이에요") for text in TEXTS[3]]
TEXTS[6] = TEXTS[1]
MONTH_COUNTS={1:32,2:40,3:56,4:48,5:32,6:40}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default=str(ROOT / "examples/reviews.report.synthetic.csv"))
    args=parser.parse_args()
    path=Path(args.output)
    if path.exists():raise SystemExit("Synthetic example exists; preserve it")
    with path.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.writer(handle)
        writer.writerow(["review_id","cafe_id","cafe_name","source","review_date","text"])
        for month,texts in TEXTS.items():
            for i in range(MONTH_COUNTS[month]):
                writer.writerow([f"report_{month}_{i}","report_demo_a","보고서 예제 카페 A","synthetic",f"2026-{month:02d}-{i%28+1:02d}",texts[i%len(texts)]])
        writer.writerow(["sparse_1","report_demo_b","소량 예제 카페 B","synthetic","2026-01-02","커피는 맛있어요"])
        writer.writerow(["sparse_2","report_demo_b","소량 예제 카페 B","synthetic","","커피는 맛없어요"])
    print(f"{sum(MONTH_COUNTS.values())+2} authored synthetic rows, six months; not customer data")


if __name__=="__main__":main()
