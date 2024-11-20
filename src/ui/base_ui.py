from rich.console import Console
from rich.panel import Panel
from rich.align import Align
from rich.live import Live
from rich.table import Table
from rich.text import Text
import time
import sys
import select
import tty
import termios

class BaseUI:
    def __init__(self):
        self.console = Console()

    def _get_key(self) -> str:
        """Get a single keypress from user."""
        if sys.platform == "win32":
            import msvcrt
            if msvcrt.kbhit():
                return msvcrt.getch().decode().lower()
        else:
            # Unix systems
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
                return ch.lower()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ''

    def display_confirmation_prompt(self, seconds: int = 30) -> bool:
        """Display countdown timer with confirmation prompt."""
        def get_countdown_text(remaining: int) -> str:
            bar_length = 20
            filled = int((seconds - remaining) / seconds * bar_length)
            progress_bar = "█" * filled + "░" * (bar_length - filled)
            return self._get_confirmation_text(remaining, progress_bar)

        start_time = time.time()
        
        # Set up terminal for Unix systems
        if sys.platform != "win32":
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            tty.setraw(fd)

        try:
            with Live(get_countdown_text(seconds), console=self.console, refresh_per_second=4) as live:
                while True:
                    elapsed = time.time() - start_time
                    if elapsed >= seconds:
                        self.console.print("\n[bold red]Time expired - Operation cancelled[/]\n")
                        return False

                    remaining = int(seconds - elapsed)
                    live.update(get_countdown_text(remaining))

                    if sys.platform == "win32":
                        import msvcrt
                        if msvcrt.kbhit():
                            key = msvcrt.getch().decode().lower()
                            if key == 'y':
                                self.console.print("\n[bold green]Confirmed - Proceeding with operation[/]\n")
                                return True
                            elif key == 'n':
                                self.console.print("\n[bold red]Cancelled by user[/]\n")
                                return False
                    else:
                        # Unix systems
                        dr, _, _ = select.select([sys.stdin], [], [], 0.1)
                        if dr:
                            key = sys.stdin.read(1).lower()
                            if key == 'y':
                                self.console.print("\n[bold green]Confirmed - Proceeding with operation[/]\n")
                                return True
                            elif key == 'n':
                                self.console.print("\n[bold red]Cancelled by user[/]\n")
                                return False

                    time.sleep(0.1)

        finally:
            # Restore terminal settings for Unix systems
            if sys.platform != "win32":
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def display_welcome(self):
        """Abstract method for welcome screen."""
        raise NotImplementedError

    def display_assumptions(self):
        """Display Know Your Assumptions (KYA) checklist."""
        assumptions = [
            ("🔐 Wallet", "Make sure your wallet has sufficient ERG and tokens"),
            ("📊 Amounts", "Token amounts will be adjusted for decimals automatically"),
            ("⚡ Network", "Ensure stable connection to your configured node"),
            ("💰 Minimum", "Each output box requires 0.001 ERG minimum"),
            ("📈 Scaling", "Large airdrops may need to be split into batches"),
            ("⏰ Timing", "Transaction processing may take a few minutes"),
            ("📡 Node", "Verify your node is fully synced before proceeding"),
            ("💾 Backup", "Always keep your wallet backup secure"),
            ("🔒 Security", "Double-check all transaction parameters"),
            ("📝 Records", "Keep transaction records for your reference")
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
            title="[bold red]KNOW YOUR ASSUMPTIONS (KYA)[/]",
            border_style="red"
        )
        
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")


    def display_wallet_balance(self, token_name: str, erg_balance: float, 
                             token_balance: float, decimals: int):
        """Display current wallet balance."""
        raise NotImplementedError

    def display_error(self, message: str):
        """Display error message."""
        panel = Panel(
            f"[bold red]Error: {message}[/]",
            title="[bold red]Error[/]",
            border_style="red"
        )
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")

    def display_success(self, tx_id: str, explorer_url: str):
        """Display success message."""
        panel = Panel(
            f"""[bold green]Transaction submitted successfully![/]
[bright_white]Transaction ID: [cyan]{tx_id}[/]
[bright_white]Explorer URL: [blue]{explorer_url}[/]""",
            title="[bold green]Success[/]",
            border_style="green"
        )
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")

    def _get_confirmation_text(self, remaining: int, progress_bar: str) -> str:
        """Abstract method for confirmation text format."""
        raise NotImplementedError