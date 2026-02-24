"""
Prompts module for LLM interactions.

Contains prompt templates for various extraction and generation tasks.
"""
from app.prompts.resume_extraction import (
    get_extraction_messages,
    get_extraction_prompt_tuple,
    get_validation_messages,
)

__all__ = [
    "get_extraction_messages",
    "get_extraction_prompt_tuple",
    "get_validation_messages",
]
