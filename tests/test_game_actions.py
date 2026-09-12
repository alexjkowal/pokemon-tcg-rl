"""Tests for GameAction integration with the game engine."""

import pytest

from pokemon_tcg_rl.engine.actions import ActionType, GameAction
from pokemon_tcg_rl.engine.game import Game
from pokemon_tcg_rl.engine.state import (
    Card,
    CardType,
    PlayerState,
    PokemonStage,
)


def make_basic_deck(prefix: str) -> list[Card]:
    """Create a 60-card deck containing only Basic Pokemon."""

    return [
        Card(
            card_id=f"{prefix}-{index}",
            name=f"Test Pokemon {index}",
            card_type=CardType.POKEMON,
            pokemon_stage=PokemonStage.BASIC,
        )
        for index in range(60)
    ]


def make_game() -> Game:
    """Create a game with two valid deterministic test decks."""

    return Game(
        player_one=PlayerState(deck=make_basic_deck("p1")),
        player_two=PlayerState(deck=make_basic_deck("p2")),
        seed=42,
    )


def test_no_legal_actions_before_setup_is_prepared() -> None:
    game = make_game()

    assert game.get_legal_actions(0) == []
    assert game.get_legal_actions(1) == []


def test_opening_actions_choose_active_pokemon() -> None:
    game = make_game()
    game.prepare_setup()

    actions = game.get_legal_actions(0)

    assert len(actions) == 7
    assert all(
        action.action_type == ActionType.CHOOSE_ACTIVE_POKEMON
        for action in actions
    )


def test_after_active_choice_player_can_bench_or_finish() -> None:
    game = make_game()
    game.prepare_setup()

    choose_active = game.get_legal_actions(0)[0]
    game.apply_action(choose_active)

    actions = game.get_legal_actions(0)

    action_types = {action.action_type for action in actions}

    assert ActionType.BENCH_BASIC_POKEMON in action_types
    assert (
        ActionType.FINISH_INITIAL_POKEMON_PLACEMENT
        in action_types
    )


def test_apply_action_rejects_illegal_action() -> None:
    game = make_game()
    game.prepare_setup()

    illegal_action = GameAction(
        action_type=ActionType.END_TURN,
        player_index=0,
    )

    with pytest.raises(ValueError, match="not currently legal"):
        game.apply_action(illegal_action)


def test_finishing_both_players_automatically_completes_setup() -> None:
    game = make_game()
    game.prepare_setup()

    for player_index in (0, 1):
        choose_active = game.get_legal_actions(player_index)[0]
        game.apply_action(choose_active)

        finish_action = next(
            action
            for action in game.get_legal_actions(player_index)
            if action.action_type
            == ActionType.FINISH_INITIAL_POKEMON_PLACEMENT
        )
        game.apply_action(finish_action)

    assert game.prizes_placed
    assert game.started

    assert len(game.player_one.prizes) == 6
    assert len(game.player_two.prizes) == 6


def test_only_current_player_can_act_after_setup() -> None:
    game = make_game()
    game.prepare_setup()

    for player_index in (0, 1):
        game.apply_action(game.get_legal_actions(player_index)[0])

        finish_action = next(
            action
            for action in game.get_legal_actions(player_index)
            if action.action_type
            == ActionType.FINISH_INITIAL_POKEMON_PLACEMENT
        )
        game.apply_action(finish_action)

    player_zero_actions = game.get_legal_actions(0)
    player_one_actions = game.get_legal_actions(1)

    assert GameAction(
        action_type=ActionType.END_TURN,
        player_index=0,
    ) in player_zero_actions

    assert all(
        action.player_index == 0
        for action in player_zero_actions
    )

    assert player_one_actions == []

def test_end_turn_action_changes_current_player() -> None:
    game = make_game()
    game.prepare_setup()

    for player_index in (0, 1):
        game.apply_action(game.get_legal_actions(player_index)[0])

        finish_action = next(
            action
            for action in game.get_legal_actions(player_index)
            if action.action_type
            == ActionType.FINISH_INITIAL_POKEMON_PLACEMENT
        )
        game.apply_action(finish_action)

    end_turn = game.get_legal_actions(0)[0]
    game.apply_action(end_turn)

    assert game.current_player == 1