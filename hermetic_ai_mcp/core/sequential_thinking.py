"""
Sequential Thinking Module - Reimplemented for Hermetic AI Platform
Based on the core logic from Sequential Thinking MCP, integrated natively
"""
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum


class ThoughtType(Enum):
    """Types of thoughts in the sequential thinking process"""
    REGULAR = "regular"
    REVISION = "revision"
    BRANCH = "branch"
    HYPOTHESIS = "hypothesis"
    VERIFICATION = "verification"


@dataclass
class ThoughtData:
    """Represents a single thought in the thinking sequence"""
    thought: str
    thought_number: int
    total_thoughts: int
    next_thought_needed: bool
    thought_type: ThoughtType = ThoughtType.REGULAR
    is_revision: bool = False
    revises_thought: Optional[int] = None
    branch_from_thought: Optional[int] = None
    branch_id: Optional[str] = None
    needs_more_thoughts: bool = False
    timestamp: float = None
    confidence_score: float = 1.0
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        
        # Auto-detect thought type
        if self.is_revision:
            self.thought_type = ThoughtType.REVISION
        elif self.branch_from_thought:
            self.thought_type = ThoughtType.BRANCH
        elif "hypothesis" in self.thought.lower():
            self.thought_type = ThoughtType.HYPOTHESIS
        elif "verif" in self.thought.lower():
            self.thought_type = ThoughtType.VERIFICATION


