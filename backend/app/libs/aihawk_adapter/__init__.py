"""
AIHawk Adapter for Hanggent

This module provides adapters to integrate AIHawk's resume/cover letter generation
functionality with Hanggent's existing LLM configuration.

Instead of using AIHawk's native langchain_openai integration, we inject
Hanggent's model configuration from Chat.model_platform/model_type.
"""
from app.libs.aihawk_adapter.llm_adapter import HanggentLLMAdapter, create_llm_from_chat_options
from app.libs.aihawk_adapter.resume_builder import AIHawkResumeBuilder

__all__ = [
    "HanggentLLMAdapter",
    "create_llm_from_chat_options",
    "AIHawkResumeBuilder",
]
