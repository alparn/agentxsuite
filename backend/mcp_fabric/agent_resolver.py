"""
Agent resolution from token claims via ServiceAccount mapping.

Source of truth: (subject, issuer) → ServiceAccount → Agent

Security principle: NEVER trust agent_id from token directly.
Always resolve via (subject, issuer) mapping and verify.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apps.agents.models import Agent
from apps.tenants.models import Environment, Organization

if TYPE_CHECKING:
    from apps.accounts.models import ServiceAccount

logger = logging.getLogger(__name__)


def resolve_agent_from_token_claims(
    claims: dict,
    org_id: str,
    env_id: str,
) -> Agent | None:
    """
    Resolve Agent from token claims via ServiceAccount mapping.

    Source of truth: (subject, issuer) → ServiceAccount → Agent

    Args:
        claims: Decoded token claims (must contain 'sub' and 'iss')
        org_id: Organization ID (must match)
        env_id: Environment ID (must match)

    Returns:
        Agent instance if found and valid, None otherwise

    Security:
        - NEVER trust agent_id from token directly
        - Lookup via (subject, issuer) mapping
        - Validate org/env match
        - If token has agent_id: hard-compare with mapped agent
        - Only return enabled agents
    """
    from apps.accounts.models import ServiceAccount

    subject = claims.get("sub")
    issuer = claims.get("iss")
    token_agent_id = claims.get("agent_id")  # Don't trust, only verify

    if not subject or not issuer:
        logger.warning(
            "Token missing subject or issuer",
            extra={
                "has_subject": bool(subject),
                "has_issuer": bool(issuer),
                "org_id": org_id,
                "env_id": env_id,
            },
        )
        return None

    # Lookup ServiceAccount via (subject, issuer) - this is the source of truth
    try:
        sa = ServiceAccount.objects.select_related("agent").get(
            subject=subject,
            issuer=issuer,
            enabled=True,
        )
    except ServiceAccount.DoesNotExist:
        logger.warning(
            f"ServiceAccount not found for (subject={subject}, issuer={issuer})",
            extra={
                "subject": subject,
                "issuer": issuer,
                "org_id": org_id,
                "env_id": env_id,
            },
        )
        return None
    except ServiceAccount.MultipleObjectsReturned:
        logger.error(
            f"Multiple ServiceAccounts found for (subject={subject}, issuer={issuer})",
            extra={
                "subject": subject,
                "issuer": issuer,
            },
        )
        return None

    # Validate org/env match (paranoid check)
    if str(sa.organization_id) != org_id:
        logger.error(
            f"ServiceAccount org mismatch: SA has {sa.organization_id}, token requires {org_id}",
            extra={
                "service_account_id": str(sa.id),
                "sa_org_id": str(sa.organization_id),
                "token_org_id": org_id,
            },
        )
        return None

    if sa.environment_id and str(sa.environment_id) != env_id:
        logger.error(
            f"ServiceAccount env mismatch: SA has {sa.environment_id}, token requires {env_id}",
            extra={
                "service_account_id": str(sa.id),
                "sa_env_id": str(sa.environment_id),
                "token_env_id": env_id,
            },
        )
        return None

    # Get Agent from ServiceAccount
    try:
        agent = sa.agent
    except Agent.DoesNotExist:
        logger.warning(
            f"ServiceAccount {sa.id} has no associated Agent",
            extra={
                "service_account_id": str(sa.id),
                "subject": subject,
                "issuer": issuer,
            },
        )
        return None

    # Validate agent org/env (double-check)
    if str(agent.organization_id) != org_id or str(agent.environment_id) != env_id:
        logger.error(
            f"Agent org/env mismatch: Agent {agent.id} belongs to different org/env",
            extra={
                "agent_id": str(agent.id),
                "agent_org_id": str(agent.organization_id),
                "agent_env_id": str(agent.environment_id),
                "token_org_id": org_id,
                "token_env_id": env_id,
            },
        )
        return None

    # If token has agent_id: HARD VERIFY (don't trust, verify)
    if token_agent_id:
        if str(agent.id) != token_agent_id:
            logger.error(
                f"Agent ID mismatch: token claims agent_id={token_agent_id}, "
                f"but (subject, issuer) mapping yields agent_id={agent.id}",
                extra={
                    "token_agent_id": token_agent_id,
                    "resolved_agent_id": str(agent.id),
                    "subject": subject,
                    "issuer": issuer,
                },
            )
            return None

    # Only return enabled agents
    if not agent.enabled:
        logger.warning(
            f"Agent {agent.id} is disabled",
            extra={
                "agent_id": str(agent.id),
                "subject": subject,
                "issuer": issuer,
            },
        )
        return None

    logger.debug(
        f"Resolved Agent {agent.id} from (subject={subject}, issuer={issuer})",
        extra={
            "agent_id": str(agent.id),
            "subject": subject,
            "issuer": issuer,
            "org_id": org_id,
            "env_id": env_id,
        },
    )

    return agent


