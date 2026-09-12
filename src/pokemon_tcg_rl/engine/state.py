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

class EnergyType(StrEnum):
    """Energy types used for Pokemon and attack costs."""

    GRASS = "grass"
    FIRE = "fire"
    WATER = "water"
    LIGHTNING = "lightning"
    PSYCHIC = "psychic"
    FIGHTING = "fighting"
    DARKNESS = "darkness"
    METAL = "metal"
    COLORLESS = "colorless"
    DRAGON = "dragon"
    FAIRY = "fairy"

@dataclass(frozen=True, slots=True)
class Attack:
    """Printed information for one Pokemon attack."""

    name: str
    energy_cost: tuple[EnergyType, ...] = ()
    base_damage: int = 0
    text: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("An attack must have a name.")

        if self.base_damage < 0:
            raise ValueError("Attack damage cannot be negative.")

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

    pokemon_type: EnergyType | None = None
    hp: int | None = None
    attacks: tuple[Attack, ...] = ()
    retreat_cost: int | None = None
    energy_type: EnergyType | None = None

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

            if self.hp is not None and self.hp <= 0:
                raise ValueError(
                    "Pokemon HP must be greater than zero."
                )

            if self.retreat_cost is not None and self.retreat_cost < 0:
                raise ValueError(
                    "Pokemon retreat cost cannot be negative."
                )

            if self.energy_type is not None:
                raise ValueError(
                    "Pokemon cards cannot specify an Energy card type."
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

            if self.pokemon_type is not None:
                raise ValueError(
                    "Trainer cards cannot specify a Pokemon type."
                )

            if self.hp is not None:
                raise ValueError(
                    "Trainer cards cannot specify HP."
                )

            if self.attacks:
                raise ValueError(
                    "Trainer cards cannot specify attacks."
                )

            if self.retreat_cost is not None:
                raise ValueError(
                    "Trainer cards cannot specify a retreat cost."
                )

            if self.energy_type is not None:
                raise ValueError(
                    "Trainer cards cannot specify an Energy type."
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

            if self.pokemon_type is not None:
                raise ValueError(
                    "Energy cards cannot specify a Pokemon type."
                )

            if self.hp is not None:
                raise ValueError(
                    "Energy cards cannot specify HP."
                )

            if self.attacks:
                raise ValueError(
                    "Energy cards cannot specify attacks."
                )

            if self.retreat_cost is not None:
                raise ValueError(
                    "Energy cards cannot specify a retreat cost."
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
class PokemonInPlay:
    """Mutable state for one Pokemon currently in play."""

    evolution_stack: list[Card]
    damage: int = 0
    attached_energy: list[Card] = field(default_factory=list)
    attached_tool: Card | None = None

    def __post_init__(self) -> None:
        if not self.evolution_stack:
            raise ValueError(
                "A Pokemon in play must contain at least one Pokemon card."
            )

        if any(
            card.card_type != CardType.POKEMON
            for card in self.evolution_stack
        ):
            raise ValueError(
                "An evolution stack may contain only Pokemon cards."
            )

        if self.damage < 0:
            raise ValueError("Pokemon damage cannot be negative.")

        if any(
            card.card_type != CardType.ENERGY
            for card in self.attached_energy
        ):
            raise ValueError(
                "Attached Energy must contain only Energy cards."
            )

        if (
            self.attached_tool is not None
            and (
                self.attached_tool.card_type != CardType.TRAINER
                or self.attached_tool.trainer_card_type
                != TrainerCardType.TOOL
            )
        ):
            raise ValueError("Attached Tool must be a Pokemon Tool card.")

    @property
    def current_card(self) -> Card:
        """Return the topmost Pokemon card in the evolution stack."""

        return self.evolution_stack[-1]

@dataclass(slots=True)
class PlayerState:
    """All zones belonging to one player."""

    deck: list[Card]
    hand: list[Card] = field(default_factory=list)
    prizes: list[Card] = field(default_factory=list)
    discard: list[Card] = field(default_factory=list)
    active: PokemonInPlay | None = None
    bench: list[PokemonInPlay] = field(default_factory=list)
    energy_attached_this_turn: bool = False