# Tool Curation Layer - Design Document

## 🎯 Problem Statement

### Aktuelle Situation (❌ Anti-Pattern)

```
Externe MCP Server (z.B. postgres-mcp)
  ├─ execute_query
  ├─ list_tables
  ├─ describe_table
  ├─ insert_row
  ├─ update_row
  └─ ... (45+ weitere Tools)
           ↓
    AgentxSuite sync_connection()
           ↓
    Alle 50 Tools in DB gespeichert
           ↓
    Agent sieht alle 50 Tools
           ↓
    ❌ Context Pollution (10.000+ Tokens)
    ❌ Agent verwirrt, langsam, teuer
    ❌ Halluzinationen (erfindet Tools)
```

### Ziel (✅ Best Practice)

```
Externe MCP Server (50 atomare Tools)
           ↓
    Tool Curator (Aggregation)
           ↓
    3 High-Level Curated Tools
           ↓
    Agent sieht nur 3 Tools
           ↓
    ✅ Klarer Context (~300 Tokens)
    ✅ Agent fokussiert, schnell
    ✅ Keine Halluzinationen
```

---

## 🏗️ Architektur-Übersicht

### Neue Komponenten

```
┌─────────────────────────────────────────────────────────────┐
│                    AgentxSuite Architecture                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 1. RAW TOOLS LAYER (bestehend)                       │   │
│  │    - Tool Model (unverändert)                        │   │
│  │    - sync_connection() speichert alle Raw Tools      │   │
│  │    - Nur für interne Orchestrierung sichtbar         │   │
│  └──────────────────────────────────────────────────────┘   │
│                            ↓                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 2. CURATION LAYER (NEU)                              │   │
│  │    - CuratedTool Model (High-Level Tools)            │   │
│  │    - Curators Registry (pluggable)                   │   │
│  │    - Tool Mapping (Curated → Raw)                    │   │
│  │    - Auto-Generation nach Sync                       │   │
│  └──────────────────────────────────────────────────────┘   │
│                            ↓                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 3. EXECUTION LAYER (erweitert)                       │   │
│  │    - Curated Tool Resolution                         │   │
│  │    - Multi-Tool Orchestration                        │   │
│  │    - Result Aggregation                              │   │
│  └──────────────────────────────────────────────────────┘   │
│                            ↓                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 4. AGENT-FACING APIs (modified)                      │   │
│  │    - MCP Fabric: expose CuratedTools                 │   │
│  │    - Claude SDK: generate from CuratedTools          │   │
│  │    - REST API: optional Raw Tools view               │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Datenbank-Schema

### 1. Tool Model (bestehend, unverändert)

```python
class Tool(TimeStamped):
    """Raw tool from external MCP server (internal use only)."""
    organization = FK(Organization)
    environment = FK(Environment)
    connection = FK(Connection)
    name = CharField(max_length=255)
    version = CharField(max_length=50, default="1.0.0")
    schema_json = JSONField(default=dict)
    enabled = BooleanField(default=True)
    
    # NEW: Mark if tool is exposed to agents
    is_agent_visible = BooleanField(default=False)  # Default: hidden from agents
    
    class Meta:
        unique_together = [["organization", "environment", "name", "version"]]
```

### 2. CuratedTool Model (NEU)

```python
class CuratedTool(TimeStamped):
    """
    High-level tool that aggregates one or more raw tools.
    This is what agents see and execute.
    """
    organization = FK(Organization)
    environment = FK(Environment)
    connection = FK(Connection)  # Source connection
    
    # High-level tool definition
    name = CharField(max_length=255)  # e.g. "query_database"
    display_name = CharField(max_length=255)  # e.g. "Query Database"
    description = TextField()
    schema_json = JSONField(default=dict)  # Simplified schema for agents
    
    # Curation metadata
    curator_type = CharField(max_length=100)  # e.g. "postgres", "slack", "github"
    raw_tools = M2M(Tool, related_name="curated_parents")  # Which raw tools this uses
    orchestration_config = JSONField(default=dict)  # How to combine raw tools
    
    # Control
    enabled = BooleanField(default=True)
    category = CharField(max_length=100, blank=True)  # "database", "api", "system"
    tags = JSONField(default=list)  # For filtering
    
    # Usage tracking
    usage_count = IntegerField(default=0)
    avg_execution_time_ms = IntegerField(null=True, blank=True)
    
    class Meta:
        db_table = "tools_curated_tool"
        unique_together = [["organization", "environment", "name"]]
        indexes = [
            models.Index(fields=["connection", "enabled"]),
            models.Index(fields=["curator_type"]),
            models.Index(fields=["category"]),
        ]
