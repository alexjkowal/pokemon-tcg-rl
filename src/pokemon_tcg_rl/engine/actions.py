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
    END_TURN = "end_turn"


@dataclass(frozen=True, slots=True)
class GameAction:
    """One concrete decision selected by a player or agent."""

    action_type: ActionType
    player_index: int
    card_id: str | None = None
    count: int | None = None

    def __post_init__(self) -> None:
        if self.player_index not in (0, 1):
            raise ValueError("Player index must be 0 or 1.")

        card_actions = {
            ActionType.CHOOSE_ACTIVE_POKEMON,
            ActionType.BENCH_BASIC_POKEMON,
        }

        if self.action_type in card_actions:
            if not self.card_id:
                raise ValueError(
                    f"{self.action_type} requires a card ID."
                )

            if self.count is not None:
                raise ValueError(
                    f"{self.action_type} cannot include a count."
                )

            return

        if self.action_type == ActionType.RESOLVE_MULLIGAN_BONUS:
            if self.card_id is not None:
                raise ValueError(
                    "Mulligan bonus actions cannot include a card ID."
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

        if self.card_id is not None or self.count is not None:
            raise ValueError(
                f"{self.action_type} does not accept additional data."
            )