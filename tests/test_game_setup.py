from collections.abc import Sequence

import pytest

from pokemon_tcg_rl.engine.game import Game
from pokemon_tcg_rl.engine.state import (
    Card,
    CardType,
    PlayerState,
    PokemonStage,
    TrainerCardType,
)


def make_deck(prefix: str) -> list[Card]:
    """Create a simple 60-card all-Basic test deck."""

    return [
        Card(
            card_id=f"{prefix}-{index}",
            name=f"Test Pokemon {index}",
            card_type=CardType.POKEMON,
            pokemon_stage=PokemonStage.BASIC,
        )
        for index in range(60)
    ]


def make_trainer_deck(prefix: str) -> list[Card]:
    return [
        Card(
            card_id=f"{prefix}-{index}",
            name=f"Test Trainer {index}",
            card_type=CardType.TRAINER,
            trainer_card_type=TrainerCardType.ITEM,
        )
        for index in range(60)
    ]


def make_mixed_deck(
    prefix: str,
    basic_indices: set[int],
    ) -> list[Card]:
        """Create a 60-card deck with Basics at selected indices."""

        cards: list[Card] = []

        for index in range(60):
            if index in basic_indices:
                card = Card(
                    card_id=f"{prefix}-{index}",
                    name=f"Test Pokemon {index}",
                    card_type=CardType.POKEMON,
                    pokemon_stage=PokemonStage.BASIC,
                )
            else:
                card = Card(
                    card_id=f"{prefix}-{index}",
                    name=f"Test Trainer {index}",
                    card_type=CardType.TRAINER,
                    trainer_card_type=TrainerCardType.ITEM,
                )

            cards.append(card)

        return cards


class ScriptedShuffler:
    """Place specified card IDs on top for each shuffle call."""

    def __init__(self, top_groups: Sequence[Sequence[str]]) -> None:
        self.top_groups = [list(group) for group in top_groups]

    def shuffle(self, cards: list[Card]) -> None:
        if not self.top_groups:
            raise AssertionError("Unexpected shuffle call.")

        top_ids = self.top_groups.pop(0)
        by_id = {card.card_id: card for card in cards}
        top_id_set = set(top_ids)
        remaining = [card for card in cards if card.card_id not in top_id_set]

        # The engine draws with list.pop(), so the final entries are on top.
        cards[:] = remaining + list(
            reversed([by_id[card_id] for card_id in top_ids])
        )


def test_make_mixed_deck_contains_selected_basic() -> None:
    deck = make_mixed_deck("test", basic_indices={59})

    assert len(deck) == 60
    assert deck[59].is_basic_pokemon
    assert sum(card.is_basic_pokemon for card in deck) == 1


def make_game(seed: int = 42) -> Game:
    return Game(
        player_one=PlayerState(deck=make_deck("p1")),
        player_two=PlayerState(deck=make_deck("p2")),
        seed=seed,
    )


def choose_first_basic_as_active(game: Game, player_index: int) -> None:
    player = game.players[player_index]
    basic = next(card for card in player.hand if card.is_basic_pokemon)
    game.choose_active_pokemon(player_index, basic.card_id)
    game.finish_initial_pokemon_placement(player_index)


def complete_standard_setup(game: Game) -> None:
    game.prepare_setup()
    choose_first_basic_as_active(game, 0)
    choose_first_basic_as_active(game, 1)
    game.place_prize_cards()

    for player_index in (0, 1):
        if not game.mulligan_bonus_resolved[player_index]:
            game.resolve_mulligan_bonus(player_index, count=0)

    game.complete_setup()


def test_prepare_setup_creates_hands_before_prizes() -> None:
    game = make_game()
    game.prepare_setup()

    for player in game.players:
        assert len(player.hand) == 7
        assert len(player.prizes) == 0
        assert len(player.deck) == 53

    assert game.started is False


def test_prizes_are_placed_after_initial_pokemon() -> None:
    game = make_game()
    game.prepare_setup()
    choose_first_basic_as_active(game, 0)
    choose_first_basic_as_active(game, 1)
    game.place_prize_cards()

    for player in game.players:
        assert player.active is not None
        assert len(player.hand) == 6
        assert len(player.prizes) == 6
        assert len(player.deck) == 47