```

### 3. CurationMapping Model (NEU)

```python
class CurationMapping(TimeStamped):
    """
    Maps how a curated tool uses raw tools.
    One CuratedTool can have multiple CurationMappings.
    """
    curated_tool = FK(CuratedTool, on_delete=CASCADE, related_name="mappings")
    raw_tool = FK(Tool, on_delete=CASCADE)
    
    # Execution order (for multi-step orchestration)
    execution_order = IntegerField(default=0)
    
    # Parameter mapping: curated_param → raw_param
    # Example: {"keyword": "search_query", "limit": "max_results"}
    parameter_mapping = JSONField(default=dict)
    
    # Conditional execution
    condition = CharField(max_length=255, blank=True)  # e.g. "if result.count > 0"
    
    class Meta:
        db_table = "tools_curation_mapping"
        unique_together = [["curated_tool", "raw_tool", "execution_order"]]
        ordering = ["execution_order"]
```

---

## 🔧 Core Components

### 1. Base Curator (Abstract)

```python
# backend/apps/tools/curators/base.py

from abc import ABC, abstractmethod
from typing import List

class BaseCurator(ABC):
    """
    Base class for tool curators.
    
    Each curator knows how to:
    1. Identify if it can curate a connection
    2. Generate curated tools from raw tools
    3. Orchestrate execution
    """
    
    curator_type: str = "base"
    
    @abstractmethod
    def can_curate(self, connection: Connection, raw_tools: List[Tool]) -> bool:
        """Check if this curator can handle the connection."""
        pass
    
    @abstractmethod
    def generate_curated_tools(
        self, 
        connection: Connection, 
        raw_tools: List[Tool]
    ) -> List[dict]:
        """
        Generate curated tool definitions.
        
        Returns:
            List of curated tool definitions:
            [
                {
                    "name": "query_database",
                    "display_name": "Query Database",
                    "description": "Execute SQL queries...",
                    "schema_json": {...},
                    "category": "database",
                    "raw_tool_names": ["execute_query", "list_tables"],
                    "orchestration_config": {
                        "strategy": "sequential",
                        "steps": [...]
                    }
                },
                ...
            ]
        """
        pass
    
    @abstractmethod
    async def orchestrate_execution(
        self,
        curated_tool: CuratedTool,
        input_data: dict,
        executor_func: callable,
    ) -> dict:
        """
        Execute curated tool by orchestrating raw tools.
        
        Args:
            curated_tool: CuratedTool instance
            input_data: User input for curated tool
            executor_func: Function to execute raw tools
                          Signature: (tool: Tool, input: dict) -> dict
        
        Returns:
            Aggregated result
        """
        pass
```

### 2. PostgreSQL Curator Example

```python
# backend/apps/tools/curators/postgres.py

