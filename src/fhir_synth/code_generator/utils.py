"""Utilities for code extraction and manipulation."""


def extract_code(response: str) -> str:
    """Extract Python code from LLM response.

    Handles Markdown code blocks and plain text responses.

    Args:
        response: LLM response text

    Returns:
        Extracted Python code
    """
    # Try to extract from Markdown code block
    if "```python" in response:
        start = response.find("```python") + 9
        end = response.find("```", start)
        if end > start:
            return response[start:end].strip()

    if "```" in response:
        start = response.find("```") + 3
        end = response.find("```", start)
        if end > start:
            code = response[start:end].strip()
            # Remove language specifier if present
            lines = code.split("\n")
            if (
                lines[0]
                and not lines[0].startswith("def ")
                and not lines[0].startswith("import")
            ):
                code = "\n".join(lines[1:])
            return code

    return response.strip()

