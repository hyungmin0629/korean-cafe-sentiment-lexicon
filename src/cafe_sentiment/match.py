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
        result.append((entry, re.compile(entry["pattern"])))
    return result


def find_matches(text, compiled):
    candidates = []
    for entry, pattern in compiled:
        for match in pattern.finditer(text):
            candidates.append((match.start(), match.end(), entry))
    # Longest expression wins when spans overlap, with stable tie breaking.
    candidates.sort(key=lambda x: (-(x[1] - x[0]), x[0], x[2]["entry_id"]))
    selected = []
    for candidate in candidates:
        if not any(candidate[0] < end and start < candidate[1]
                   for start, end, _ in selected):
            selected.append(candidate)
    return sorted(selected, key=lambda x: x[0])