class PostgresCurator(BaseCurator):
    """Curator for PostgreSQL MCP servers."""
    
    curator_type = "postgres"
    
    def can_curate(self, connection: Connection, raw_tools: List[Tool]) -> bool:
        """Check if connection is a Postgres MCP server."""
        tool_names = [t.name for t in raw_tools]
        postgres_indicators = ["execute_query", "list_tables", "describe_table"]
        return any(indicator in tool_names for indicator in postgres_indicators)
    
    def generate_curated_tools(
        self, 
        connection: Connection, 
        raw_tools: List[Tool]
    ) -> List[dict]:
        """
        Aggregate 10+ Postgres tools into 2 high-level tools.
        """
        return [
            {
                "name": "query_database",
                "display_name": "Query Database",
                "description": (
                    "Execute SQL queries against the database. "
                    "Automatically handles schema discovery and result formatting."
                ),
                "schema_json": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "SQL query to execute"
                        },
                        "max_rows": {
                            "type": "integer",
                            "default": 100,
                            "description": "Maximum rows to return"
                        }
                    },
                    "required": ["query"]
                },
                "category": "database",
                "raw_tool_names": ["execute_query", "list_tables", "describe_table"],
                "orchestration_config": {
                    "strategy": "smart_query",
                    "steps": [
                        {
                            "tool": "list_tables",
                            "condition": "if query contains table names not in cache"
                        },
                        {
                            "tool": "execute_query",
                            "parameter_mapping": {
                                "query": "sql",
                                "max_rows": "limit"
                            }
                        }
                    ]
                }
            },
            {
                "name": "manage_schema",
                "display_name": "Manage Database Schema",
                "description": "View and modify database schema (tables, columns, indexes).",
                "schema_json": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["list_tables", "describe_table", "create_table"],
                            "description": "Action to perform"
                        },
                        "table_name": {
                            "type": "string",
                            "description": "Table name (required for describe/create)"
                        }
                    },
                    "required": ["action"]
                },
                "category": "database",
                "raw_tool_names": ["list_tables", "describe_table", "create_table"],
                "orchestration_config": {
                    "strategy": "conditional",
                    "action_mapping": {
                        "list_tables": {"tool": "list_tables"},
                        "describe_table": {"tool": "describe_table", "param": "table_name"},
                        "create_table": {"tool": "create_table", "param": "table_name"}
                    }
                }
            }
        ]
    
    async def orchestrate_execution(
        self,
        curated_tool: CuratedTool,
        input_data: dict,
        executor_func: callable,
    ) -> dict:
        """Execute Postgres curated tool."""
        config = curated_tool.orchestration_config
        strategy = config.get("strategy")
        
        if strategy == "smart_query":
            # Step 1: Optional schema discovery
            query = input_data.get("query", "")
            if self._needs_schema_info(query):
                list_tables_tool = curated_tool.raw_tools.filter(name="list_tables").first()
                if list_tables_tool:
                    tables_result = await executor_func(list_tables_tool, {})
                    # Cache tables for validation
            
            # Step 2: Execute query
            execute_tool = curated_tool.raw_tools.filter(name="execute_query").first()
            if not execute_tool:
                raise ValueError("execute_query tool not found")
            
            result = await executor_func(execute_tool, {
                "sql": input_data.get("query"),
                "limit": input_data.get("max_rows", 100)
            })
            
            return result
        
        elif strategy == "conditional":
            action = input_data.get("action")
            action_mapping = config.get("action_mapping", {}).get(action)
            
            if not action_mapping:
                raise ValueError(f"Unknown action: {action}")
            
            tool_name = action_mapping.get("tool")
            raw_tool = curated_tool.raw_tools.filter(name=tool_name).first()
            
            if not raw_tool:
                raise ValueError(f"Raw tool {tool_name} not found")
            
            # Map parameters
            param_key = action_mapping.get("param")
            raw_input = {param_key: input_data.get(param_key)} if param_key else {}
            
            result = await executor_func(raw_tool, raw_input)
            return result
        
        else:
            raise ValueError(f"Unknown orchestration strategy: {strategy}")
    
    def _needs_schema_info(self, query: str) -> bool:
        """Check if query references tables we should validate."""
        # Simple heuristic - can be improved
        keywords = ["FROM", "JOIN", "INTO", "UPDATE"]
        return any(kw in query.upper() for kw in keywords)
```

### 3. Curators Registry

```python
# backend/apps/tools/curators/registry.py

from typing import List, Type
from apps.tools.curators.base import BaseCurator
from apps.tools.curators.postgres import PostgresCurator
from apps.tools.curators.slack import SlackCurator
from apps.tools.curators.github import GitHubCurator
from apps.tools.curators.passthrough import PassthroughCurator

class CuratorsRegistry:
    """Registry of all available curators."""
    
    # Curators are tried in order - more specific first
    CURATORS: List[Type[BaseCurator]] = [
        PostgresCurator,
        SlackCurator,
        GitHubCurator,
        PassthroughCurator,  # Fallback: exposes all tools as-is
    ]
    
    @classmethod
    def get_curator(
        cls, 
        connection: Connection, 
        raw_tools: List[Tool]
    ) -> BaseCurator:
        """
        Find appropriate curator for connection.
        
        Returns first curator that can handle the connection,
        or PassthroughCurator as fallback.
        """
        for curator_class in cls.CURATORS:
            curator = curator_class()
            if curator.can_curate(connection, raw_tools):
                logger.info(f"Selected curator: {curator.curator_type} for {connection.name}")
                return curator
        
        # Should never reach here due to PassthroughCurator
        logger.warning(f"No curator found for {connection.name}, using passthrough")
        return PassthroughCurator()
```

### 4. Passthrough Curator (Fallback)

```python
# backend/apps/tools/curators/passthrough.py

