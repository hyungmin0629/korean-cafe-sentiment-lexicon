import re


def resolve_category(entry, clause, start, end, targets):
    if entry["category"] != "auto":
        return entry["category"], "lexicon_category"
    distances = {}
    for category, terms in targets.items():
        for term in terms:
            for match in re.finditer(re.escape(term), clause):
                distance = max(start - match.end(), match.start() - end, 0)
                distances[category] = min(distance, distances.get(category, float("inf")))
    if not distances:
        return "overall", "no_target_overall"
    closest = min(distances.values())
    choices = [category for category, distance in distances.items() if distance == closest]
    if len(choices) > 1:
        return None, "ambiguous_target"
    return choices[0], "nearest_target"


def apply_context(entry, clause, start, end, rules):
    before, after = clause[:start], clause[end:]
    polarity = entry["polarity"]
    applied = []
    # Conservative clause-wide abstention prevents obvious hypothetical/quoted
    # evaluations being asserted as observed opinions. See docs for its limits.
    for reason, pattern in rules["abstain_patterns"].items():
        if re.search(pattern, clause):
            return None, [reason], start, end
    suffix = re.match(rules["negation_suffix"], after)
    prefix = re.search(rules["negation_prefix"], before)
    if suffix or prefix:
        # Negating a negative is weak positive, not emphatically positive.
        polarity = -polarity if polarity >= 0 else 1
        applied.append("negation")
        if suffix:
            end += suffix.end()
        if prefix:
            start = prefix.start()
    if not applied:
        if re.search(rules["intensifier_prefix"], before[-12:]):
            polarity = max(-2, min(2, polarity * 1.5))
            applied.append("intensifier")
        elif re.search(rules["diminisher_prefix"], before[-12:]):
            polarity *= 0.5
            applied.append("diminisher")
    return polarity, applied, start, end
