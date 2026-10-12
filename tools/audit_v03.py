"""Versioned execution coverage, without accuracy claims or review publication."""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    dataset=json.loads((ROOT/'docs/dataset.v03.json').read_text(encoding='utf-8'))
    with (ROOT/'outputs_private/actual_all_v03_final/reviews.jsonl').open(encoding='utf-8') as handle:
        records=[json.loads(line) for line in handle]
    lexicon=json.loads((ROOT/'lexicon/cafe_sentiment.json').read_text(encoding='utf-8'))
    matched,scored=Counter(),Counter()
    development={'terarosa_gangneung','fritz_dohwa'}
    for r in records:
        if r['cafe_id'] not in development: continue
        matched.update({e['entry_id'] for e in r['evidence']})
        scored.update({e['entry_id'] for e in r['evidence'] if e['polarity'] is not None})
    with (ROOT/'lexicon/development_coverage.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        fields=['entry_id','expression','category','polarity','development_reviews_matched','development_reviews_scored','status']
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        for e in lexicon['entries']:
            writer.writerow({k:e[k] for k in ('entry_id','expression','category','polarity','status')} | {'development_reviews_matched':matched[e['entry_id']], 'development_reviews_scored':scored[e['entry_id']]})
    def has_score(r): return any(c['score'] is not None for c in r['categories'].values())
    cafes=[]
    for cafe in dataset['cafes']:
        selected=[r for r in records if r['cafe_id']==cafe['cafe_id']]
        cafes.append(cafe | {'scored_reviews':sum(map(has_score,selected)), 'needs_review':sum(r['needs_review'] for r in selected),
                            'category_scored_reviews':{key:sum(r['categories'][key]['score'] is not None for r in selected) for key in selected[0]['categories']}})
    report={'version':'0.3.0','entries':len(lexicon['entries']),'development_reviews':221,
            'entries_observed_in_development':len(matched),'entries_unobserved_in_development':len(lexicon['entries'])-len(matched),
            'observation_definition':'Selected evidence in fixed 221 development texts, includes abstained evidence; not human validation',
            'cafes':cafes,'analyzed_reviews':len(records),'scored_reviews':sum(map(has_score,records)),
            'interpretation':'Execution coverage only; human accuracy unmeasured',
            'lexicon_sha256':dataset['lexicon_sha256'],'rules_sha256':dataset['rules_sha256']}
    (ROOT/'docs/coverage.v03.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='cafes'},ensure_ascii=False))


if __name__=='__main__':main()
