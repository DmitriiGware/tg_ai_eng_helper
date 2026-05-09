ROADMAP = {
    "A1": [
        "to be",
        "articles",
        "plural nouns",
        "present simple",
        "basic prepositions",
    ],
    "A2": [
        "past simple",
        "present continuous",
        "comparatives",
        "going to",
        "some and any",
    ],
    "B1": [
        "present perfect",
        "first conditional",
        "second conditional",
        "passive voice",
        "reported speech",
    ],
    "B2": [
        "third conditional",
        "future perfect",
        "advanced passive",
        "relative clauses",
        "modals in the past",
    ],
    "C1": [
        "advanced inversion",
        "hedging",
        "nominalisation",
        "formal register",
        "complex clauses",
    ],
    "C2": [
        "idiomatic precision",
        "subtle emphasis",
        "advanced discourse markers",
        "formal cohesion",
        "pragmatic nuance",
    ],
}


def get_current_topic(user):
    topics = ROADMAP.get(user.level, [])
    index = user.current_topic_index or 0

    if index < 0:
        index = 0

    if index >= len(topics):
        return None

    return topics[index]


def update_progress(user, result):
    if result:
        user.current_topic_index = (user.current_topic_index or 0) + 1
        user.last_result = "correct"
        return

    if user.last_result in {"wrong", "wrong_twice"}:
        user.last_result = "wrong_twice"
    else:
        user.last_result = "wrong"
