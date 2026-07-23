"""Compatibility imports for core plugin dialogue interception."""
# Author: Clive Bostock
# Date: 17-Jul-2026
# Description: Re-exports the shared plugin routing interception implementation.

from __future__ import annotations

from model.plugin_routing.interception import (
    CompiledInterceptMetadata as CompiledInterceptMetadata,
)
from model.plugin_routing.interception import CompiledInterceptRule as CompiledInterceptRule
from model.plugin_routing.interception import InterceptMatch as PluginInterceptMatch
from model.plugin_routing.interception import InterceptMetadata as PluginInterceptMetadata
from model.plugin_routing.interception import (
    PluginInterceptionMetadataError as PluginInterceptMetadataError,
)

__all__ = [
    "CompiledInterceptMetadata",
    "CompiledInterceptRule",
    "PluginInterceptMatch",
    "PluginInterceptMetadata",
    "PluginInterceptMetadataError",
]
