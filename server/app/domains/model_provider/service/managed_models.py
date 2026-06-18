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

"""Managed model providers.

Server-supplied model providers that users get WITHOUT entering any
credentials. For self-hosted deployments backed by a shared AWS account, we
provision a preferred AWS Bedrock Converse provider per user. The provider row
stores NO AWS secret (``api_key`` stays empty) and the region lives only in
``encrypted_config``; the Brain supplies credentials at runtime from the EC2
instance role (boto3 default credential chain). This keeps AWS credentials
server-side only — never in the browser or the database.

``provision_on_login`` is the single, failure-safe entry point every auth flow
calls after a user authenticates (Cognito, password, auto-login, ...).
"""

from loguru import logger
from sqlmodel import select

from app.core.database import session_make
from app.core.environment import env
from app.domains.model_provider.service.provider_service import ProviderService
from app.model.provider.provider import Provider, VaildStatus

_BEDROCK_PLATFORM = "aws-bedrock-converse"
_DEFAULT_REGION = "us-east-1"


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_managed_bedrock_enabled() -> bool:
    """True when the deployment hands out a managed Bedrock model."""
    return _truthy(env("bedrock_managed")) and bool(env("bedrock_model_type"))


def ensure_managed_bedrock_provider(user_id: int) -> None:
    """Idempotently give the user a preferred, credential-free Bedrock provider.

    No-op unless ``bedrock_managed`` is enabled. Safe to call on every login:
    it only creates the managed provider once (detected by an empty
    ``api_key`` on an ``aws-bedrock-converse`` row), and sets it as the user's
    preferred model so no manual configuration is required.
    """
    if not is_managed_bedrock_enabled():
        return

    model_type = env("bedrock_model_type")
    region = env("bedrock_region", _DEFAULT_REGION)

    with session_make() as s:
        existing = s.exec(
            select(Provider).where(
                Provider.user_id == user_id,
                Provider.no_delete(),
                Provider.provider_name == _BEDROCK_PLATFORM,
                Provider.api_key == "",
            )
        ).first()
        if existing is not None:
            return

    result = ProviderService.create(
        user_id,
        {
            "provider_name": _BEDROCK_PLATFORM,
            "model_type": model_type,
            "api_key": "",  # no secret stored; Brain uses server-side creds
            "endpoint_url": "",  # empty -> boto3 builds the regional endpoint
            "encrypted_config": {"region_name": region},
            "is_valid": VaildStatus.is_valid,
            "prefer": True,
        },
    )
    provider = result["provider"]
    # Make it the sole preferred provider so the app needs no model setup.
    ProviderService.set_prefer(provider.id, user_id)
    logger.info(
        "Provisioned managed Bedrock provider",
        extra={
            "user_id": user_id,
            "provider_id": provider.id,
            "model_type": model_type,
            "region": region,
        },
    )


def provision_on_login(user_id: int) -> None:
    """Apply all managed-provider provisioning for a freshly authenticated user.

    The single hook every auth flow calls. Provisioning must never block or
    break login, so all failures are swallowed and logged here — callers do
    not need their own try/except.
    """
    try:
        ensure_managed_bedrock_provider(user_id)
    except Exception as e:
        logger.error(
            "Managed provider provisioning failed",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True,
        )