def test_prepare_setup_is_deterministic_for_same_seed() -> None:
    game_one = make_game(seed=42)
    game_two = make_game(seed=42)
    game_one.prepare_setup()
    game_two.prepare_setup()

    assert [c.card_id for c in game_one.player_one.hand] == [
        c.card_id for c in game_two.player_one.hand
    ]


def test_different_seeds_change_opening_hand() -> None:
    game_one = make_game(seed=42)
    game_two = make_game(seed=84)
    game_one.prepare_setup()
    game_two.prepare_setup()

    assert [c.card_id for c in game_one.player_one.hand] != [
        c.card_id for c in game_two.player_one.hand
    ]


def test_prepare_setup_cannot_run_twice() -> None:
    game = make_game()
    game.prepare_setup()

    with pytest.raises(RuntimeError, match="already begun"):
        game.prepare_setup()


def test_cannot_draw_before_setup_is_complete() -> None:
    game = make_game()
    game.prepare_setup()

    with pytest.raises(RuntimeError, match="has not started"):
        game.draw_card(player_index=0)


def test_draw_card_moves_card_from_deck_to_hand() -> None:
    game = make_game()
    complete_standard_setup(game)

    player = game.player_one
    original_deck_size = len(player.deck)
    original_hand_size = len(player.hand)
    expected_card = player.deck[-1]
    drawn_card = game.draw_card(player_index=0)

    assert drawn_card == expected_card
    assert len(player.deck) == original_deck_size - 1
    assert len(player.hand) == original_hand_size + 1


def test_end_turn_switches_current_player() -> None:
    game = make_game()
    complete_standard_setup(game)

    game.end_turn()
    assert game.current_player == 1
    game.end_turn()
    assert game.current_player == 0


def test_setup_rejects_deck_with_wrong_card_count() -> None:
    game = Game(
        player_one=PlayerState(deck=make_deck("short")[:59]),
        player_two=PlayerState(deck=make_deck("p2")),
    )

    with pytest.raises(ValueError, match="exactly 60 cards"):
        game.prepare_setup()


def test_setup_rejects_deck_without_basic_pokemon() -> None:
    game = Game(
        player_one=PlayerState(deck=make_trainer_deck("p1")),
        player_two=PlayerState(deck=make_deck("p2")),
    )

    with pytest.raises(ValueError, match="at least one Basic Pokemon"):
        game.prepare_setup()


def test_one_sided_mulligan_creates_net_bonus() -> None:
    game = Game(
        player_one=PlayerState(
            deck=make_mixed_deck("p1", basic_indices={59})
        ),
        player_two=PlayerState(
            deck=make_mixed_deck("p2", basic_indices={59})
        ),
    )
    game.rng = ScriptedShuffler(
        [
            [f"p1-{index}" for index in range(7)],
            ["p2-59", "p2-0", "p2-1", "p2-2", "p2-3", "p2-4", "p2-5"],
            ["p1-59", "p1-7", "p1-8", "p1-9", "p1-10", "p1-11", "p1-12"],
        ]
    )

    game.prepare_setup()

    assert game.mulligan_counts == [1, 0]
    assert game.mulligan_bonus_available == [0, 1]
    assert len(game.mulligan_reveals) == 1


def test_matching_mulligans_cancel_bonus_cards() -> None:
    game = Game(
        player_one=PlayerState(
            deck=make_mixed_deck("p1", basic_indices={59})
        ),
        player_two=PlayerState(
            deck=make_mixed_deck("p2", basic_indices={59})
        ),
    )
    game.rng = ScriptedShuffler(
        [
            [f"p1-{index}" for index in range(7)],
            [f"p2-{index}" for index in range(7)],
            ["p1-59", "p1-7", "p1-8", "p1-9", "p1-10", "p1-11", "p1-12"],
            ["p2-59", "p2-7", "p2-8", "p2-9", "p2-10", "p2-11", "p2-12"],
        ]
    )

    game.prepare_setup()

    assert game.mulligan_counts == [1, 1]
    assert game.mulligan_bonus_available == [0, 0]
    assert game.mulligan_bonus_resolved == [True, True]


def test_setup_preserves_total_card_count() -> None:
    game = make_game()
    complete_standard_setup(game)

    for player in game.players:
        total_cards = (
            len(player.deck)
            + len(player.hand)
            + len(player.prizes)
            + len(player.discard)
            + len(player.bench)
            + (1 if player.active is not None else 0)
        )
        assert total_cards == 60