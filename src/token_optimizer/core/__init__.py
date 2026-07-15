"""Core infrastructure shared across the application.

Cross-cutting concerns that the feature packages build on: configuration
([config]), the Claude client and response cache ([llm]), and per-run logging
([run_log]). Nothing here is domain-specific.
"""
