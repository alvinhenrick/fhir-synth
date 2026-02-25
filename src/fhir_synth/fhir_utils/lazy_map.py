"""Lazy loading resource map for FHIR resource classes."""

from collections.abc import Iterator

from pydantic import BaseModel

from fhir_synth.fhir_spec import get_resource_class, resource_names


def _get_fhir_class(name: str) -> type[BaseModel]:
    """Lazy wrapper — only imports the module when first accessed."""
    return get_resource_class(name)


class _LazyResourceMap(dict[str, type[BaseModel]]):
    """Dict that lazily loads FHIR resource classes on first access."""

    def __init__(self) -> None:
        super().__init__()
        self._names = set(resource_names())

    def __contains__(self, key: object) -> bool:
        return key in self._names

    def __getitem__(self, key: str) -> type[BaseModel]:
        if key not in self._names:
            raise KeyError(key)
        if not super().__contains__(key):
            super().__setitem__(key, _get_fhir_class(key))
        return super().__getitem__(key)

    def keys(self) -> set[str]:  # type: ignore[override]
        return self._names

    def __iter__(self) -> Iterator[str]:
        return iter(self._names)

    def __len__(self) -> int:
        return len(self._names)


FHIR_RESOURCE_CLASSES: dict[str, type[BaseModel]] = _LazyResourceMap()
