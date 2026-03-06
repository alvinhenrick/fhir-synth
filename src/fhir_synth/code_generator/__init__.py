"""Dynamic code generation for FHIR resources from LLM prompts."""

from fhir_synth.code_generator.constants import (
    ALLOWED_MODULE_PREFIXES,
    ALLOWED_MODULES,
    SUPPORTED_RESOURCE_TYPES,
)
from fhir_synth.code_generator.converter import PromptToRulesConverter
from fhir_synth.code_generator.dspy_generator import DSPyCodeGenerator
from fhir_synth.code_generator.executor import (
    DifySandboxExecutor,
    E2BExecutor,
    ExecutionResult,
    Executor,
    ExecutorBackend,
    LocalSubprocessExecutor,
    get_executor,
)
from fhir_synth.code_generator.generator import CodeGenerator
from fhir_synth.code_generator.metrics import calculate_code_quality_score, print_quality_report

__all__ = [
    "ALLOWED_MODULE_PREFIXES",
    "ALLOWED_MODULES",
    "CodeGenerator",
    "DSPyCodeGenerator",
    "DifySandboxExecutor",
    "E2BExecutor",
    "ExecutionResult",
    "Executor",
    "ExecutorBackend",
    "LocalSubprocessExecutor",
    "PromptToRulesConverter",
    "SUPPORTED_RESOURCE_TYPES",
    "calculate_code_quality_score",
    "get_executor",
    "print_quality_report",
]
