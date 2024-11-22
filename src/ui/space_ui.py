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
    def __init__(self):
        self.console = Console()
        
    def display_help(self):
        """Display tool usage information."""
        help_text = """[bold yellow]╭─ Ergonauts AIRDROP MISSION GUIDE ─╮[/]

[bold cyan]COMMAND FORMAT:[/]
python airdrop.py <token_name> <amount> [options]

[bold cyan]REQUIRED PARAMETERS:[/]
• token_name     : Token to distribute (e.g., ProxyToken)
• amount         : Amount per recipient

[bold cyan]OPTIONS:[/]
• --min-hashrate : Minimum hashrate filter
• --debug        : Simulation mode, no real transaction
• --recipient-list: Path to CSV file with recipients
• --addresses    : Space-separated list of addresses

[bold cyan]EXAMPLES:[/]
• Test run:
  python airdrop.py ProxyToken 1.0 --debug
• Live distribution:
  python airdrop.py ProxyToken 1.0
• From CSV:
  python airdrop.py ProxyToken 1.0 --recipient-list recipients.csv
• Specific addresses:
  python airdrop.py ProxyToken 1.0 --addresses addr1 addr2 addr3

[bold cyan]TIPS FOR SUCCESSFUL MISSION:[/]
• Always run in debug mode first
• Verify wallet balances before launch
• Monitor node synchronization status
• Keep sufficient ERG for transaction fees
• Check recipient list carefully

[bold yellow]╰────────────────────────────────────╯[/]
"""
        self.console.print(help_text)

    def log_info(self, message: str):
        """Display formatted info log."""
        self.console.print(f"[bright_blue]ℹ [white]{message}[/]")

    def log_success(self, message: str):
        """Display formatted success log."""
        self.console.print(f"[bright_green]✓ [white]{message}[/]")

    def log_warning(self, message: str):
        """Display formatted warning log."""
        self.console.print(f"[bright_yellow]⚠ [white]{message}[/]")

    def log_error(self, message: str):
        """Display formatted error log."""
        self.console.print(f"[bright_red]✖ [white]{message}[/]")

    def display_wallet_balance(self, token_name: str, erg_balance: float, 
                             token_balance: float, decimals: int):
        """Display space-themed wallet balance."""
        table = Table(show_header=False, border_style="bright_blue")
        table.add_column("Asset", style="cyan")
        table.add_column("Balance", style="green")
        table.add_row("💰 ERG", f"[bold bright_green]{erg_balance:.4f} ERG[/]")
        table.add_row(f"🪙 {token_name}", 
                     f"[bold bright_yellow]{token_balance:,.{decimals}f} {token_name}[/]")
        
        panel = Panel(table, 
                     title="[bold cyan]Current Wallet Balance[/]", 
                     border_style="bright_blue")
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")

    def display_welcome(self):
        """Display welcome message with space theme."""
        title = Text()
        title.append("🌟 ERGONAUTS ", style="bold yellow")
        title.append("TOKEN ", style="bold blue")
        title.append("AIRDROP ", style="bold magenta")
        title.append("MISSION ", style="bold cyan")
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

    def display_summary(self, token_name: str, recipients_count: int, total_amount: float, 
                       total_erg: float, total_hashrate: float, decimals: int):
        """Display space-themed summary."""
        table = Table(
            title="🚀 Airdrop Mission Control 🚀",
            show_header=True,
            header_style="bold bright_magenta",
            border_style="bright_blue"
        )
        
        table.add_column("📊 Metric", style="cyan", justify="right")
        table.add_column("📈 Value", style="green", justify="left")
        
        metrics = [
            ("🪙 Token", token_name),
            ("👥 Recipients", f"{recipients_count:,} miners"),
            (f"💎 Total {token_name}", f"{total_amount:,.{decimals}f}"),
            ("💰 Total ERG", f"{total_erg:,.4f}"),
            ("⛏️ Hashrate", f"{total_hashrate:,.0f} H/s")
        ]
        
        for metric, value in metrics:
            table.add_row(metric, value)
        
        panel = Panel(
            table,
            border_style="bright_blue",
            title="[bold yellow]Mission Parameters[/]",
            subtitle="[bold cyan]Ready for Launch[/]"
        )
        
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")

    def display_confirmation_prompt(self, seconds: int = 30) -> bool:
        """Display space-themed countdown timer with confirmation prompt."""
        def get_countdown_text(remaining: int) -> str:
            bar_length = 20
            filled = int((seconds - remaining) / seconds * bar_length)
            progress_bar = "=" * filled + ">" + " " * (bar_length - filled - 1)
            
            content = Text()
            content.append("\n🚨 LAUNCH SEQUENCE ACTIVE 🚨\n", style="bold yellow")
            content.append(f"\nT-minus: {remaining:02d} seconds\n", style="bright_white")
            content.append(f"\n[{progress_bar}]\n", style="bright_blue")
            content.append("\nMission Control Options:\n", style="bright_white")
            content.append("Y - Confirm Launch 🚀\n", style="bright_green")
            content.append("N - Abort Mission 🔴", style="bright_red")
            
            return Panel(
                Align.center(content),
                title="[bold yellow]Mission Control[/]",
                border_style="bright_blue",
                padding=(1, 2)
            )
    
        if sys.platform != "win32":
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                start_time = time.time()
                while True:
                    elapsed = time.time() - start_time
                    if elapsed >= seconds:
                        self.console.print("\n[bold red]🔴 Launch sequence timed out[/]")
                        return False
    
                    remaining = int(seconds - elapsed)
                    self.console.clear()
                    self.console.print(get_countdown_text(remaining))
    
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        key = sys.stdin.read(1).lower()
                        if key == 'y':
                            self.console.print("\n[bold green]🚀 Launch confirmed - Initiating sequence[/]")
                            return True
                        elif key == 'n':
                            self.console.print("\n[bold red]🔴 Launch aborted by mission control[/]")
                            return False
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        else:
            import msvcrt
            start_time = time.time()
            while True:
                elapsed = time.time() - start_time
                if elapsed >= seconds:
                    self.console.print("\n[bold red]🔴 Launch sequence timed out[/]")
                    return False
    
                remaining = int(seconds - elapsed)
                self.console.clear()
                self.console.print(get_countdown_text(remaining))
    
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode().lower()
                    if key == 'y':
                        self.console.print("\n[bold green]🚀 Launch confirmed - Initiating sequence[/]")
                        return True
                    elif key == 'n':
                        self.console.print("\n[bold red]🔴 Launch aborted by mission control[/]")
                        return False
                time.sleep(0.1)

    def display_transaction_progress(self, duration: int = 10):
        """Display space-themed transaction progress."""
        with Live(console=self.console, refresh_per_second=4) as live:
            start_time = time.time()
            while True:
                elapsed = time.time() - start_time
                if elapsed >= duration:
                    break
                
                progress = elapsed / duration
                bar_length = 30
                filled = int(progress * bar_length)
                progress_bar = "🚀" + "=" * filled + ">" + " " * (bar_length - filled - 1)
                
                frame = f"""
[bold yellow]Transmission in Progress[/]
[bright_white]{progress_bar} {int(progress * 100)}%[/]
[cyan]Sending tokens to recipients...[/]
"""
                live.update(frame)
                time.sleep(0.1)

    def display_error(self, message: str):
        """Display error message with space theme."""
        panel = Panel(
            f"[bold red]🔴 Error: {message}[/]",
            title="[bold red]Mission Failed[/]",
            border_style="red"
        )
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")

    def display_success(self, tx_id: str, explorer_url: str):
        """Display success message with space theme."""
        cleaned_url = explorer_url.replace('"', '')  # Remove any quotes from the URL
        panel = Panel(
            f"""[bold green]🚀 Transaction successfully launched![/]

[bright_white]Transaction ID: [cyan]{tx_id}[/]
[bright_white]Explorer URL: [blue]{cleaned_url}[/]

[bold green]Mission Status: [bright_green]Tokens deployed successfully[/]""",
            title="[bold green]🌟 Mission Accomplished![/]",
            border_style="green"
        )
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")