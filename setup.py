#!/usr/bin/env python3
"""
Setup script for Hermetic AI Platform
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    with open(requirements_file) as f:
        requirements = [line.strip() for line in f 
                       if line.strip() and not line.startswith("#")]

setup(
    name="hermetic-ai-mcp",
    version="1.0.0",
    author="Hermetic AI Team",
    description="Universal AI Platform with Memory, Verification, and Sequential Thinking",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/private/hermetic-ai-mcp",
    packages=find_packages(exclude=["tests", "tests.*", "docs", "docs.*"]),
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.4.0",
        ],
        "docs": [
            "mkdocs>=1.5.0",
            "mkdocs-material>=9.0.0",
        ],
        "lsp": [
            "pylsp-server>=1.8.0",
            "python-lsp-jsonrpc>=1.1.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "hermetic-mcp=hermetic_ai_mcp.server:main",
            "hermetic-api=hermetic_ai_mcp.api_server:main",
        ],
        "mcp_servers": [
            "hermetic-ai=server:HermeticMCPServer",
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: Other/Proprietary License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="mcp ai llm memory verification thinking claude openai",
    project_urls={
        "Documentation": "https://github.com/private/hermetic-ai-mcp/docs",
        "Source": "https://github.com/private/hermetic-ai-mcp",
        "Issues": "https://github.com/private/hermetic-ai-mcp/issues",
    },
)