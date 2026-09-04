"""Backward-compatible import for the application pipeline."""

from .application.pipeline import SyslogPipeline

__all__ = ["SyslogPipeline"]
