"""Build a prediction-blind offline review workspace from an EMPTY label CSV.

Reads only the annotation template, category names and optional cafe names.
Never opens predictions, lexicon entries, scores, ratings or provisional labels.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {"menu":"메뉴·맛", "service":"친절·서비스", "space":"공간·분위기", "location":"입지·접근성",
              "value":"가격·가성비", "hygiene":"청결", "operation":"이용·운영", "overall":"전반 만족"}
FIELDS = ["source", "review_id", "cafe_id", "split", "text", "category", "gold_label", "evidence_text", "reviewer", "notes"]


def build_model(source, cafe_names=None):
    source=Path(source)
    reviews={}
    with source.open(encoding="utf-8-sig",newline="") as handle:
        reader=csv.DictReader(handle)
        if not set(FIELDS).issubset(reader.fieldnames or []):
            raise ValueError("Missing annotation template columns")
        for row in reader:
            if any(row.get(key,"").strip() for key in ("gold_label","evidence_text","reviewer","notes")):
                raise ValueError("Use an empty template; prefilled judgments are not accepted")
            if row["category"] not in CATEGORIES or any(not row[key].strip() for key in ("source","review_id","cafe_id","split","text")):
                raise ValueError("Invalid category or empty review identity/text")
            identity=(row["source"],row["cafe_id"],row["review_id"])
            key=json.dumps(identity,ensure_ascii=False,separators=(",",":"))
            review=reviews.setdefault(key,{"key":key,"source":row["source"],"cafe_id":row["cafe_id"],"review_id":row["review_id"],
                "split":row["split"],"text":row["text"],"text_sha256":hashlib.sha256(row["text"].encode()).hexdigest(),
                "cafe_name":(cafe_names or {}).get(row["cafe_id"],row["cafe_id"]),"categories":[]})
            if review["text"]!=row["text"] or review["split"]!=row["split"]:
                raise ValueError("Inconsistent text/split within a review")
            if row["category"] in review["categories"]:
                raise ValueError("Duplicate review/category")
            review["categories"].append(row["category"])
    if not reviews or any(set(r["categories"])!=set(CATEGORIES) for r in reviews.values()):
        raise ValueError("Each review must have exactly the eight categories")
    ordered=list(reviews.values())
    for review in ordered: review["categories"]=list(CATEGORIES)
    return {"schema_version":1,"ui_version":"0.1.0","dataset_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
            "categories":CATEGORIES,"reviews":ordered,"aspect_count":len(ordered)*len(CATEGORIES),
            "is_synthetic":all(r["source"]=="synthetic" for r in ordered),"prediction_blind":True}


def write_ui(source,destination,cafe_names=None):
    destination=Path(destination)
    if destination.exists(): raise ValueError("Output exists; choose a new file")
    model=build_model(source,cafe_names)
    resources=ROOT/"src/cafe_sentiment/resources"
    html=(resources/"annotation.html").read_text(encoding="utf-8")
    for placeholder,name in [("__ANNOTATION_CSS__","annotation.css"),("__ANNOTATION_CORE__","annotation-core.js"),("__ANNOTATION_JS__","annotation.js")]:
        html=html.replace(placeholder,(resources/name).read_text(encoding="utf-8"))
    payload=json.dumps(model,ensure_ascii=False,separators=(",",":")).replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
    html=html.replace("__ANNOTATION_DATA__",payload)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(html,encoding="utf-8")
    return {"path":str(destination),"reviews":len(model["reviews"]),"aspects":model["aspect_count"],"prediction_blind":True,
            "contains_external_review_text":not model["is_synthetic"],"dataset_sha256":model["dataset_sha256"]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--cafes",help="Optional [cafe_id,name,rid] cafe configuration")
    args=parser.parse_args()
    try:
        names={r[0]:r[1] for r in json.loads(Path(args.cafes).read_text(encoding="utf-8"))} if args.cafes else None
        print(json.dumps(write_ui(args.input,args.output,names),ensure_ascii=False))
    except (ValueError,OSError,KeyError) as error: parser.error(str(error))


if __name__=="__main__":main()
