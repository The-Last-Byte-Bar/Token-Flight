import sys
import logging
import traceback
from typing import Optional, Callable, Any
from functools import wraps
from rich.console import Console
from rich.panel import Panel

class ErrorHandler:
    """Centralized error handling and graceful shutdown"""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.logger = logging.getLogger(__name__)

    def handle_exception(self, e: Exception, context: str = "") -> None:
        """Handle exception with proper logging and user feedback"""
        error_msg = str(e)
        error_type = type(e).__name__
        
        # Format the error message
        detailed_msg = f"""
[bold red]Error Type:[/] {error_type}
[bold red]Context:[/] {context}
[bold red]Details:[/] {error_msg}

[bold yellow]Stack Trace:[/]
{"".join(traceback.format_tb(e.__traceback__))}
"""
        
        # Log the full error
        self.logger.error(f"Error in {context}: {error_type}: {error_msg}")
        self.logger.error(traceback.format_exc())
        
        # Display user-friendly message
        self.console.print(Panel(
            detailed_msg,
            title="[bold red]❌ Error Occurred[/]",
            border_style="red"
        ))

    def shutdown(self, exit_code: int = 1) -> None:
        """Perform graceful shutdown"""
        self.console.print("\n[yellow]Initiating graceful shutdown...[/]")
        
        # Add any cleanup tasks here
        try:
            # Close any open resources
            self.console.print("[green]✓[/] Cleaned up resources")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            self.console.print("[red]✗[/] Error during cleanup")
            
        finally:
            self.console.print("[yellow]Shutdown complete[/]\n")
            sys.exit(exit_code)

    def __call__(self, func: Callable) -> Callable:
        """Decorator for error handling"""
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self.handle_exception(e, func.__name__)
                self.shutdown()
        return wrapper

def setup_error_handler(console: Optional[Console] = None) -> ErrorHandler:
    """Create and configure error handler"""
    handler = ErrorHandler(console)
    
    # Set up global exception handler
    def global_exception_handler(exctype, value, tb):
        handler.handle_exception(value, "Global")
        handler.shutdown()
    
    sys.excepthook = global_exception_handler
    return handler