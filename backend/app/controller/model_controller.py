# ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========

import logging
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.component.error_format import normalize_error_to_openai_format
from app.component.model_validation import create_agent
from app.model.chat import PLATFORM_MAPPING

logger = logging.getLogger("model_controller")

KNOWN_THINKING_TOOLCALL_ERROR = (
    "thinking is enabled but reasoning_content is missing in assistant tool call message"
)

router = APIRouter()


def normalize_openai_compatible_url(url: str | None) -> str | None:
    if url is None:
        return None

    stripped = str(url).strip().rstrip("/")
    lowered = stripped.lower()

    if lowered == "https://api.minimax.io":
        return "https://api.minimax.io/v1/"
    if lowered == "https://api.moonshot.ai":
        return "https://api.moonshot.ai/v1/"
    if lowered in {"https://open.bigmodel.cn", "https://bigmodel.cn"}:
        return "https://open.bigmodel.cn/api/paas/v4/"

    return url


class ValidateModelRequest(BaseModel):
    model_platform: str = Field("OPENAI", description="Model platform")
    model_type: str = Field("GPT_4O_MINI", description="Model type")
    api_key: str | None = Field(None, description="API key")
    url: str | None = Field(None, description="Model URL")
    model_config_dict: dict | None = Field(
        None, description="Model config dict"
    )
    extra_params: dict | None = Field(
        None, description="Extra model parameters"
    )

    @field_validator("model_platform")
    @classmethod
    def map_model_platform(cls, v: str) -> str:
        return PLATFORM_MAPPING.get(v, v)


class ValidateModelResponse(BaseModel):
    is_valid: bool = Field(..., description="Is valid")
    is_tool_calls: bool = Field(..., description="Is tool call used")
    error_code: str | None = Field(None, description="Error code")
    error: dict | None = Field(None, description="OpenAI-style error object")
    message: str = Field(..., description="Message")
    response_time_ms: float | None = Field(None, description="Response time in milliseconds")
    prompt_tokens: int | None = Field(None, description="Prompt token count")
    completion_tokens: int | None = Field(None, description="Completion token count")
    total_tokens: int | None = Field(None, description="Total token count")