class SequentialThinkingEngine:
    """
    Core engine for sequential thinking process
    Reimplemented from TypeScript to Python with enhancements
    """
    
    def __init__(self, memory_system=None):
        """
        Initialize the sequential thinking engine
        
        Args:
            memory_system: Optional reference to memory system for persistence
        """
        self.thought_history: List[ThoughtData] = []
        self.branches: Dict[str, List[ThoughtData]] = {}
        self.current_branch: Optional[str] = None
        self.memory_system = memory_system
        self.thought_patterns = {}
        self.hypothesis_stack = []
        
    def validate_thought_input(self, data: Dict[str, Any]) -> ThoughtData:
        """
        Validate and convert input data to ThoughtData
        
        Args:
            data: Raw input dictionary
            
        Returns:
            Validated ThoughtData object
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Required fields
        if not data.get('thought') or not isinstance(data['thought'], str):
            raise ValueError('Invalid thought: must be a non-empty string')
        
        if not isinstance(data.get('thoughtNumber'), int) or data['thoughtNumber'] < 1:
            raise ValueError('Invalid thoughtNumber: must be a positive integer')
            
        if not isinstance(data.get('totalThoughts'), int) or data['totalThoughts'] < 1:
            raise ValueError('Invalid totalThoughts: must be a positive integer')
            
        if not isinstance(data.get('nextThoughtNeeded'), bool):
            raise ValueError('Invalid nextThoughtNeeded: must be a boolean')
        
        # Auto-adjust total if needed
        if data['thoughtNumber'] > data['totalThoughts']:
            data['totalThoughts'] = data['thoughtNumber']
        
        return ThoughtData(
            thought=data['thought'],
            thought_number=data['thoughtNumber'],
            total_thoughts=data['totalThoughts'],
            next_thought_needed=data['nextThoughtNeeded'],
            is_revision=data.get('isRevision', False),
            revises_thought=data.get('revisesThought'),
            branch_from_thought=data.get('branchFromThought'),
            branch_id=data.get('branchId'),
            needs_more_thoughts=data.get('needsMoreThoughts', False)
        )
    
    def process_thought(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single thought in the sequence
        
        Args:
            input_data: Thought data dictionary
            
        Returns:
            Processing result with metadata
        """
        try:
            # Validate and create thought
            thought_data = self.validate_thought_input(input_data)
            
            # Add to history
            self.thought_history.append(thought_data)
            
            # Handle branching
            if thought_data.branch_from_thought and thought_data.branch_id:
                if thought_data.branch_id not in self.branches:
                    self.branches[thought_data.branch_id] = []
                self.branches[thought_data.branch_id].append(thought_data)
                self.current_branch = thought_data.branch_id
            
            # Handle hypothesis
            if thought_data.thought_type == ThoughtType.HYPOTHESIS:
                self.hypothesis_stack.append(thought_data)
            elif thought_data.thought_type == ThoughtType.VERIFICATION and self.hypothesis_stack:
                hypothesis = self.hypothesis_stack[-1]
                # Link verification to hypothesis
                thought_data.revises_thought = hypothesis.thought_number
            
            # Extract patterns for learning
            self._extract_patterns(thought_data)
            
            # Store in memory if available
            if self.memory_system:
                self._store_in_memory(thought_data)
            
            return {
                'success': True,
                'thoughtNumber': thought_data.thought_number,
                'totalThoughts': thought_data.total_thoughts,
                'nextThoughtNeeded': thought_data.next_thought_needed,
                'thoughtType': thought_data.thought_type.value,
                'branches': list(self.branches.keys()),
                'currentBranch': self.current_branch,
                'thoughtHistoryLength': len(self.thought_history),
                'hypothesisCount': len(self.hypothesis_stack)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'thoughtHistoryLength': len(self.thought_history)
            }
    
    def _extract_patterns(self, thought: ThoughtData):
        """Extract thinking patterns for future learning"""
        # Pattern detection logic
        if thought.thought_type == ThoughtType.REVISION:
            pattern_key = f"revision_after_{thought.revises_thought}"
            self.thought_patterns[pattern_key] = {
                'type': 'revision',
                'original': thought.revises_thought,
                'revised': thought.thought_number,
                'reason': thought.thought[:100]
            }
        
        # Track thought flow patterns
        if len(self.thought_history) > 1:
            prev_thought = self.thought_history[-2]
            transition = f"{prev_thought.thought_type.value}_to_{thought.thought_type.value}"
            if transition not in self.thought_patterns:
                self.thought_patterns[transition] = 0
            self.thought_patterns[transition] += 1
    
    def _store_in_memory(self, thought: ThoughtData):
        """Store thought in memory system for future reference"""
        if not self.memory_system:
            return
            
        # Import memory types locally to avoid circular dependency
        try:
            from .memory_system import MemoryType, MemoryScope
            
            # Store the thought in project-specific memory
            self.memory_system.store(
                content=thought.thought,
                memory_type=MemoryType.THOUGHT,
                scope=MemoryScope.PROJECT,
                metadata={
                    'thought_number': thought.thought_number,
                    'total_thoughts': thought.total_thoughts,
                    'thought_type': thought.thought_type.value,
                    'timestamp': thought.timestamp,
                    'branch_id': thought.branch_id,
                    'confidence_score': thought.confidence_score,
                    'is_revision': thought.is_revision,
                    'revises_thought': thought.revises_thought
                }
            )
        except ImportError:
            # If memory system is not available, log but don't fail
            import logging
            logging.warning("Memory system not available for thought storage")
    
    def get_thought_summary(self) -> Dict[str, Any]:
        """Get a summary of the thinking process"""
        if not self.thought_history:
            return {'status': 'no_thoughts'}
        
        return {
            'total_thoughts': len(self.thought_history),
            'branches_created': len(self.branches),
            'revisions_made': sum(1 for t in self.thought_history if t.is_revision),
            'hypotheses_generated': len(self.hypothesis_stack),
            'thought_types': {
                t_type.value: sum(1 for t in self.thought_history if t.thought_type == t_type)
                for t_type in ThoughtType
            },
            'patterns_detected': len(self.thought_patterns),
            'completion_status': not self.thought_history[-1].next_thought_needed if self.thought_history else False
        }
    
    def get_branch_analysis(self, branch_id: str = None) -> Dict[str, Any]:
        """Analyze a specific branch or all branches"""
        if branch_id and branch_id in self.branches:
            branch_thoughts = self.branches[branch_id]
            return {
                'branch_id': branch_id,
                'thought_count': len(branch_thoughts),
                'origin_thought': branch_thoughts[0].branch_from_thought if branch_thoughts else None,
                'thoughts': [asdict(t) for t in branch_thoughts]
            }
        
        # Analyze all branches
        return {
            'total_branches': len(self.branches),
            'branches': {
                bid: {
                    'thought_count': len(thoughts),
                    'origin': thoughts[0].branch_from_thought if thoughts else None
                }
                for bid, thoughts in self.branches.items()
            }
        }
    
    def reset(self):
        """Reset the thinking process"""
        self.thought_history.clear()
        self.branches.clear()
        self.current_branch = None
        self.hypothesis_stack.clear()
        self.thought_patterns.clear()
    
    def export_session(self) -> Dict[str, Any]:
        """Export the entire thinking session for analysis or replay"""
        def serialize_thought(thought):
            """Convert ThoughtData to serializable dict"""
            data = asdict(thought)
            # Convert enum to string
            if 'thought_type' in data and hasattr(data['thought_type'], 'value'):
                data['thought_type'] = data['thought_type'].value
            return data
        
        return {
            'timestamp': datetime.now().isoformat(),
            'thoughts': [serialize_thought(t) for t in self.thought_history],
            'branches': {
                bid: [serialize_thought(t) for t in thoughts]
                for bid, thoughts in self.branches.items()
            },
            'patterns': self.thought_patterns,
            'summary': self.get_thought_summary()
        }
    
    def import_session(self, session_data: Dict[str, Any]):
        """Import a previous thinking session"""
        self.reset()
        
        # Reconstruct thoughts
        for thought_dict in session_data.get('thoughts', []):
            thought = ThoughtData(**{k: v for k, v in thought_dict.items() if k != 'thought_type'})
            self.thought_history.append(thought)
        
        # Reconstruct branches
        for bid, branch_thoughts in session_data.get('branches', {}).items():
            self.branches[bid] = [
                ThoughtData(**{k: v for k, v in t.items() if k != 'thought_type'})
                for t in branch_thoughts
            ]
        
        self.thought_patterns = session_data.get('patterns', {})