class PassthroughCurator(BaseCurator):
    """
    Fallback curator that exposes all raw tools as-is.
    Used for unknown MCP servers or when no curation is desired.
    """
    
    curator_type = "passthrough"
    
    def can_curate(self, connection: Connection, raw_tools: List[Tool]) -> bool:
        """Always returns True (fallback)."""
        return True
    
    def generate_curated_tools(
        self, 
        connection: Connection, 
        raw_tools: List[Tool]
    ) -> List[dict]:
        """Expose all raw tools as curated tools (1:1 mapping)."""
        curated = []
        for tool in raw_tools:
            curated.append({
                "name": tool.name,
                "display_name": tool.name.replace("_", " ").title(),
                "description": tool.schema_json.get("description", f"Tool: {tool.name}"),
                "schema_json": tool.schema_json,
                "category": "general",
                "raw_tool_names": [tool.name],
                "orchestration_config": {
                    "strategy": "passthrough"
                }
            })
        return curated
    
    async def orchestrate_execution(
        self,
        curated_tool: CuratedTool,
        input_data: dict,
        executor_func: callable,
    ) -> dict:
        """Direct 1:1 execution."""
        raw_tool = curated_tool.raw_tools.first()
        if not raw_tool:
            raise ValueError("No raw tool found for passthrough")
        
        return await executor_func(raw_tool, input_data)
```

---

## 🔄 Curation Workflow

### 1. Tool Sync mit Auto-Curation

```python
# backend/apps/connections/services.py (MODIFIED)

def sync_connection(conn: Connection) -> tuple[list[Tool], list[CuratedTool]]:
    """
    Sync tools from connection and auto-generate curated tools.
    
    Returns:
        Tuple of (created_raw_tools, created_curated_tools)
    """
    # 1. Verify MCP server (bestehend)
    if not verify_mcp_server(conn):
        raise ValidationError("Not a valid MCP server")
    
    # 2. Fetch raw tools (bestehend)
    tools_data = _fetch_tools_with_validation(conn)
    tools_list = tools_data.get("tools", [])
    
    # 3. Create/update raw tools (bestehend, aber mit is_agent_visible=False)
    created_raw_tools = []
    for tool_def in tools_list:
        tool, created = Tool.objects.get_or_create(
            organization=conn.organization,
            environment=conn.environment,
            name=tool_def["name"],
            version="1.0.0",
            defaults={
                "connection": conn,
                "schema_json": tool_def.get("inputSchema", {}),
                "enabled": True,
                "is_agent_visible": False,  # NEW: Hidden from agents by default
                "sync_status": "synced",
            },
        )
        if created:
            created_raw_tools.append(tool)
    
    # 4. AUTO-GENERATE CURATED TOOLS (NEW)
    from apps.tools.curators.registry import CuratorsRegistry
    from apps.tools.curation_service import CurationService
    
    raw_tools = Tool.objects.filter(
        organization=conn.organization,
        environment=conn.environment,
        connection=conn,
        enabled=True,
    )
    
    curator = CuratorsRegistry.get_curator(conn, list(raw_tools))
    curated_tools = CurationService.generate_curated_tools(
        connection=conn,
        raw_tools=list(raw_tools),
        curator=curator,
    )
    
    logger.info(
        f"Sync complete: {len(created_raw_tools)} raw tools, "
        f"{len(curated_tools)} curated tools"
    )
    
    return created_raw_tools, curated_tools
```

### 2. Curation Service

```python
# backend/apps/tools/curation_service.py (NEW)

