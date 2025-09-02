"""
Verification Engine - Reimplemented for Hermetic AI Platform
Based on Hermetic Consciousness verification with enhancements
"""
import ast
import re
import subprocess
import tempfile
import hashlib
import multiprocessing
import resource
import contextlib
import io
from typing import Dict, Any, Tuple, List, Optional
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CodeVerifier:
    """
    The ultimate code quality guardian
    Detects and prevents mock code, placeholders, and security issues
    """
    
    # Forbidden patterns that indicate mock/incomplete code
    FORBIDDEN_PATTERNS = {
        # Direct mock indicators
        'TODO': r'\bTODO\b',
        'FIXME': r'\bFIXME\b',
        'XXX': r'\bXXX\b',
        'HACK': r'\bHACK\b',
        'stub': r'\bstub\b',
        'mock': r'\bmock',
        'fake': r'\bfake',
        'dummy': r'\bdummy\b',
        'placeholder': r'placeholder',
        'not_implemented': r'not[_\s]implemented',
        'pass_only': r'^\s*pass\s*$',
        'ellipsis': r'^\s*\.\.\.\s*$',
        'raise_not_implemented': r'raise\s+NotImplementedError',
        
        # Incomplete patterns
        'empty_except': r'except\s*:\s*pass',
        'bare_except': r'except\s*:',
        'todo_comment': r'#.*\b(todo|fixme|xxx|hack)\b',
        
        # Hardcoded test values
        'hardcoded_test': r'(test|Test|TEST).*=.*["\'].*test.*["\']',
        'example_com': r'example\.(com|org|net)',
        'localhost_hardcoded': r'["\']localhost["\']',
        '127_0_0_1': r'["\']127\.0\.0\.1["\']',
        
        # Security patterns
        'eval_usage': r'\beval\s*\(',
        'exec_usage': r'\bexec\s*\(',
        'hardcoded_password': r'(password|passwd|pwd)\s*=\s*["\'][^"\']+["\']',
        'hardcoded_api_key': r'(api[_\s]?key|apikey)\s*=\s*["\'][^"\']+["\']',
        'hardcoded_secret': r'(secret|token)\s*=\s*["\'][^"\']+["\']',
    }
    
    # Allowed exceptions for certain patterns
    ALLOWED_CONTEXTS = {
        'mock': ['test_', '_test.py', 'tests/', 'testing/'],
        'fake': ['test_', '_test.py', 'tests/', 'testing/'],
        'dummy': ['test_', '_test.py', 'tests/', 'testing/'],
        'example_com': ['documentation', 'README', 'docs/'],
        'localhost_hardcoded': ['config', 'development', 'test'],
        '127_0_0_1': ['config', 'development', 'test']
    }
    
    def __init__(self, memory_system=None, strict_mode: bool = True):
        """
        Initialize the code verifier
        
        Args:
            memory_system: Optional memory system for storing results
            strict_mode: Whether to use strict verification rules
        """
        self.memory_system = memory_system
        self.strict_mode = strict_mode
        self.verification_cache = {}
        
    def verify_code(self, 
                   code: str, 
                   file_path: Optional[str] = None,
                   language: str = "python") -> Dict[str, Any]:
        """
        Complete verification pipeline
        
        Args:
            code: Code to verify
            file_path: Optional file path for context
            language: Programming language
            
        Returns:
            Verification results dictionary
        """
        # Generate code hash for caching
        code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
        
        # Check cache
        if code_hash in self.verification_cache:
            logger.info(f"Using cached verification for {code_hash}")
            return self.verification_cache[code_hash]
        
        result = {
            'passed': True,
            'has_mocks': False,
            'violations': [],
            'security_issues': [],
            'pattern_violations': [],
            'ast_issues': [],
            'execution_result': None,
            'confidence': 1.0,
            'timestamp': datetime.now().isoformat(),
            'code_hash': code_hash
        }
        
        # Step 1: Pattern check
        pattern_result = self._check_patterns(code, file_path)
        if not pattern_result['clean']:
            result['passed'] = False
            result['has_mocks'] = True
            result['pattern_violations'] = pattern_result['violations']
            result['violations'].extend([v['message'] for v in pattern_result['violations']])
            result['confidence'] *= 0.5
        
        # Step 2: AST analysis (for Python)
        if language == "python":
            ast_result = self._analyze_ast(code)
            if not ast_result['valid']:
                result['passed'] = False
                result['ast_issues'] = ast_result['issues']
                result['violations'].extend(ast_result['issues'])
                result['confidence'] *= 0.7
        
        # Step 3: Security check
        security_result = self._check_security(code)
        if security_result['has_issues']:
            result['security_issues'] = security_result['issues']
            result['violations'].extend([f"Security: {issue}" for issue in security_result['issues']])
            if self.strict_mode:
                result['passed'] = False
                result['confidence'] *= 0.3
        
        # Step 4: Sandbox execution (if Python)
        if language == "python" and self.strict_mode:
            exec_result = self._sandbox_execute(code)
            result['execution_result'] = exec_result
            if not exec_result['success']:
                result['passed'] = False
                result['violations'].append(f"Execution failed: {exec_result.get('error', 'Unknown error')}")
                result['confidence'] *= 0.4
        
        # Store in cache
        self.verification_cache[code_hash] = result
        
        # Store in memory if available
        if self.memory_system:
            from .memory_system import MemoryType, MemoryScope
            self.memory_system.store(
                content=f"Verification result for {code_hash}: {'PASSED' if result['passed'] else 'FAILED'} - {len(result.get('violations', []))} violations",
                memory_type=MemoryType.VERIFICATION,
                scope=MemoryScope.PROJECT,
                metadata={
                    'code_hash': code_hash,
                    'file_path': file_path,
                    'language': language,
                    'passed': result['passed'],
                    'violations': result.get('violations', []),
                    'confidence': result.get('confidence', 0)
                }
            )
        
        return result
    
    def _check_patterns(self, code: str, file_path: Optional[str] = None) -> Dict[str, Any]:
        """Check for forbidden patterns in code"""
        violations = []
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Skip empty lines
            if not line.strip():
                continue
            
            # Strip strings and comments for accurate pattern matching
            cleaned_line = self._strip_strings_and_comments(line)
            
            for pattern_name, pattern_regex in self.FORBIDDEN_PATTERNS.items():
                # Check if pattern is in allowed context
                if file_path and self._is_allowed_context(pattern_name, file_path):
                    continue
                
                # Check if pattern is only in strings/comments (acceptable)
                if self._is_only_in_strings_or_comments(line, pattern_regex):
                    continue
                
                # Check for pattern match
                if re.search(pattern_regex, cleaned_line, re.IGNORECASE):
                    violations.append({
                        'line': line_num,
                        'pattern': pattern_name,
                        'content': line.strip(),
                        'message': f"Forbidden pattern '{pattern_name}' found at line {line_num}"
                    })
        
        return {
            'clean': len(violations) == 0,
            'violations': violations
        }
    
    def _strip_strings_and_comments(self, line: str) -> str:
        """Remove string literals and comments from a line"""
        # Remove single-line comments
        if '#' in line:
            line = line[:line.index('#')]
        
        # Remove string literals (simplified)
        # This is a basic implementation - could be enhanced
        line = re.sub(r'"[^"]*"', '""', line)
        line = re.sub(r"'[^']*'", "''", line)
        line = re.sub(r'""".*?"""', '""""""', line, flags=re.DOTALL)
        line = re.sub(r"'''.*?'''", "''''''", line, flags=re.DOTALL)
        
        return line
    
    def _is_only_in_strings_or_comments(self, line: str, pattern: str) -> bool:
        """Check if pattern only appears in strings or comments"""
        # Check if pattern is in the line at all
        if not re.search(pattern, line, re.IGNORECASE):
            return False
        
        # Check if it's in cleaned line (not in strings/comments)
        cleaned = self._strip_strings_and_comments(line)
        return not re.search(pattern, cleaned, re.IGNORECASE)
    
    def _is_allowed_context(self, pattern_name: str, file_path: str) -> bool:
        """Check if pattern is allowed in this context"""
        if pattern_name not in self.ALLOWED_CONTEXTS:
            return False
        
        allowed_contexts = self.ALLOWED_CONTEXTS[pattern_name]
        for context in allowed_contexts:
            if context in file_path:
                return True
        
        return False
    
    def _analyze_ast(self, code: str) -> Dict[str, Any]:
        """Analyze Python code AST for structural issues"""
        issues = []
        
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {
                'valid': False,
                'issues': [f"Syntax error: {e}"]
            }
        
        # Check for various AST patterns
        for node in ast.walk(tree):
            # Check for empty functions (only pass)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    issues.append(f"Empty function '{node.name}' with only 'pass'")
            
            # Check for empty classes
            if isinstance(node, ast.ClassDef):
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    issues.append(f"Empty class '{node.name}' with only 'pass'")
            
            # Check for NotImplementedError
            if isinstance(node, ast.Raise):
                if node.exc and isinstance(node.exc, ast.Call):
                    if hasattr(node.exc.func, 'id') and node.exc.func.id == 'NotImplementedError':
                        issues.append("NotImplementedError found - incomplete implementation")
            
            # Check for bare except clauses
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    issues.append("Bare except clause found - too broad exception handling")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues
        }
    
    def _check_security(self, code: str) -> Dict[str, Any]:
        """Check for security vulnerabilities"""
        issues = []
        
        # Check for dangerous functions
        dangerous_patterns = {
            'eval': r'\beval\s*\(',
            'exec': r'\bexec\s*\(',
            'compile': r'\bcompile\s*\(',
            '__import__': r'__import__\s*\(',
            'os.system': r'os\.system\s*\(',
            'subprocess.shell': r'shell\s*=\s*True',
            'pickle.loads': r'pickle\.loads\s*\(',
        }
        
        for name, pattern in dangerous_patterns.items():
            if re.search(pattern, code):
                issues.append(f"Potentially dangerous function: {name}")
        
        # Check for hardcoded credentials
        credential_patterns = {
            'password': r'(password|passwd|pwd)\s*=\s*["\'][^"\']+["\']',
            'api_key': r'(api[_\s]?key|apikey)\s*=\s*["\'][^"\']+["\']',
            'secret': r'(secret|token)\s*=\s*["\'][^"\']+["\']',
            'private_key': r'(private[_\s]?key)\s*=\s*["\'][^"\']+["\']',
        }
        
        for name, pattern in credential_patterns.items():
            # Skip if it's a variable assignment to another variable
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                value = match.group()
                # Check if it's actually a hardcoded value (not empty or placeholder)
                if not any(placeholder in value.lower() for placeholder in ['your_', 'example', 'placeholder', '<', '>']):
                    stripped_value = value.split('=')[1].strip()
                    # Remove quotes safely
                    if stripped_value.startswith('"') and stripped_value.endswith('"'):
                        stripped_value = stripped_value[1:-1]
                    elif stripped_value.startswith("'") and stripped_value.endswith("'"):
                        stripped_value = stripped_value[1:-1]
                    
                    if len(stripped_value) > 3:  # Not empty or very short
                        issues.append(f"Hardcoded {name} detected")
        
        return {
            'has_issues': len(issues) > 0,
            'issues': issues
        }
    
    def _sandbox_execute(self, code: str, timeout: int = 5) -> Dict[str, Any]:
        """Execute code in sandboxed environment"""
        result = {
            'success': False,
            'output': '',
            'error': '',
            'timeout': False
        }
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # Run in subprocess with timeout
            process = subprocess.Popen(
                ['python3', temp_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                result['success'] = process.returncode == 0
                result['output'] = stdout
                result['error'] = stderr
            except subprocess.TimeoutExpired:
                process.kill()
                result['timeout'] = True
                result['error'] = f"Execution timed out after {timeout} seconds"
        
        except Exception as e:
            result['error'] = str(e)
        
        finally:
            # Clean up temp file
            Path(temp_file).unlink(missing_ok=True)
        
        return result
    
    def verify_with_skepticism(self, code: str, runs: int = 3) -> Dict[str, Any]:
        """
        Run multiple verification passes with skepticism
        Each run may reveal different issues
        """
        all_results = []
        final_result = {
            'execution_proved': True,
            'runs_performed': runs,
            'all_passed': True,
            'unique_violations': set(),
            'confidence_scores': []
        }
        
        for run_num in range(runs):
            logger.info(f"Skepticism run {run_num + 1}/{runs}")
            
            # Clear cache to force re-verification
            self.verification_cache.clear()
            
            result = self.verify_code(code)
            all_results.append(result)
            
            if not result['passed']:
                final_result['all_passed'] = False
                final_result['execution_proved'] = False
            
            # Collect unique violations
            for violation in result.get('violations', []):
                final_result['unique_violations'].add(violation)
            
            final_result['confidence_scores'].append(result.get('confidence', 0))
        
        # Calculate average confidence
        avg_confidence = sum(final_result['confidence_scores']) / len(final_result['confidence_scores'])
        
        final_result['summary'] = {
            'all_passed': final_result['all_passed'],
            'average_confidence': avg_confidence,
            'total_unique_violations': len(final_result['unique_violations']),
            'violations': list(final_result['unique_violations'])
        }
        
        return final_result
    
    def generate_forensic_report(self, code: str) -> Dict[str, Any]:
        """Generate detailed forensic analysis of code"""
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        lines = code.split('\n')
        
        # Perform verification
        verification = self.verify_code(code)
        
        # Analyze code metrics
        metrics = {
            'line_count': len(lines),
            'char_count': len(code),
            'non_empty_lines': sum(1 for line in lines if line.strip()),
            'comment_lines': sum(1 for line in lines if line.strip().startswith('#')),
            'import_count': sum(1 for line in lines if line.strip().startswith(('import ', 'from ')))
        }
        
        # AST analysis for Python
        ast_info = {}
        try:
            tree = ast.parse(code)
            ast_info = {
                'ast_node_count': sum(1 for _ in ast.walk(tree)),
                'functions': [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)],
                'classes': [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)],
                'imports': [node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)]
            }
        except:
            ast_info = {'error': 'Failed to parse AST'}
        
        return {
            'code_hash': code_hash,
            'timestamp': datetime.now().isoformat(),
            'verification': verification,
            'forensic': {
                'code_hash': code_hash,
                'metrics': metrics,
                'ast_analysis': ast_info,
                'line_count': metrics['line_count'],
                'ast_node_count': ast_info.get('ast_node_count', 0)
            }
        }