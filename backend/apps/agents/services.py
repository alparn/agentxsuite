"""
Services for agent token management.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from decouple import config
from django.utils import timezone as django_timezone

from apps.agents.models import Agent, IssuedToken, AgentMode
from apps.accounts.models import ServiceAccount
from apps.policies.models import Policy, PolicyRule, PolicyBinding
from apps.tenants.models import Organization, Environment
from mcp_fabric.settings import MCP_CANONICAL_URI, MCP_TOKEN_MAX_TTL_MINUTES

logger = logging.getLogger(__name__)

# JWT signing key (should be loaded from SecretStore in production)
JWT_PRIVATE_KEY = config("JWT_PRIVATE_KEY", default=None)
JWT_PUBLIC_KEY = config("JWT_PUBLIC_KEY", default=None)
JWT_ISSUER = config("JWT_ISSUER", default="https://agentxsuite.local")
JWT_ALGORITHM = "RS256"


def _get_signing_key() -> rsa.RSAPrivateKey:
    """
    Get JWT signing private key.
    
    In production, this should load from SecretStore.
    For development, generates a key if not configured.
    """
    if JWT_PRIVATE_KEY:
        try:
            return serialization.load_pem_private_key(
                JWT_PRIVATE_KEY.encode(),
                password=None,
            )
        except Exception as e:
            logger.error(f"Failed to load JWT private key: {e}")
            raise
    
    # Fallback: generate a key (for development only)
    logger.warning("JWT_PRIVATE_KEY not configured, generating temporary key (development only)")
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _get_public_key() -> rsa.RSAPublicKey:
    """Get JWT public key."""
    if JWT_PUBLIC_KEY:
        try:
            return serialization.load_pem_public_key(JWT_PUBLIC_KEY.encode())
        except Exception:
            pass
    
    # Fallback: derive from private key
    private_key = _get_signing_key()
    return private_key.public_key()


def generate_token_for_agent(
    agent: Agent,
    *,
    user=None,
    name: str | None = None,
    purpose: str = "api",
    ttl_minutes: int | None = None,
    scopes: list[str] | None = None,
    metadata: dict | None = None,
) -> tuple[str, IssuedToken]:
    """
    Generate a JWT token for an agent.
    
    Args:
        agent: Agent instance
        user: User who is creating the token (required)
        name: Token name (optional, will be auto-generated if not provided)
        purpose: Token purpose (default: "api")
        ttl_minutes: Token TTL in minutes (default: MCP_TOKEN_MAX_TTL_MINUTES)
        scopes: List of scopes to grant (default: ["mcp:run", "mcp:tools"])
        metadata: Additional metadata to store with token
    
    Returns:
        Tuple of (token_string, IssuedToken instance)
    """
    if not agent.service_account:
        raise ValueError("Agent must have a ServiceAccount to generate tokens")
    
    if not user:
        raise ValueError("User is required to generate tokens")
    
    sa = agent.service_account
    
    # Default TTL
    if ttl_minutes is None:
        ttl_minutes = MCP_TOKEN_MAX_TTL_MINUTES
    else:
        # Enforce max TTL
        ttl_minutes = min(ttl_minutes, MCP_TOKEN_MAX_TTL_MINUTES)
    
    # Default scopes
    if scopes is None:
        scopes = ["mcp:run", "mcp:tools", "mcp:manifest"]
    
    # Validate scopes against ServiceAccount allowlist
    if sa.scope_allowlist:
        invalid_scopes = [s for s in scopes if s not in sa.scope_allowlist]
        if invalid_scopes:
            raise ValueError(
                f"Scopes {invalid_scopes} are not in ServiceAccount allowlist: {sa.scope_allowlist}"
            )
    
    # Generate jti
    jti = str(uuid.uuid4())
    
    # Calculate timestamps
    now = django_timezone.now()
    iat = int(now.timestamp())
    exp = int((now + timedelta(minutes=ttl_minutes)).timestamp())
    nbf = int((now - timedelta(minutes=1)).timestamp())
    
    # Build token claims
    claims = {
        "iss": JWT_ISSUER,
        "aud": sa.audience or MCP_CANONICAL_URI,
        "sub": sa.subject,
        "jti": jti,
        "iat": iat,
        "exp": exp,
        "nbf": nbf,
        "org_id": str(agent.organization.id),
        "env_id": str(agent.environment.id),
        "agent_id": str(agent.id),
        "scope": " ".join(scopes),
    }
    
    # Sign token
    private_key = _get_signing_key()
    token_string = jwt.encode(claims, private_key, algorithm=JWT_ALGORITHM)
    
    # Generate token name if not provided
    if not name:
        name = f"Token for {agent.name} ({django_timezone.now().strftime('%Y-%m-%d %H:%M')})"
    
    # Store token metadata
    issued_token = IssuedToken.objects.create(
        agent=agent,
        organization=agent.organization,
        environment=agent.environment,
        name=name,
        purpose=purpose,
        issued_to=user,  # Can be None for system-generated tokens
        jti=jti,
        expires_at=datetime.fromtimestamp(exp, tz=ZoneInfo("UTC")),
        scopes=scopes,
        metadata=metadata or {},
    )
    
    logger.info(
        f"Generated token for agent {agent.id}",
        extra={
            "agent_id": str(agent.id),
            "jti": jti,
            "ttl_minutes": ttl_minutes,
            "scopes": scopes,
        },
    )
    
    return token_string, issued_token


def generate_mcp_token(
    claims: dict,
    *,
    expires_in: timedelta | None = None,
) -> str:
    """
    Generate a JWT token for MCP usage (user tokens, Claude Desktop, etc.).
    
    This is a simpler version of generate_token_for_agent that doesn't require
    an Agent or ServiceAccount. Used for user-created tokens in Token Management.
    
    Args:
        claims: Token claims (must include org_id, env_id, sub, jti, scope)
        expires_in: Token lifetime (default: 90 days)
    
    Returns:
        Token string (JWT)
    """
    if expires_in is None:
        expires_in = timedelta(days=90)
    
    # Calculate timestamps
    now = django_timezone.now()
    iat = int(now.timestamp())
    exp = int((now + expires_in).timestamp())
    nbf = int((now - timedelta(minutes=1)).timestamp())
    
    # Build complete token claims
    full_claims = {
        "iss": JWT_ISSUER,
        "aud": MCP_CANONICAL_URI,
        "iat": iat,
        "exp": exp,
        "nbf": nbf,
        **claims,  # Merge provided claims
    }
    
    # Sign token
    private_key = _get_signing_key()
    token_string = jwt.encode(full_claims, private_key, algorithm=JWT_ALGORITHM)
    
    logger.info(
        f"Generated MCP token",
        extra={
            "jti": claims.get("jti"),
            "purpose": claims.get("purpose"),
            "expires_in_days": expires_in.days,
        },
    )
    
    return token_string


def revoke_token(jti: str, revoked_by=None) -> IssuedToken:
    """
    Revoke a token by jti.
    
    Args:
        jti: JWT ID
        revoked_by: User who revoked the token (optional)
    
    Returns:
        Updated IssuedToken instance
    """
    try:
        token = IssuedToken.objects.get(jti=jti)
    except IssuedToken.DoesNotExist:
        raise ValueError(f"Token with jti '{jti}' not found")
    
    if token.revoked_at:
        raise ValueError(f"Token with jti '{jti}' is already revoked")
    
    token.revoked_at = django_timezone.now()
    token.revoked_by = revoked_by
    token.save()
    
    # Also revoke in jti_store (for immediate effect)
    from mcp_fabric.jti_store import revoke_jti
    
    revoke_jti(jti)
    
    logger.info(f"Revoked token {jti}", extra={"jti": jti, "revoked_by": str(revoked_by.id) if revoked_by else None})
    
    return token


def create_axcore_agent(
    organization: Organization,
    environment: Environment,
    name: str,
    mode: str = "runner",
    enabled: bool = True,
    version: str = "1.0.0",
    connection_id: str | None = None,
) -> tuple[Agent, ServiceAccount, Policy, str]:
    """
    Erstellt einen vollständig konfigurierten AxCore-Agent.
    
    Erstellt automatisch:
    1. Agent mit "axcore" Tag
    2. ServiceAccount für Token-Generierung
    3. Policy für System-Tools-Zugriff
    4. Initial Token für sofortige Verwendung
    
    Args:
        organization: Organization instance
        environment: Environment instance
        name: Agent name
        mode: Agent mode (runner/caller)
        enabled: Whether agent should be enabled
        version: Agent version
        connection_id: Optional connection ID
    
    Returns:
        Tuple of (Agent, ServiceAccount, Policy, token_string)
    
    Raises:
        ValueError: If agent already exists or validation fails
    """
    # Prüfe ob Agent bereits existiert
    if Agent.objects.filter(organization=organization, environment=environment, name=name).exists():
        raise ValueError(f"Agent with name '{name}' already exists")
    
    # 1. ServiceAccount erstellen
    sa_name = f"axcore-{name.lower().replace(' ', '-')}"
    sa_subject = f"axcore-{name.lower().replace(' ', '-')}@{organization.name.lower().replace(' ', '-')}"
    
    # Prüfe ob ServiceAccount bereits existiert
    sa = ServiceAccount.objects.filter(
        organization=organization,
        subject=sa_subject,
        issuer="https://agentxsuite.local",
    ).first()
    
    if not sa:
        sa = ServiceAccount.objects.create(
            organization=organization,
            environment=environment,
            name=sa_name,
            subject=sa_subject,
            audience="https://agentxsuite.local",
            issuer="https://agentxsuite.local",
            scope_allowlist=["mcp:run", "mcp:tools", "mcp:manifest"],
            enabled=True,
        )
        logger.info(
            f"Created ServiceAccount for AxCore agent: {sa_name}",
            extra={
                "service_account_id": str(sa.id),
                "organization_id": str(organization.id),
            },
        )
    
    # 2. Agent erstellen
    agent_data = {
        "organization": organization,
        "environment": environment,
        "name": name,
        "mode": AgentMode(mode),
        "enabled": enabled,
        "service_account": sa,
        "tags": ["axcore"],  # AxCore-Markierung
        "capabilities": ["agentxsuite:admin", "agentxsuite:read", "agentxsuite:write"],
        "version": version,
    }
    
    if connection_id:
        from apps.connections.models import Connection
        try:
            connection = Connection.objects.get(
                id=connection_id,
                organization=organization,
                environment=environment,
            )
            agent_data["connection"] = connection
        except Connection.DoesNotExist:
            logger.warning(
                f"Connection {connection_id} not found, creating agent without connection",
                extra={"connection_id": connection_id},
            )
    
    agent = Agent.objects.create(**agent_data)
    
    logger.info(
        f"Created AxCore agent: {name}",
        extra={
            "agent_id": str(agent.id),
            "organization_id": str(organization.id),
            "environment_id": str(environment.id),
        },
    )
    
    # 3. Policy für System-Tools erstellen
    policy_name = f"axcore-policy-{agent.slug}"
    
    policy = Policy.objects.create(
        organization=organization,
        environment=environment,
        name=policy_name,
        is_active=True,
        enabled=True,
    )
    
    # PolicyRule: Erlaube alle System-Tools
    rule = PolicyRule.objects.create(
        policy=policy,
        action="tool.invoke",
        target="tool:agentxsuite:*",
        effect="allow",
        conditions={},
    )
    
    # PolicyBinding: Nur für diesen Agent
    binding = PolicyBinding.objects.create(
        policy=policy,
        scope_type="agent",
        scope_id=str(agent.id),
        priority=1,  # Sehr spezifisch
    )
    
    logger.info(
        f"Created policy for AxCore agent: {policy_name}",
        extra={
            "policy_id": str(policy.id),
            "rule_id": str(rule.id),
            "binding_id": str(binding.id),
            "agent_id": str(agent.id),
        },
    )
    
    # 4. Initial Token generieren
    # Get system user (first superuser or get/create a system user)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    system_user = User.objects.filter(is_superuser=True).first()
    if not system_user:
        # Try to get or create a system user (for automated token generation)
        system_user, created = User.objects.get_or_create(
            username="system",
            defaults={
                "email": "system@agentxsuite.local",
                "is_superuser": True,
                "is_staff": True,
            }
        )
        if not system_user.is_superuser:
            # Update if user exists but is not superuser
            system_user.is_superuser = True
            system_user.is_staff = True
            system_user.save()
    
    token_string, issued_token = generate_token_for_agent(
        agent,
        user=system_user,
        name=f"Initial token for {name}",
        purpose="api",
        ttl_minutes=60,  # 1 Stunde
        scopes=["mcp:run", "mcp:tools", "mcp:manifest"],
        metadata={"created_by": "axcore_setup", "initial": True},
    )
    
    logger.info(
        f"Generated initial token for AxCore agent: {name}",
        extra={
            "agent_id": str(agent.id),
            "token_jti": issued_token.jti,
        },
    )
    
    return agent, sa, policy, token_string

