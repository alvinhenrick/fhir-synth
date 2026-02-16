"""Tests for code generator."""

from fhir_synth.code_generator import CodeGenerator
from fhir_synth.llm import MockLLMProvider


def test_code_generator_extracts_code_block():
    response = """Here is code:\n```python\nprint('hi')\n```\n"""
    llm = MockLLMProvider(response=response)
    code_gen = CodeGenerator(llm)

    code = code_gen.generate_code_from_prompt("test")

    assert "print('hi')" in code


def test_code_generator_executes_generated_code():
    code = """
from fhir.resources.R4B import patient

def generate_resources():
    p = patient.Patient(id='p1', name=[{'given':['A'], 'family':'B'}])
    return [p.model_dump()]
"""
    llm = MockLLMProvider(response=code)
    code_gen = CodeGenerator(llm)

    generated_code = code_gen.generate_code_from_prompt("test")
    resources = code_gen.execute_generated_code(generated_code)

    assert len(resources) == 1
    assert resources[0]["id"] == "p1"

