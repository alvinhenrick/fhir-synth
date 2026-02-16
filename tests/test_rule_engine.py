"""Tests for rule engine."""

from fhir_synth.rule_engine import Rule, RuleEngine, RuleSet


def test_rule_engine_selects_matching_rule():
    engine = RuleEngine()
    ruleset = RuleSet(
        resource_type="Patient",
        description="Test patients",
        rules=[
            Rule(
                name="adult",
                description="Adult patient",
                conditions={"age_group": "adult"},
                actions={"resourceType": "Patient", "id": "p1"},
                weight=1.0,
            ),
            Rule(
                name="child",
                description="Child patient",
                conditions={"age_group": "child"},
                actions={"resourceType": "Patient", "id": "p2"},
                weight=1.0,
            ),
        ],
    )
    engine.register_ruleset(ruleset)

    resources = engine.execute("Patient", {"age_group": "adult"}, count=1)

    assert len(resources) == 1
    assert resources[0]["id"] == "p1"


def test_rule_engine_falls_back_to_default_rule():
    engine = RuleEngine()
    default_rule = Rule(
        name="default",
        description="Default patient",
        conditions={},
        actions={"resourceType": "Patient", "id": "default"},
        weight=1.0,
    )
    ruleset = RuleSet(
        resource_type="Patient",
        description="Test patients",
        rules=[],
        default_rule=default_rule,
    )
    engine.register_ruleset(ruleset)

    resources = engine.execute("Patient", {"age_group": "adult"}, count=2)

    assert len(resources) == 2
    assert all(resource["id"] == "default" for resource in resources)

