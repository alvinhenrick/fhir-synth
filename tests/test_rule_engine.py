"""Tests for rule engine."""

from fhir_synth.rule_engine import GenerationRules, MetaConfig, Rule, RuleEngine, RuleSet


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


def test_metadata_applied_from_rule():
    """Metadata from rule should be applied to generated resource."""
    engine = RuleEngine()
    meta_config = MetaConfig(
        security=[
            {
                "system": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality",
                "code": "R",
                "display": "Restricted",
            }
        ],
        tag=[{"system": "http://example.org/tags", "code": "synthetic"}],
        profile=["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"],
        source="http://example.org/fhir",
    )
    ruleset = RuleSet(
        resource_type="Patient",
        description="Test patients",
        rules=[
            Rule(
                name="secure_patient",
                description="Patient with security tags",
                actions={"name": [{"family": "Doe"}]},
                meta=meta_config,
            )
        ],
    )
    engine.register_ruleset(ruleset)

    resources = engine.execute("Patient", {}, count=1)

    assert len(resources) == 1
    meta = resources[0].get("meta")
    assert meta is not None
    assert len(meta["security"]) == 1
    assert meta["security"][0]["code"] == "R"
    assert len(meta["tag"]) == 1
    assert meta["tag"][0]["code"] == "synthetic"
    assert len(meta["profile"]) == 1
    assert meta["source"] == "http://example.org/fhir"


def test_global_metadata_applied_from_ruleset():
    """Global metadata from ruleset should be applied to all resources."""
    engine = RuleEngine()
    global_meta = MetaConfig(
        tag=[{"system": "http://example.org/tags", "code": "test-data"}],
        source="http://test-system.org",
    )
    ruleset = RuleSet(
        resource_type="Observation",
        description="Test observations",
        global_meta=global_meta,
        rules=[
            Rule(
                name="obs1",
                description="Simple observation",
                actions={"status": "final"},
            )
        ],
    )
    engine.register_ruleset(ruleset)

    resources = engine.execute("Observation", {}, count=2)

    for resource in resources:
        meta = resource.get("meta")
        assert meta is not None
        assert meta["tag"][0]["code"] == "test-data"
        assert meta["source"] == "http://test-system.org"


def test_rule_metadata_overrides_global_metadata():
    """Rule-level metadata should be merged with global metadata."""
    engine = RuleEngine()
    global_meta = MetaConfig(
        tag=[{"system": "http://example.org/tags", "code": "global"}],
        source="http://global-system.org",
    )
    rule_meta = MetaConfig(
        tag=[{"system": "http://example.org/tags", "code": "rule-specific"}],
        security=[{"system": "http://security.org", "code": "SENSITIVE"}],
    )
    ruleset = RuleSet(
        resource_type="Condition",
        description="Test conditions",
        global_meta=global_meta,
        rules=[
            Rule(
                name="cond1",
                description="Condition with rule meta",
                actions={"clinicalStatus": {"coding": [{"code": "active"}]}},
                meta=rule_meta,
            )
        ],
    )
    engine.register_ruleset(ruleset)

    resources = engine.execute("Condition", {}, count=1)

    meta = resources[0].get("meta")
    assert meta is not None
    # Both global and rule tags should be present
    assert len(meta["tag"]) == 2
    assert any(t["code"] == "global" for t in meta["tag"])
    assert any(t["code"] == "rule-specific" for t in meta["tag"])
    # Security from rule
    assert meta["security"][0]["code"] == "SENSITIVE"
    # Source from global (not overridden by rule)
    assert meta["source"] == "http://global-system.org"


def test_metadata_with_all_fields():
    """Test all metadata fields can be set."""
    engine = RuleEngine()
    meta_config = MetaConfig(
        security=[{"system": "http://security.org", "code": "SEC"}],
        tag=[{"system": "http://tags.org", "code": "TAG"}],
        profile=["http://profile.org/StructureDefinition/custom"],
        source="http://source-system.org",
        versionId="v1.0",
        lastUpdated="2026-02-23T12:00:00Z",
    )
    ruleset = RuleSet(
        resource_type="Patient",
        description="Patient with all meta fields",
        rules=[
            Rule(
                name="full_meta",
                description="All metadata fields",
                actions={},
                meta=meta_config,
            )
        ],
    )
    engine.register_ruleset(ruleset)

    resources = engine.execute("Patient", {}, count=1)

    meta = resources[0].get("meta")
    assert meta is not None
    assert meta["security"][0]["code"] == "SEC"
    assert meta["tag"][0]["code"] == "TAG"
    assert meta["profile"][0] == "http://profile.org/StructureDefinition/custom"
    assert meta["source"] == "http://source-system.org"
    assert meta["versionId"] == "v1.0"
    assert meta["lastUpdated"] == "2026-02-23T12:00:00Z"



