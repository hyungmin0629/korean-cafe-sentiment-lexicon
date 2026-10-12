import hashlib
import json
import re
from importlib.resources import files
from pathlib import Path

from .context import apply_context, resolve_category
from .match import compile_entries, find_matches
from .preprocess import clauses, normalize


def read_json(path, default):
    data = Path(path).read_bytes() if path else files("cafe_sentiment").joinpath(
        "resources", default).read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def label(values):
    if not values:
        return "unscored"
    if any(x > 0 for x in values) and any(x < 0 for x in values):
        return "mixed"
    mean = sum(values) / len(values)
    return "positive" if mean > 0 else "negative" if mean < 0 else "neutral"


class Analyzer:
    def __init__(self, lexicon=None, rules=None, aliases=None):
        self.lexicon, self.lexicon_hash = read_json(lexicon, "cafe_sentiment.json")
        self.rules, self.rules_hash = read_json(rules, "context_rules.json")
        self.compiled = compile_entries(self.lexicon["entries"])
        self.categories = self.rules["category_labels"]
        self.targets = {key: list(value) for key, value in self.rules["targets"].items()}
        self.aliases_hash = None
        self.aliases = {}
        if aliases:
            self.aliases, self.aliases_hash = read_json(aliases, "unused")
            for cafe_id, mapping in self.aliases.items():
                for category, terms in mapping.items():
                    if category not in self.categories or not isinstance(terms, list) or not all(
                            isinstance(term, str) and term for term in terms):
                        raise ValueError("Invalid cafe aliases: " + cafe_id)

    def analyze(self, text, cafe_id=""):
        normalized = normalize(text)
        targets = {key: list(value) for key, value in self.targets.items()}
        for key, terms in self.aliases.get(cafe_id, {}).items():
            targets.setdefault(key, []).extend(terms)
        terms = sorted({term for group in targets.values() for term in group}, key=len, reverse=True)
        attached_prefix = re.compile(r"(?:" + "|".join(re.escape(term) for term in terms) +
            r")[이가은는을를에도와과의로]*\s*(?:(?:정말|매우|엄청|너무|진짜|아주|조금|약간|살짝|좀)\s*)?(?:안|못)?$"
            r"|(?:정말|매우|엄청|너무|진짜|아주|조금|약간|살짝|좀|안|못|하고)$")
        evidence = []
        mentioned = set()
        topic = None
        for offset, _, clause in clauses(normalized):
            # An isolated category heading applies to the next clause only.
            header = re.fullmatch(r"\s*([가-힣]+)\s*[:：]\s*", clause)
            if header:
                topic = self.rules.get("topic_headers", {}).get(header.group(1))
                continue
            for category, terms in targets.items():
                if any(term in clause for term in terms):
                    mentioned.add(category)
            for start, end, entry in find_matches(clause, self.compiled, attached_prefix):
                category, target_rule = resolve_category(entry, clause, start, end, targets, topic)
                polarity, applied, evidence_start, evidence_end = apply_context(
                    entry, clause, start, end, self.rules)
                if category:
                    mentioned.add(category)
                else:
                    polarity = None
                evidence.append({
                    "entry_id": entry["entry_id"], "expression": entry["expression"],
                    "matched_text": clause[evidence_start:evidence_end],
                    "start": offset + evidence_start, "end": offset + evidence_end,
                    "category": category, "base_polarity": entry["polarity"],
                    "polarity": polarity, "rules": [target_rule] + applied,
                    "status": "scored" if polarity is not None else "needs_review",
                })
            topic = None
        category_scores = {}
        for category in self.categories:
            values = [e["polarity"] for e in evidence
                      if e["category"] == category and e["polarity"] is not None]
            mean = sum(values) / len(values) if values else None
            category_scores[category] = {
                "mentioned": category in mentioned, "polarity": mean,
                "score": 50 + 25 * mean if mean is not None else None,
                "label": label(values), "evidence_count": len(values),
                "positive_evidence": sum(v > 0 for v in values),
                "negative_evidence": sum(v < 0 for v in values),
                "neutral_evidence": sum(v == 0 for v in values),
            }
        return {"normalized_text": normalized, "categories": category_scores,
                "evidence": evidence,
                "needs_review": any(e["status"] == "needs_review" for e in evidence)}
