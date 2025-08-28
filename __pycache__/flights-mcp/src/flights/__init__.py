"""Flight search MCP package initialization."""

from . import server
import asyncio

def main():
    """Main entry point for the package."""
    server.main()  # Direct call since server.main() is not async

__all__ = ['main', 'server']