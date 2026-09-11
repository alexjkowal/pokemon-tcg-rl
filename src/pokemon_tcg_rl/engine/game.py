from dataclasses import dataclass, field
from random import Random

from pokemon_tcg_rl.engine.actions import ActionType, GameAction
from pokemon_tcg_rl.engine.state import (
    Card,
    PlayerState,
    PokemonInPlay,
)

MAX_BENCH_SIZE = 5
OPENING_HAND_SIZE = 7
PRIZE_CARD_COUNT = 6
DECK_SIZE = 60


@dataclass(slots=True)
class Game:
    """A minimal two-player Pokemon TCG game."""

    player_one: PlayerState
    player_two: PlayerState
    seed: int | None = None

    current_player: int = 0
    started: bool = False
    setup_prepared: bool = False
    prizes_placed: bool = False

    initial_placement_complete: list[bool] = field(
        default_factory=lambda: [False, False]
    )
    mulligan_counts: list[int] = field(default_factory=lambda: [0, 0])
    mulligan_bonus_available: list[int] = field(
        default_factory=lambda: [0, 0]
    )
    mulligan_bonus_drawn: list[int] = field(default_factory=lambda: [0, 0])
    mulligan_bonus_resolved: list[bool] = field(
        default_factory=lambda: [False, False]
    )
    mulligan_reveals: list[tuple[int, tuple[str, ...]]] = field(
        default_factory=list
    )

    rng: Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.rng = Random(self.seed)

    @property
    def players(self) -> tuple[PlayerState, PlayerState]:
        """Return both player states in player-index order."""

        return self.player_one, self.player_two

    def get_legal_actions(self, player_index: int) -> list[GameAction]:
        """Return every action currently available to one player."""

        self._validate_player_index(player_index)

        if not self.setup_prepared:
            return []

        player = self.players[player_index]

        # Setup phase
        if not self.started:
            if not self.initial_placement_complete[player_index]:
                if player.active is None:
                    return [
                        GameAction(
                            action_type=ActionType.CHOOSE_ACTIVE_POKEMON,
                            player_index=player_index,
                            card_id=card.card_id,
                        )
                        for card in player.hand
                        if card.is_basic_pokemon
                    ]

                actions = [
                    GameAction(
                        action_type=ActionType.FINISH_INITIAL_POKEMON_PLACEMENT,
                        player_index=player_index,
                    )
                ]

                if len(player.bench) < MAX_BENCH_SIZE:
                    actions.extend(
                        GameAction(
                            action_type=ActionType.BENCH_BASIC_POKEMON,
                            player_index=player_index,
                            card_id=card.card_id,
                        )
                        for card in player.hand
                        if card.is_basic_pokemon
                    )

                return actions

            if (
                self.prizes_placed
                and not self.mulligan_bonus_resolved[player_index]
            ):
                available = self.mulligan_bonus_available[player_index]

                return [
                    GameAction(
                        action_type=ActionType.RESOLVE_MULLIGAN_BONUS,
                        player_index=player_index,
                        count=count,
                    )
                    for count in range(available + 1)
                ]

            return []

        # Normal gameplay
        if player_index != self.current_player:
            return []

        return [
            GameAction(
                action_type=ActionType.END_TURN,
                player_index=player_index,
            )
        ]

    def apply_action(self, action: GameAction) -> None:
        """Validate and execute one player or agent action."""

        legal_actions = self.get_legal_actions(action.player_index)

        if action not in legal_actions:
            raise ValueError("The requested action is not currently legal.")

        if action.action_type == ActionType.CHOOSE_ACTIVE_POKEMON:
            if action.card_id is None:
                raise RuntimeError("Choose Active action is missing a card ID.")

            self.choose_active_pokemon(
                action.player_index,
                action.card_id,
            )
            return

        if action.action_type == ActionType.BENCH_BASIC_POKEMON:
            if action.card_id is None:
                raise RuntimeError("Bench action is missing a card ID.")

            self.bench_basic_pokemon(
                action.player_index,
                action.card_id,
            )
            return

        if (
            action.action_type
            == ActionType.FINISH_INITIAL_POKEMON_PLACEMENT
        ):
            self.finish_initial_pokemon_placement(action.player_index)
            self._advance_setup_if_ready()
            return

        if action.action_type == ActionType.RESOLVE_MULLIGAN_BONUS:
            if action.count is None:
                raise RuntimeError(
                    "Mulligan bonus action is missing a draw count."
                )

            self.resolve_mulligan_bonus(
                action.player_index,
                action.count,
            )
            self._advance_setup_if_ready()
            return

        if action.action_type == ActionType.END_TURN:
            self.end_turn()
            return

        raise ValueError(f"Unsupported action type: {action.action_type}")

    def prepare_setup(self) -> None:
        """Create valid opening hands, resolving mulligans as needed.

        This does not choose initial Pokemon, place Prize cards, or draw
        mulligan bonus cards because those steps involve player decisions.
        """

        if self.started or self.setup_prepared:
            raise RuntimeError("Game setup has already begun.")

        # Validate both decks before changing either player's state.
        for player in self.players:
            self._validate_initial_player_state(player)

        for player in self.players:
            self.rng.shuffle(player.deck)
            player.hand.extend(
                self._take_top_cards(player, count=OPENING_HAND_SIZE)
            )

        while True:
            invalid_players = [
                player_index
                for player_index, player in enumerate(self.players)
                if not self._has_basic_pokemon(player.hand)
            ]

            if not invalid_players:
                break

            for player_index in invalid_players:
                self._take_mulligan(player_index)

        player_one_mulligans = self.mulligan_counts[0]
        player_two_mulligans = self.mulligan_counts[1]

        self.mulligan_bonus_available[0] = max(
            0,
            player_two_mulligans - player_one_mulligans,
        )
        self.mulligan_bonus_available[1] = max(
            0,
            player_one_mulligans - player_two_mulligans,
        )

        self.mulligan_bonus_resolved = [
            available == 0 for available in self.mulligan_bonus_available
        ]
        self.setup_prepared = True

    def choose_active_pokemon(self, player_index: int, card_id: str) -> None:
        """Move one Basic Pokemon from the opening hand to the Active Spot."""

        self._require_setup_prepared()
        self._validate_player_index(player_index)
        player = self.players[player_index]

        if player.active is not None:
            raise RuntimeError("This player already has an Active Pokemon.")

        card = self._find_card_in_hand(player, card_id)
        if not card.is_basic_pokemon:
            raise ValueError("The initial Active Pokemon must be Basic.")

        player.hand.remove(card)
        player.active = PokemonInPlay(
            evolution_stack=[card]
        )

    def bench_basic_pokemon(self, player_index: int, card_id: str) -> None:
        """Move one Basic Pokemon from the hand to the Bench during setup."""

        self._require_setup_prepared()
        self._validate_player_index(player_index)
        player = self.players[player_index]

        if len(player.bench) >= MAX_BENCH_SIZE:
            raise RuntimeError("The Bench is full.")

        card = self._find_card_in_hand(player, card_id)
        if not card.is_basic_pokemon:
            raise ValueError("Only a Basic Pokemon may be placed during setup.")

        player.hand.remove(card)
        player.bench.append(
            PokemonInPlay(
                evolution_stack=[card]
            )
        )

    def finish_initial_pokemon_placement(self, player_index: int) -> None:
        """Mark a player's initial Active and Bench choices as complete."""

        self._require_setup_prepared()
        self._validate_player_index(player_index)
        player = self.players[player_index]

        if player.active is None:
            raise RuntimeError(
                "A player must choose an Active Pokemon before finishing setup."
            )

        self.initial_placement_complete[player_index] = True

    def place_prize_cards(self) -> None:
        """Place six Prize cards after both players finish initial placement."""

        self._require_setup_prepared()

        if self.prizes_placed:
            raise RuntimeError("Prize cards have already been placed.")

        if not all(self.initial_placement_complete):
            raise RuntimeError(
                "Both players must finish initial Pokemon placement first."
            )

        for player in self.players:
            player.prizes.extend(
                self._take_top_cards(player, count=PRIZE_CARD_COUNT)
            )

        self.prizes_placed = True

    def resolve_mulligan_bonus(self, player_index: int, count: int) -> None:
        """Draw zero or more mulligan bonus cards offered to a player."""

        self._require_setup_prepared()
        self._validate_player_index(player_index)

        if not self.prizes_placed:
            raise RuntimeError(
                "Mulligan bonus cards are drawn after Prize cards are placed."
            )

        if self.mulligan_bonus_resolved[player_index]:
            raise RuntimeError(
                "This player's mulligan bonus decision is already resolved."
            )

        available = self.mulligan_bonus_available[player_index]
        if not 0 <= count <= available:
            raise ValueError(
                f"Bonus draw count must be between 0 and {available}."
            )

        player = self.players[player_index]
        player.hand.extend(self._take_top_cards(player, count=count))
        self.mulligan_bonus_drawn[player_index] = count
        self.mulligan_bonus_resolved[player_index] = True

    def complete_setup(self) -> None:
        """Finish setup after all mandatory and optional choices."""

        self._require_setup_prepared()

        if not self.prizes_placed:
            raise RuntimeError("Prize cards must be placed before setup ends.")

        if not all(self.initial_placement_complete):
            raise RuntimeError(
                "Both players must finish initial Pokemon placement."
            )

        if not all(self.mulligan_bonus_resolved):
            raise RuntimeError(
                "Both mulligan bonus decisions must be resolved."
            )

        if any(player.active is None for player in self.players):
            raise RuntimeError("Both players must have an Active Pokemon.")

        self.started = True

    def draw_card(self, player_index: int) -> Card:
        """Draw one card for the selected player after the game begins."""

        if not self.started:
            raise RuntimeError("The game has not started.")

        self._validate_player_index(player_index)
        return self._draw_one(self.players[player_index])

    def end_turn(self) -> None:
        """Pass control to the other player."""

        if not self.started:
            raise RuntimeError("The game has not started.")

        self.current_player = 1 - self.current_player

    def _advance_setup_if_ready(self) -> None:
        """Perform automatic setup steps when their requirements are met."""

        if (
            not self.prizes_placed
            and all(self.initial_placement_complete)
        ):
            self.place_prize_cards()

        if (
            self.prizes_placed
            and all(self.mulligan_bonus_resolved)
            and not self.started
        ):
            self.complete_setup()

    def _take_mulligan(self, player_index: int) -> None:
        """Reveal, reshuffle, and replace an invalid opening hand."""

        player = self.players[player_index]
        revealed_card_ids = tuple(card.card_id for card in player.hand)
        self.mulligan_reveals.append((player_index, revealed_card_ids))
        self.mulligan_counts[player_index] += 1

        player.deck.extend(player.hand)
        player.hand.clear()
        self.rng.shuffle(player.deck)
        player.hand.extend(
            self._take_top_cards(player, count=OPENING_HAND_SIZE)
        )

    @staticmethod
    def _has_basic_pokemon(cards: list[Card]) -> bool:
        return any(card.is_basic_pokemon for card in cards)

    @staticmethod
    def _validate_initial_player_state(player: PlayerState) -> None:
        if (
            player.hand
            or player.prizes
            or player.discard
            or player.active
            or player.bench
        ):
            raise ValueError("Player state must be empty before game setup.")

        if len(player.deck) != DECK_SIZE:
            raise ValueError(
                f"A valid deck must contain exactly {DECK_SIZE} cards."
            )

        if not Game._has_basic_pokemon(player.deck):
            raise ValueError("A deck must contain at least one Basic Pokemon.")

    def _require_setup_prepared(self) -> None:
        if not self.setup_prepared:
            raise RuntimeError("Opening hands have not been prepared.")

        if self.started:
            raise RuntimeError("The game has already started.")

    @staticmethod
    def _find_card_in_hand(player: PlayerState, card_id: str) -> Card:
        for card in player.hand:
            if card.card_id == card_id:
                return card

        raise ValueError(f"Card {card_id!r} is not in the player's hand.")

    @staticmethod
    def _draw_one(player: PlayerState) -> Card:
        if not player.deck:
            raise RuntimeError("Cannot draw from an empty deck.")

        card = player.deck.pop()
        player.hand.append(card)
        return card

    @staticmethod
    def _take_top_cards(player: PlayerState, count: int) -> list[Card]:
        if count < 0:
            raise ValueError("Card count cannot be negative.")

        if len(player.deck) < count:
            raise RuntimeError(
                f"Cannot take {count} cards from a deck containing "
                f"{len(player.deck)} cards."
            )

        return [player.deck.pop() for _ in range(count)]

    @staticmethod
    def _validate_player_index(player_index: int) -> None:
        if player_index not in (0, 1):
            raise ValueError("Player index must be 0 or 1.")