"""
PropertyKING — Provider Registry

Add a new data source by writing one module here and registering it below.
Nothing else in the codebase needs to change.
"""

from typing import Dict, List, Type

from app.services.providers.base import (
    BaseProvider, NormalizedProperty, NormalizedImage, ProviderFilters
)
from app.services.providers.mock_provider import MockProvider
from app.services.providers.reefapi_zillow import ReefZillowProvider


PROVIDERS: Dict[str, Type[BaseProvider]] = {
    MockProvider.name: MockProvider,
    ReefZillowProvider.name: ReefZillowProvider,
}

DEFAULT_PROVIDER = MockProvider.name


def get_provider(name: str) -> BaseProvider:
    """Instantiate a provider by name, falling back to the demo provider."""
    provider_cls = PROVIDERS.get(name) or PROVIDERS[DEFAULT_PROVIDER]
    return provider_cls()


def list_providers() -> List[dict]:
    """Provider metadata for the admin panel dropdown."""
    return [cls.info() for cls in PROVIDERS.values()]


__all__ = [
    "BaseProvider", "NormalizedProperty", "NormalizedImage", "ProviderFilters",
    "PROVIDERS", "DEFAULT_PROVIDER", "get_provider", "list_providers",
]
