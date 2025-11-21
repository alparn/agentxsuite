"""
Management command to sync MCP servers from GitHub to database.

This command:
1. Fetches MCP servers from GitHub using multiple search queries
2. Compares with existing database records
3. Only creates/updates records when data has changed
4. Marks servers as inactive if they no longer exist on GitHub
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import httpx
from decouple import config
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.mcp_ext.models import MCPHubServer

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = config("GITHUB_TOKEN", default=None)  # Can be set via environment variable


def fetch_github_repos(query: str, per_page: int = 100) -> list[dict[str, Any]]:
    """Fetch repositories from GitHub API."""
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    
    url = f"{GITHUB_API_BASE}/search/repositories"
    params = {"q": query, "per_page": per_page, "sort": "stars", "order": "desc"}
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("items", [])
    except Exception as e:
        logger.error(f"Failed to fetch GitHub repos for query '{query}': {e}")
        return []


def fetch_github_code_search(query: str, per_page: int = 100) -> list[dict[str, Any]]:
    """Fetch repositories from GitHub code search."""
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    
    url = f"{GITHUB_API_BASE}/search/code"
    params = {"q": query, "per_page": per_page}
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            repos = []
            seen = set()
            for item in data.get("items", []):
                repo = item.get("repository")
                if repo and repo.get("full_name") not in seen:
                    seen.add(repo["full_name"])
                    repos.append(repo)
            return repos
    except Exception as e:
        logger.error(f"Failed to fetch GitHub code search for query '{query}': {e}")
        return []


class Command(BaseCommand):
    """Sync MCP servers from GitHub to database."""

    help = "Sync MCP servers from GitHub API to database (only updates changed records)"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force update even if data hasn't changed",
        )
        parser.add_argument(
            "--github-token",
            type=str,
            help="GitHub API token for higher rate limits",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        global GITHUB_TOKEN
        # Use command-line argument if provided, otherwise use environment variable
        GITHUB_TOKEN = options.get("github_token") or GITHUB_TOKEN or os.getenv("GITHUB_TOKEN")
        
        force = options.get("force", False)
        
        if GITHUB_TOKEN:
            self.stdout.write(self.style.SUCCESS("Using GitHub token for API requests"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "No GitHub token provided. Rate limits may apply. "
                    "Set GITHUB_TOKEN environment variable or use --github-token flag."
                )
            )
        
        self.stdout.write("Starting MCP Hub sync from GitHub...")
        
        # Collect all unique repositories
        all_repos = {}
        
        # Query 1: Code search for .well-known/mcp manifest
        self.stdout.write("Querying GitHub for .well-known/mcp manifests...")
        code_results = fetch_github_code_search('".well-known/mcp"+in:path+language:json')
        for repo in code_results:
            if repo.get("full_name"):
                all_repos[repo["full_name"]] = repo
        
        # Query 2: Repositories with "mcp server" in description
        self.stdout.write("Querying GitHub for 'mcp server' repositories...")
        repo_results = fetch_github_repos('"mcp server"')
        for repo in repo_results:
            if repo.get("full_name"):
                all_repos[repo["full_name"]] = repo
        
        # Query 3: Repositories with "model context protocol"
        self.stdout.write("Querying GitHub for 'model context protocol' repositories...")
        repo_results = fetch_github_repos('"model context protocol"')
        for repo in repo_results:
            if repo.get("full_name"):
                all_repos[repo["full_name"]] = repo
        
        # Query 4: Repositories with topic:mcp or topic:mcp-server
        self.stdout.write("Querying GitHub for topic:mcp repositories...")
        repo_results = fetch_github_repos("topic:mcp+topic:mcp-server")
        for repo in repo_results:
            if repo.get("full_name"):
                all_repos[repo["full_name"]] = repo
        
        # Query 5: Repositories with "mcp" in name
        self.stdout.write("Querying GitHub for repositories with 'mcp' in name...")
        repo_results = fetch_github_repos("mcp+in:name")
        for repo in repo_results:
            if repo.get("full_name"):
                all_repos[repo["full_name"]] = repo
        
        self.stdout.write(f"Found {len(all_repos)} unique repositories")
        
        # Process each repository
        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for full_name, repo_data in all_repos.items():
            try:
                github_id = repo_data.get("id")
                if not github_id:
                    error_count += 1
                    continue
                
                # Parse updated_at from GitHub
                updated_at_str = repo_data.get("updated_at")
                if updated_at_str:
                    updated_at_github = datetime.fromisoformat(
                        updated_at_str.replace("Z", "+00:00")
                    )
                else:
                    updated_at_github = timezone.now()
                
                # Check if server already exists
                try:
                    existing = MCPHubServer.objects.get(github_id=github_id)
                    
                    # Check if data has changed (only update if changed or forced)
                    data_changed = (
                        existing.full_name != full_name or
                        existing.name != repo_data.get("name", "") or
                        existing.description != (repo_data.get("description") or "") or
                        existing.stargazers_count != repo_data.get("stargazers_count", 0) or
                        existing.forks_count != repo_data.get("forks_count", 0) or
                        existing.language != (repo_data.get("language") or "") or
                        existing.topics != (repo_data.get("topics") or []) or
                        existing.owner_login != repo_data.get("owner", {}).get("login", "") or
                        existing.owner_avatar_url != (repo_data.get("owner", {}).get("avatar_url") or "") or
                        existing.html_url != repo_data.get("html_url", "") or
                        existing.updated_at_github != updated_at_github
                    )
                    
                    if not force and not data_changed:
                        skipped_count += 1
                        continue
                    
                    # Update existing record
                    existing.full_name = full_name
                    existing.name = repo_data.get("name", "")
                    existing.description = repo_data.get("description") or ""
                    existing.stargazers_count = repo_data.get("stargazers_count", 0)
                    existing.forks_count = repo_data.get("forks_count", 0)
                    existing.language = repo_data.get("language") or ""
                    existing.topics = repo_data.get("topics") or []
                    existing.owner_login = repo_data.get("owner", {}).get("login", "")
                    existing.owner_avatar_url = repo_data.get("owner", {}).get("avatar_url") or ""
                    existing.html_url = repo_data.get("html_url", "")
                    existing.updated_at_github = updated_at_github
                    existing.last_synced_at = timezone.now()
                    existing.is_active = True
                    existing.save()
                    updated_count += 1
                    
                except MCPHubServer.DoesNotExist:
                    # Create new record
                    MCPHubServer.objects.create(
                        github_id=github_id,
                        full_name=full_name,
                        name=repo_data.get("name", ""),
                        description=repo_data.get("description") or "",
                        stargazers_count=repo_data.get("stargazers_count", 0),
                        forks_count=repo_data.get("forks_count", 0),
                        language=repo_data.get("language") or "",
                        topics=repo_data.get("topics") or [],
                        owner_login=repo_data.get("owner", {}).get("login", ""),
                        owner_avatar_url=repo_data.get("owner", {}).get("avatar_url") or "",
                        html_url=repo_data.get("html_url", ""),
                        updated_at_github=updated_at_github,
                        last_synced_at=timezone.now(),
                        is_active=True,
                    )
                    created_count += 1
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing repository {full_name}: {e}")
                self.stdout.write(
                    self.style.WARNING(f"Error processing {full_name}: {e}")
                )
        
        # Mark servers as inactive if they weren't found in this sync
        # (only if we successfully synced some servers)
        if created_count + updated_count > 0:
            active_github_ids = {repo.get("id") for repo in all_repos.values() if repo.get("id")}
            inactive_count = MCPHubServer.objects.exclude(
                github_id__in=active_github_ids
            ).update(is_active=False)
            
            if inactive_count > 0:
                self.stdout.write(
                    self.style.WARNING(f"Marked {inactive_count} servers as inactive")
                )
        
        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Sync completed!"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Created: {created_count}")
        self.stdout.write(f"Updated: {updated_count}")
        self.stdout.write(f"Skipped (no changes): {skipped_count}")
        self.stdout.write(f"Errors: {error_count}")
        self.stdout.write(f"Total processed: {len(all_repos)}")

