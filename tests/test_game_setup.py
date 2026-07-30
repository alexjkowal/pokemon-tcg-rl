"""Tests for deterministic game setup."""

from pokemon_tcg_rl.engine.game import Game
from pokemon_tcg_rl.engine.state import Card, CardType, PlayerState


def make_deck(prefix: str) -> list[Card]:
    """Create a simple 60-card test deck."""

    return [
        Card(
            card_id=f"{prefix}-{index}",
            name=f"Test Card {index}",
            card_type=CardType.POKEMON,
        )
        for index in range(60)
    ]


def make_game(seed: int) -> Game:
    return Game(
        player_one=PlayerState(deck=make_deck("p1")),
        player_two=PlayerState(deck=make_deck("p2")),
        seed=seed,
    )


def test_setup_creates_correct_zone_sizes() -> None:
    game = make_game(seed=42)

    game.setup()

    for player in game.players:
        assert len(player.hand) == 7
        assert len(player.prizes) == 6
        assert len(player.deck) == 47


def test_setup_is_deterministic_for_same_seed() -> None:
    game_one = make_game(seed=42)
    game_two = make_game(seed=42)

    game_one.setup()
    game_two.setup()

    game_one_hand = [card.card_id for card in game_one.player_one.hand]
    game_two_hand = [card.card_id for card in game_two.player_one.hand]

    assert game_one_hand == game_two_hand


def test_different_seeds_change_opening_hand() -> None:
    game_one = make_game(seed=42)
    game_two = make_game(seed=84)

    game_one.setup()
    game_two.setup()

    game_one_hand = [card.card_id for card in game_one.player_one.hand]
    game_two_hand = [card.card_id for card in game_two.player_one.hand]

    assert game_one_hand != game_two_hand


def test_end_turn_switches_current_player() -> None:
    game = make_game(seed=42)
    game.setup()

    assert game.current_player == 0

    game.end_turn()

    assert game.current_player == 1

    game.end_turn()

    assert game.current_player == 0