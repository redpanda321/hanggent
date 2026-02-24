"""
LLM Adapter for AIHawk integration with Hanggent

This module creates LangChain-compatible LLM instances using Hanggent's
model configuration (model_platform, model_type, api_key) instead of
AIHawk's default OpenAI configuration.
"""
import os
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from app.model.chat import Chat
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("aihawk_llm_adapter")


class HanggentLLMAdapter:
    """
    Adapter to create LangChain LLM instances from Hanggent's Chat options.
    
    AIHawk uses LangChain's ChatOpenAI internally. This adapter creates
    compatible LLM instances using Hanggent's model configuration.
    """
    
    # Map Hanggent model platforms to LangChain model classes
    PLATFORM_MAP = {
        "openai": "langchain_openai.ChatOpenAI",
        "anthropic": "langchain_anthropic.ChatAnthropic",
        "google": "langchain_google_genai.ChatGoogleGenerativeAI",
        "ollama": "langchain_ollama.ChatOllama",
    }
    
    def __init__(self, chat_options: Chat):
        self.chat_options = chat_options
        self.model_platform = chat_options.model_platform.lower()
        self.model_type = chat_options.model_type
        self.api_key = chat_options.api_key
        self.api_url = getattr(chat_options, 'api_url', None)
    
    def create_llm(self, temperature: float = 0.4) -> BaseChatModel:
        """
        Create a LangChain chat model based on Hanggent's configuration.
        
        Args:
            temperature: Model temperature (default 0.4 for resume generation)
            
        Returns:
            BaseChatModel: A LangChain-compatible chat model instance
        """
        logger.info(f"Creating LLM for platform: {self.model_platform}, model: {self.model_type}")
        
        if self.model_platform in ["openai", "openrouter"]:
            return self._create_openai_model(temperature)
        elif self.model_platform == "anthropic":
            return self._create_anthropic_model(temperature)
        elif self.model_platform == "google":
            return self._create_google_model(temperature)
        elif self.model_platform == "ollama":
            return self._create_ollama_model(temperature)
        else:
            # Default to OpenAI-compatible interface
            logger.warning(f"Unknown platform {self.model_platform}, falling back to OpenAI interface")
            return self._create_openai_model(temperature)
    
    def _create_openai_model(self, temperature: float) -> ChatOpenAI:
        """Create OpenAI or OpenAI-compatible model"""
        kwargs = {
            "model_name": self.model_type,
            "openai_api_key": self.api_key,
            "temperature": temperature,
        }
        
        # Handle custom API URLs (e.g., OpenRouter, Azure)
        if self.api_url:
            kwargs["openai_api_base"] = self.api_url
            
        return ChatOpenAI(**kwargs)
    
    def _create_anthropic_model(self, temperature: float) -> BaseChatModel:
        """Create Anthropic Claude model"""
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=self.model_type,
                anthropic_api_key=self.api_key,
                temperature=temperature,
            )
        except ImportError:
            logger.warning("langchain_anthropic not installed, falling back to OpenAI")
            return self._create_openai_model(temperature)
    
    def _create_google_model(self, temperature: float) -> BaseChatModel:
        """Create Google Gemini model"""
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=self.model_type,
                google_api_key=self.api_key,
                temperature=temperature,
            )
        except ImportError:
            logger.warning("langchain_google_genai not installed, falling back to OpenAI")
            return self._create_openai_model(temperature)
    
    def _create_ollama_model(self, temperature: float) -> BaseChatModel:
        """Create Ollama local model"""
        try:
            from langchain_ollama import ChatOllama
            base_url = self.api_url or "http://localhost:11434"
            return ChatOllama(
                model=self.model_type,
                base_url=base_url,
                temperature=temperature,
            )
        except ImportError:
            logger.warning("langchain_ollama not installed, falling back to OpenAI")
            return self._create_openai_model(temperature)
    
    def get_api_key(self) -> str:
        """Get the API key for AIHawk modules that need it directly"""
        return self.api_key


def create_llm_from_chat_options(
    chat_options: Chat,
    temperature: float = 0.4
) -> BaseChatModel:
    """
    Convenience function to create an LLM from Chat options.
    
    Args:
        chat_options: Hanggent Chat model with model configuration
        temperature: Model temperature
        
    Returns:
        BaseChatModel: A LangChain-compatible chat model
    """
    adapter = HanggentLLMAdapter(chat_options)
    return adapter.create_llm(temperature)


def inject_llm_into_aihawk(chat_options: Chat) -> str:
    """
    Set up environment for AIHawk to use Hanggent's API key.
    
    AIHawk reads OPENAI_API_KEY from environment. This function
    temporarily sets it from Hanggent's configuration.
    
    Args:
        chat_options: Hanggent Chat model with API configuration
        
    Returns:
        str: The API key that was set
    """
    api_key = chat_options.api_key
    os.environ["OPENAI_API_KEY"] = api_key
    
    if chat_options.api_url:
        os.environ["OPENAI_API_BASE"] = chat_options.api_url
    
    return api_key
