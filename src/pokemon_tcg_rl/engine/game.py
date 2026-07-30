"""Core deterministic game controller."""

from dataclasses import dataclass, field
from random import Random

from pokemon_tcg_rl.engine.state import Card, PlayerState


@dataclass(slots=True)
class Game:
    """A minimal two-player Pokemon TCG game."""

    player_one: PlayerState
    player_two: PlayerState
    seed: int | None = None

    current_player: int = 0
    started: bool = False
    rng: Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.rng = Random(self.seed)

    @property
    def players(self) -> tuple[PlayerState, PlayerState]:
        return self.player_one, self.player_two

    def setup(self) -> None:
        """Shuffle both decks, draw opening hands, and place prizes."""

        if self.started:
            raise RuntimeError("Game has already been started.")

        for player in self.players:
            self._setup_player(player)

        self.started = True

    def _setup_player(self, player: PlayerState) -> None:
        if len(player.deck) < 13:
            raise ValueError(
                "A player needs at least 13 cards for a seven-card hand "
                "and six prize cards."
            )

        self.rng.shuffle(player.deck)

        player.hand.extend(self._take_top_cards(player, count=7))
        player.prizes.extend(self._take_top_cards(player, count=6))

    def draw_card(self, player_index: int) -> Card:
        """Draw one card for the selected player."""

        self._validate_player_index(player_index)
        player = self.players[player_index]

        if not player.deck:
            raise RuntimeError("Cannot draw from an empty deck.")

        card = player.deck.pop()
        player.hand.append(card)
        return card

    def end_turn(self) -> None:
        """Pass control to the other player."""

        if not self.started:
            raise RuntimeError("The game has not started.")

        self.current_player = 1 - self.current_player

    @staticmethod
    def _take_top_cards(player: PlayerState, count: int) -> list[Card]:
        return [player.deck.pop() for _ in range(count)]

    @staticmethod
    def _validate_player_index(player_index: int) -> None:
        if player_index not in (0, 1):
            raise ValueError("Player index must be 0 or 1.")