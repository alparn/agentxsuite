"""
OAuth authentication for Claude Agent SDK integration.

This module handles OAuth flows for authenticating Claude agents
with AgentxSuite's API.
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.authtoken.models import Token

User = get_user_model()

logger = logging.getLogger(__name__)


class OAuthManager:
    """Manages OAuth flows for Claude agent authentication."""

    # Cache timeouts
    AUTH_CODE_TIMEOUT = 600  # 10 minutes
    STATE_TOKEN_TIMEOUT = 600  # 10 minutes
    
    # Valid OAuth scopes
    VALID_SCOPES = {
        "agent:execute": "Execute agents and tools",
        "tools:read": "Read available tools",
        "runs:read": "Read execution history",
        "agent:read": "Read agent information"
    }
    
    # Default scopes
    DEFAULT_SCOPES = ["agent:execute", "tools:read"]

    def __init__(self):
        """Initialize OAuth manager."""
        self.client_id = getattr(settings, "CLAUDE_AGENT_CLIENT_ID", "agentxsuite-claude-agent")
        self.client_secret = getattr(settings, "CLAUDE_AGENT_CLIENT_SECRET", None)
        self.redirect_uri = getattr(settings, "CLAUDE_AGENT_REDIRECT_URI", "http://localhost:3000/auth/callback")

    def generate_authorization_url(
        self, organization_id: str, environment_id: str
    ) -> dict[str, str]:
        """
        Generate OAuth authorization URL.

        Args:
            organization_id: Organization ID for access scoping
            environment_id: Environment ID for access scoping

        Returns:
            Dictionary with authorization URL and state token
        """
        # Generate secure state token
        state = secrets.token_urlsafe(32)

        # Store state with metadata in cache
        state_key = f"oauth_state:{state}"
        cache.set(
            state_key,
            {
                "organization_id": organization_id,
                "environment_id": environment_id,
                "created_at": datetime.utcnow().isoformat(),
            },
            self.STATE_TOKEN_TIMEOUT,
        )

        # Build authorization URL
        base_url = getattr(settings, "OAUTH_AUTHORIZE_URL", "http://localhost:8000/api/v1/oauth/authorize")
        auth_url = (
            f"{base_url}?"
            f"client_id={self.client_id}&"
            f"redirect_uri={self.redirect_uri}&"
            f"response_type=code&"
            f"state={state}&"
            f"scope=agent:execute+tools:read+runs:read"
        )

        return {"authorization_url": auth_url, "state": state}

    def validate_state(self, state: str) -> dict[str, Any] | None:
        """
        Validate OAuth state token.

        Args:
            state: State token to validate

        Returns:
            State metadata if valid, None otherwise
        """
        state_key = f"oauth_state:{state}"
        state_data = cache.get(state_key)

        if not state_data:
            logger.warning(f"Invalid or expired state token: {state}")
            return None

        # Delete state after use (one-time use)
        cache.delete(state_key)

        return state_data

    def generate_authorization_code(
        self, user: User, organization_id: str, environment_id: str
    ) -> str:
        """
        Generate authorization code for OAuth flow.

        Args:
            user: User granting authorization
            organization_id: Organization ID
            environment_id: Environment ID

        Returns:
            Authorization code
        """
        # Generate secure code
        code = secrets.token_urlsafe(32)

        # Store code with metadata
        code_key = f"oauth_code:{code}"
        cache.set(
            code_key,
            {
                "user_id": user.id,
                "organization_id": organization_id,
                "environment_id": environment_id,
                "created_at": datetime.utcnow().isoformat(),
            },
            self.AUTH_CODE_TIMEOUT,
        )

        logger.info(f"Generated authorization code for user={user.id}, org={organization_id}")

        return code

    def exchange_code_for_token(self, code: str, client_secret: str | None = None) -> dict[str, Any] | None:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code
            client_secret: Optional client secret for validation

        Returns:
            Token data if valid, None otherwise
        """
        # Validate client secret if configured
        if self.client_secret and client_secret != self.client_secret:
            logger.warning("Invalid client secret provided")
            return None

        # Retrieve and validate code
        code_key = f"oauth_code:{code}"
        code_data = cache.get(code_key)

        if not code_data:
            logger.warning(f"Invalid or expired authorization code: {code}")
            return None

        # Delete code after use (one-time use)
        cache.delete(code_key)

        # Get user and create/retrieve token
        try:
            user = User.objects.get(id=code_data["user_id"])
            token, created = Token.objects.get_or_create(user=user)

            # Store token metadata in cache for later retrieval
            token_key = f"oauth_token_meta:{token.key}"
            cache.set(
                token_key,
                {
                    "organization_id": code_data["organization_id"],
                    "environment_id": code_data["environment_id"],
                    "scope": code_data.get("scope", "agent:execute tools:read"),
                    "issued_at": datetime.utcnow().isoformat(),
                    "user_id": user.id
                },
                31536000  # 1 year (same as token expiry)
            )

            logger.info(f"Exchanged code for token (user={user.id}, token_created={created})")

            return {
                "access_token": token.key,
                "token_type": "Bearer",
                "expires_in": 31536000,  # 1 year (tokens don't expire in DRF by default)
                "organization_id": code_data["organization_id"],
                "environment_id": code_data["environment_id"],
                "scope": code_data.get("scope", "agent:execute tools:read")
            }

        except User.DoesNotExist:
            logger.error(f"User {code_data['user_id']} not found during token exchange")
            return None

    def revoke_token(self, access_token: str) -> bool:
        """
        Revoke an access token.

        Args:
            access_token: Token to revoke

        Returns:
            True if revoked successfully, False otherwise
        """
        try:
            token = Token.objects.get(key=access_token)
            user_id = token.user_id
            token.delete()
            
            # Also remove token metadata from cache
            token_key = f"oauth_token_meta:{access_token}"
            cache.delete(token_key)
            
            logger.info(f"Revoked token for user={user_id}")
            return True

        except Token.DoesNotExist:
            logger.warning(f"Attempted to revoke non-existent token")
            return False

    # Request Handler Methods (called by views.py)

    def authorize(self, request) -> dict[str, Any]:
        """
        Handle OAuth authorization request.

        Validates request parameters and generates authorization URL.
        In a production system, this would redirect to a login page.

        Args:
            request: Django request object

        Returns:
            Authorization response with code or redirect URL

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Extract OAuth parameters
        client_id = request.GET.get("client_id") or request.data.get("client_id")
        redirect_uri = request.GET.get("redirect_uri") or request.data.get("redirect_uri")
        response_type = request.GET.get("response_type") or request.data.get("response_type", "code")
        state = request.GET.get("state") or request.data.get("state")
        scope = request.GET.get("scope") or request.data.get("scope", "")
        
        # Additional AgentxSuite-specific parameters
        organization_id = request.GET.get("organization_id") or request.data.get("organization_id")
        environment_id = request.GET.get("environment_id") or request.data.get("environment_id")

        # Validate required parameters
        if not client_id:
            raise ValueError("client_id is required")
        if not redirect_uri:
            raise ValueError("redirect_uri is required")
        if response_type != "code":
            raise ValueError("Only authorization_code flow (response_type=code) is supported")
        if not state:
            raise ValueError("state parameter is required for security")
        if not organization_id:
            raise ValueError("organization_id is required")
        if not environment_id:
            raise ValueError("environment_id is required")

        # Validate client_id
        if client_id != self.client_id:
            raise ValueError(f"Invalid client_id: {client_id}")

        # Parse and validate scopes
        requested_scopes = scope.split() if scope else self.DEFAULT_SCOPES
        valid_scopes, invalid_scopes = self.validate_scopes(requested_scopes)
        
        if invalid_scopes:
            raise ValueError(f"Invalid scopes requested: {', '.join(invalid_scopes)}")

        # Validate state token
        state_data = self.validate_state(state)
        if not state_data:
            raise ValueError("Invalid or expired state token")

        # Check if user is authenticated
        if not request.user.is_authenticated:
            # In production, redirect to login page with return URL
            return {
                "status": "login_required",
                "login_url": f"/login?next=/api/v1/claude-agent/authorize",
                "message": "User must authenticate before granting access"
            }

        # Check if user has access to the organization
        from apps.tenants.models import Organization
        try:
            org = Organization.objects.get(id=organization_id)
            # Check if user is member of organization
            if not org.members.filter(id=request.user.id).exists():
                raise ValueError(f"User does not have access to organization {organization_id}")
        except Organization.DoesNotExist:
            raise ValueError(f"Organization {organization_id} not found")

        # Generate authorization code
        auth_code = self.generate_authorization_code(
            user=request.user,
            organization_id=organization_id,
            environment_id=environment_id
        )

        # Store scope information with the code
        code_key = f"oauth_code:{auth_code}"
        code_data = cache.get(code_key)
        code_data["scope"] = " ".join(valid_scopes) if valid_scopes else " ".join(self.DEFAULT_SCOPES)
        cache.set(code_key, code_data, self.AUTH_CODE_TIMEOUT)

        # Build redirect URL with code
        redirect_url = f"{redirect_uri}?code={auth_code}&state={state}"

        logger.info(
            f"Authorization granted",
            extra={
                "user_id": request.user.id,
                "organization_id": organization_id,
                "environment_id": environment_id,
                "scopes": requested_scopes
            }
        )

        return {
            "status": "success",
            "redirect_url": redirect_url,
            "code": auth_code,
            "state": state
        }

    def token(self, request) -> dict[str, Any]:
        """
        Handle OAuth token exchange request.

        Exchanges authorization code for access token following OAuth 2.0 spec.

        Args:
            request: Django request object

        Returns:
            Token response with access_token and metadata

        Raises:
            ValueError: If parameters are invalid or code is expired
        """
        # Extract token request parameters
        grant_type = request.data.get("grant_type")
        code = request.data.get("code")
        redirect_uri = request.data.get("redirect_uri")
        client_id = request.data.get("client_id")
        client_secret = request.data.get("client_secret")

        # Validate grant_type
        if grant_type != "authorization_code":
            raise ValueError("Only authorization_code grant type is supported")

        # Validate required parameters
        if not code:
            raise ValueError("authorization code is required")
        if not redirect_uri:
            raise ValueError("redirect_uri is required")
        if not client_id:
            raise ValueError("client_id is required")

        # Validate client_id
        if client_id != self.client_id:
            raise ValueError(f"Invalid client_id: {client_id}")

        # Validate client_secret if configured
        if self.client_secret:
            if not client_secret:
                raise ValueError("client_secret is required")
            if client_secret != self.client_secret:
                raise ValueError("Invalid client_secret")

        # Exchange code for token
        token_data = self.exchange_code_for_token(code, client_secret)
        
        if not token_data:
            raise ValueError("Invalid or expired authorization code")

        logger.info(
            f"Token issued successfully",
            extra={
                "organization_id": token_data.get("organization_id"),
                "environment_id": token_data.get("environment_id")
            }
        )

        # Return OAuth 2.0 compliant response
        return {
            "access_token": token_data["access_token"],
            "token_type": "Bearer",
            "expires_in": token_data["expires_in"],
            "scope": "agent:execute tools:read runs:read",
            "organization_id": token_data["organization_id"],
            "environment_id": token_data["environment_id"]
        }

    def revoke(self, request) -> dict[str, Any]:
        """
        Handle OAuth token revocation request.

        Revokes an access token following RFC 7009.

        Args:
            request: Django request object

        Returns:
            Revocation status

        Raises:
            ValueError: If token parameter is missing
        """
        # Extract token from request
        token = request.data.get("token")
        token_type_hint = request.data.get("token_type_hint", "access_token")

        if not token:
            # Also try to get from Authorization header
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
        
        if not token:
            raise ValueError("token parameter is required")

        # Only access_token revocation is supported
        if token_type_hint not in ["access_token", None]:
            raise ValueError("Only access_token revocation is supported")

        # Attempt to revoke token
        success = self.revoke_token(token)

        if success:
            logger.info("Token revoked successfully")
            return {
                "status": "success",
                "message": "Token revoked successfully"
            }
        else:
            # RFC 7009: The authorization server responds with HTTP 200
            # even if the token doesn't exist (for security reasons)
            logger.info("Token revocation requested for non-existent token")
            return {
                "status": "success",
                "message": "Token revocation processed"
            }

    def get_access_info(self, access_token: str) -> dict[str, Any] | None:
        """
        Get information about an access token.

        Args:
            access_token: Token to inspect

        Returns:
            Token information if valid, None otherwise
        """
        try:
            token = Token.objects.select_related("user").get(key=access_token)
            
            # Get organization and environment from token metadata
            # (stored when token was issued)
            token_key = f"oauth_token_meta:{access_token}"
            metadata = cache.get(token_key)

            return {
                "active": True,
                "user_id": token.user.id,
                "username": token.user.username,
                "email": token.user.email,
                "organization_id": metadata.get("organization_id") if metadata else None,
                "environment_id": metadata.get("environment_id") if metadata else None,
                "scope": metadata.get("scope", "agent:execute tools:read") if metadata else "agent:execute tools:read",
                "issued_at": token.created.isoformat() if hasattr(token, "created") else None
            }

        except Token.DoesNotExist:
            return None

    def validate_scopes(self, requested_scopes: list[str]) -> tuple[list[str], list[str]]:
        """
        Validate requested OAuth scopes.

        Args:
            requested_scopes: List of scope strings

        Returns:
            Tuple of (valid_scopes, invalid_scopes)
        """
        valid = []
        invalid = []
        
        for scope in requested_scopes:
            if scope in self.VALID_SCOPES:
                valid.append(scope)
            else:
                invalid.append(scope)
        
        return valid, invalid

    def initiate_flow(self, organization_id: str, environment_id: str, base_url: str | None = None) -> dict[str, str]:
        """
        Initiate OAuth flow by generating state and authorization URL.

        This is a convenience method for external clients to start the OAuth flow.

        Args:
            organization_id: Organization ID for access scoping
            environment_id: Environment ID for access scoping
            base_url: Optional base URL override (e.g., for different environments)

        Returns:
            Dictionary with authorization_url and state token

        Example:
            >>> oauth = OAuthManager()
            >>> flow_data = oauth.initiate_flow(
            ...     organization_id="org-123",
            ...     environment_id="env-456"
            ... )
            >>> print(flow_data["authorization_url"])
            >>> # User visits the URL, approves access
            >>> # Then exchange the code for token using token() method
        """
        # Generate state token with metadata
        state = secrets.token_urlsafe(32)
        
        # Store state with metadata
        state_key = f"oauth_state:{state}"
        cache.set(
            state_key,
            {
                "organization_id": organization_id,
                "environment_id": environment_id,
                "created_at": datetime.utcnow().isoformat(),
            },
            self.STATE_TOKEN_TIMEOUT,
        )
        
        # Build authorization URL
        if base_url is None:
            base_url = getattr(settings, "OAUTH_AUTHORIZE_URL", "http://localhost:8000")
        
        auth_url = (
            f"{base_url}/api/v1/claude-agent/authorize?"
            f"client_id={self.client_id}&"
            f"redirect_uri={self.redirect_uri}&"
            f"response_type=code&"
            f"state={state}&"
            f"organization_id={organization_id}&"
            f"environment_id={environment_id}&"
            f"scope={'+'.join(self.DEFAULT_SCOPES)}"
        )
        
        return {
            "authorization_url": auth_url,
            "state": state,
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri
        }

