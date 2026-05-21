"""Surface-agnostic progress reporter for generation pipelines.

The CLI and MCP server both want to emit the same status messages
(``📂 Run: ...``, ``🎯 Selected N/M skills``, ``✅ FHIR validation`` …) but
through different transports — ``typer.echo`` for the CLI, MCP
``notifications/message`` and ``notifications/progress`` for the MCP server.

This module defines a single :class:`ProgressReporter` protocol with three
implementations:

- :class:`NullReporter` — drops all messages (default for library use).
- :class:`TyperReporter` — writes to stdout/stderr via ``typer.echo`` (CLI).
- :class:`MCPReporter` — sends notifications via a FastMCP ``Context``.

Pipelines accept any ``ProgressReporter`` and stay decoupled from the surface
they're invoked from.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ProgressReporter(Protocol):
    """Async progress/log sink consumed by generation pipelines."""

    async def info(self, message: str) -> None: ...
    async def warning(self, message: str) -> None: ...
    async def error(self, message: str) -> None: ...
    async def progress(self, step: int, total: int, message: str) -> None: ...


class NullReporter:
    """No-op reporter — drops every message. Use when no surface is attached."""

    async def info(self, message: str) -> None:
        return

    async def warning(self, message: str) -> None:
        return

    async def error(self, message: str) -> None:
        return

    async def progress(self, step: int, total: int, message: str) -> None:
        return


class TyperReporter:
    """Reporter that writes to stdout/stderr via ``typer.echo``.

    Suitable for the CLI. ``progress()`` is intentionally a no-op — the CLI
    already prints granular status messages, and a progress bar would compete
    with them.
    """

    async def info(self, message: str) -> None:
        import typer

        typer.echo(message)

    async def warning(self, message: str) -> None:
        import typer

        typer.echo(message, err=True)

    async def error(self, message: str) -> None:
        import typer

        typer.echo(message, err=True)

    async def progress(self, step: int, total: int, message: str) -> None:
        return


class MCPReporter:
    """Reporter that emits MCP notifications via a FastMCP ``Context``.

    Pass the ``ctx`` parameter received by an MCP tool. If ``ctx`` is ``None``
    (tool invoked outside an MCP request — e.g. direct unit tests), the
    reporter degrades to a no-op.
    """

    def __init__(self, ctx: Any | None) -> None:
        self._ctx = ctx

    async def info(self, message: str) -> None:
        if self._ctx is not None:
            await self._ctx.info(message)

    async def warning(self, message: str) -> None:
        if self._ctx is not None:
            await self._ctx.warning(message)

    async def error(self, message: str) -> None:
        if self._ctx is not None:
            await self._ctx.error(message)

    async def progress(self, step: int, total: int, message: str) -> None:
        if self._ctx is not None:
            await self._ctx.report_progress(progress=step, total=total, message=message)


__all__ = [
    "MCPReporter",
    "NullReporter",
    "ProgressReporter",
    "TyperReporter",
]
