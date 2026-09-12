"""Tests for normal-turn Pokemon TCG actions."""

from pokemon_tcg_rl.engine.actions import (
    ActionType,
    GameAction,
    PokemonZone,
)
from pokemon_tcg_rl.engine.game import Game
from pokemon_tcg_rl.engine.state import (
    Card,
    CardType,
    EnergyType,
    PlayerState,
    PokemonInPlay,
    PokemonStage,
)


def make_basic(card_id: str) -> Card:
    return Card(
        card_id=card_id,
        name=card_id,
        card_type=CardType.POKEMON,
        pokemon_stage=PokemonStage.BASIC,
        hp=60,
    )


def make_energy(card_id: str) -> Card:
    return Card(
        card_id=card_id,
        name=card_id,
        card_type=CardType.ENERGY,
        energy_type=EnergyType.FIRE,
    )


def make_started_game() -> Game:
    player_one = PlayerState(
        deck=[],
        hand=[
            make_basic("bench-basic"),
            make_energy("fire-energy"),
        ],
        active=PokemonInPlay(
            evolution_stack=[make_basic("p1-active")]
        ),
    )

    player_two = PlayerState(
        deck=[],
        active=PokemonInPlay(
            evolution_stack=[make_basic("p2-active")]
        ),
    )

    return Game(
        player_one=player_one,
        player_two=player_two,
        current_player=0,
        started=True,
        setup_prepared=True,
        prizes_placed=True,
    )


def test_current_player_can_play_basic_pokemon() -> None:
    game = make_started_game()

    actions = game.get_legal_actions(0)

    assert GameAction(
        action_type=ActionType.PLAY_BASIC_POKEMON,
        player_index=0,
        card_id="bench-basic",
    ) in actions


def test_play_basic_moves_pokemon_to_bench() -> None:
    game = make_started_game()

    action = GameAction(
        action_type=ActionType.PLAY_BASIC_POKEMON,
        player_index=0,
        card_id="bench-basic",
    )

    game.apply_action(action)

    assert len(game.player_one.bench) == 1
    assert (
        game.player_one.bench[0].current_card.card_id
        == "bench-basic"
    )
    assert all(
        card.card_id != "bench-basic"
        for card in game.player_one.hand
    )


def test_energy_can_target_active_pokemon() -> None:
    game = make_started_game()

    action = GameAction(
        action_type=ActionType.ATTACH_ENERGY,
        player_index=0,
        card_id="fire-energy",
        target_zone=PokemonZone.ACTIVE,
    )

    assert action in game.get_legal_actions(0)

    game.apply_action(action)

    assert game.player_one.active is not None
    assert len(game.player_one.active.attached_energy) == 1
    assert (
        game.player_one.active.attached_energy[0].card_id
        == "fire-energy"
    )
    assert game.player_one.energy_attached_this_turn


def test_only_one_energy_attachment_is_allowed_per_turn() -> None:
    game = make_started_game()

    game.player_one.hand.append(
        make_energy("second-energy")
    )

    first_action = GameAction(
        action_type=ActionType.ATTACH_ENERGY,
        player_index=0,
        card_id="fire-energy",
        target_zone=PokemonZone.ACTIVE,
    )

    game.apply_action(first_action)

    remaining_actions = game.get_legal_actions(0)

    assert not any(
        action.action_type == ActionType.ATTACH_ENERGY
        for action in remaining_actions
    )


def test_end_turn_resets_energy_attachment() -> None:
    game = make_started_game()

    game.apply_action(
        GameAction(
            action_type=ActionType.ATTACH_ENERGY,
            player_index=0,
            card_id="fire-energy",
            target_zone=PokemonZone.ACTIVE,
        )
    )

    assert game.player_one.energy_attached_this_turn

    game.end_turn()

    assert not game.player_one.energy_attached_this_turn
    assert game.current_player == 1