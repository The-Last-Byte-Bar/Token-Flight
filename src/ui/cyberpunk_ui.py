from rich.panel import Panel
from rich.align import Align
from rich.live import Live
from rich.table import Table
from rich.text import Text
import time

from ui.base_ui import BaseUI

class CyberpunkUI(BaseUI):
    def display_welcome(self):
        """Display clean, modern tech-themed welcome."""
        title = Text()
        title.append("\n▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄\n", style="bright_blue")
        title.append("  SIGMANAUTS TOKEN AIRDROP\n", style="bold white")
        title.append("▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀\n", style="bright_blue")
        
        info = Text()
        info.append("\n⚡ Efficient Token Distribution System")
        info.append("\n🔒 Secure Transaction Processing")
        info.append("\n📊 Real-time Network Analysis")
        info.append("\n🌐 Decentralized Operations\n")
        
        panel = Panel(
            Align.center(title + info),
            border_style="bright_blue",
            padding=(1, 2)
        )
        
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")

    def display_summary(self, token_name: str, recipients_count: int, 
                       total_amount: float, total_erg: float, 
                       total_hashrate: float, decimals: int):
        """Display clean, modern summary."""
        table = Table(
            title="Token Distribution Summary",
            show_header=True,
            header_style="bold blue",
            border_style="bright_blue"
        )
        
        table.add_column("Parameter", justify="right", style="cyan")
        table.add_column("Value", justify="left", style="bright_white")
        
        metrics = [
            ("Token", token_name),
            ("Recipients", f"{recipients_count:,} miners"),
            (f"Total {token_name}", f"{total_amount:,.{decimals}f}"),
            ("Total ERG", f"{total_erg:,.4f}"),
            ("Network Hashrate", f"{total_hashrate:,.0f} H/s")
        ]
        
        for metric, value in metrics:
            table.add_row(metric, value)
        
        panel = Panel(
            table,
            border_style="bright_blue",
            title="[bold white]Distribution Parameters[/]",
            subtitle="[bold green]Ready to Process[/]"
        )
        
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")

    def display_wallet_balance(self, token_name: str, erg_balance: float, 
                             token_balance: float, decimals: int):
        """Display clean wallet balance."""
        table = Table(show_header=False, border_style="bright_blue")
        table.add_column("Asset", style="cyan")
        table.add_column("Balance", style="bright_white")
        
        table.add_row("ERG Balance", f"{erg_balance:.4f} ERG")
        table.add_row(f"{token_name} Balance", 
                     f"{token_balance:,.{decimals}f} {token_name}")
        
        panel = Panel(
            table,
            title="[bold white]Wallet Status[/]",
            border_style="bright_blue"
        )
        
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")

    def _get_confirmation_text(self, remaining: int, progress_bar: str) -> str:
        """Generate clean confirmation text."""
        return f"""
[bold white]Transaction Confirmation Required
[bright_blue]Time Remaining: {remaining:02d} seconds
[blue]{progress_bar}[/]

[bold green]Press 'Y' to confirm transaction ✓[/]
[bold red]Press 'N' to cancel transaction ×[/]"""

    def display_transaction_progress(self, duration: int = 10):
        """Display clean transaction progress."""
        with Live(console=self.console, refresh_per_second=4) as live:
            start_time = time.time()
            while True:
                elapsed = time.time() - start_time
                if elapsed >= duration:
                    break
                
                progress = elapsed / duration
                bar_length = 30
                filled = int(progress * bar_length)
                progress_bar = "█" * filled + "▒" * (bar_length - filled)
                
                frame = f"""
[bold white]Transaction Processing
[bright_blue]{progress_bar} {int(progress * 100)}%
[cyan]Distributing tokens to recipients...[/]
"""
                live.update(frame)
                time.sleep(0.1)