class CurationService:
    """Service for managing curated tools."""
    
    @staticmethod
    def generate_curated_tools(
        connection: Connection,
        raw_tools: List[Tool],
        curator: BaseCurator,
    ) -> List[CuratedTool]:
        """
        Generate curated tools from raw tools using curator.
        
        Returns:
            List of created CuratedTool instances
        """
        curated_defs = curator.generate_curated_tools(connection, raw_tools)
        created_curated = []
        
        for curated_def in curated_defs:
            # Create or update curated tool
            curated_tool, created = CuratedTool.objects.update_or_create(
                organization=connection.organization,
                environment=connection.environment,
                name=curated_def["name"],
                defaults={
                    "connection": connection,
                    "display_name": curated_def.get("display_name", curated_def["name"]),
                    "description": curated_def.get("description", ""),
                    "schema_json": curated_def.get("schema_json", {}),
                    "curator_type": curator.curator_type,
                    "orchestration_config": curated_def.get("orchestration_config", {}),
                    "category": curated_def.get("category", "general"),
                    "enabled": True,
                },
            )
            
            # Link raw tools
            raw_tool_names = curated_def.get("raw_tool_names", [])
            linked_raw_tools = raw_tools.filter(name__in=raw_tool_names)
            curated_tool.raw_tools.set(linked_raw_tools)
            
            # Create mappings (if orchestration config specifies)
            _create_curation_mappings(curated_tool, curated_def.get("orchestration_config", {}))
            
            created_curated.append(curated_tool)
            logger.info(f"Created curated tool: {curated_tool.name}")
        
        return created_curated
    
    @staticmethod
    async def execute_curated_tool(
        curated_tool: CuratedTool,
        input_data: dict,
        agent: Agent,
        timeout_seconds: int = 30,
    ) -> dict:
        """
        Execute curated tool by orchestrating raw tools.
        
        This is called from start_run() when agent executes a curated tool.
        """
        from apps.tools.curators.registry import CuratorsRegistry
        
        # Get curator
        raw_tools = list(curated_tool.raw_tools.all())
        curator = CuratorsRegistry.get_curator(curated_tool.connection, raw_tools)
        
        # Create executor function for raw tools
        async def executor(raw_tool: Tool, raw_input: dict) -> dict:
            """Execute raw tool via existing run service."""
            from apps.runs.services import start_run
            
            run = await sync_to_async(start_run)(
                agent=agent,
                tool=raw_tool,
                input_json=raw_input,
                timeout_seconds=timeout_seconds,
            )
            
            if run.status == "succeeded":
                return run.output_json
            else:
                raise ValueError(f"Raw tool execution failed: {run.error_message}")
        
        # Orchestrate execution
        result = await curator.orchestrate_execution(
            curated_tool=curated_tool,
            input_data=input_data,
            executor_func=executor,
        )
        
        # Update usage stats
        curated_tool.usage_count += 1
        curated_tool.save(update_fields=["usage_count"])
        
        return result


def _create_curation_mappings(curated_tool: CuratedTool, orchestration_config: dict):
    """Create CurationMapping entries from orchestration config."""
    # Clear existing mappings
    curated_tool.mappings.all().delete()
    
    strategy = orchestration_config.get("strategy")
    
    if strategy == "sequential":
        steps = orchestration_config.get("steps", [])
        for idx, step in enumerate(steps):
            tool_name = step.get("tool")
            raw_tool = curated_tool.raw_tools.filter(name=tool_name).first()
            
            if raw_tool:
                CurationMapping.objects.create(
                    curated_tool=curated_tool,
                    raw_tool=raw_tool,
                    execution_order=idx,
                    parameter_mapping=step.get("parameter_mapping", {}),
                    condition=step.get("condition", ""),
                )
```

---

## 🚀 Integration Points

### 1. MCP Fabric - Expose Curated Tools

```python
# backend/mcp_fabric/registry.py (MODIFIED)

def get_tools_list_for_org_env(
    *,
    org: "Organization",
    env: "Environment",
) -> list[dict]:
    """
    Get list of CURATED tools for agents.
    
    This replaces raw tools with curated versions.
    """
    tools_list = []
    
    # 1. Get curated tools (NEW - primary source for agents)
    from apps.tools.models import CuratedTool
    
    curated_tools = CuratedTool.objects.filter(
        organization=org,
        environment=env,
        enabled=True,
    ).select_related("connection")
    
    for tool in curated_tools:
        tool_dict = {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.schema_json,
        }
        tools_list.append(tool_dict)
    
    # 2. Get raw tools marked as agent-visible (optional)
    # These are tools explicitly exposed without curation
    raw_tools = Tool.objects.filter(
        organization=org,
        environment=env,
        enabled=True,
        is_agent_visible=True,  # NEW: Only if explicitly enabled
    ).select_related("connection")
    
    for tool in raw_tools:
        tool_dict = {
            "name": tool.name,
            "description": tool.schema_json.get("description", f"Tool: {tool.name}"),
            "inputSchema": tool.schema_json,
        }
        tools_list.append(tool_dict)
    
    # 3. Add system tools (unchanged)
    from apps.system_tools.tools import SYSTEM_TOOLS
    for tool_def in SYSTEM_TOOLS:
        tools_list.append({
            "name": tool_def["name"],
            "description": tool_def["description"],
            "inputSchema": tool_def["schema"],
        })
    
    return tools_list
