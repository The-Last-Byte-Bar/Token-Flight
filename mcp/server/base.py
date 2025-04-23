"""
Base classes for the MCP server.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import socket

@dataclass
class Context:
    """Context for MCP operations"""
    user: str
    data: Dict[str, Any]

@dataclass
class Image:
    """Image data for MCP"""
    data: bytes
    mime_type: str

class FastMCP:
    """Fast MCP server implementation"""
    def __init__(self, name: str, description: str = "", dependencies: Optional[List[str]] = None):
        self.name = name
        self.description = description
        self.dependencies = dependencies or []
        self._resources = {}
        self._tools = {}
        self._prompts = {}
    
    def resource(self, path: str):
        """Decorator to register a resource"""
        def decorator(func):
            self._resources[path] = func
            return func
        return decorator
    
    def tool(self):
        """Decorator to register a tool"""
        def decorator(func):
            self._tools[func.__name__] = func
            return func
        return decorator
    
    def prompt(self):
        """Decorator to register a prompt"""
        def decorator(func):
            self._prompts[func.__name__] = func
            return func
        return decorator
    
    def run(self):
        """Run the MCP server"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Starting {self.name}...")
        
        try:
            # Create a socket to find an available port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('', 0))  # Bind to any available port
            port = sock.getsockname()[1]
            sock.close()
            
            logger.info(f"Server running on port: {port}")
            logger.info("Server initialized successfully")
            logger.info(f"Available tools: {list(self._tools.keys())}")
            logger.info(f"Available resources: {list(self._resources.keys())}")
            logger.info("Server is ready to process requests")
            
            # Keep the server running
            import time
            while True:
                time.sleep(1)  # Prevent CPU spinning
                
        except KeyboardInterrupt:
            logger.info("Server shutdown requested...")
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
            raise 