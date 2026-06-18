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

from unittest.mock import patch

from app.service import mcp_config

_LOCAL = {"mcpServers": {"odoo": {"url": "http://odoo"}}}


def _with_local(local):
    return patch.object(mcp_config, "read_mcp_config", return_value=local)


def test_merge_installed_mcp_uses_local_config_when_request_empty():
    with _with_local(_LOCAL):
        assert mcp_config.merge_installed_mcp({"mcpServers": {}}) == _LOCAL


def test_merge_installed_mcp_handles_none_request():
    with _with_local(_LOCAL):
        assert mcp_config.merge_installed_mcp(None) == _LOCAL


def test_merge_installed_mcp_unions_request_and_local():
    with _with_local(_LOCAL):
        merged = mcp_config.merge_installed_mcp(
            {"mcpServers": {"github": {"url": "http://gh"}}}
        )
    assert set(merged["mcpServers"]) == {"odoo", "github"}


def test_merge_installed_mcp_request_wins_on_key_clash():
    with _with_local(_LOCAL):
        merged = mcp_config.merge_installed_mcp(
            {"mcpServers": {"odoo": {"url": "http://override"}}}
        )
    assert merged["mcpServers"]["odoo"] == {"url": "http://override"}
