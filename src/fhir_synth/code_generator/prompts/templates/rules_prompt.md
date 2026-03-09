Convert this natural language requirement into structured generation rules:

$requirement

Return JSON with this structure:
{
  "rules": [
    {
      "name": "rule_name",
      "description": "what this rule does",
      "conditions": {"condition_key": "value"},
      "actions": {"field": "value"},
      "weight": 1.0
    }
  ],
  "resource_type": "FHIR ResourceType",
  "bundle_config": {"type": "transaction", "batch_size": 10},
  "variation_config": {
    "age_distribution": {"neonatal": 0.05, "pediatric": 0.15, "adult": 0.55, "geriatric": 0.25},
    "gender_distribution": {"male": 0.48, "female": 0.48, "other": 0.03, "unknown": 0.01},
    "include_sdoh": true,
    "include_comorbidities": true,
    "include_deceased": true,
    "deceased_rate": 0.03,
    "data_completeness": {"full": 0.6, "partial": 0.3, "sparse": 0.1}
  }
}

