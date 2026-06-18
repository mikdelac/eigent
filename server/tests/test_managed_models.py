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

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.domains.model_provider.service import managed_models


@contextmanager
def _managed_env(enabled=True, model_type="anthropic.claude", region="us-east-1"):
    values = {
        "bedrock_managed": "true" if enabled else "false",
        "bedrock_model_type": model_type,
        "bedrock_region": region,
    }

    def fake_env(key, default=None):
        return values.get(key, default)

    with patch.object(managed_models, "env", side_effect=fake_env):
        yield


def _patch_session(existing):
    """Patch session_make so the existence query returns ``existing``."""
    session = MagicMock()
    session.exec.return_value.first.return_value = existing
    ctx = MagicMock()
    ctx.__enter__.return_value = session
    ctx.__exit__.return_value = False
    return patch.object(managed_models, "session_make", return_value=ctx)


def test_disabled_is_noop():
    with _managed_env(enabled=False), patch.object(
        managed_models, "ProviderService"
    ) as svc:
        managed_models.ensure_managed_bedrock_provider(1)
    svc.create.assert_not_called()


def test_creates_preferred_provider_when_absent():
    provider = SimpleNamespace(id=42)
    with _managed_env(region="eu-west-1"), _patch_session(None), patch.object(
        managed_models, "ProviderService"
    ) as svc:
        svc.create.return_value = {"provider": provider}
        managed_models.ensure_managed_bedrock_provider(7)

    svc.create.assert_called_once()
    user_id, data = svc.create.call_args.args
    assert user_id == 7
    assert data["provider_name"] == "aws-bedrock-converse"
    assert data["api_key"] == ""  # no secret stored
    assert data["encrypted_config"] == {"region_name": "eu-west-1"}
    assert data["prefer"] is True
    svc.set_prefer.assert_called_once_with(42, 7)


def test_existing_managed_provider_is_not_recreated():
    with _managed_env(), _patch_session(SimpleNamespace(id=1)), patch.object(
        managed_models, "ProviderService"
    ) as svc:
        managed_models.ensure_managed_bedrock_provider(7)
    svc.create.assert_not_called()
    svc.set_prefer.assert_not_called()


def test_provision_on_login_swallows_errors():
    with patch.object(
        managed_models,
        "ensure_managed_bedrock_provider",
        side_effect=RuntimeError("boom"),
    ):
        # Must never raise — provisioning can't be allowed to block login.
        managed_models.provision_on_login(7)
