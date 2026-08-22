from core.i18n import _


def best_of(client) -> int:
    try:
        return int(getattr(client.room, "best_of", 1))
    except (AttributeError, TypeError, ValueError):
        return 1


def is_match(client) -> bool:
    return best_of(client) > 1


def get_match_state(client) -> dict:
    match_best_of = best_of(client)
    state = getattr(client.memory, "match_state", None)
    if not state or state.get("best_of") != match_best_of:
        state = {
            "best_of": match_best_of,
            "player_wins": 0,
            "opponent_wins": 0,
            "draws": 0,
            "current_game": 1,
        }
        client.memory.match_state = state
    return state


def record_duel_result(client, winner: int) -> dict | None:
    if not is_match(client):
        return None
    state = get_match_state(client)
    if winner == 2:
        state["draws"] += 1
    elif winner == client.what_player_am_i:
        state["player_wins"] += 1
    else:
        state["opponent_wins"] += 1
    state["current_game"] += 1
    return state


def wins_needed(state: dict) -> int:
    return (int(state.get("best_of", 1)) // 2) + 1


def is_match_over(client) -> bool:
    if not is_match(client):
        return True
    state = get_match_state(client)
    needed = wins_needed(state)
    return state["player_wins"] >= needed or state["opponent_wins"] >= needed


def score_text(client) -> str:
    if not is_match(client):
        return _("Single duel.")
    state = get_match_state(client)
    text = _("Match score: you {you}, opponent {opponent}. Game {game} of best-of-{best_of}.").format(
        you=state["player_wins"],
        opponent=state["opponent_wins"],
        game=state["current_game"],
        best_of=state["best_of"],
    )
    if state["draws"]:
        text += " " + _("Draws: {draws}.").format(draws=state["draws"])
    return text
