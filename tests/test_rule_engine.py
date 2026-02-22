"""Tests for rule engine."""

from fhir_synth.rule_engine import GenerationRules, Rule, RuleEngine, RuleSet


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


def test_rule_engine_works_with_any_fhir_type():
    """Prove the engine works with non-hardcoded types like Immunization."""
    engine = RuleEngine()
    ruleset = RuleSet(
        resource_type="Immunization",
        description="Flu shots",
        rules=[
            Rule(
                name="flu",
                description="Influenza vaccine",
                conditions={},
                actions={"vaccineCode": {"text": "Influenza"}},
                weight=1.0,
            ),
        ],
    )
    engine.register_ruleset(ruleset)

    resources = engine.execute("Immunization", {}, count=3)

    assert len(resources) == 3
    for r in resources:
        assert r["resourceType"] == "Immunization"
        assert r["vaccineCode"]["text"] == "Influenza"


def test_ruleset_accepts_any_resource_type_string():
    """RuleSet accepts any resource type — no hardcoded validation."""
    rs = RuleSet(
        resource_type="CustomResource",
        description="Anything goes",
        rules=[],
    )
    assert rs.resource_type == "CustomResource"


def test_default_executor_sets_resource_type_from_ruleset():
    """The default executor should always set resourceType from the ruleset."""
    engine = RuleEngine()
    ruleset = RuleSet(
        resource_type="AllergyIntolerance",
        description="Allergies",
        rules=[
            Rule(name="peanut", description="Peanut allergy", actions={}),
        ],
    )
    engine.register_ruleset(ruleset)

    resources = engine.execute("AllergyIntolerance", {}, count=1)
    assert resources[0]["resourceType"] == "AllergyIntolerance"


def test_generation_rules_generic_by_type():
    """GenerationRules should store rules keyed by any resource type."""
    gr = GenerationRules()
    gr.add_rules("Coverage", [Rule(name="r1", description="Coverage rule")])
    gr.add_rules("Claim", [Rule(name="r2", description="Claim rule")])

    assert "Coverage" in gr.resource_types
    assert "Claim" in gr.resource_types
    assert len(gr.get_rules("Coverage")) == 1
    assert len(gr.get_rules("Claim")) == 1


def test_generation_rules_roundtrip():
    """to_dict → from_dict should preserve all data."""
    gr = GenerationRules(population={"count": 10})
    gr.add_rules("Patient", [Rule(name="p", description="Patient rule")])
    gr.add_rules("Immunization", [Rule(name="i", description="Imm rule")])

    data = gr.to_dict()
    restored = GenerationRules.from_dict(data)

    assert restored.population == {"count": 10}
    assert len(restored.get_rules("Patient")) == 1
    assert len(restored.get_rules("Immunization")) == 1
    assert restored.get_rules("Patient")[0].name == "p"


def test_generation_rules_backwards_compat():
    """Old-style keys (conditions, medications, etc.) should still load."""
    old_data = {
        "population": {},
        "conditions": [{"name": "c", "description": "cond"}],
        "medications": [{"name": "m", "description": "med"}],
    }
    gr = GenerationRules.from_dict(old_data)

    assert len(gr.get_rules("Condition")) == 1
    assert len(gr.get_rules("MedicationRequest")) == 1
