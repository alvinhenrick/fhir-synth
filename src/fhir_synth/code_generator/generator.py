"""Main code generation engine."""

from __future__ import annotations

import logging
from typing import Any

from fhir_synth.code_generator.executor import (
    Executor,
    LocalSmolagentsExecutor,
    fix_common_imports,
    validate_code,
    validate_imports,
)
from fhir_synth.code_generator.metrics import calculate_code_quality_score
from fhir_synth.code_generator.prompts import (
    build_code_prompt,
    build_fix_prompt,
    get_system_prompt,
)
from fhir_synth.code_generator.utils import extract_code
from fhir_synth.llm import LLMProvider

logger = logging.getLogger(__name__)


class CodeGenerator:
    """Generates Python code for FHIR resource creation from natural language."""

    def __init__(
        self,
        llm: LLMProvider,
        max_retries: int = 2,
        enable_scoring: bool = False,
        executor: Executor | None = None,
        fhir_version: str = "R4B",
        context_resources: list[dict[str, Any]] | None = None,
    ) -> None:
        """Initialize code generator with LLM.

        Args:
            llm: LLM provider for code generation
            max_retries: Number of times to retry if generated code fails execution
            enable_scoring: Enable code quality scoring and logging
            executor: Executor backend for running generated code.
                Defaults to :class:`LocalSubprocessExecutor`.
            fhir_version: FHIR version to use (R4B, STU3). Defaults to R4B.
            context_resources: Existing FHIR resources to use as state context
        """
        self.llm = llm
        self.max_retries = max_retries
        self.enable_scoring = enable_scoring
        self.executor: Executor = executor or LocalSmolagentsExecutor()
        self.fhir_version = fhir_version
        self.context_resources = context_resources or []

        # Set the FHIR version for the spec module
        from fhir_synth import fhir_spec

        fhir_spec.set_fhir_version(fhir_version)

    def generate_code_from_prompt(self, prompt: str) -> str:
        """Generate Python code from natural language prompt.

        Args:
            prompt: Natural language description of resources to generate

        Returns:
            Generated Python code as string
        """
        user_prompt = build_code_prompt(prompt, context_resources=self.context_resources)
        system_prompt = get_system_prompt(user_prompt=prompt)
        code = self.llm.generate_text(system_prompt, user_prompt)
        return extract_code(code)

    def execute_generated_code(self, code: str, timeout: int = 30) -> list[dict[str, Any]]:
        """Execute generated code safely, with self-healing retry on failure.

        If execution fails, the error is sent back to the LLM to produce a
        corrected version. This repeats up to ``max_retries`` times.

        Args:
            code: Generated Python code
            timeout: Timeout in seconds

        Returns:
            List of generated resources
        """
        # Pre-execution validation: check imports before running
        import_errors = validate_imports(code)
        if import_errors:
            # Try auto-fixing common import issues
            fixed_code = fix_common_imports(code)
            fixed_import_errors = validate_imports(fixed_code)

            if not fixed_import_errors:
                # Auto-fix succeeded
                code = fixed_code
            else:
                # Auto-fix didn't work, include errors in first retry
                error_msg = "\n".join(import_errors)
                code = self._retry_with_error(code, f"Import validation failed:\n{error_msg}")

        last_error: Exception | None = None

        for attempt in range(1 + self.max_retries):
            if not validate_code(code):
                last_error = ValueError("Generated code is not valid Python")
                code = self._retry_with_error(code, str(last_error))
                continue

            try:
                result = self.executor.execute(code, timeout=timeout)
                resources = result.artifacts

                # Always score code quality (includes FHIR Pydantic validation)
                metrics = calculate_code_quality_score(code, resources)

                if self.enable_scoring:
                    logger.info(
                        f"Code quality: {metrics['score']:.2f} ({metrics['grade']}) - "
                        f"{len(metrics.get('warnings', []))} warnings"
                    )
                    if metrics.get("warnings"):
                        for warning in metrics["warnings"]:
                            logger.debug(f"  • {warning}")

                # If FHIR validation failed, retry with error details
                fhir_vr = metrics.get("fhir_validation")
                if fhir_vr and fhir_vr["invalid"] > 0:
                    error_lines = [
                        f"  {e['resourceType']}/{e['id']}: {'; '.join(e['errors'])}"
                        for e in fhir_vr["errors"][:10]
                    ]
                    error_detail = "\n".join(error_lines)

                    if attempt < self.max_retries:
                        logger.info(
                            "FHIR validation: %d/%d invalid (attempt %d/%d), retrying…",
                            fhir_vr["invalid"],
                            fhir_vr["total"],
                            attempt + 1,
                            self.max_retries + 1,
                        )
                        last_error = ValueError(
                            f"FHIR validation failed for {fhir_vr['invalid']}/{fhir_vr['total']} "
                            f"resources. Fix these errors:\n{error_detail}"
                        )
                        code = self._retry_with_error(code, str(last_error))
                        continue
                    else:
                        # Last attempt — log the failures but return what we have
                        logger.warning(
                            "FHIR validation: %d/%d resources invalid after %d attempts:\n%s",
                            fhir_vr["invalid"],
                            fhir_vr["total"],
                            self.max_retries + 1,
                            error_detail,
                        )

                return resources
            except ImportError as exc:
                # Import errors get special handling with auto-fix attempt
                last_error = exc
                if attempt < self.max_retries:
                    fixed_code = fix_common_imports(code)
                    if fixed_code != code:
                        code = fixed_code
                    else:
                        code = self._retry_with_error(code, f"ImportError: {exc}")
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    code = self._retry_with_error(code, str(exc))

        # If we got here, all retries failed
        # Build helpful error message
        error_msg = f"Code execution failed after {self.max_retries + 1} attempts: {last_error}"
        if isinstance(last_error, ImportError):
            error_msg += (
                "\n\nSuggestions:\n"
                "  1. Try a more reliable provider: --provider gpt-4\n"
                "  2. Save and inspect the code: --save-code output.py\n"
                "  3. Check import paths in fhir.resources package"
            )

        raise RuntimeError(error_msg) from last_error

    def _retry_with_error(self, code: str, error: str) -> str:
        """Ask the LLM to fix broken generated code.

        Args:
            code: The code that failed
            error: The error message / traceback

        Returns:
            Corrected Python code
        """
        fix_prompt = build_fix_prompt(code, error)
        system_prompt = get_system_prompt()
        fixed = self.llm.generate_text(system_prompt, fix_prompt)
        return extract_code(fixed)

    @staticmethod
    def apply_metadata_to_resources(
        resources: list[dict[str, Any]],
        security: list[dict[str, Any]] | None = None,
        tag: list[dict[str, Any]] | None = None,
        profile: list[str] | None = None,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        """Apply metadata to a list of resources.

        Args:
            resources: List of FHIR resource dicts
            security: Security labels to add
            tag: Tags to add
            profile: Profile URLs to add
            source: Source system URI

        Returns:
            Modified resources with metadata
        """
        for resource in resources:
            if not any([security, tag, profile, source]):
                continue

            meta = resource.setdefault("meta", {})

            if security:
                existing = meta.get("security", [])
                # Deduplicate by (system, code) tuple
                seen = {(s.get("system"), s.get("code")) for s in existing}
                merged = list(existing)
                for s in security:
                    key = (s.get("system"), s.get("code"))
                    if key not in seen:
                        merged.append(s)
                        seen.add(key)
                meta["security"] = merged

            if tag:
                existing = meta.get("tag", [])
                seen = {(t.get("system"), t.get("code")) for t in existing}
                merged = list(existing)
                for t in tag:
                    key = (t.get("system"), t.get("code"))
                    if key not in seen:
                        merged.append(t)
                        seen.add(key)
                meta["tag"] = merged

            if profile:
                existing = meta.get("profile", [])
                # Deduplicate profile URLs
                seen_profiles = set(existing)
                merged = list(existing)
                for p in profile:
                    if p not in seen_profiles:
                        merged.append(p)
                        seen_profiles.add(p)
                meta["profile"] = merged

            if source:
                meta["source"] = source

        return resources
