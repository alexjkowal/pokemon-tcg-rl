"""Core state models for the Pokemon TCG engine."""

from dataclasses import dataclass, field
from enum import StrEnum


class CardType(StrEnum):
    """Broad categories of Pokemon TCG cards."""

    POKEMON = "pokemon"
    TRAINER = "trainer"
    ENERGY = "energy"


@dataclass(frozen=True, slots=True)
class Card:
    """A minimal card definition.

    Card effects and detailed Pokemon attributes will be added later.
    """

    card_id: str
    name: str
    card_type: CardType


@dataclass(slots=True)
class PlayerState:
    """All zones belonging to one player."""

    deck: list[Card]
    hand: list[Card] = field(default_factory=list)
    prizes: list[Card] = field(default_factory=list)
    discard: list[Card] = field(default_factory=list)
    active: Card | None = None
    bench: list[Card] = field(default_factory=list)