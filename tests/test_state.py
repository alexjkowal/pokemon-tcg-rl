import pytest

from pokemon_tcg_rl.engine.actions import (
    ChoiceType,
    PokemonTargetScope,
)
from pokemon_tcg_rl.engine.state import (
    Attack,
    AttackChoice,
    Card,
    CardType,
    EnergyType,
    PokemonInPlay,
    PokemonRule,
    PokemonStage,
    TrainerCardType,
)


def test_tera_pokemon_ex_can_have_both_rules() -> None:
    card = Card(
        card_id="tera-ex-001",
        name="Test Tera ex",
        card_type=CardType.POKEMON,
        pokemon_stage=PokemonStage.BASIC,
        pokemon_rules=frozenset(
            {
                PokemonRule.EX,
                PokemonRule.TERA,
            }
        ),
    )

    assert card.is_pokemon_ex
    assert card.is_tera
    assert card.has_rule_box


def test_trainer_requires_trainer_type() -> None:
    with pytest.raises(
        ValueError,
        match="must specify a Trainer card type",
    ):
        Card(
            card_id="trainer-001",
            name="Test Trainer",
            card_type=CardType.TRAINER,
        )


def test_item_card_is_valid() -> None:
    card = Card(
        card_id="item-001",
        name="Test Item",
        card_type=CardType.TRAINER,
        trainer_card_type=TrainerCardType.ITEM,
    )

    assert card.trainer_card_type == TrainerCardType.ITEM


def test_energy_cannot_have_pokemon_rules() -> None:
    with pytest.raises(
        ValueError,
        match="cannot specify Pokemon rules",
    ):
        Card(
            card_id="energy-001",
            name="Test Energy",
            card_type=CardType.ENERGY,
            pokemon_rules=frozenset({PokemonRule.TERA}),
        )

def test_pokemon_in_play_starts_with_clean_state() -> None:
    card = Card(
        card_id="basic-001",
        name="Test Pokemon",
        card_type=CardType.POKEMON,
        pokemon_stage=PokemonStage.BASIC,
    )

    pokemon = PokemonInPlay(
        evolution_stack=[card]
    )

    assert pokemon.current_card == card
    assert pokemon.damage == 0
    assert pokemon.attached_energy == []
    assert pokemon.attached_tool is None


def test_pokemon_in_play_damage_is_mutable() -> None:
    card = Card(
        card_id="basic-001",
        name="Test Pokemon",
        card_type=CardType.POKEMON,
        pokemon_stage=PokemonStage.BASIC,
    )

    pokemon = PokemonInPlay(
        evolution_stack=[card]
    )

    pokemon.damage = 50

    assert pokemon.damage == 50


def test_pokemon_in_play_rejects_non_pokemon_stack() -> None:
    energy = Card(
        card_id="energy-001",
        name="Test Energy",
        card_type=CardType.ENERGY,
    )

    with pytest.raises(
        ValueError,
        match="only Pokemon cards",
    ):
        PokemonInPlay(
            evolution_stack=[energy]
        )

def test_attack_stores_printed_combat_data() -> None:
    attack = Attack(
        name="Test Attack",
        energy_cost=(
            EnergyType.FIRE,
            EnergyType.COLORLESS,
        ),
        base_damage=50,
    )

    assert attack.name == "Test Attack"
    assert attack.energy_cost == (
        EnergyType.FIRE,
        EnergyType.COLORLESS,
    )
    assert attack.base_damage == 50


def test_attack_rejects_negative_damage() -> None:
    with pytest.raises(
        ValueError,
        match="cannot be negative",
    ):
        Attack(
            name="Invalid Attack",
            base_damage=-10,
        )


def test_pokemon_can_store_combat_data() -> None:
    attack = Attack(
        name="Test Attack",
        energy_cost=(EnergyType.LIGHTNING,),
        base_damage=30,
    )

    card = Card(
        card_id="pokemon-001",
        name="Test Pokemon",
        card_type=CardType.POKEMON,
        pokemon_stage=PokemonStage.BASIC,
        pokemon_type=EnergyType.LIGHTNING,
        hp=70,
        attacks=(attack,),
        retreat_cost=1,
    )

    assert card.hp == 70
    assert card.pokemon_type == EnergyType.LIGHTNING
    assert card.attacks == (attack,)
    assert card.retreat_cost == 1


def test_pokemon_rejects_nonpositive_hp() -> None:
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        Card(
            card_id="pokemon-001",
            name="Invalid Pokemon",
            card_type=CardType.POKEMON,
            pokemon_stage=PokemonStage.BASIC,
            hp=0,
        )

def test_evolution_card_stores_evolves_from() -> None:
    card = Card(
        card_id="metang-001",
        name="Metang",
        card_type=CardType.POKEMON,
        pokemon_stage=PokemonStage.STAGE_1,
        evolves_from="Beldum",
        hp=100,
    )

    assert card.evolves_from == "Beldum"


def test_basic_pokemon_rejects_evolves_from() -> None:
    with pytest.raises(
        ValueError,
        match="Basic Pokemon cannot",
    ):
        Card(
            card_id="beldum-001",
            name="Beldum",
            card_type=CardType.POKEMON,
            pokemon_stage=PokemonStage.BASIC,
            evolves_from="Something",
            hp=60,
        )

def test_attack_can_store_pokemon_target_choice() -> None:
    choice = AttackChoice(
        choice_type=ChoiceType.POKEMON_TARGET,
        target_scope=PokemonTargetScope.OPPONENT_BENCH,
    )

    attack = Attack(
        name="Bench Strike",
        choices=(choice,),
    )

    assert len(attack.choices) == 1
    assert (
        attack.choices[0].choice_type
        == ChoiceType.POKEMON_TARGET
    )
    assert (
        attack.choices[0].target_scope
        == PokemonTargetScope.OPPONENT_BENCH
    )

def test_damage_allocation_choice_stores_amount() -> None:
    choice = AttackChoice(
        choice_type=ChoiceType.DAMAGE_ALLOCATION,
        target_scope=PokemonTargetScope.OPPONENT_ANY,
        amount=6,
    )

    assert choice.amount == 6

def test_damage_allocation_requires_amount() -> None:
    with pytest.raises(
        ValueError,
        match="require an amount",
    ):
        AttackChoice(
            choice_type=ChoiceType.DAMAGE_ALLOCATION,
            target_scope=PokemonTargetScope.OPPONENT_ANY,
        )

def test_damage_allocation_rejects_nonpositive_amount() -> None:
    with pytest.raises(
        ValueError,
        match="must be positive",
    ):
        AttackChoice(
            choice_type=ChoiceType.DAMAGE_ALLOCATION,
            target_scope=PokemonTargetScope.OPPONENT_ANY,
            amount=0,
        )

def test_pokemon_target_choice_rejects_amount() -> None:
    with pytest.raises(
        ValueError,
        match="Only damage allocation",
    ):
        AttackChoice(
            choice_type=ChoiceType.POKEMON_TARGET,
            target_scope=PokemonTargetScope.OPPONENT_BENCH,
            amount=1,
        )