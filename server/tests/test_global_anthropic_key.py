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

from app.model.config.config import ConfigInfo
from app.shared.types.config_group import ConfigGroup


def test_anthropic_config_group_accepts_global_api_key():
    assert ConfigInfo.is_valid_env_var(
        ConfigGroup.ANTHROPIC.value,
        "ANTHROPIC_API_KEY",
    )


def test_build_global_anthropic_key_response_uses_backend_secret():
    from app.domains.user.service.key_service import (
        build_global_anthropic_key_response,
    )

    response = build_global_anthropic_key_response(
        {
            "ANTHROPIC_API_KEY": "test-anthropic-key",
        }
    )

    assert response == {
        "value": "test-anthropic-key",
        "api_url": "https://api.anthropic.com",
        "model_platform": "anthropic",
        "model_type": "claude-sonnet-4-5",
    }
