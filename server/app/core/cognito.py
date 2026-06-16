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

"""
Amazon Cognito Hosted UI (OAuth2 Authorization Code) helpers.

Used by the self-hosted web login flow to authenticate users against a shared
Cognito User Pool. The backend performs the code exchange (so the client_secret
never reaches the browser) and verifies the returned id_token against the pool's
JWKS before minting an Eigent JWT.
"""

from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient

from app.core.environment import env, env_not_empty

_OAUTH_SCOPES = "openid email profile"


@dataclass(frozen=True)
class CognitoConfig:
    region: str
    user_pool_id: str
    client_id: str
    client_secret: str
    domain: str  # e.g. https://steamovap-auth.auth.us-east-1.amazoncognito.com
    redirect_uri: str  # must match a Callback URL configured on the app client

    @property
    def issuer(self) -> str:
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/.well-known/jwks.json"

    @property
    def authorize_endpoint(self) -> str:
        return f"{self.domain.rstrip('/')}/oauth2/authorize"

    @property
    def token_endpoint(self) -> str:
        return f"{self.domain.rstrip('/')}/oauth2/token"


@lru_cache(maxsize=1)
def get_config() -> CognitoConfig:
    return CognitoConfig(
        region=env_not_empty("cognito_region"),
        user_pool_id=env_not_empty("cognito_user_pool_id"),
        client_id=env_not_empty("cognito_client_id"),
        client_secret=env("cognito_client_secret", "") or "",
        domain=env_not_empty("cognito_domain"),
        redirect_uri=env_not_empty("cognito_redirect_uri"),
    )


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    # PyJWKClient caches signing keys internally and refreshes on unknown kid.
    return PyJWKClient(get_config().jwks_url)


def build_authorize_url(state: str) -> str:
    """Build the Cognito Hosted UI authorize URL for the Authorization Code flow."""
    cfg = get_config()
    params = {
        "response_type": "code",
        "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_uri,
        "scope": _OAUTH_SCOPES,
        "state": state,
    }
    return f"{cfg.authorize_endpoint}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    """Exchange an authorization code for tokens at the Cognito token endpoint.

    :raises httpx.HTTPStatusError: if Cognito rejects the exchange.
    """
    cfg = get_config()
    data = {
        "grant_type": "authorization_code",
        "client_id": cfg.client_id,
        "code": code,
        "redirect_uri": cfg.redirect_uri,
    }
    # Confidential clients must authenticate with HTTP Basic (client_id:client_secret).
    auth = (cfg.client_id, cfg.client_secret) if cfg.client_secret else None
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(
            cfg.token_endpoint,
            data=data,
            auth=auth,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()


def verify_id_token(id_token: str) -> dict:
    """Verify a Cognito id_token signature, issuer, audience and expiry.

    :returns: the decoded claims (contains ``email``, ``sub``, ...).
    :raises jwt.InvalidTokenError: if the token is invalid.
    """
    cfg = get_config()
    signing_key = _jwks_client().get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=cfg.client_id,
        issuer=cfg.issuer,
        options={"require": ["exp", "iss", "aud", "sub"]},
    )
    if claims.get("token_use") != "id":
        raise jwt.InvalidTokenError("Not an id_token (token_use != 'id')")
    return claims
