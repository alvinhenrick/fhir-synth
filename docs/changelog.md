# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases are managed automatically by [python-semantic-release](https://python-semantic-release.readthedocs.io/).

## [0.1.0] - 2026-02-24

### Added

- Initial release
- LLM-powered FHIR R4B code generation with self-healing execution
- Declarative rule engine with weighted rule selection
- EMPI (Person → Patient) linkage support
- Bundle builder with transaction/batch/collection support
- Custom metadata support (security labels, tags, profiles, source)
- YAML-based metadata configuration
- CLI commands: `generate`, `rules`, `codegen`, `bundle`
- Mock LLM provider for testing without API keys
- Support for 100+ LLM providers via LiteLLM
- Auto-discovery of all 141 FHIR R4B resource types

