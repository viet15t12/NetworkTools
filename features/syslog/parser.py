"""Backward-compatible entry point for the Cisco-aware parser."""

from .parsing.parser import parse_message

__all__ = ["parse_message"]
