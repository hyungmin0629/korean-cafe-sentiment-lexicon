"""One-time migration of v0.1 context rules to scoped v0.2 endings."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "lexicon/context_rules.json"
rules = json.loads(path.read_text(encoding="utf-8"))
rules["abstain_patterns"] = {
    "conditional_or_wish": r"^(?:하)?(?:다면|라면|으면|면|었으면|겠|아야|어야)",
    "quoted_or_hearsay": r"^(?:하)?(?:다고|다며|대요|라던|라고|다는)",
    "uncertain": r"^(?:어|아)?\s*보[이여입였]|^(?:한지|는지|을지|ㄹ지)\s*모르",
    "out_of_scope_negation": r"^(?:은|는|한|다는)?\s*(?:것은|건|것도)\s*아니",
}
rules["negation_prefix"] = r"(?:안|못)\s*$"
path.write_text(json.dumps(rules, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
