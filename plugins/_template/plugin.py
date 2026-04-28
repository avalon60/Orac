"""Illustrative starter module for an Orac plugin implementation."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Provides a lightweight example structure for future Orac plugin code.

from __future__ import annotations


class TemplatePlugin:
    """Illustrative plugin class showing a modest starting shape.

    This is not a framework base class and is not currently used by Orac runtime
    loading. It exists only as a developer-facing example of where plugin code
    might live relative to the plugin manifest.
    """

    def __init__(self) -> None:
        self.name = "template"

    def describe(self) -> str:
        """Returns a short human-readable description."""
        return "Illustrative Orac plugin template."
