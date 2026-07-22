"""
LLM Provider Utilities for HALAL Koperasi Agent
Supports: NVIDIA NIM (OpenAI-compatible), Groq, Ollama
"""

import os
import logging
from typing import Optional, List, Dict, Any, Literal, AsyncGenerator
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.callbacks import CallbackManagerForLLMRun

logger = logging.getLogger(__name__)


class LLMProviderConfig(BaseModel):
    """Configuration for an LLM provider"""
    provider: Literal["nvidia_nim", "groq", "ollama"]
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: int = 60


class ChatMessage(BaseModel):
    """Standardized chat message"""
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class LLMResponse(BaseModel):
    """Standardized LLM response"""
    content: str
    provider: str
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: str = "stop"


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self, config: LLMProviderConfig):
        self.config = config
    
    @abstractmethod
    async def chat(
        self,
        messages: List[ChatMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> LLMResponse | AsyncGenerator[LLMResponse, None]:
        """Chat completion"""
        pass
    
    @abstractmethod
    def get_langchain_model(self) -> BaseChatModel:
        """Get LangChain-compatible model"""
        pass


class NVIDIANIMProvider(BaseLLMProvider):
    """NVIDIA NIM Provider (OpenAI-compatible API)"""
    
    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                api_key=config.api_key or os.getenv("NVIDIA_NIM_API_KEY"),
                base_url=config.base_url or "https://integrate.api.nvidia.com/v1",
                timeout=config.timeout,
            )
            self.sync_client = None  # Lazy init
        except ImportError:
            raise ImportError("openai package required for NVIDIA NIM provider")
    
    def _get_sync_client(self):
        if self.sync_client is None:
            from openai import OpenAI
            self.sync_client = OpenAI(
                api_key=self.config.api_key or os.getenv("NVIDIA_NIM_API_KEY"),
                base_url=self.config.base_url or "https://integrate.api.nvidia.com/v1",
                timeout=self.config.timeout,
            )
        return self.sync_client
    
    def _convert_messages(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        result = []
        for msg in messages:
            if msg.role == "tool":
                result.append({
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id,
                })
            elif msg.tool_calls:
                result.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": msg.tool_calls,
                })
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result
    
    async def chat(
        self,
        messages: List[ChatMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> LLMResponse | AsyncGenerator[LLMResponse, None]:
        """Chat completion with NVIDIA NIM"""
        formatted_messages = self._convert_messages(messages)
        
        params = {
            "model": self.config.model,
            "messages": formatted_messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": stream,
        }
        
        if stream:
            return self._stream_chat(params)
        else:
            return await self._single_chat(params)
    
    async def _single_chat(self, params: Dict[str, Any]) -> LLMResponse:
        response = await self.client.chat.completions.create(**params)
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            provider="nvidia_nim",
            model=self.config.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            } if response.usage else None,
            finish_reason=choice.finish_reason or "stop",
        )
    
    async def _stream_chat(self, params: Dict[str, Any]) -> AsyncGenerator[LLMResponse, None]:
        stream = await self.client.chat.completions.create(**params)
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield LLMResponse(
                    content=chunk.choices[0].delta.content,
                    provider="nvidia_nim",
                    model=self.config.model,
                    finish_reason=chunk.choices[0].finish_reason or "stop",
                )
    
    def get_langchain_model(self) -> BaseChatModel:
        """Get LangChain-compatible model"""
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                api_key=self.config.api_key or os.getenv("NVIDIA_NIM_API_KEY"),
                base_url=self.config.base_url or "https://integrate.api.nvidia.com/v1",
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout,
            )
        except ImportError:
            raise ImportError("langchain-openai required for LangChain integration")


class GroqProvider(BaseLLMProvider):
    """Groq Provider (OpenAI-compatible API)"""
    
    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        try:
            from groq import AsyncGroq
            self.client = AsyncGroq(
                api_key=config.api_key or os.getenv("GROQ_API_KEY"),
                timeout=config.timeout,
            )
        except ImportError:
            raise ImportError("groq package required for Groq provider")
    
    def _convert_messages(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        result = []
        for msg in messages:
            if msg.role == "tool":
                result.append({
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id,
                })
            elif msg.tool_calls:
                result.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": msg.tool_calls,
                })
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result
    
    async def chat(
        self,
        messages: List[ChatMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> LLMResponse | AsyncGenerator[LLMResponse, None]:
        formatted_messages = self._convert_messages(messages)
        
        params = {
            "model": self.config.model,
            "messages": formatted_messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": stream,
        }
        
        if stream:
            return self._stream_chat(params)
        else:
            return await self._single_chat(params)
    
    async def _single_chat(self, params: Dict[str, Any]) -> LLMResponse:
        response = await self.client.chat.completions.create(**params)
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            provider="groq",
            model=self.config.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            } if response.usage else None,
            finish_reason=choice.finish_reason or "stop",
        )
    
    async def _stream_chat(self, params: Dict[str, Any]) -> AsyncGenerator[LLMResponse, None]:
        stream = await self.client.chat.completions.create(**params)
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield LLMResponse(
                    content=chunk.choices[0].delta.content,
                    provider="groq",
                    model=self.config.model,
                    finish_reason=chunk.choices[0].finish_reason or "stop",
                )
    
    def get_langchain_model(self) -> BaseChatModel:
        try:
            from langchain_groq import ChatGroq
            return ChatGroq(
                api_key=self.config.api_key or os.getenv("GROQ_API_KEY"),
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout,
            )
        except ImportError:
            raise ImportError("langchain-groq required for LangChain integration")


