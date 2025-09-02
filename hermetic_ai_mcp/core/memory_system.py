"""
Dual-Layer Memory System - Universal + Project-Specific
Core innovation of Hermetic AI Platform
"""
import sqlite3
import json
import time
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Types of memory entries"""
    PATTERN = "pattern"
    ERROR = "error"
    SOLUTION = "solution"
    COMMAND = "command"
    VERIFICATION = "verification"
    THOUGHT = "thought"
    ARCHITECTURE = "architecture"
    DOCUMENTATION = "documentation"


class MemoryScope(Enum):
    """Scope of memory storage"""
    UNIVERSAL = "universal"  # Cross-project knowledge
    PROJECT = "project"      # Project-specific knowledge
    SESSION = "session"      # Session-only (temporary)


@dataclass
class MemoryEntry:
    """Represents a memory entry"""
    id: str
    scope: MemoryScope
    type: MemoryType
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    created_at: float = None
    accessed_count: int = 0
    confidence_score: float = 1.0
    project_hash: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.id is None:
            # Generate ID from content hash
            self.id = hashlib.sha256(
                f"{self.content}_{self.created_at}".encode()
            ).hexdigest()[:16]


class DualLayerMemorySystem:
    """
    Dual-layer memory system with universal and project-specific storage
    """
    
    def __init__(self, base_dir: str = None):
        """
        Initialize dual-layer memory system
        
        Args:
            base_dir: Base directory for memory storage
        """
        self.base_dir = Path(base_dir) if base_dir else Path.home() / ".hermetic-ai"
        self.universal_dir = self.base_dir / "universal"
        self.projects_dir = self.base_dir / "projects"
        
        # Create directories
        self.universal_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize databases
        self.universal_conn = None
        self.project_conn = None
        self.current_project_hash = None
        
        # Memory caches
        self._universal_cache = {}
        self._project_cache = {}
        self._cache_size = 100
        
        # Pattern tracking for promotion
        self.pattern_usage = {}
        self.promotion_threshold = 3  # Times used across projects before promotion
        
        # Initialize universal database
        self._init_universal_db()
        
        logger.info("Dual-layer memory system initialized")
    
    def _init_universal_db(self):
        """Initialize universal memory database"""
        db_path = self.universal_dir / "universal_memory.db"
        self.universal_conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.universal_conn.row_factory = sqlite3.Row
        
        # Create tables with FTS5 for fast search
        cursor = self.universal_conn.cursor()
        
        # Main memory table with full-text search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories USING fts5(
                id UNINDEXED,
                type UNINDEXED,
                content,
                metadata UNINDEXED,
                embedding UNINDEXED,
                created_at UNINDEXED,
                accessed_count UNINDEXED,
                confidence_score UNINDEXED,
                source_projects UNINDEXED,
                tokenize='porter'
            )
        """)
        
        # Error patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS error_patterns (
                id TEXT PRIMARY KEY,
                error_type TEXT NOT NULL,
                error_message TEXT,
                solution TEXT,
                language TEXT,
                frequency INTEGER DEFAULT 1,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confidence REAL DEFAULT 1.0
            )
        """)
        
        # Command library table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS command_library (
                id TEXT PRIMARY KEY,
                command TEXT NOT NULL,
                description TEXT,
                category TEXT,
                usage_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 1.0,
                last_used TIMESTAMP
            )
        """)
        
        # Architecture patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS architecture_patterns (
                id TEXT PRIMARY KEY,
                pattern_name TEXT NOT NULL,
                description TEXT,
                implementation TEXT,
                use_cases TEXT,
                pros_cons TEXT,
                usage_count INTEGER DEFAULT 0,
                rating REAL DEFAULT 0.0
            )
        """)
        
        self.universal_conn.commit()
    
    def _init_project_db(self, project_hash: str):
        """Initialize project-specific memory database"""
        project_dir = self.projects_dir / project_hash
        project_dir.mkdir(exist_ok=True)
        
        db_path = project_dir / "project_memory.db"
        self.project_conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.project_conn.row_factory = sqlite3.Row
        
        cursor = self.project_conn.cursor()
        
        # Project-specific memories with FTS5
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS project_memories USING fts5(
                id UNINDEXED,
                type UNINDEXED,
                content,
                metadata UNINDEXED,
                file_path UNINDEXED,
                line_numbers UNINDEXED,
                created_at UNINDEXED,
                accessed_count UNINDEXED,
                relevance_score UNINDEXED,
                tokenize='porter'
            )
        """)
        
        # Project context table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_context (
                id TEXT PRIMARY KEY,
                context_type TEXT NOT NULL,
                content TEXT,
                relevance REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Project-specific verification results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verification_history (
                id TEXT PRIMARY KEY,
                code_hash TEXT NOT NULL,
                verification_result TEXT,
                has_mocks BOOLEAN,
                violations TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confidence REAL
            )
        """)
        
        # Project documentation requirements
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documentation_requirements (
                id TEXT PRIMARY KEY,
                requirement_type TEXT NOT NULL,
                content TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        
        self.project_conn.commit()
    
    def set_project(self, project_hash: str):
        """
        Set the current project for memory operations
        
        Args:
            project_hash: Project identifier hash
        """
        if self.current_project_hash == project_hash:
            return  # Already set
        
        # Close previous project connection if exists
        if self.project_conn:
            self.project_conn.close()
            self._project_cache.clear()
        
        self.current_project_hash = project_hash
        self._init_project_db(project_hash)
        
        logger.info(f"Project memory set to: {project_hash}")
    
    def store(self, 
              content: str, 
              memory_type: MemoryType,
              scope: MemoryScope = MemoryScope.PROJECT,
              metadata: Dict[str, Any] = None) -> MemoryEntry:
        """
        Store a memory entry
        
        Args:
            content: Content to store
            memory_type: Type of memory
            scope: Storage scope (universal or project)
            metadata: Additional metadata
            
        Returns:
            Created MemoryEntry
        """
        if metadata is None:
            metadata = {}
        
        # Create memory entry
        entry = MemoryEntry(
            id=None,  # Will be auto-generated
            scope=scope,
            type=memory_type,
            content=content,
            metadata=metadata,
            project_hash=self.current_project_hash if scope == MemoryScope.PROJECT else None
        )
        
        if scope == MemoryScope.UNIVERSAL:
            self._store_universal(entry)
        elif scope == MemoryScope.PROJECT:
            if not self.current_project_hash:
                raise ValueError("No project set for project-scoped memory")
            self._store_project(entry)
        
        return entry
    
    def _store_universal(self, entry: MemoryEntry):
        """Store in universal memory"""
        cursor = self.universal_conn.cursor()
        
        # Store based on type
        if entry.type == MemoryType.ERROR:
            cursor.execute("""
                INSERT OR REPLACE INTO error_patterns 
                (id, error_type, error_message, solution, language, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                entry.id,
                entry.metadata.get('error_type', 'unknown'),
                entry.content,
                entry.metadata.get('solution', ''),
                entry.metadata.get('language', ''),
                entry.confidence_score
            ))
        
        elif entry.type == MemoryType.COMMAND:
            cursor.execute("""
                INSERT OR REPLACE INTO command_library
                (id, command, description, category)
                VALUES (?, ?, ?, ?)
            """, (
                entry.id,
                entry.content,
                entry.metadata.get('description', ''),
                entry.metadata.get('category', 'general')
            ))
        
        elif entry.type == MemoryType.ARCHITECTURE:
            cursor.execute("""
                INSERT OR REPLACE INTO architecture_patterns
                (id, pattern_name, description, implementation)
                VALUES (?, ?, ?, ?)
            """, (
                entry.id,
                entry.metadata.get('pattern_name', 'unnamed'),
                entry.metadata.get('description', ''),
                entry.content
            ))
        
        # Also store in general memories table
        cursor.execute("""
            INSERT INTO memories 
            (id, type, content, metadata, created_at, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            entry.id,
            entry.type.value,
            entry.content,
            json.dumps(entry.metadata),
            entry.created_at,
            entry.confidence_score
        ))
        
        self.universal_conn.commit()
        
        # Update cache
        self._universal_cache[entry.id] = entry
    
    def _store_project(self, entry: MemoryEntry):
        """Store in project-specific memory"""
        if not self.project_conn:
            raise ValueError("No project database initialized")
        
        cursor = self.project_conn.cursor()
        
        # Store based on type
        if entry.type == MemoryType.VERIFICATION:
            cursor.execute("""
                INSERT INTO verification_history
                (id, code_hash, verification_result, has_mocks, violations, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                entry.id,
                entry.metadata.get('code_hash', ''),
                entry.content,
                entry.metadata.get('has_mocks', False),
                json.dumps(entry.metadata.get('violations', [])),
                entry.confidence_score
            ))
        
        elif entry.type == MemoryType.DOCUMENTATION:
            cursor.execute("""
                INSERT INTO documentation_requirements
                (id, requirement_type, content, status)
                VALUES (?, ?, ?, ?)
            """, (
                entry.id,
                entry.metadata.get('requirement_type', 'general'),
                entry.content,
                entry.metadata.get('status', 'pending')
            ))
        
        # Store in general project memories
        cursor.execute("""
            INSERT INTO project_memories
            (id, type, content, metadata, file_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            entry.id,
            entry.type.value,
            entry.content,
            json.dumps(entry.metadata),
            entry.metadata.get('file_path', ''),
            entry.created_at
        ))
        
        self.project_conn.commit()
        
        # Update cache
        self._project_cache[entry.id] = entry
        
        # Track pattern usage for potential promotion
        self._track_pattern_usage(entry)
    
    def _track_pattern_usage(self, entry: MemoryEntry):
        """Track pattern usage across projects for promotion"""
        if entry.type not in [MemoryType.PATTERN, MemoryType.SOLUTION]:
            return
        
        pattern_key = hashlib.sha256(entry.content.encode()).hexdigest()[:8]
        
        if pattern_key not in self.pattern_usage:
            self.pattern_usage[pattern_key] = {
                'projects': set(),
                'count': 0,
                'content': entry.content,
                'type': entry.type
            }
        
        self.pattern_usage[pattern_key]['projects'].add(self.current_project_hash)
        self.pattern_usage[pattern_key]['count'] += 1
        
        # Check for promotion
        if len(self.pattern_usage[pattern_key]['projects']) >= self.promotion_threshold:
            self._promote_to_universal(entry)
    
    def _promote_to_universal(self, entry: MemoryEntry):
        """Promote a project memory to universal"""
        logger.info(f"Promoting pattern to universal: {entry.id}")
        
        # Change scope and store in universal
        entry.scope = MemoryScope.UNIVERSAL
        entry.metadata['promoted'] = True
        entry.metadata['source_projects'] = list(
            self.pattern_usage.get(entry.id[:8], {}).get('projects', [])
        )
        
        self._store_universal(entry)
    
    def search(self, 
               query: str, 
               scope: MemoryScope = None,
               memory_type: MemoryType = None,
               limit: int = 10) -> List[MemoryEntry]:
        """
        Search memories using semantic search
        
        Args:
            query: Search query
            scope: Optional scope filter
            memory_type: Optional type filter
            limit: Maximum results
            
        Returns:
            List of matching MemoryEntry objects
        """
        results = []
        
        # Search universal if not filtered to project only
        if scope != MemoryScope.PROJECT:
            results.extend(self._search_universal(query, memory_type, limit))
        
        # Search project if not filtered to universal only
        if scope != MemoryScope.UNIVERSAL and self.project_conn:
            results.extend(self._search_project(query, memory_type, limit))
        
        # Sort by relevance and limit
        results.sort(key=lambda x: x.confidence_score, reverse=True)
        return results[:limit]
    
    def _search_universal(self, query: str, memory_type: MemoryType = None, limit: int = 10) -> List[MemoryEntry]:
        """Search universal memory"""
        cursor = self.universal_conn.cursor()
        
        # Use FTS5 for search or get all records for wildcard
        type_filter = f"AND type = '{memory_type.value}'" if memory_type else ""
        
        if query == "*":
            # Get all records without MATCH
            cursor.execute(f"""
                SELECT id, type, content, metadata, created_at, confidence_score
                FROM memories
                WHERE 1=1
                {type_filter}
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        else:
            # Use FTS5 MATCH for actual queries
            cursor.execute(f"""
                SELECT id, type, content, metadata, created_at, confidence_score
                FROM memories
                WHERE memories MATCH ?
                {type_filter}
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
        
        results = []
        for row in cursor.fetchall():
            entry = MemoryEntry(
                id=row['id'],
                scope=MemoryScope.UNIVERSAL,
                type=MemoryType(row['type']),
                content=row['content'],
                metadata=json.loads(row['metadata']),
                created_at=row['created_at'],
                confidence_score=row['confidence_score']
            )
            results.append(entry)
        
        return results
    
    def _search_project(self, query: str, memory_type: MemoryType = None, limit: int = 10) -> List[MemoryEntry]:
        """Search project-specific memory"""
        if not self.project_conn:
            return []
        
        cursor = self.project_conn.cursor()
        
        type_filter = f"AND type = '{memory_type.value}'" if memory_type else ""
        
        if query == "*":
            # Get all records without MATCH
            cursor.execute(f"""
                SELECT id, type, content, metadata, created_at
                FROM project_memories
                WHERE 1=1
                {type_filter}
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        else:
            # Use FTS5 MATCH for actual queries
            cursor.execute(f"""
                SELECT id, type, content, metadata, created_at
                FROM project_memories
                WHERE project_memories MATCH ?
                {type_filter}
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
        
        results = []
        for row in cursor.fetchall():
            entry = MemoryEntry(
                id=row['id'],
                scope=MemoryScope.PROJECT,
                type=MemoryType(row['type']),
                content=row['content'],
                metadata=json.loads(row['metadata']),
                created_at=row['created_at'],
                project_hash=self.current_project_hash
            )
            results.append(entry)
        
        return results
    
    def get_relevant_context(self, query: str, max_tokens: int = 4000) -> Dict[str, Any]:
        """
        Get relevant context for a query, combining universal and project memories
        
        Args:
            query: Context query
            max_tokens: Maximum tokens to return
            
        Returns:
            Context dictionary with memories and metadata
        """
        # Search both layers
        universal_results = self._search_universal(query, limit=5)
        project_results = self._search_project(query, limit=10)
        
        # Combine and prioritize
        all_results = project_results + universal_results  # Project first
        
        # Build context within token limit
        context = {
            'memories': [],
            'total_found': len(all_results),
            'sources': {'universal': len(universal_results), 'project': len(project_results)}
        }
        
        current_tokens = 0
        for entry in all_results:
            # Rough token estimation (4 chars = 1 token)
            entry_tokens = len(entry.content) // 4
            if current_tokens + entry_tokens > max_tokens:
                break
            
            context['memories'].append({
                'content': entry.content,
                'type': entry.type.value,
                'scope': entry.scope.value,
                'metadata': entry.metadata
            })
            current_tokens += entry_tokens
        
        context['token_count'] = current_tokens
        return context
    
    def export_universal_knowledge(self) -> Dict[str, Any]:
        """Export all universal knowledge for backup or sharing"""
        cursor = self.universal_conn.cursor()
        
        export = {
            'timestamp': datetime.now().isoformat(),
            'error_patterns': [],
            'commands': [],
            'architecture_patterns': [],
            'general_memories': []
        }
        
        # Export error patterns
        cursor.execute("SELECT * FROM error_patterns")
        for row in cursor.fetchall():
            export['error_patterns'].append(dict(row))
        
        # Export commands
        cursor.execute("SELECT * FROM command_library")
        for row in cursor.fetchall():
            export['commands'].append(dict(row))
        
        # Export architecture patterns
        cursor.execute("SELECT * FROM architecture_patterns")
        for row in cursor.fetchall():
            export['architecture_patterns'].append(dict(row))
        
        return export
    
    def close(self):
        """Close database connections"""
        if self.universal_conn:
            self.universal_conn.close()
        if self.project_conn:
            self.project_conn.close()