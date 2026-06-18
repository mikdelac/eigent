# ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========
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
# ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========

import logging
from typing import Annotated, Any, Final

from pydantic import BeforeValidator

logger = logging.getLogger("model_platform")

PLATFORM_ALIAS_MAPPING: Final[dict[str, str]] = {
    "z.ai": "zhipuai",
    "ModelArk": "openai-compatible-model",
    "grok": "openai-compatible-model",
    "ernie": "qianfan",
    "llama.cpp": "openai-compatible-model",
    "nebius": "openai-compatible-model",
    "orcarouter": "openai-compatible-model",
}

# Bedrock Converse requires a region during model initialization.
BEDROCK_CONVERSE_REGION: Final[str] = "us-west-2"

# Azure OpenAI requires an api_version. The cloud proxy accepts any modern
# version; this default keeps cloud-mode requests working when the frontend
# does not surface api_version in extra_params.
AZURE_DEFAULT_API_VERSION: Final[str] = "2024-10-21"


_bedrock_compat_installed = False


def patch_bedrock_converse_compat() -> None:
    """Install Camel ``AWSBedrockConverseModel`` compatibility shims.

    Bedrock Converse is stricter than the OpenAI/Anthropic native APIs about
    request shapes, so a couple of values that Camel emits are accepted
    everywhere else but rejected by Bedrock. These shims patch Camel
    process-wide, so they belong at Brain startup (see
    :func:`patch_bedrock_converse_compat` callers) rather than in the
    per-agent hot path. Idempotent and a no-op when Camel's Bedrock model is
    unavailable.

    - **Tool-result encoding.** ``_parse_json_or_text`` puts JSON arrays
      straight into ``toolResult.content[].json``. Bedrock requires that
      field to be a JSON *object*, rejecting arrays with::

          ValidationException: ... toolResult.content.0.json is invalid.
          Provide a json object for the field and try again.

      Tools that return a top-level list (e.g. the Odoo MCP
      ``search_records``/``aggregate_records`` tools, or the MCP search
      toolkit) trip this on every call, so array values are wrapped as
      ``{"result": [...]}``.
    - **Tool descriptions.** ``_convert_openai_tools_to_bedrock`` forwards a
      tool's description verbatim, but Bedrock requires
      ``toolSpec.description`` to be a non-empty string. A toolkit method that
      overrides its parent without a docstring produces an empty description
      and crashes the request (``ParamValidationError`` on ``toolConfig``);
      empty descriptions are backfilled from the tool name here so a single
      missing docstring can never break a Bedrock conversation.
    """
    global _bedrock_compat_installed
    if _bedrock_compat_installed:
        return
    try:
        from camel.models.aws_bedrock_converse_model import (
            AWSBedrockConverseModel,
        )
    except Exception:
        return

    _original_parse = AWSBedrockConverseModel._parse_json_or_text

    def _parse_json_or_text(value: Any) -> dict:
        out = _original_parse(value)
        if isinstance(out, dict) and isinstance(out.get("json"), list):
            return {"json": {"result": out["json"]}}
        return out

    AWSBedrockConverseModel._parse_json_or_text = staticmethod(
        _parse_json_or_text
    )

    _original_convert = (
        AWSBedrockConverseModel._convert_openai_tools_to_bedrock
    )

    def _convert_openai_tools_to_bedrock(self, tools):
        bedrock_tools = _original_convert(self, tools)
        for tool in bedrock_tools or []:
            spec = tool.get("toolSpec") if isinstance(tool, dict) else None
            if isinstance(spec, dict) and not spec.get("description"):
                spec["description"] = spec.get("name") or "tool"
        return bedrock_tools

    AWSBedrockConverseModel._convert_openai_tools_to_bedrock = (
        _convert_openai_tools_to_bedrock
    )
    _bedrock_compat_installed = True
    logger.info("Installed AWS Bedrock Converse compatibility shims")


def patch_bedrock_config(
    api_url: str, extra_params: dict, *, is_cloud: bool
) -> tuple[str, dict]:
    """Patch API URL and extra_params for Bedrock Converse.

    Single config entry point for every Bedrock path (cloud and
    self-hosted, agent and MCP factory) so URL/region handling can't diverge.
    Mirrors :func:`patch_azure_cloud_config`: pure config, no side effects —
    the Camel compatibility shims are installed once at startup by
    :func:`patch_bedrock_converse_compat`.

    - Cloud: defaults the region and rewrites the proxy URL to ``/bedrock``.
    - Self-hosted: the region comes from the provider's ``encrypted_config``
      (carried in ``extra_params.region_name``) and credentials from the EC2
      instance role (boto3 default chain) — never from the client — so there
      is nothing to inject here.

    Returns the updated ``(api_url, extra_params)``.
    """
    extra_params = dict(extra_params)
    if is_cloud:
        extra_params.setdefault("region_name", BEDROCK_CONVERSE_REGION)
        if not api_url.rstrip("/").endswith("/bedrock"):
            api_url = api_url + "/bedrock"
    return api_url, extra_params


def patch_azure_cloud_config(extra_params: dict) -> dict:
    """Default Azure `api_version` for cloud mode.

    The cloud proxy fronts Azure OpenAI but the frontend sends an empty
    `extra_params` for cloud, leaving `api_version` unset. Camel's
    `AzureOpenAIModel` raises if neither the kwarg nor `AZURE_API_VERSION`
    env var is provided — inject a sensible default here so cloud-mode
    GPT models (gpt-5.4, gpt-5.5, gpt-5-mini, ...) construct cleanly.
    """
    extra_params = dict(extra_params)
    extra_params.setdefault("api_version", AZURE_DEFAULT_API_VERSION)
    return extra_params


def normalize_model_platform(platform: str) -> str:
    """Normalize provider aliases to supported model platform names."""
    return PLATFORM_ALIAS_MAPPING.get(platform, platform)


def normalize_optional_model_platform(platform: str | None) -> str | None:
    """Optional variant of normalize_model_platform."""
    if platform is None:
        return None
    return normalize_model_platform(platform)


NormalizedModelPlatform = Annotated[
    str, BeforeValidator(normalize_model_platform)
]
NormalizedOptionalModelPlatform = Annotated[
    str | None, BeforeValidator(normalize_optional_model_platform)
]