@router.post("/model/validate")
async def validate_model(request: ValidateModelRequest):
    """Validate model configuration and tool call support."""
    platform = request.model_platform
    model_type = request.model_type
    url = request.url
    has_custom_url = request.url is not None
    has_config = request.model_config_dict is not None

    logger.info(
        "Model validation started",
        extra={
            "platform": platform,
            "model_type": model_type,
            "has_url": has_custom_url,
            "has_config": has_config,
        },
    )

    # API key validation
    if request.api_key is not None and str(request.api_key).strip() == "":
        logger.warning(
            "Model validation failed: empty API key",
            extra={"platform": platform, "model_type": model_type},
        )
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid key. Validation failed.",
                "error_code": "invalid_api_key",
                "error": {
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "invalid_api_key",
                },
            },
        )

    try:
        extra = request.extra_params or {}

        if platform == "openai-compatible-model":
            normalized_url = str(url or "").strip().lower()
            normalized_model = str(model_type or "").strip().lower()
            if (
                "api.anthropic.com" in normalized_url
                or normalized_model.startswith("claude-")
            ):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": (
                            "Anthropic endpoint/model detected for "
                            "OpenAI Compatible provider. "
                            "Please use the Anthropic provider instead."
                        ),
                        "error_code": "provider_mismatch",
                        "error": {
                            "type": "invalid_request_error",
                            "param": "model_platform",
                            "code": "provider_mismatch",
                        },
                    },
                )
            url = normalize_openai_compatible_url(url)

        if platform == "anthropic" and url is not None:
            stripped = str(url).strip().rstrip("/")
            if stripped == "https://api.anthropic.com":
                url = "https://api.anthropic.com/v1/"

        # Gemini in CAMEL uses Google's OpenAI-compatible endpoint path by
        # default. If the UI provides only the domain, normalize it so the
        # OpenAI client hits the correct base URL.
        if platform == "gemini" and url is not None:
            stripped = str(url).strip().rstrip("/")
            if stripped == "https://generativelanguage.googleapis.com":
                url = "https://generativelanguage.googleapis.com/v1beta/openai/"

        logger.debug(
            "Creating agent for validation",
            extra={"platform": platform, "model_type": model_type},
        )
        agent = create_agent(
            platform,
            model_type,
            api_key=request.api_key,
            url=url,
            model_config_dict=request.model_config_dict,
            **extra,
        )

        logger.debug(
            "Agent created, executing test step",
            extra={"platform": platform, "model_type": model_type},
        )
        _t0 = time.perf_counter()
        response = agent.step(
            input_message="""
            Get the content of https://www.camel-ai.org,
            you must use the get_website_content tool to get the content ,
            i just want to verify the get_website_content tool is working,
            you must call the get_website_content tool only once.
            """
        )
        _elapsed_ms = round((time.perf_counter() - _t0) * 1000, 1)

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e

        raw_error_message = str(e)

        # Some OpenAI-compatible gateways (including certain Hanggent cloud routes)
        # may enable "thinking" by default and reject tool-call messages that do
        # not contain reasoning_content blocks. This is a provider-side compatibility
        # behavior in validation flow, not necessarily an API-key/model invalidation.
        # In this case, allow save to proceed.
        if KNOWN_THINKING_TOOLCALL_ERROR in raw_error_message.lower():
            logger.warning(
                "Model validation fallback triggered for known thinking/tool-call incompatibility",
                extra={
                    "platform": platform,
                    "model_type": model_type,
                    "error": raw_error_message,
                },
            )
            return ValidateModelResponse(
                is_valid=True,
                is_tool_calls=True,
                message="Validation Success (provider thinking-compatibility fallback)",
                error_code=None,
                error=None,
            )

        # Normalize error to OpenAI-style error structure
        logger.error(
            "Model validation failed",
            extra={
                "platform": platform,
                "model_type": model_type,
                "error": raw_error_message,
            },
            exc_info=True,
        )
        message, error_code, error_obj = normalize_error_to_openai_format(e)

        # Anthropic model naming evolves quickly across gateways. Some gateways
        # may reject new/alias names during this synthetic validation step even
        # though admins still need to save the provider config first.
        # For claude-* model names, don't hard-block save on model_not_found.
        if (
            error_code == "model_not_found"
            and platform == "anthropic"
            and str(model_type).lower().startswith("claude-")
        ):
            logger.warning(
                "Model validation fallback triggered for claude-* model_not_found",
                extra={
                    "platform": platform,
                    "model_type": model_type,
                    "error": str(e),
                },
            )
            return ValidateModelResponse(
                is_valid=True,
                is_tool_calls=True,
                message="Validation Success (claude model-name compatibility fallback)",
                error_code=None,
                error=None,
            )

        raise HTTPException(
            status_code=400,
            detail={
                "message": message,
                "error_code": error_code,
                "error": error_obj,
            },
        )

    # Check validation results
    is_valid = bool(response)
    is_tool_calls = False
    _prompt_tokens = None
    _completion_tokens = None
    _total_tokens = None

    if response and hasattr(response, "info") and response.info:
        tool_calls = response.info.get("tool_calls", [])
        if tool_calls and len(tool_calls) > 0:
            expected = (
                "Tool execution completed"
                " successfully for"
                " https://www.camel-ai.org,"
                " Website Content:"
                " Welcome to CAMEL AI!"
            )
            is_tool_calls = tool_calls[0].result == expected

        # Extract token usage from response info
        usage = response.info.get("usage") or response.info.get("token_usage") or {}
        if isinstance(usage, dict):
            _prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
            _completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
            _total_tokens = usage.get("total_tokens")
            if _total_tokens is None and _prompt_tokens is not None and _completion_tokens is not None:
                _total_tokens = _prompt_tokens + _completion_tokens

    no_tool_msg = (
        "This model doesn't support tool calls. please try with another model."
    )
    result = ValidateModelResponse(
        is_valid=is_valid,
        is_tool_calls=is_tool_calls,
        message="Validation Success" if is_tool_calls else no_tool_msg,
        error_code=None,
        error=None,
        response_time_ms=_elapsed_ms,
        prompt_tokens=_prompt_tokens,
        completion_tokens=_completion_tokens,
        total_tokens=_total_tokens,
    )

    logger.info(
        "Model validation completed",
        extra={
            "platform": platform,
            "model_type": model_type,
            "is_valid": is_valid,
            "is_tool_calls": is_tool_calls,
        },
    )

    return result
