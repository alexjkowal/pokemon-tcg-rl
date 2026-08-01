import pytest

from pokemon_tcg_rl.engine.state import (
    Card,
    CardType,
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