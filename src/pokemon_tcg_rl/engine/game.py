from dataclasses import dataclass, field
from random import Random

from pokemon_tcg_rl.engine.actions import (
    ActionType,
    ChoiceType,
    GameAction,
    PendingChoice,
    PokemonTargetScope,
    PokemonZone,
)
from pokemon_tcg_rl.engine.state import (
    Attack,
    Card,
    CardType,
    EnergyType,
    PlayerState,
    PokemonInPlay,
)

MAX_BENCH_SIZE = 5
OPENING_HAND_SIZE = 7
PRIZE_CARD_COUNT = 6
DECK_SIZE = 60


@dataclass(slots=True)
class Game:
    player_one: PlayerState
    player_two: PlayerState
    seed: int | None = None

    current_player: int = 0
    turn_number: int = 0
    player_turn_counts: list[int] = field(
        default_factory=lambda: [0, 0]
    )

    pending_choice: PendingChoice | None = None
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

                if player.active is not None:
                    for attack_index, attack in enumerate(
                        player.active.current_card.attacks
                    ):
                        if self._can_attack(
                            player_index,
                            attack,
                        ):
                            actions.append(
                                GameAction(
                                    action_type=ActionType.ATTACK,
                                    player_index=player_index,
                                    attack_index=attack_index,
                                )
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

        if self.pending_choice is not None:
            if player_index != self.pending_choice.player_index:
                return []

            return self._get_pending_choice_actions()

        # Normal gameplay
        if player_index != self.current_player:
            return []

        actions = [
            GameAction(
                action_type=ActionType.END_TURN,
                player_index=player_index,
            )
        ]

        # Play Basic Pokemon from the hand to the Bench.
        if len(player.bench) < MAX_BENCH_SIZE:
            actions.extend(
                GameAction(
                    action_type=ActionType.PLAY_BASIC_POKEMON,
                    player_index=player_index,
                    card_id=card.card_id,
                )
                for card in player.hand
                if card.is_basic_pokemon
            )

        # Evolve eligible Pokemon.
        evolution_cards = [
            card
            for card in player.hand
            if (
                card.card_type == CardType.POKEMON
                and not card.is_basic_pokemon
                and card.evolves_from is not None
            )
        ]

        if player.active is not None:
            actions.extend(
                GameAction(
                    action_type=ActionType.EVOLVE_POKEMON,
                    player_index=player_index,
                    card_id=card.card_id,
                    target_zone=PokemonZone.ACTIVE,
                )
                for card in evolution_cards
                if self._can_evolve(
                    player_index,
                    player.active,
                    card,
                )
            )

        for bench_index, pokemon in enumerate(player.bench):
            actions.extend(
                GameAction(
                    action_type=ActionType.EVOLVE_POKEMON,
                    player_index=player_index,
                    card_id=card.card_id,
                    target_zone=PokemonZone.BENCH,
                    target_index=bench_index,
                )
                for card in evolution_cards
                if self._can_evolve(
                    player_index,
                    pokemon,
                    card,
                )
            )

        # Attach one Energy from the hand per turn.
        if not player.energy_attached_this_turn:
            energy_cards = [
                card
                for card in player.hand
                if card.card_type == CardType.ENERGY
            ]

            if player.active is not None:
                actions.extend(
                    GameAction(
                        action_type=ActionType.ATTACH_ENERGY,
                        player_index=player_index,
                        card_id=card.card_id,
                        target_zone=PokemonZone.ACTIVE,
                    )
                    for card in energy_cards
                )

            for bench_index, _ in enumerate(player.bench):
                actions.extend(
                    GameAction(
                        action_type=ActionType.ATTACH_ENERGY,
                        player_index=player_index,
                        card_id=card.card_id,
                        target_zone=PokemonZone.BENCH,
                        target_index=bench_index,
                    )
                    for card in energy_cards
                )

        return actions

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

        if action.action_type == ActionType.PLAY_BASIC_POKEMON:
            if action.card_id is None:
                raise RuntimeError(
                    "Play Basic action is missing a card ID."
                )

            self.play_basic_pokemon(
                action.player_index,
                action.card_id,
            )
            return

        if action.action_type == ActionType.EVOLVE_POKEMON:
            if action.card_id is None:
                raise RuntimeError(
                    "Evolution action is missing a card ID."
                )

            if action.target_zone is None:
                raise RuntimeError(
                    "Evolution action is missing a target."
                )

            self.evolve_pokemon(
                player_index=action.player_index,
                card_id=action.card_id,
                target_zone=action.target_zone,
                target_index=action.target_index,
            )
            return

        if action.action_type == ActionType.ATTACH_ENERGY:
            if action.card_id is None:
                raise RuntimeError(
                    "Attach Energy action is missing a card ID."
                )

            if action.target_zone is None:
                raise RuntimeError(
                    "Attach Energy action is missing a target."
                )

            self.attach_energy(
                player_index=action.player_index,
                card_id=action.card_id,
                target_zone=action.target_zone,
                target_index=action.target_index,
            )
            return

        if action.action_type == ActionType.END_TURN:
            self.end_turn()
            return

        if action.action_type == ActionType.ATTACK:
            if action.attack_index is None:
                raise RuntimeError(
                    "Attack action is missing an attack index."
                )

            self.attack(
                player_index=action.player_index,
                attack_index=action.attack_index,
            )
            return

        if action.action_type == ActionType.CHOOSE_POKEMON_TARGET:
            self.choose_pokemon_target(action)
            return

        if action.action_type == ActionType.ALLOCATE_DAMAGE:
            self.allocate_damage(action)
            return

        raise ValueError(f"Unsupported action type: {action.action_type}")

    def allocate_damage(
    self,
    action: GameAction,
    ) -> None:
        """Allocate some remaining damage counters to one Pokemon."""

        choice = self.pending_choice

        if (
            choice is None
            or choice.choice_type
            != ChoiceType.DAMAGE_ALLOCATION
        ):
            raise RuntimeError(
                "No damage allocation is currently pending."
            )

        if action not in self._get_pending_choice_actions():
            raise ValueError(
                "That damage allocation is not legal."
            )

        if (
            action.target_player_index is None
            or action.target_zone is None
            or action.amount is None
        ):
            raise RuntimeError(
                "Damage allocation action is incomplete."
            )

        if choice.remaining_amount is None:
            raise RuntimeError(
                "Damage allocation has no remaining amount."
            )

        target = self._get_targeted_pokemon(
            action.target_player_index,
            action.target_zone,
            action.target_index,
        )

        # One Pokemon TCG damage counter represents 10 damage.
        target.damage += action.amount * 10

        choice.remaining_amount -= action.amount

        if choice.remaining_amount > 0:
            return

        if (
            choice.source_attack_index is None
            or choice.source_choice_index is None
        ):
            raise RuntimeError(
                "Pending attack choice is missing source information."
            )

        player_index = choice.player_index
        attack_index = choice.source_attack_index
        next_choice_index = choice.source_choice_index + 1

        self.pending_choice = None

        self._continue_attack_resolution(
            player_index,
            attack_index,
            next_choice_index,
        )

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

    def choose_pokemon_target(
    self,
    action: GameAction,
    ) -> None:
        """Resolve a pending Pokemon-target decision."""

        choice = self.pending_choice

        if (
            choice is None
            or choice.choice_type != ChoiceType.POKEMON_TARGET
        ):
            raise RuntimeError(
                "No Pokemon target choice is currently pending."
            )

        if action not in self._get_pending_choice_actions():
            raise ValueError(
                "That Pokemon is not a legal target."
            )

        if (
            action.target_player_index is None
            or action.target_zone is None
        ):
            raise RuntimeError(
                "Pokemon target action is incomplete."
            )

        if (
            choice.source_attack_index is None
            or choice.source_choice_index is None
        ):
            raise RuntimeError(
                "Pending attack choice is missing source information."
            )

        attacker = self.players[choice.player_index]

        if attacker.active is None:
            raise RuntimeError(
                "Attacking player has no Active Pokemon."
            )

        attack = attacker.active.current_card.attacks[
            choice.source_attack_index
        ]

        attack_choice = attack.choices[
            choice.source_choice_index
        ]

        target = self._get_targeted_pokemon(
            action.target_player_index,
            action.target_zone,
            action.target_index,
        )

        if attack_choice.damage is not None:
            target.damage += attack_choice.damage

        next_choice_index = choice.source_choice_index + 1

        self.pending_choice = None

        self._continue_attack_resolution(
            choice.player_index,
            choice.source_attack_index,
            next_choice_index,
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

    def play_basic_pokemon(
        self,
        player_index: int,
        card_id: str,
    ) -> None:
        """Play one Basic Pokemon from the hand to the Bench."""

        self._require_current_turn(player_index)
        player = self.players[player_index]

        if len(player.bench) >= MAX_BENCH_SIZE:
            raise RuntimeError("The Bench is full.")

        card = self._find_card_in_hand(player, card_id)

        if not card.is_basic_pokemon:
            raise ValueError(
                "Only a Basic Pokemon may be played to the Bench."
            )

        player.hand.remove(card)
        player.bench.append(
            PokemonInPlay(
                evolution_stack=[card],
                entered_play_turn=self.turn_number,
            )
        )

    def evolve_pokemon(
    self,
    player_index: int,
    card_id: str,
    target_zone: PokemonZone,
    target_index: int | None = None,
    ) -> None:
        """Evolve one Pokemon using a card from the player's hand."""

        self._require_current_turn(player_index)
        player = self.players[player_index]

        card = self._find_card_in_hand(
            player,
            card_id,
        )

        if (
            card.card_type != CardType.POKEMON
            or card.is_basic_pokemon
        ):
            raise ValueError(
                "Only an Evolution Pokemon may evolve a Pokemon."
            )

        if card.evolves_from is None:
            raise ValueError(
                "Evolution card must specify what Pokemon it evolves from."
            )

        target = self._get_pokemon_target(
            player,
            target_zone,
            target_index,
        )

        if card.evolves_from != target.current_card.name:
            raise ValueError(
                f"{card.name} evolves from "
                f"{card.evolves_from}, not "
                f"{target.current_card.name}."
            )

        if not self._can_evolve(
            player_index,
            target,
            card,
        ):
            raise RuntimeError(
                "This Pokemon cannot evolve this turn."
            )

        player.hand.remove(card)
        target.evolution_stack.append(card)
        target.last_evolved_turn = self.turn_number


    def attack(
    self,
    player_index: int,
    attack_index: int,
    ) -> None:
        """Begin resolving one attack from the Active Pokemon."""

        self._require_current_turn(player_index)

        player = self.players[player_index]

        if player.active is None:
            raise RuntimeError(
                "A player must have an Active Pokemon to attack."
            )

        attacks = player.active.current_card.attacks

        if attack_index < 0 or attack_index >= len(attacks):
            raise ValueError(
                "Attack index is out of range."
            )

        selected_attack = attacks[attack_index]

        if not self._can_attack(
            player_index,
            selected_attack,
        ):
            raise RuntimeError(
                "This attack cannot currently be used."
            )

        opponent = self.players[1 - player_index]

        if (
            selected_attack.base_damage > 0
            and opponent.active is not None
        ):
            opponent.active.damage += selected_attack.base_damage

        self._continue_attack_resolution(
            player_index,
            attack_index,
            0,
        )


    def attach_energy(
        self,
        player_index: int,
        card_id: str,
        target_zone: PokemonZone,
        target_index: int | None = None,
    ) -> None:
        """Attach one Energy card from the hand during the current turn."""

        self._require_current_turn(player_index)
        player = self.players[player_index]

        if player.energy_attached_this_turn:
            raise RuntimeError(
                "This player has already attached an Energy this turn."
            )

        card = self._find_card_in_hand(player, card_id)

        if card.card_type != CardType.ENERGY:
            raise ValueError(
                "Only an Energy card may be attached as the turn attachment."
            )

        target = self._get_pokemon_target(
            player,
            target_zone,
            target_index,
        )

        player.hand.remove(card)
        target.attached_energy.append(card)
        player.energy_attached_this_turn = True

    def end_turn(self) -> None:
        """Finish the current turn and begin the opponent's turn."""

        if not self.started:
            raise RuntimeError("The game has not started.")

        player = self.players[self.current_player]
        player.energy_attached_this_turn = False

        self.current_player = 1 - self.current_player
        self._begin_turn()

    def _begin_turn(self) -> None:
        """Begin the current player's turn."""

        self.turn_number += 1
        self.player_turn_counts[self.current_player] += 1

        player = self.players[self.current_player]
        player.energy_attached_this_turn = False

        self._draw_one(player)

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

    @staticmethod
    def _get_pokemon_target(
        player: PlayerState,
        target_zone: PokemonZone,
        target_index: int | None,
    ) -> PokemonInPlay:
        """Return a Pokemon from a player's Active Spot or Bench."""

        if target_zone == PokemonZone.ACTIVE:
            if target_index is not None:
                raise ValueError(
                    "Active Pokemon targets cannot include an index."
                )

            if player.active is None:
                raise RuntimeError(
                    "This player does not have an Active Pokemon."
                )

            return player.active

        if target_zone == PokemonZone.BENCH:
            if target_index is None:
                raise ValueError(
                    "Bench Pokemon targets require an index."
                )

            if not 0 <= target_index < len(player.bench):
                raise ValueError(
                    "Bench target index is out of range."
                )

            return player.bench[target_index]

        raise ValueError(
            f"Unsupported Pokemon target zone: {target_zone}"
        )

    def _require_current_turn(self, player_index: int) -> None:
        """Require an action to come from the current player."""

        if not self.started:
            raise RuntimeError("The game has not started.")

        self._validate_player_index(player_index)

        if player_index != self.current_player:
            raise RuntimeError("It is not this player's turn.")

    def _can_evolve(
        self,
        player_index: int,
        pokemon: PokemonInPlay,
        evolution_card: Card,
    ) -> bool:
        """Return whether a Pokemon can legally evolve with this card."""

        if evolution_card.card_type != CardType.POKEMON:
            return False

        if evolution_card.is_basic_pokemon:
            return False

        if evolution_card.evolves_from is None:
            return False

        # A player cannot evolve during their first turn.
        if self.player_turn_counts[player_index] <= 1:
            return False

        # A Pokemon cannot evolve on the turn it entered play.
        if pokemon.entered_play_turn == self.turn_number:
            return False

        # A Pokemon cannot evolve twice during the same turn.
        if pokemon.last_evolved_turn == self.turn_number:
            return False

        # Exact full-name comparison is intentional.
        return (
            evolution_card.evolves_from
            == pokemon.current_card.name
        )

    @staticmethod
    def _can_pay_attack_cost(
        pokemon: PokemonInPlay,
        attack: Attack,
    ) -> bool:
        """Return whether attached Energy satisfies an attack cost."""

        attached_energy = pokemon.attached_energy

        if len(attached_energy) < len(attack.energy_cost):
            return False

        required_specific_types = [
            energy_type
            for energy_type in attack.energy_cost
            if energy_type != EnergyType.COLORLESS
        ]

        for required_type in set(required_specific_types):
            required_count = required_specific_types.count(
                required_type
            )

            attached_count = sum(
                1
                for card in attached_energy
                if card.energy_type == required_type
            )

            if attached_count < required_count:
                return False

        return True

    def _can_attack(
    self,
    player_index: int,
    attack: Attack,
    ) -> bool:
        """Return whether a player can currently use an attack."""

        if player_index != self.current_player:
            return False

        if self.pending_choice is not None:
            return False

        # The starting player cannot attack on turn 1.
        if self.turn_number == 1:
            return False

        player = self.players[player_index]

        if player.active is None:
            return False

        return self._can_pay_attack_cost(
            player.active,
            attack,
        )

    def _get_pokemon_targets(
    self,
    player_index: int,
    target_scope: PokemonTargetScope,
    ) -> list[tuple[int, PokemonZone, int | None]]:
        """Return every concrete Pokemon allowed by a target scope."""

        opponent_index = 1 - player_index

        if target_scope in {
            PokemonTargetScope.OWN_ACTIVE,
            PokemonTargetScope.OWN_BENCH,
            PokemonTargetScope.OWN_ANY,
        }:
            target_player_index = player_index
        else:
            target_player_index = opponent_index

        target_player = self.players[target_player_index]

        targets: list[
            tuple[int, PokemonZone, int | None]
        ] = []

        if (
            target_scope
            in {
                PokemonTargetScope.OWN_ACTIVE,
                PokemonTargetScope.OPPONENT_ACTIVE,
                PokemonTargetScope.OWN_ANY,
                PokemonTargetScope.OPPONENT_ANY,
            }
            and target_player.active is not None
        ):
            targets.append(
                (
                    target_player_index,
                    PokemonZone.ACTIVE,
                    None,
                )
            )

        if target_scope in {
            PokemonTargetScope.OWN_BENCH,
            PokemonTargetScope.OPPONENT_BENCH,
            PokemonTargetScope.OWN_ANY,
            PokemonTargetScope.OPPONENT_ANY,
        }:
            targets.extend(
                (
                    target_player_index,
                    PokemonZone.BENCH,
                    bench_index,
                )
                for bench_index, _ in enumerate(
                    target_player.bench
                )
            )

        return targets

    def _get_pending_choice_actions(
    self,
    ) -> list[GameAction]:
        """Return the legal actions for the current pending choice."""

        choice = self.pending_choice

        if choice is None:
            return []

        targets = self._get_pokemon_targets(
            choice.player_index,
            choice.target_scope,
        )

        if choice.choice_type == ChoiceType.POKEMON_TARGET:
            return [
                GameAction(
                    action_type=ActionType.CHOOSE_POKEMON_TARGET,
                    player_index=choice.player_index,
                    target_player_index=target_player_index,
                    target_zone=target_zone,
                    target_index=target_index,
                )
                for (
                    target_player_index,
                    target_zone,
                    target_index,
                ) in targets
            ]

        if choice.choice_type == ChoiceType.DAMAGE_ALLOCATION:
            if (
                choice.remaining_amount is None
                or choice.remaining_amount <= 0
            ):
                raise RuntimeError(
                    "Damage allocation requires a positive "
                    "remaining amount."
                )

            return [
                GameAction(
                    action_type=ActionType.ALLOCATE_DAMAGE,
                    player_index=choice.player_index,
                    target_player_index=target_player_index,
                    target_zone=target_zone,
                    target_index=target_index,
                    amount=amount,
                )
                for (
                    target_player_index,
                    target_zone,
                    target_index,
                ) in targets
                for amount in range(
                    1,
                    choice.remaining_amount + 1,
                )
            ]

        raise RuntimeError(
            f"Unsupported pending choice type: "
            f"{choice.choice_type}"
        )

    def _continue_attack_resolution(
    self,
    player_index: int,
    attack_index: int,
    choice_index: int,
    ) -> None:
        """Continue resolving an attack after its direct damage."""

        player = self.players[player_index]

        if player.active is None:
            raise RuntimeError(
                "Attacking player has no Active Pokemon."
            )

        attacks = player.active.current_card.attacks

        if attack_index >= len(attacks):
            raise RuntimeError(
                "Attack index is out of range."
            )

        attack = attacks[attack_index]

        if choice_index >= len(attack.choices):
            self.pending_choice = None
            self.end_turn()
            return

        attack_choice = attack.choices[choice_index]

        remaining_amount = None

        if (
            attack_choice.choice_type
            == ChoiceType.DAMAGE_ALLOCATION
        ):
            remaining_amount = attack_choice.amount

        self.pending_choice = PendingChoice(
            choice_type=attack_choice.choice_type,
            player_index=player_index,
            target_scope=attack_choice.target_scope,
            source_attack_index=attack_index,
            source_choice_index=choice_index,
            remaining_amount=remaining_amount,
        )

    def _get_targeted_pokemon(
    self,
    target_player_index: int,
    target_zone: PokemonZone,
    target_index: int | None,
    ) -> PokemonInPlay:
        """Return one concrete Pokemon selected by an effect."""

        player = self.players[target_player_index]

        if target_zone == PokemonZone.ACTIVE:
            if player.active is None:
                raise RuntimeError(
                    "Target player has no Active Pokemon."
                )

            return player.active

        if target_index is None:
            raise RuntimeError(
                "Bench targets require an index."
            )

        if target_index >= len(player.bench):
            raise RuntimeError(
                "Bench target index is out of range."
            )

        return player.bench[target_index]