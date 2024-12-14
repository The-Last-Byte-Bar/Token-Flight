from rich.panel import Panel
from rich.align import Align
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich.console import Console
import time
import sys
import select
import termios
import tty
from ui.base_ui import BaseUI

class SpaceUI(BaseUI):
    def display_welcome(self):
        """Display welcome message with Last Byte theme."""
        title = Text()
        title.append("🌟 LAST BYTE ", style="bold yellow")
        title.append("TOKEN ", style="bold blue")
        title.append("FLIGHT ", style="bold magenta")
        title.append("SYSTEM ", style="bold cyan")
        title.append("🌟", style="bold yellow")
        
        welcome_text = """
             🌎
         *         *
    *                  *
           🚀
    *                  *
         *         *
        """
        
        panel = Panel(
            Align.center(Text(welcome_text + "\n" + title.plain)),
            border_style="bright_blue",
            padding=(1, 2)
        )
        
        self.console.clear()
        self.console.print(panel)
        time.sleep(2)

    def display_summary(self, token_name: str, recipients_count: int, 
                       total_amount: float, total_erg: float, 
                       total_hashrate: float, decimals: int):
        """Display Last Byte themed summary."""
        table = Table(
            title="🚀 Token Flight Mission Control 🚀",
            show_header=True,
            header_style="bold bright_magenta",
            border_style="bright_blue"
        )
        
        table.add_column("📊 Metric", style="cyan", justify="right")
        table.add_column("📈 Value", style="green", justify="left")
        
        metrics = [
            ("🪙 Token", token_name),
            ("👥 Recipients", f"{recipients_count:,} recipients"),
            (f"💎 Total {token_name}", f"{total_amount:,.{decimals}f}"),
            ("💰 Total ERG", f"{total_erg:,.4f}"),
            ("⛏️ Hashrate", f"{total_hashrate:,.0f} H/s")
        ]
        
        for metric, value in metrics:
            table.add_row(metric, value)
        
        panel = Panel(
            table,
            border_style="bright_blue",
            title="[bold yellow]Last Byte Flight Parameters[/]",
            subtitle="[bold cyan]Ready for Launch[/]"
        )
        
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")

    def display_wallet_balance(self, token_name: str, erg_balance: float, 
                             token_balance: float, decimals: int):
        """Display current wallet balances in Last Byte theme."""
        table = Table(show_header=False, border_style="bright_blue")
        table.add_column("Asset", style="cyan")
        table.add_column("Balance", style="green")
        
        table.add_row(
            "💰 ERG",
            f"[bold bright_green]{erg_balance:.4f} ERG[/]"
        )
        table.add_row(
            f"🪙 {token_name}",
            f"[bold bright_yellow]{token_balance:,.{decimals}f} {token_name}[/]"
        )
        
        panel = Panel(
            table,
            title="[bold yellow]Current Launch Resources[/]",
            border_style="bright_blue"
        )
        
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")

    def _get_confirmation_text(self, remaining: int, progress_bar: str) -> str:
        """Generate Last Byte themed confirmation text."""
        return f"""
[bold yellow]⏳ Launch Sequence Initiated[/]
[bright_white]Time remaining: {remaining}s[/]
[blue]{progress_bar}[/]
[bold green]Press 'Y' to initialize token flight[/]
[bold red]Press 'N' to abort mission[/]"""