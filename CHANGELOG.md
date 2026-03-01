# CHANGELOG

<!-- version list -->

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
