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
    VMAX = "vmax"
    VSTAR = "vstar"


class TrainerCardType(StrEnum):
    """Type of trainer card"""

    SUPPORTER = "supporter"
    TOOL = "tool"
    ITEM = "item"
    STADIUM = "stadium"


class PokemonRule(StrEnum):
    """Printed rule-box classifications on Pokemon cards."""

    EX = "ex"
    V = "v"
    VMAX = "vmax"
    VSTAR = "vstar"
    TERA = "tera"


@dataclass(frozen=True, slots=True)
class Card:
    """An immutable card definition."""

    card_id: str
    name: str
    card_type: CardType

    pokemon_stage: PokemonStage | None = None
    pokemon_rules: frozenset[PokemonRule] = field(
        default_factory=frozenset
    )
    trainer_card_type: TrainerCardType | None = None

    def __post_init__(self) -> None:
        if self.card_type == CardType.POKEMON:
            if self.pokemon_stage is None:
                raise ValueError(
                    "Pokemon cards must specify a Pokemon stage."
                )

            if self.trainer_card_type is not None:
                raise ValueError(
                    "Pokemon cards cannot specify a Trainer card type."
                )

        elif self.card_type == CardType.TRAINER:
            if self.trainer_card_type is None:
                raise ValueError(
                    "Trainer cards must specify a Trainer card type."
                )

            if self.pokemon_stage is not None:
                raise ValueError(
                    "Trainer cards cannot specify a Pokemon stage."
                )

            if self.pokemon_rules:
                raise ValueError(
                    "Trainer cards cannot specify Pokemon rules."
                )

        else:
            # Energy cards
            if self.pokemon_stage is not None:
                raise ValueError(
                    "Energy cards cannot specify a Pokemon stage."
                )

            if self.pokemon_rules:
                raise ValueError(
                    "Energy cards cannot specify Pokemon rules."
                )

            if self.trainer_card_type is not None:
                raise ValueError(
                    "Energy cards cannot specify a Trainer card type."
                )

    @property
    def is_basic_pokemon(self) -> bool:
        """Return whether this card is a Basic Pokemon."""

        return (
            self.card_type == CardType.POKEMON
            and self.pokemon_stage == PokemonStage.BASIC
        )

    @property
    def is_tera(self) -> bool:
        """Return whether this card has the Tera rule."""

        return PokemonRule.TERA in self.pokemon_rules

    @property
    def is_pokemon_ex(self) -> bool:
        """Return whether this card is a modern Pokemon ex."""

        return PokemonRule.EX in self.pokemon_rules

    @property
    def has_rule_box(self) -> bool:
        """Return whether this Pokemon has any modeled rule box."""

        return bool(self.pokemon_rules)


@dataclass(slots=True)
class PlayerState:
    """All zones belonging to one player."""

    deck: list[Card]
    hand: list[Card] = field(default_factory=list)
    prizes: list[Card] = field(default_factory=list)
    discard: list[Card] = field(default_factory=list)
    active: Card | None = None
    bench: list[Card] = field(default_factory=list)