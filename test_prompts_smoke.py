#!/usr/bin/env python3
"""Quick smoke test for the new prompts package."""
import sys

try:
    from fhir_synth.code_generator.prompts import clinical_rules, get_rule, RULE_NAMES
    r = clinical_rules()
    print(f"OK clinical_rules: {len(r)} chars")
    print(f"OK RULE_NAMES: {RULE_NAMES}")

    for name in RULE_NAMES:
        section = get_rule(name)
        print(f"OK get_rule({name!r}): {len(section)} chars")

    from fhir_synth.code_generator.prompts import SYSTEM_PROMPT
    sp = str(SYSTEM_PROMPT)
    print(f"OK SYSTEM_PROMPT: {len(sp)} chars")

    from fhir_synth.code_generator.prompts import build_code_prompt
    p = build_code_prompt("3 patients")
    print(f"OK build_code_prompt: {len(p)} chars")

    from fhir_synth.code_generator.prompts import _SANDBOX_SECTION
    print(f"OK _SANDBOX_SECTION: {len(_SANDBOX_SECTION)} chars")

    print("\nALL PASSED")
except Exception as e:
    print(f"FAIL: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)

