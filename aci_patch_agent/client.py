"""A single provider client; credentials never enter prompts or saved traces."""

import json
import os
from urllib import error, request

from .tools import TOOLS


DEFAULT_MODEL = "qwen/qwen3-next-80b-a3b-instruct"


class ModelError(RuntimeError):
    pass


class OpenRouterClient:
    def __init__(self, model=DEFAULT_MODEL, max_tokens=1200, temperature=0, tools=None):
        self.key = os.environ.get("OPENROUTER_API_KEY")
        if not self.key:
            raise ModelError("Set OPENROUTER_API_KEY in your environment.")
        self.model, self.max_tokens, self.temperature = model, max_tokens, temperature
        self.tools = tools if tools is not None else TOOLS

    def complete(self, messages):
        body = {"model": self.model, "messages": messages, "tools": self.tools,
                "tool_choice": "required", "temperature": self.temperature,
                "max_tokens": self.max_tokens}
        req = request.Request("https://openrouter.ai/api/v1/chat/completions",
                              data=json.dumps(body).encode(),
                              headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        try:
            with request.urlopen(req, timeout=90) as response:
                data = json.load(response)
            message = data["choices"][0]["message"]
            if not isinstance(message, dict):
                raise ValueError("invalid message")
            return {"message": {k: message[k] for k in ("role", "content", "tool_calls") if k in message},
                    "usage": data.get("usage") or {}, "model": data.get("model", self.model),
                    "provider": data.get("provider"), "id": data.get("id")}
        except error.HTTPError as failure:
            # Provider error bodies may echo requests; never log them or the Authorization header.
            raise ModelError(f"api_http_{failure.code}") from None
        except (OSError, ValueError, TypeError, KeyError, IndexError):
            raise ModelError("api_transport_or_response_error") from None
