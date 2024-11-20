from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.live import Live
from typing import List, Tuple
import time
import sys
import select
import tty
import termios

class AirdropUI:
    # Simplified ASCII art that works better with Rich
    ASCII_MOON = """
           🌕
      *   .-""-,  *
    *    /      \\    *
        |        |
         \\      /
     *    `-..-'   *
    """
    
    ASCII_ROCKET = """
           🚀
          /|\\
         /_|_\\
        |     |
        |_____|
          | |
         /___\\
    """

    def __init__(self):
        self.console = Console()
        self.live_display = None

    def display_welcome(self):
        """Display welcome message with moon theme."""
        title = Text()
        title.append("🌟 SIGMANAUTS ", style="bold yellow")
        title.append("TOKEN ", style="bold blue")
        title.append("AIRDROP ", style="bold magenta")
        title.append("SYSTEM ", style="bold cyan")
        title.append("🌟", style="bold yellow")
        
        # Combine art with proper spacing
        art = Text()
        art.append(self.ASCII_MOON, style="bright_blue")
        art.append("\n")
        art.append(self.ASCII_ROCKET, style="bright_white")
        
        # Center the artwork
        centered_art = Align.center(art)
        
        panel = Panel(
            centered_art,
            title=title,
            border_style="bright_blue",
            padding=(1, 2),
        )
        
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")

    def _getch_unix(self):
        """Read a single keypress on Unix systems."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    def _kbhit_unix(self):
        """Check if a keypress is available on Unix systems."""
        dr, dw, de = select.select([sys.stdin], [], [], 0)
        return dr != []

    def display_confirmation_prompt(self, seconds: int = 30) -> bool:
        """Display countdown timer with confirmation prompt - cross-platform version."""
        def get_countdown_text(remaining: int) -> str:
            bar_length = 20
            filled = int((seconds - remaining) / seconds * bar_length)
            progress_bar = "█" * filled + "░" * (bar_length - filled)
            return f"""[bold yellow]⏳ Confirm Airdrop Launch Sequence[/]
[bright_white]Time remaining: {remaining}s[/]
[blue]{progress_bar}[/]
[bold green]Press 'Y' to initiate launch[/]
[bold red]Press 'N' to abort mission[/]"""

        try:
            # Set up Unix terminal
            if sys.platform != "win32":
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                tty.setraw(fd)

            with Live(get_countdown_text(seconds), console=self.console, refresh_per_second=4) as live:
                start_time = time.time()
                while time.time() - start_time < seconds:
                    remaining = int(seconds - (time.time() - start_time))
                    live.update(get_countdown_text(remaining))

                    if sys.platform == "win32":
                        import msvcrt
                        if msvcrt.kbhit():
                            key = msvcrt.getch().decode().lower()
                            if key == 'y':
                                self.console.print("[bold green]✅ Launch sequence confirmed - Initiating airdrop![/]")
                                return True
                            elif key == 'n':
                                self.console.print("[bold red]❌ Launch sequence aborted by user[/]")
                                return False
                    else:
                        if self._kbhit_unix():
                            key = self._getch_unix().lower()
                            if key == 'y':
                                self.console.print("[bold green]✅ Launch sequence confirmed - Initiating airdrop![/]")
                                return True
                            elif key == 'n':
                                self.console.print("[bold red]❌ Launch sequence aborted by user[/]")
                                return False

                    time.sleep(0.1)

            self.console.print("[bold red]❌ Launch sequence timed out - Mission aborted[/]")
            return False

        except Exception as e:
            self.console.print(f"[bold red]Error in confirmation prompt: {str(e)}[/]")
            return False
        finally:
            # Restore Unix terminal settings
            if sys.platform != "win32":
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def display_assumptions(self):
        """Display important assumptions and warnings."""
        assumptions = [
            ("🔐 Wallet", "Make sure your wallet has sufficient ERG and tokens"),
            ("📊 Amounts", "Token amounts will be adjusted for decimals automatically"),
            ("⚡ Network", "Ensure stable connection to your configured node"),
            ("💰 Minimum", "Each output box requires 0.001 ERG minimum"),
            ("📈 Scaling", "Large airdrops may need to be split into batches"),
            ("⏰ Timing", "Transaction processing may take a few minutes"),
            ("📡 Node", "Verify your node is fully synced before proceeding"),
            ("💾 Backup", "Always keep your wallet backup secure")
        ]
        
        table = Table(
            show_header=True,
            header_style="bold yellow",
            border_style="bright_blue",
            title="[bold red]Pre-flight Checklist[/]"
        )
        table.add_column("⚠️ Check", style="cyan")
        table.add_column("📝 Description", style="bright_white")
        
        for check, desc in assumptions:
            table.add_row(check, desc)
        
        panel = Panel(
            table,
            title="[bold red]Important Checks[/]",
            border_style="red"
        )
        
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")

    def display_summary(self, token_name: str, recipients_count: int, 
                       total_amount: float, total_erg: float, 
                       total_hashrate: float, decimals: int):
        """Display airdrop summary with enhanced styling."""
        table = Table(
            title="🚀 Airdrop Mission Control 🚀",
            show_header=True,
            header_style="bold bright_magenta",
            border_style="bright_blue",
            title_style="bold yellow",
            box=None
        )
        
        table.add_column("📊 Metric", style="cyan", justify="right")
        table.add_column("📈 Value", justify="left", style="green")
        
        table.add_row("🪙 Token", f"[bold bright_yellow]{token_name}[/]")
        table.add_row("👥 Recipients", f"[bold bright_green]{recipients_count:,}[/] miners")
        table.add_row(
            f"💎 Total {token_name}", 
            f"[bold bright_yellow]{total_amount:,.{decimals}f}[/] tokens"
        )
        table.add_row("💰 Total ERG", f"[bold bright_cyan]{total_erg:,.4f}[/] ERG")
        table.add_row(
            "⛏️ Total Hashrate", 
            f"[bold bright_magenta]{total_hashrate:,.0f}[/] H/s"
        )
        
        panel = Panel(
            table,
            border_style="bright_blue",
            title="[bold yellow]Mission Parameters[/]",
            subtitle="[bold cyan]Ready for Launch[/]"
        )
        
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")

    def display_wallet_balance(self, token_name: str, erg_balance: float, 
                             token_balance: float, decimals: int):
        """Display current wallet balances."""
        table = Table(
            show_header=False,
            border_style="bright_blue",
            title="[bold cyan]Current Wallet Balance[/]"
        )
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
        
        self.console.print("\n")
        self.console.print(Panel(table, border_style="bright_blue"))
        self.console.print("\n")

    def display_error(self, error_message: str):
        """Display error message with styling."""
        panel = Panel(
            f"[bold red]Error: {error_message}[/]",
            title="[bold red]Mission Failed[/]",
            border_style="red"
        )
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")

    def display_success(self, tx_id: str, explorer_url: str):
        """Display success message with transaction details."""
        panel = Panel(
            f"""[bold green]Transaction successfully submitted![/]
[bright_white]Transaction ID: [cyan]{tx_id}[/]
[bright_white]Explorer URL: [blue]{explorer_url}[/]""",
            title="[bold green]🚀 Mission Accomplished![/]",
            border_style="green"
        )
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")