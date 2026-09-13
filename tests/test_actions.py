"""Tests for agent-facing game actions."""

import pytest

from pokemon_tcg_rl.engine.actions import (
    ActionType,
    ChoiceType,
    GameAction,
    PendingChoice,
    PokemonTargetScope,
    PokemonZone,
)


def test_choose_active_action_is_valid() -> None:
    action = GameAction(
        action_type=ActionType.CHOOSE_ACTIVE_POKEMON,
        player_index=0,
        card_id="pokemon-001",
    )

    assert action.player_index == 0
    assert action.card_id == "pokemon-001"
    assert action.count is None


def test_mulligan_bonus_action_allows_zero_cards() -> None:
    action = GameAction(
        action_type=ActionType.RESOLVE_MULLIGAN_BONUS,
        player_index=1,
        count=0,
    )

    assert action.count == 0


def test_card_action_requires_card_id() -> None:
    with pytest.raises(ValueError, match="requires a card ID"):
        GameAction(
            action_type=ActionType.BENCH_BASIC_POKEMON,
            player_index=0,
        )


def test_card_action_rejects_count() -> None:
    with pytest.raises(ValueError, match="cannot include a count"):
        GameAction(
            action_type=ActionType.CHOOSE_ACTIVE_POKEMON,
            player_index=0,
            card_id="pokemon-001",
            count=1,
        )


def test_mulligan_bonus_requires_count() -> None:
    with pytest.raises(ValueError, match="require a draw count"):
        GameAction(
            action_type=ActionType.RESOLVE_MULLIGAN_BONUS,
            player_index=0,
        )


def test_mulligan_bonus_rejects_negative_count() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        GameAction(
            action_type=ActionType.RESOLVE_MULLIGAN_BONUS,
            player_index=0,
            count=-1,
        )


def test_end_turn_rejects_extra_data() -> None:
    with pytest.raises(ValueError, match="does not accept"):
        GameAction(
            action_type=ActionType.END_TURN,
            player_index=0,
            card_id="pokemon-001",
        )


def test_action_rejects_invalid_player_index() -> None:
    with pytest.raises(ValueError, match="must be 0 or 1"):
        GameAction(
            action_type=ActionType.END_TURN,
            player_index=2,
        )

def test_attach_energy_to_active_is_valid() -> None:
    action = GameAction(
        action_type=ActionType.ATTACH_ENERGY,
        player_index=0,
        card_id="energy-001",
        target_zone=PokemonZone.ACTIVE,
    )

    assert action.card_id == "energy-001"
    assert action.target_zone == PokemonZone.ACTIVE
    assert action.target_index is None


def test_attach_energy_to_bench_requires_index() -> None:
    with pytest.raises(
        ValueError,
        match="require an index",
    ):
        GameAction(
            action_type=ActionType.ATTACH_ENERGY,
            player_index=0,
            card_id="energy-001",
            target_zone=PokemonZone.BENCH,
        )


def test_active_target_rejects_index() -> None:
    with pytest.raises(
        ValueError,
        match="cannot include an index",
    ):
        GameAction(
            action_type=ActionType.ATTACH_ENERGY,
            player_index=0,
            card_id="energy-001",
            target_zone=PokemonZone.ACTIVE,
            target_index=0,
        )

def test_evolution_action_can_target_active() -> None:
    action = GameAction(
        action_type=ActionType.EVOLVE_POKEMON,
        player_index=0,
        card_id="metang-001",
        target_zone=PokemonZone.ACTIVE,
    )

    assert action.card_id == "metang-001"
    assert action.target_zone == PokemonZone.ACTIVE
    assert action.target_index is None

def test_evolution_to_bench_requires_index() -> None:
    with pytest.raises(
        ValueError,
        match="require an index",
    ):
        GameAction(
            action_type=ActionType.EVOLVE_POKEMON,
            player_index=0,
            card_id="metang-001",
            target_zone=PokemonZone.BENCH,
        )

def test_pending_pokemon_target_choice_is_valid() -> None:
    choice = PendingChoice(
        choice_type=ChoiceType.POKEMON_TARGET,
        player_index=0,
        target_scope=PokemonTargetScope.OPPONENT_BENCH,
        source_attack_index=1,
    )

    assert choice.player_index == 0
    assert choice.source_attack_index == 1
    assert choice.remaining_amount is None

def test_pending_damage_allocation_tracks_remaining_amount() -> None:
    choice = PendingChoice(
        choice_type=ChoiceType.DAMAGE_ALLOCATION,
        player_index=0,
        target_scope=PokemonTargetScope.OPPONENT_ANY,
        source_attack_index=0,
        remaining_amount=6,
    )

    assert choice.remaining_amount == 6