class OllamaProvider(BaseLLMProvider):
    """Ollama Local Provider"""
    
    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        try:
            from ollama import AsyncClient
            self.client = AsyncClient(
                host=config.base_url or "http://localhost:11434",
                timeout=config.timeout,
            )
        except ImportError:
            raise ImportError("ollama package required for Ollama provider")
    
    def _convert_messages(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        result = []
        for msg in messages:
            if msg.role == "tool":
                result.append({
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id,
                })
            elif msg.tool_calls:
                result.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": msg.tool_calls,
                })
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result
    
    async def chat(
        self,
        messages: List[ChatMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> LLMResponse | AsyncGenerator[LLMResponse, None]:
        formatted_messages = self._convert_messages(messages)
        
        options = {
            "temperature": temperature or self.config.temperature,
            "num_predict": max_tokens or self.config.max_tokens,
        }
        
        if stream:
            return self._stream_chat(formatted_messages, options)
        else:
            return await self._single_chat(formatted_messages, options)
    
    async def _single_chat(self, messages: List[Dict], options: Dict) -> LLMResponse:
        response = await self.client.chat(
            model=self.config.model,
            messages=messages,
            options=options,
        )
        return LLMResponse(
            content=response.get("message", {}).get("content", ""),
            provider="ollama",
            model=self.config.model,
            finish_reason="stop",
        )
    
    async def _stream_chat(self, messages: List[Dict], options: Dict) -> AsyncGenerator[LLMResponse, None]:
        stream = await self.client.chat(
            model=self.config.model,
            messages=messages,
            options=options,
            stream=True,
        )
        async for chunk in stream:
            if chunk.get("message", {}).get("content"):
                yield LLMResponse(
                    content=chunk["message"]["content"],
                    provider="ollama",
                    model=self.config.model,
                    finish_reason="stop",
                )
    
    def get_langchain_model(self) -> BaseChatModel:
        try:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                base_url=self.config.base_url or "http://localhost:11434",
                model=self.config.model,
                temperature=self.config.temperature,
                num_predict=self.config.max_tokens,
                timeout=self.config.timeout,
            )
        except ImportError:
            raise ImportError("langchain-ollama required for LangChain integration")


class LLMProviderFactory:
    """Factory for creating LLM providers"""
    
    _providers: Dict[str, BaseLLMProvider] = {}
    
    @classmethod
    def create_provider(cls, config: LLMProviderConfig) -> BaseLLMProvider:
        if config.provider == "nvidia_nim":
            return NVIDIANIMProvider(config)
        elif config.provider == "groq":
            return GroqProvider(config)
        elif config.provider == "ollama":
            return OllamaProvider(config)
        else:
            raise ValueError(f"Unknown provider: {config.provider}")
    
    @classmethod
    def get_provider(
        cls,
        provider: Literal["nvidia_nim", "groq", "ollama"] = "nvidia_nim",
        model: Optional[str] = None,
    ) -> BaseLLMProvider:
        """Get or create provider with default config from settings"""
        from halal_koperasi_agent.config import settings
        
        cache_key = f"{provider}:{model or ''}"
        if cache_key in cls._providers:
            return cls._providers[cache_key]
        
        if provider == "nvidia_nim":
            config = LLMProviderConfig(
                provider="nvidia_nim",
                api_key=settings.NVIDIA_API_KEY,
                base_url=settings.NVIDIA_BASE_URL,
                model=model or settings.LLM_MODEL,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
                timeout=settings.LLM_TIMEOUT,
            )
        elif provider == "groq":
            config = LLMProviderConfig(
                provider="groq",
                api_key=settings.GROQ_API_KEY,
                model=model or settings.GROQ_MODEL,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
                timeout=settings.LLM_TIMEOUT,
            )
        elif provider == "ollama":
            config = LLMProviderConfig(
                provider="ollama",
                base_url=settings.OLLAMA_HOST,
                model=model or settings.OLLAMA_LLM_MODEL,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
                timeout=settings.OLLAMA_TIMEOUT,
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        provider_instance = cls.create_provider(config)
        cls._providers[cache_key] = provider_instance
        return provider_instance
    
    @classmethod
    def clear_cache(cls):
        cls._providers.clear()


# Convenience functions
async def chat_completion(
    messages: List[ChatMessage],
    provider: Literal["nvidia_nim", "groq", "ollama"] = "nvidia_nim",
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stream: bool = False,
) -> LLMResponse | AsyncGenerator[LLMResponse, None]:
    """Quick chat completion with any provider"""
    llm_provider = LLMProviderFactory.get_provider(provider, model)
    return await llm_provider.chat(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
    )


def get_langchain_model(
    provider: Literal["nvidia_nim", "groq", "ollama"] = "nvidia_nim",
    model: Optional[str] = None,
) -> BaseChatModel:
    """Get LangChain-compatible model"""
    llm_provider = LLMProviderFactory.get_provider(provider, model)
    return llm_provider.get_langchain_model()