from dataclasses import dataclass, field
from enum import StrEnum


class CardType(StrEnum):
    """Broad categories of Pokemon TCG cards."""

    POKEMON = "pokemon"
    TRAINER = "trainer"
    ENERGY = "energy"


class PokemonStage(StrEnum):
    """Evolution stage of a Pokemon card."""

    BASIC = "basic"
    STAGE_1 = "stage_1"
    STAGE_2 = "stage_2"


@dataclass(frozen=True, slots=True)
class Card:
    """A minimal immutable card definition."""

    card_id: str
    name: str
    card_type: CardType
    pokemon_stage: PokemonStage | None = None

    def __post_init__(self) -> None:
        if self.card_type == CardType.POKEMON and self.pokemon_stage is None:
            raise ValueError("Pokemon cards must specify a Pokemon stage.")

        if self.card_type != CardType.POKEMON and self.pokemon_stage is not None:
            raise ValueError("Only Pokemon cards may specify a Pokemon stage.")

    @property
    def is_basic_pokemon(self) -> bool:
        """Return whether this card is a Basic Pokemon."""

        return (
            self.card_type == CardType.POKEMON
            and self.pokemon_stage == PokemonStage.BASIC
        )


@dataclass(slots=True)
class PlayerState:
    """All zones belonging to one player."""

    deck: list[Card]
    hand: list[Card] = field(default_factory=list)
    prizes: list[Card] = field(default_factory=list)
    discard: list[Card] = field(default_factory=list)
    active: Card | None = None
    bench: list[Card] = field(default_factory=list)