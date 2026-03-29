# CHANGELOG

<!-- version list -->

## v1.7.0 (2026-03-29)

### Chores

- Remove unnecessary blank line in test_executor.py
  ([`0c8a0da`](https://github.com/alvinhenrick/fhir-synth/commit/0c8a0da67b5b7941784bdc98a5ad99b986d145f6))

### Features

- Remove blaxel_sandbox option from executor and CLI; update documentation accordingly
  ([`1207adb`](https://github.com/alvinhenrick/fhir-synth/commit/1207adbef091910f4fad717c0677c88bbd4e6564))

- Remove docker_host and docker_port options from executor and CLI; update documentation accordingly
  ([`d21d37a`](https://github.com/alvinhenrick/fhir-synth/commit/d21d37a168f4bac6a582e78106c97c4fb56b49bf))

- Update .env.example to clarify executor backends and usage instructions
  ([`bf60722`](https://github.com/alvinhenrick/fhir-synth/commit/bf60722266c54fe9539af10b7bbfe86bfba243a4))

- Update .env.example to streamline executor backend instructions
  ([`c81835e`](https://github.com/alvinhenrick/fhir-synth/commit/c81835ed73b9880f62e7a110e199e1b0f015da99))


## v1.6.1 (2026-03-18)


## v1.6.0 (2026-03-15)

### Bug Fixes

- Improve comments and documentation clarity in cli.py, fhir_spec.py, loader.py, and selector.py
  ([`cd0314b`](https://github.com/alvinhenrick/fhir-synth/commit/cd0314b1139f50aac4a116a3fe33fa2ed5add539))

### Chores

- Set FORCE_JAVASCRIPT_ACTIONS_TO_NODE24 environment variable in CI workflows
  ([`33f4eca`](https://github.com/alvinhenrick/fhir-synth/commit/33f4ecabcb0ab513a05480e52c522761e24237fa))

- Update GitHub Actions to use latest versions of checkout, setup-python, and upload-artifact
  ([`833ab56`](https://github.com/alvinhenrick/fhir-synth/commit/833ab56d8a174ca0827eeb5d34978dc89cfe09fa))

### Features

- Add Skills System documentation and improve skill discovery in index and mkdocs
  ([`3760246`](https://github.com/alvinhenrick/fhir-synth/commit/376024699e25c4ba5709d8c9f3e636181f3775ea))

- Enhance code generation with context resources and improve FHIR validation
  ([`dc70670`](https://github.com/alvinhenrick/fhir-synth/commit/dc706702e3c6835309270d07a0dc4d511d70405f))

- Enhance FHIR validation with strict mode, required fields, and cardinality checks
  ([`e7ddee3`](https://github.com/alvinhenrick/fhir-synth/commit/e7ddee3abed3ccfc8109f4b8309311d42218058f))

- Implement skills system with modular SKILL.md files for clinical knowledge and enhance prompt
  assembly with skill selection
  ([`79aadcf`](https://github.com/alvinhenrick/fhir-synth/commit/79aadcf23f1946f001e615c3584e83a748078b24))

### Refactoring

- Remove unused development dependencies from pyproject.toml
  ([`9ce28e5`](https://github.com/alvinhenrick/fhir-synth/commit/9ce28e5653a390bf99f64aae0def44d1141945bc))

- Rename test methods for consistency and clarity in test files
  ([`fe86a51`](https://github.com/alvinhenrick/fhir-synth/commit/fe86a513389e54f51de65a4288d1c1b123a62898))

- Streamline CI checks and improve code clarity in cli.py and fhir_validation.py
  ([`b876dce`](https://github.com/alvinhenrick/fhir-synth/commit/b876dce7840a00c0d4ab8ebbf1a054f563b22ebf))


## v1.5.0 (2026-03-11)

### Features

- Add comprehensive guidelines for patient variation, comorbidity patterns, and realism in FHIR
  resource generation
  ([`2653c2d`](https://github.com/alvinhenrick/fhir-synth/commit/2653c2ddef3de3991bb4ac7697821d55ecc9211a))

- Add fix_naive_date_times function to handle naive datetime patterns
  ([`db31ab1`](https://github.com/alvinhenrick/fhir-synth/commit/db31ab148ab7c4b43713010ef4b52b04545c4553))

- Enforce timezone-aware DateTime handling and update related documentation
  ([`b3fb3c1`](https://github.com/alvinhenrick/fhir-synth/commit/b3fb3c1a1df27f32ddb2dc92e70487232e2eb14d))

- Enhance architecture diagram with improved formatting and connections
  ([`3350977`](https://github.com/alvinhenrick/fhir-synth/commit/3350977280782028b9167ec4aefb6f25a891e2c8))

- Enhance patient resource generation with realistic demographics and encounter details
  ([`3ff5f2c`](https://github.com/alvinhenrick/fhir-synth/commit/3ff5f2c0c98435b0065fa2a337278e9dacb418a1))

- Implement EMPI prompt generation and FHIR resource validation
  ([`c690d1d`](https://github.com/alvinhenrick/fhir-synth/commit/c690d1d1a2a106f84b72813cad12b778cc6ead80))

- Improve code formatting and readability in cli.py and fhir_spec.py
  ([`bf7a352`](https://github.com/alvinhenrick/fhir-synth/commit/bf7a352274f74cd09afc7d43a0cb93a74b8e6e22))

- Refine FHIR spec documentation and error handling guidelines
  ([`bf484dc`](https://github.com/alvinhenrick/fhir-synth/commit/bf484dc4c6ed0d3f471c11e6a9a60e8fe23002a6))

- Remove build_bundle_code_prompt function and update related references
  ([`cb3a905`](https://github.com/alvinhenrick/fhir-synth/commit/cb3a905f4f292d8248c7fbb3c56626b7a2e793d3))

- Remove build_rules_prompt function and related references
  ([`584a95d`](https://github.com/alvinhenrick/fhir-synth/commit/584a95d3ca603693a7b903360e8314121f057ddb))

- Remove fix_naive_date_times function and update related references
  ([`3b0baf0`](https://github.com/alvinhenrick/fhir-synth/commit/3b0baf020f56a4341ea68cf421891292b0153aec))

- Remove print_quality_report function and simplify grade calculation logic
  ([`f3a2bd8`](https://github.com/alvinhenrick/fhir-synth/commit/f3a2bd8b597eba2d2e4ecf3719866fbf2379d5d4))

- Remove unused imports for improved code cleanliness in constants.py, fhir_spec.py, manager.py, and
  test_prompts.py
  ([`e87a7ac`](https://github.com/alvinhenrick/fhir-synth/commit/e87a7ac23f5ce914b49fc9f9ac866764c5981ba8))

- Support multiple FHIR versions (R4B, STU3) in prompts and documentation
  ([`fa0005e`](https://github.com/alvinhenrick/fhir-synth/commit/fa0005e6645d9461d1825feb0108fc74d700d7ce))

- Update architecture diagram with enhanced theme variables for improved clarity
  ([`5022f7d`](https://github.com/alvinhenrick/fhir-synth/commit/5022f7d1d56d076070451f932073a65162e1de33))

- Update hard rules and EMPI linkage requirements for clarity and precision
  ([`da0a556`](https://github.com/alvinhenrick/fhir-synth/commit/da0a5568f76e691a0287eb8ecca426984712f62f))

- Update validation step to use model_dump with exclude_none and json mode
  ([`4a0326e`](https://github.com/alvinhenrick/fhir-synth/commit/4a0326e3e64aeae2ba9fb681292f36b6dfed65ef))


## v1.4.0 (2026-03-03)

### Code Style

- Clean up docstring formatting and remove unnecessary whitespace
  ([`0455db1`](https://github.com/alvinhenrick/fhir-synth/commit/0455db1a8f977b47a2b5ac2a8ad435720f8ad82b))

### Documentation

- Update documentation to include Faker integration and inspiration source
  ([`98fba67`](https://github.com/alvinhenrick/fhir-synth/commit/98fba6737d8476638625e71113a86cd5c559ebf9))

### Features

- Enhance patient data generation with demographic diversity, comorbidity realism, and SDOH
  observations
  ([`001f054`](https://github.com/alvinhenrick/fhir-synth/commit/001f0540c826e57c1bd11572c98320eac2245457))


## v1.3.0 (2026-03-01)

### Code Style

- Fix formatting issues in docstrings and remove unnecessary imports
  ([`986f511`](https://github.com/alvinhenrick/fhir-synth/commit/986f511ed2db9d452d1bf94e8adb5a126e0ab3fd))

### Features

- Add E2B executor backend for running code in isolated micro-VMs
  ([`a5502b9`](https://github.com/alvinhenrick/fhir-synth/commit/a5502b9d9b316a705dfdc9a5839db4931b4f2831))

- Add Faker library for generating realistic demographic data
  ([`af00d49`](https://github.com/alvinhenrick/fhir-synth/commit/af00d49a38a6acd1452674cddb0cff29cb2aa9dd))

- Implement pluggable executor backends for running LLM-generated code
  ([`41b2370`](https://github.com/alvinhenrick/fhir-synth/commit/41b23700c0229d2f0a99b746fa7900947ab9032e))


## v1.2.0 (2026-03-01)

### Code Style

- Clean up code formatting and remove unnecessary whitespace
  ([`7edbd90`](https://github.com/alvinhenrick/fhir-synth/commit/7edbd90fde94efca92fc62ff3ae03924cefdaf59))

### Documentation

- Update changelog format and mkdocs configuration for snippets
  ([`f902076`](https://github.com/alvinhenrick/fhir-synth/commit/f9020766615e04d40a9f8a72c9fd57d900d9e1da))

- Update documentation for LLM providers and AWS Bedrock integration
  ([`18700ac`](https://github.com/alvinhenrick/fhir-synth/commit/18700acaf78cdae7f82c57718c945c9629221e93))


## v1.1.0 (2026-02-28)

### Documentation

- Update documentation for fhir-synth CLI; enhance output modes and AWS Bedrock integration details
  ([`1c4284b`](https://github.com/alvinhenrick/fhir-synth/commit/1c4284bac5f189fedf2dd7900ebeb732b168e20f))

### Features

- Add AWS Bedrock support; include options for AWS profile and region in CLI
  ([`439233c`](https://github.com/alvinhenrick/fhir-synth/commit/439233c2bafbc7fd62b6d436a550e9894315432c))

- Add code quality scoring and robust error handling; enhance import validation and auto-fixing
  ([`4bd9282`](https://github.com/alvinhenrick/fhir-synth/commit/4bd92822aedeb952769c1530d9a0812a98b5fcc7))

- Add Makefile for build automation and improve code formatting in metrics and prompts
  ([`e60124a`](https://github.com/alvinhenrick/fhir-synth/commit/e60124a2704705b04a62d129db4fffe898722477))

- Add mypy overrides for boto3 to ignore missing imports
  ([`45a3590`](https://github.com/alvinhenrick/fhir-synth/commit/45a3590cef72b897041afdf1ba8a419258650b1b))

- Enhance import handling with introspection for FHIR resources and data types
  ([`8d38bff`](https://github.com/alvinhenrick/fhir-synth/commit/8d38bfff800949503bbc4e9a4f5cb30c79ce6f72))

### Refactoring

- Improve formatting of code quality report output in metrics.py
  ([`baff8a6`](https://github.com/alvinhenrick/fhir-synth/commit/baff8a677de80b5185586dd4ad373b7fd339f145))

- Improve readability of AWS region retrieval logic in llm.py
  ([`d1ae95e`](https://github.com/alvinhenrick/fhir-synth/commit/d1ae95edd96d3d479f1127f8b9d3b5a45f0d2d3d))


## v1.0.0 (2026-02-25)

- Initial Release
