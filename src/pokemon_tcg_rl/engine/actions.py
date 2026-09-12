"""Agent-facing action definitions for the Pokemon TCG engine."""

from dataclasses import dataclass
from enum import StrEnum


class ActionType(StrEnum):
    """Types of decisions a player or agent can make."""

    CHOOSE_ACTIVE_POKEMON = "choose_active_pokemon"
    BENCH_BASIC_POKEMON = "bench_basic_pokemon"
    FINISH_INITIAL_POKEMON_PLACEMENT = (
        "finish_initial_pokemon_placement"
    )
    RESOLVE_MULLIGAN_BONUS = "resolve_mulligan_bonus"
    PLAY_BASIC_POKEMON = "play_basic_pokemon"
    EVOLVE_POKEMON = "evolve_pokemon"
    ATTACH_ENERGY = "attach_energy"

    END_TURN = "end_turn"


class PokemonZone(StrEnum):
    """Locations containing Pokemon that can be targeted."""

    ACTIVE = "active"
    BENCH = "bench"

@dataclass(frozen=True, slots=True)
class GameAction:
    """One concrete decision selected by a player or agent."""

    action_type: ActionType
    player_index: int
    card_id: str | None = None
    count: int | None = None
    target_zone: PokemonZone | None = None
    target_index: int | None = None

    def __post_init__(self) -> None:
        if self.player_index not in (0, 1):
            raise ValueError("Player index must be 0 or 1.")

        card_only_actions = {
            ActionType.CHOOSE_ACTIVE_POKEMON,
            ActionType.BENCH_BASIC_POKEMON,
            ActionType.PLAY_BASIC_POKEMON,
        }

        if self.action_type in card_only_actions:
            if not self.card_id:
                raise ValueError(
                    f"{self.action_type} requires a card ID."
                )

            if self.count is not None:
                raise ValueError(
                    f"{self.action_type} cannot include a count."
                )

            if (
                self.target_zone is not None
                or self.target_index is not None
            ):
                raise ValueError(
                    f"{self.action_type} cannot include a target."
                )

            return

        actions_requiring_pokemon_target = {
            ActionType.ATTACH_ENERGY,
            ActionType.EVOLVE_POKEMON,
        }

        if self.action_type in actions_requiring_pokemon_target:
            if not self.card_id:
                raise ValueError(
                    f"{self.action_type} actions require a card ID."
                )

            if self.count is not None:
                raise ValueError(
                    f"{self.action_type} actions cannot include a count."
                )

            if self.target_zone is None:
                raise ValueError(
                    f"{self.action_type} actions require a target zone."
                )

            if self.target_zone == PokemonZone.ACTIVE:
                if self.target_index is not None:
                    raise ValueError(
                        "Active Pokemon targets cannot include an index."
                    )

            elif self.target_zone == PokemonZone.BENCH:
                if self.target_index is None:
                    raise ValueError(
                        "Bench Pokemon targets require an index."
                    )

                if self.target_index < 0:
                    raise ValueError(
                        "Bench target index cannot be negative."
                    )

            return

        if self.action_type == ActionType.RESOLVE_MULLIGAN_BONUS:
            if self.card_id is not None:
                raise ValueError(
                    "Mulligan bonus actions cannot include a card ID."
                )

            if (
                self.target_zone is not None
                or self.target_index is not None
            ):
                raise ValueError(
                    "Mulligan bonus actions cannot include a target."
                )

            if self.count is None:
                raise ValueError(
                    "Mulligan bonus actions require a draw count."
                )

            if self.count < 0:
                raise ValueError(
                    "Mulligan bonus draw count cannot be negative."
                )

            return

        if (
            self.card_id is not None
            or self.count is not None
            or self.target_zone is not None
            or self.target_index is not None
        ):
            raise ValueError(
                f"{self.action_type} does not accept additional data."
            )