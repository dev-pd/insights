"""Prompt registry — organized by family.

Submodules:
  app.llm.prompts.extraction — per-feedback insight extraction
  app.llm.prompts.summary    — aggregate dashboard summary

Import directly from the family you need:

    from app.llm.prompts.extraction import ACTIVE_PROMPT, ACTIVE_VERSION
    from app.llm.prompts.summary import (
        ACTIVE_PROMPT as ACTIVE_SUMMARY_PROMPT,
        ACTIVE_VERSION as ACTIVE_SUMMARY_VERSION,
    )

Each family's __init__.py owns the "which version is ACTIVE" decision.
Each version is its own immutable file — see app.llm.prompts.extraction
for the rationale (trace reproducibility).
"""