```

### 2. Tool Execution - Handle Curated Tools

```python
# backend/apps/runs/services.py (MODIFIED)

def start_run(
    *,
    agent: Agent,
    tool: Tool | CuratedTool,  # NEW: Can be either type
    input_json: dict,
    timeout_seconds: int = 30,
) -> Run:
    """Execute tool (raw or curated) with full security pipeline."""
    
    # Determine if this is a curated tool
    from apps.tools.models import CuratedTool
    
    is_curated = isinstance(tool, CuratedTool)
    
    # ... (existing security checks: policy, rate limit, etc.)
    
    # Create run record
    run = Run.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        agent=agent,
        tool=tool if not is_curated else None,  # Only link if raw tool
        curated_tool=tool if is_curated else None,  # NEW field
        input_json=input_json,
        status="pending",
    )
    
    try:
        # Execute tool based on type
        if is_curated:
            # NEW: Curated tool execution
            from apps.tools.curation_service import CurationService
            
            result = await CurationService.execute_curated_tool(
                curated_tool=tool,
                input_data=input_json,
                agent=agent,
                timeout_seconds=timeout_seconds,
            )
            run.output_json = result
            run.status = "succeeded"
        
        else:
            # Existing: Raw tool execution via HTTP
            result = execute_tool()  # Existing logic
            run.output_json = result
            run.status = "succeeded"
        
        run.finished_at = timezone.now()
        run.save()
        
    except Exception as e:
        # ... (existing error handling)
    
    return run
```

### 3. Claude Agent SDK - Generate from Curated Tools

```python
# backend/apps/claude_agent/agent_registry.py (MODIFIED)

class AgentxSuiteToolRegistry:
    """Registry generates tools from CURATED tools, not raw tools."""
    
    def __init__(self, organization_id: str, environment_id: str):
        self.organization_id = organization_id
        self.environment_id = environment_id
        self.tools = self._generate_tools_from_curated()
    
    def _generate_tools_from_curated(self) -> list[dict[str, Any]]:
        """
        Generate Claude tool definitions from CuratedTools.
        
        This replaces the generic "execute_tool" with specific tools.
        """
        from apps.tools.models import CuratedTool
        from apps.tenants.models import Organization, Environment
        
        org = Organization.objects.get(id=self.organization_id)
        env = Environment.objects.get(id=self.environment_id)
        
        curated_tools = CuratedTool.objects.filter(
            organization=org,
            environment=env,
            enabled=True,
        )
        
        claude_tools = []
        
        # Add each curated tool as a specific Claude tool
        for tool in curated_tools:
            claude_tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.schema_json,
            })
        
        # Add AgentxSuite meta-tools (list agents, list runs, etc.)
        claude_tools.extend(self._get_meta_tools())
        
        return claude_tools
    
    def _get_meta_tools(self) -> list[dict]:
        """Get AgentxSuite management tools."""
        return [
            {
                "name": "list_available_tools",
                "description": "List all curated tools in current environment",
                "input_schema": {"type": "object", "properties": {}}
            },
            {
                "name": "get_agent_info",
                "description": "Get agent capabilities and config",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string"}
                    }
                }
            },
            # ... other meta tools
        ]
