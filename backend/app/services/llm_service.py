"""Provider-agnostic LLM layer. Swap the body of complete() to change providers."""
import re
import anthropic
from openai import APIConnectionError as OpenRouterConnectionError
from openai import APIStatusError as OpenRouterStatusError
from openai import APITimeoutError as OpenRouterTimeoutError
from openai import OpenAI
from .. import config

class LLMError(Exception):
    def __init__(self, message, code="request_failed"):
        super().__init__(message)
        self.code = code

_client = None
def _get():
    global _client
    if config.LLM_PROVIDER == "openrouter":
        key = config.OPENROUTER_API_KEY
        if not key or key.strip() in {"your_key_here", "change-me"}:
            raise LLMError("OPENROUTER_API_KEY is not configured in backend/.env.", code="missing_api_key")
        if _client is None or not isinstance(_client, OpenAI):
            _client = OpenAI(
                api_key=key,
                base_url="https://openrouter.ai/api/v1",
                timeout=60,
                max_retries=2,
                default_headers={"HTTP-Referer": "http://localhost:5173", "X-Title": "CareerLens AI"},
            )
        return _client
    if config.LLM_PROVIDER != "anthropic":
        raise LLMError("LLM_PROVIDER must be 'anthropic' or 'openrouter'.", code="invalid_provider")
    if not config.ANTHROPIC_API_KEY or config.ANTHROPIC_API_KEY.strip() in {"your_key_here", "change-me"}:
        raise LLMError("ANTHROPIC_API_KEY is not configured on the server.", code="missing_api_key")
    if _client is None or not isinstance(_client, anthropic.Anthropic):
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=60, max_retries=2)
    return _client

def complete(system, messages, max_tokens=2000, json_mode=False):
    if config.LLM_PROVIDER == "openrouter":
        try:
            params = {
                "model": config.MODEL,
                "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, *messages],
            }
            if json_mode:
                params["response_format"] = {"type": "json_object"}
            try:
                response = _get().chat.completions.create(**params)
            except OpenRouterStatusError as e:
                # Some free models do not implement JSON response_format. The
                # system prompt already constrains output, so retry without it.
                if not json_mode or e.status_code != 400:
                    raise
                params.pop("response_format", None)
                response = _get().chat.completions.create(**params)
            text = response.choices[0].message.content
            if not text:
                raise LLMError("OpenRouter returned an empty response.", code="empty_response")
            return text
        except OpenRouterStatusError as e:
            status = e.status_code
            request_id = getattr(e, "request_id", None)
            suffix = f" (request ID: {request_id})" if request_id else ""
            if status == 401:
                raise LLMError("OpenRouter rejected OPENROUTER_API_KEY. Check the key in backend/.env.", code="authentication") from e
            if status == 402:
                raise LLMError("OpenRouter reports insufficient credits. Check your OpenRouter account balance.", code="billing") from e
            if status == 403:
                raise LLMError("OpenRouter denied access to this model. Check model access and provider settings.", code="permission") from e
            if status == 404:
                raise LLMError(f"OpenRouter could not find model '{config.MODEL}'. Set OPENROUTER_MODEL to a supported model ID.", code="model_not_found") from e
            if status == 429:
                raise LLMError("OpenRouter rate limit reached. Try again shortly or check your account limits.", code="rate_limit") from e
            raise LLMError(f"OpenRouter request failed (HTTP {status}).{suffix}", code="provider_error") from e
        except OpenRouterTimeoutError as e:
            raise LLMError("The OpenRouter request timed out. Please try again.", code="timeout") from e
        except OpenRouterConnectionError as e:
            raise LLMError("Could not connect to OpenRouter. Check your network and try again.", code="connection") from e
    try:
        r = _get().messages.create(model=config.MODEL, max_tokens=max_tokens, system=system, messages=messages)
        return "".join(b.text for b in r.content if b.type == "text")
    except anthropic.AuthenticationError as e:
        raise LLMError("Anthropic rejected the API key. It may be invalid, revoked, expired, or overridden by an exported environment variable.", code="authentication") from e
    except anthropic.PermissionDeniedError as e:
        raise LLMError("The Anthropic account or API key does not have permission to use this model.", code="permission") from e
    except anthropic.NotFoundError as e:
        raise LLMError(f"Anthropic could not find model '{config.MODEL}'. Check ANTHROPIC_MODEL.", code="model_not_found") from e
    except anthropic.RateLimitError as e:
        raise LLMError("Anthropic rate limit or spending limit reached. Check your Console usage and try again shortly.", code="rate_limit") from e
    except anthropic.APITimeoutError as e:
        raise LLMError("The Anthropic request timed out. Please try again.", code="timeout") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Could not connect to Anthropic. Check the network connection and try again.", code="connection") from e
    except anthropic.APIError as e:
        request_id = getattr(e, "request_id", None)
        suffix = f" (request ID: {request_id})" if request_id else ""
        raise LLMError(f"Anthropic request failed ({e.__class__.__name__}).{suffix}", code="provider_error") from e

def complete_json(system, user, model_cls, max_tokens=3500):
    text = complete(system + "\nRespond with ONLY one valid JSON object, no prose or code fences.",
                    [{"role": "user", "content": user}], max_tokens, json_mode=True)
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return model_cls.model_validate_json(m.group(0))
    except Exception:
        raise LLMError("The model returned output we could not validate.", code="invalid_output")
