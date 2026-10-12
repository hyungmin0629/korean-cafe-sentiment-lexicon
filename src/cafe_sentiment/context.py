import re


def resolve_categories(entry, clause, start, end, targets, topic=None):
    """Share one explicit predicate across an enumerated target list."""
    if entry["category"] == "auto":
        enumeration = re.fullmatch(r"\s*(.+?)\s*(?:모두|전부|둘\s*다)\s*", clause[:start])
        if enumeration:
            tokens = re.split(r"\s*(?:,|및|와|과|랑|하고)\s*", enumeration.group(1))
            categories = []
            for token in tokens:
                matched = [category for category, terms in targets.items() if any(
                    re.fullmatch(re.escape(term) + r"[이가은는을를도]*", token.strip()) for term in terms)]
                if len(matched) != 1:
                    categories = []
                    break
                categories.extend(matched)
            if len(tokens) > 1 and categories:
                return [(category, "shared_enumeration") for category in dict.fromkeys(categories)]
    return [resolve_category(entry, clause, start, end, targets, topic)]


def resolve_category(entry, clause, start, end, targets, topic=None):
    if entry["category"] != "auto":
        return entry["category"], "lexicon_category"
    distances = {}
    for category, terms in targets.items():
        for term in terms:
            for match in re.finditer(re.escape(term), clause):
                distance = max(start - match.end(), match.start() - end, 0)
                distances[category] = min(distance, distances.get(category, float("inf")))
    if not distances:
        if topic:
            return topic, "preceding_topic_header"
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
    if re.search(r"(?:다른|옆|근처|주변)\s*(?:카페|가게|곳|매장)[이가은는]|\S+(?:동|지역)[의은는]*\s*물가|지역\s*물가", clause):
        return None, ["external_target"], start, end
    if re.search(r"(?:에|엔)\s*$", before) and re.match(r"은\s*(?:곳|카페)[이가은는]*\s*많", after):
        return None, ["external_target"], start, end
    if "추천" in entry["expression"] and re.search(
            r"(?:친구|지인|동료|블로그|후기|리뷰|누군가)[이가은는]*\s*(?:[가-힣]+\s*){0,3}$", before):
        return None, ["attributed_recommendation"], start, end
    # Attach uncertainty to the evaluation ending rather than excluding a whole
    # clause just because it also contains "기대" or an unrelated quotation.
    for reason, pattern in rules["abstain_patterns"].items():
        if re.match(pattern, after):
            return None, [reason], start, end
    if re.search(r"(?:안|못)\s*(?:먹|마셔|마시)[가-힣]*\s*$", before[-25:]):
        return None, ["not_experienced"], start, end
    if re.match(r"^(?:하)?(?:지|지는|지도|진)\s*(?:않|못)(?:았|했)?(?:다고|다며|대요|다면|으면|겠)", after):
        return None, ["negated_quote_or_condition"], start, end
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
