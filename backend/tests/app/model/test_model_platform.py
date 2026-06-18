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

from pydantic import BaseModel

from app.model.model_platform import (
    BEDROCK_CONVERSE_REGION,
    NormalizedModelPlatform,
    NormalizedOptionalModelPlatform,
    normalize_model_platform,
    normalize_optional_model_platform,
    patch_bedrock_config,
    patch_bedrock_converse_compat,
)


def test_normalize_model_platform_maps_known_aliases():
    assert normalize_model_platform("grok") == "openai-compatible-model"
    assert normalize_model_platform("z.ai") == "zhipuai"
    assert normalize_model_platform("ModelArk") == "openai-compatible-model"
    assert normalize_model_platform("ernie") == "qianfan"
    assert normalize_model_platform("llama.cpp") == "openai-compatible-model"
    assert normalize_model_platform("nebius") == "openai-compatible-model"


def test_normalize_model_platform_keeps_non_alias_unchanged():
    assert normalize_model_platform("openai") == "openai"
    assert normalize_model_platform("mistral") == "mistral"


def test_normalize_optional_model_platform_handles_none():
    assert normalize_optional_model_platform(None) is None


def test_normalized_model_platform_type_applies_in_pydantic_model():
    class _Model(BaseModel):
        model_platform: NormalizedModelPlatform
        optional_model_platform: NormalizedOptionalModelPlatform = None

    item = _Model(
        model_platform="ernie",
        optional_model_platform="ModelArk",
    )

    assert item.model_platform == "qianfan"
    assert item.optional_model_platform == "openai-compatible-model"


def test_patch_bedrock_config_cloud_adds_region_and_bedrock_suffix():
    api_url, extra = patch_bedrock_config(
        "https://proxy.example.com", {}, is_cloud=True
    )
    assert api_url == "https://proxy.example.com/bedrock"
    assert extra["region_name"] == BEDROCK_CONVERSE_REGION


def test_patch_bedrock_config_cloud_keeps_explicit_region_and_suffix():
    api_url, extra = patch_bedrock_config(
        "https://proxy.example.com/bedrock/",
        {"region_name": "eu-west-1"},
        is_cloud=True,
    )
    assert api_url == "https://proxy.example.com/bedrock/"
    assert extra["region_name"] == "eu-west-1"


def test_patch_bedrock_config_self_hosted_is_passthrough():
    # Self-hosted region comes from the provider's encrypted_config, carried
    # in extra_params; the URL must stay untouched (no /bedrock proxy suffix).
    api_url, extra = patch_bedrock_config(
        "https://bedrock-runtime.us-east-1.amazonaws.com",
        {"region_name": "us-east-1"},
        is_cloud=False,
    )
    assert api_url == "https://bedrock-runtime.us-east-1.amazonaws.com"
    assert extra == {"region_name": "us-east-1"}


def test_patch_bedrock_config_does_not_mutate_input():
    extra_in = {"region_name": "us-east-1"}
    patch_bedrock_config("https://x", extra_in, is_cloud=True)
    assert extra_in == {"region_name": "us-east-1"}


def test_patch_bedrock_converse_compat_shims_are_installed():
    patch_bedrock_converse_compat()
    patch_bedrock_converse_compat()  # idempotent

    from camel.models.aws_bedrock_converse_model import (
        AWSBedrockConverseModel as M,
    )

    # Array tool results are wrapped in a JSON object Bedrock accepts.
    assert M._parse_json_or_text([1, 2]) == {"json": {"result": [1, 2]}}
    assert M._parse_json_or_text({"a": 1}) == {"json": {"a": 1}}

    # Empty tool descriptions are backfilled from the tool name.
    class _Fake(M):
        def __init__(self):
            pass

    tools = [
        {
            "function": {
                "name": "todo_write",
                "description": "",
                "parameters": {"type": "object"},
            }
        }
    ]
    out = _Fake._convert_openai_tools_to_bedrock(_Fake(), tools)
    assert out[0]["toolSpec"]["description"] == "todo_write"
