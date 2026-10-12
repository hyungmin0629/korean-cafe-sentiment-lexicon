import re


def compile_entries(entries):
    result = []
    ids = set()
    for entry in entries:
        if entry["entry_id"] in ids:
            raise ValueError("Duplicate lexicon entry_id: " + entry["entry_id"])
        ids.add(entry["entry_id"])
        if entry["status"] == "deprecated":
            continue
        if entry["category"] not in {
            "menu", "service", "space", "location", "value", "hygiene",
            "operation", "overall", "auto"
        } or entry["polarity"] not in (-2, -1, 0, 1, 2):
            raise ValueError("Invalid lexicon category/polarity: " + entry["entry_id"])
        # Relax only our authored leading boundary; find_matches checks whether
        # an attached preceding token is a target, particle or modifier.
        pattern = entry["pattern"].removeprefix(r"(?<![가-힣])")
        result.append((entry, re.compile(pattern)))
    return result


def find_matches(text, compiled, attached_prefix=None):
    candidates = []
    for entry, pattern in compiled:
        for match in pattern.finditer(text):
            if match.group().endswith("좋") and match.end() < len(text):
                following = text[match.end()]
                if re.match(r"[가-힣]", following) and following not in "다아았고은음네지겠더던으게냐나":
                    continue
            if match.start() and re.match(r"[가-힣]", text[match.start() - 1]):
                if attached_prefix is None or not attached_prefix.search(text[:match.start()]):
                    continue
            terms = entry.get("target_terms", [])
            if terms and not any(term in text for term in terms):
                continue
            candidates.append((match.start(), match.end(), entry))
    # Longest expression wins when spans overlap, with stable tie breaking.
    candidates.sort(key=lambda x: (-(x[1] - x[0]), x[0], x[2]["entry_id"]))
    selected = []
    for candidate in candidates:
        if not any(candidate[0] < end and start < candidate[1]
                   for start, end, _ in selected):
            selected.append(candidate)
    return sorted(selected, key=lambda x: x[0])