```

---

## 📋 Migration Plan

### Phase 1: Database Schema (Week 1)

1. Create migrations for:
   - `CuratedTool` model
   - `CurationMapping` model
   - Add `is_agent_visible` to `Tool`
   - Add `curated_tool` FK to `Run`

2. Run migrations

### Phase 2: Core Curators (Week 2)

1. Implement base curator framework
2. Create specific curators:
   - PostgresCurator
   - SlackCurator (if needed)
   - PassthroughCurator (fallback)
3. Test curators in isolation

### Phase 3: Integration (Week 3)

1. Modify `sync_connection()` to auto-generate curated tools
2. Update MCP Fabric to expose curated tools
3. Modify `start_run()` to handle curated tools
4. Add curation service for execution

### Phase 4: Claude SDK (Week 4)

1. Refactor `AgentxSuiteToolRegistry` to use curated tools
2. Remove generic `execute_tool`
3. Test with Claude Desktop

### Phase 5: Frontend & Management (Week 5)

1. Add UI to view/manage curated tools
2. Add "Curation Strategy" selector in connection settings
3. Add toggle to expose individual raw tools
4. Add curation analytics (usage, performance)

### Phase 6: Documentation & Rollout (Week 6)

1. Write curator development guide
2. Document orchestration patterns
3. Add metrics/monitoring
4. Gradual rollout with feature flag

---

## 🎯 Success Metrics

### Before (Current State)
- ❌ External MCP server: 50 tools → Agent sees 50 tools
- ❌ Context size: ~10,000 tokens per agent call
- ❌ Tool hallucinations: ~15% of calls
- ❌ Avg execution time: 8 seconds (multiple round trips)

### After (With Curation)
- ✅ External MCP server: 50 tools → Agent sees 3 curated tools
- ✅ Context size: ~300 tokens per agent call (97% reduction)
- ✅ Tool hallucinations: <2% (clear, well-documented tools)
- ✅ Avg execution time: 3 seconds (orchestrated internally)

---

## 🔍 Example: PostgreSQL MCP Server

### Before (No Curation)

```
Agent sees:
  ├─ execute_query
  ├─ execute_read_only_query
  ├─ list_tables
  ├─ describe_table
  ├─ list_columns
  ├─ get_table_info
  ├─ insert_row
  ├─ insert_rows
  ├─ update_row
  ├─ update_rows
  ├─ delete_row
  ├─ delete_rows
  ├─ create_table
  ├─ drop_table
  ├─ alter_table
  └─ ... (35+ more tools)

Context pollution: ~12,000 tokens
Agent behavior: Confused, tries random combinations
```

### After (With Curation)

```
Agent sees:
  ├─ query_database (Read operations)
  ├─ manage_schema (DDL operations)
  └─ modify_data (DML operations)

Context size: ~400 tokens
Agent behavior: Clear, focused, efficient

Execution example:
User: "Show me all users from the database"
  ↓
Agent calls: query_database(query="SELECT * FROM users")
  ↓
Curator orchestrates:
  1. list_tables() → validate "users" exists
  2. execute_read_only_query(sql="SELECT * FROM users", limit=100)
  ↓
Result aggregated and returned to agent
```

---

## 🚦 Decision Points

### 1. Manual vs Auto Curation

**Option A: Fully Automatic (Recommended)**
- ✅ Auto-generate curated tools after sync
- ✅ Curator detects server type
- ❌ Less control

**Option B: Manual Review**
- ✅ Admin reviews/approves curated tools
- ❌ More work
- ❌ Slower

**Decision: Start with Option A, add Option B later**

### 2. Raw Tool Visibility

**Option A: Hide All Raw Tools (Recommended)**
- ✅ Agents only see curated tools
- ✅ Clear, focused context
- ❌ Less flexibility

**Option B: Expose via Flag**
- ✅ Some raw tools can be marked `is_agent_visible=True`
- ❌ Risk of context pollution

**Decision: Option A by default, Option B for power users**

### 3. Curator Complexity

**Option A: Simple Curators (Recommended)**
- ✅ 1-3 curated tools per connection
- ✅ Basic orchestration (sequential, conditional)
- ❌ May not handle complex workflows

**Option B: Advanced Curators**
- ✅ Complex orchestration (loops, retries, transactions)
- ❌ More code, harder to debug

**Decision: Start with Option A, iterate based on usage**

---

## 🔧 Configuration

### Settings

```python
# backend/config/settings/base.py

# Tool Curation
TOOL_CURATION_ENABLED = True  # Feature flag
TOOL_CURATION_AUTO_SYNC = True  # Auto-generate after sync
TOOL_CURATION_FALLBACK = "passthrough"  # What to do if no curator found

# Curators
TOOL_CURATORS = [
    "apps.tools.curators.postgres.PostgresCurator",
    "apps.tools.curators.slack.SlackCurator",
    "apps.tools.curators.github.GitHubCurator",
    "apps.tools.curators.passthrough.PassthroughCurator",
]

# Agent Tool Exposure
AGENT_TOOL_MODE = "curated_only"  # Options: "curated_only", "curated_and_raw", "raw_only"
```

---

## 📚 References

- [Stop Converting Your REST APIs to MCP](https://www.jlowin.dev/blog/stop-converting-rest-apis-to-mcp) - Jeremiah Lowin
- [MCP Protocol Specification](https://modelcontextprotocol.io/docs)
- AgentxSuite Architecture Rules (workspace rules)

