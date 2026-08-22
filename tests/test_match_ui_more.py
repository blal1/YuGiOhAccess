from types import SimpleNamespace

from core.dotdict import DotDict


def _client(best_of=3, player=0):
    return SimpleNamespace(
        room=SimpleNamespace(best_of=best_of),
        memory=DotDict(),
        what_player_am_i=player,
    )


def test_match_best_of_falls_back_for_bad_room_values():
    from ui import match_ui

    assert match_ui.best_of(SimpleNamespace()) == 1
    assert match_ui.best_of(SimpleNamespace(room=SimpleNamespace(best_of=None))) == 1
    assert match_ui.best_of(SimpleNamespace(room=SimpleNamespace(best_of="bad"))) == 1
    assert match_ui.best_of(SimpleNamespace(room=SimpleNamespace(best_of="5"))) == 5


def test_match_state_is_created_and_reset_when_best_of_changes():
    from ui import match_ui

    client = _client(best_of=3)
    state = match_ui.get_match_state(client)

    assert state == {
        "best_of": 3,
        "player_wins": 0,
        "opponent_wins": 0,
        "draws": 0,
        "current_game": 1,
    }

    client.memory.match_state["player_wins"] = 1
    client.room.best_of = 5
    assert match_ui.get_match_state(client)["best_of"] == 5
    assert match_ui.get_match_state(client)["player_wins"] == 0


def test_record_duel_result_tracks_player_opponent_and_draws():
    from ui import match_ui

    single = _client(best_of=1)
    assert match_ui.record_duel_result(single, winner=0) is None

    client = _client(best_of=3, player=1)
    state = match_ui.record_duel_result(client, winner=1)
    assert state["player_wins"] == 1
    assert state["current_game"] == 2

    state = match_ui.record_duel_result(client, winner=0)
    assert state["opponent_wins"] == 1
    assert state["current_game"] == 3

    state = match_ui.record_duel_result(client, winner=2)
    assert state["draws"] == 1
    assert state["current_game"] == 4


def test_match_over_and_score_text():
    from ui import match_ui

    single = _client(best_of=1)
    assert match_ui.is_match(single) is False
    assert match_ui.is_match_over(single) is True
    assert match_ui.score_text(single) == "Single duel."

    client = _client(best_of=3)
    state = match_ui.get_match_state(client)
    assert match_ui.wins_needed(state) == 2
    assert match_ui.is_match_over(client) is False

    state["player_wins"] = 2
    state["draws"] = 1
    assert match_ui.is_match_over(client) is True
    assert match_ui.score_text(client) == "Match score: you 2, opponent 0. Game 1 of best-of-3. Draws: 1."

    state["player_wins"] = 0
    state["opponent_wins"] = 2
    assert match_ui.is_match_over(client) is True
