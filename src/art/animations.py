from rich.live import Live
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
import time
import random

class SpaceAnimation:
    def __init__(self, console):
        self.console = console
        self.height = 10
        self.width = 50
        
        # Animation characters
        self.EARTH_FRAMES = ['🌎', '🌍', '🌏']
        self.ROCKET = '🚀'
        self.STARS = ['✦', '✧', '*', '⋆', '✺']
        self.EMPTY = ' '
    
    def _create_frame(self, earth_pos: int, rocket_pos: int) -> str:
        """Create a single frame of the launch animation."""
        try:
            # Initialize empty frame
            frame = [self.EMPTY * self.width for _ in range(self.height)]
            
            # Add Earth
            if 0 <= earth_pos < self.height:
                earth_line = list(frame[earth_pos])
                earth_x = self.width // 2 - 2
                earth_symbol = random.choice(self.EARTH_FRAMES)
                earth_line[earth_x:earth_x + len(earth_symbol)] = earth_symbol
                frame[earth_pos] = ''.join(earth_line)
            
            # Add Rocket
            if 0 <= rocket_pos < self.height:
                rocket_line = list(frame[rocket_pos])
                rocket_x = self.width // 2 - 2
                rocket_line[rocket_x:rocket_x + len(self.ROCKET)] = self.ROCKET
                frame[rocket_pos] = ''.join(rocket_line)
            
            # Add random stars
            for i in range(len(frame)):
                line = list(frame[i])
                for _ in range(3):  # Add 3 stars per line
                    star_pos = random.randint(0, self.width-1)
                    if line[star_pos] == self.EMPTY:
                        line[star_pos] = random.choice(self.STARS)
                frame[i] = ''.join(line)
            
            return "\n".join(frame)
            
        except Exception as e:
            self.console.print(f"[red]Frame creation error: {str(e)}[/]")
            return "Animation frame error"

    def _create_success_frame(self) -> str:
        """Create a single frame of the success animation."""
        try:
            # Create starfield
            stars = ''.join(random.choice(self.STARS + [self.EMPTY] * 3) 
                          for _ in range(self.width))
            
            # Build frame with centered text
            frame = [
                self.EMPTY * self.width,
                stars,
                self.EMPTY * self.width,
                f"{self.EMPTY * ((self.width-20)//2)}🚀 Mission Complete 🌟",
                self.EMPTY * self.width,
                stars
            ]
            
            return "\n".join(frame)
            
        except Exception as e:
            self.console.print(f"[red]Success frame creation error: {str(e)}[/]")
            return "Animation frame error"

    def launch_animation(self, duration: int = 5):
        """Animate rocket launch sequence."""
        try:
            with Live(console=self.console, refresh_per_second=4) as live:
                steps = self.height * 4  # Total animation steps
                for i in range(steps):
                    # Calculate positions
                    earth_pos = max(0, self.height - (i // 4))  # Earth moves up slowly
                    rocket_pos = self.height - 1 - (i // 2)     # Rocket moves up faster
                    
                    # Create and display frame
                    frame = self._create_frame(earth_pos, rocket_pos)
                    panel = Panel(
                        frame,
                        title="[bold yellow]🚀 Launch Sequence[/]",
                        subtitle=f"[bold blue]Step {i+1}/{steps}[/]",
                        border_style="bright_blue"
                    )
                    live.update(panel)
                    time.sleep(0.1)
                    
        except Exception as e:
            self.console.print(f"[bold red]Launch animation error: {str(e)}[/]")

    def success_animation(self, duration: int = 5):
        """Animate successful transaction sequence."""
        try:
            with Live(console=self.console, refresh_per_second=4) as live:
                frames = duration * 10  # 10 frames per second
                
                for frame_num in range(frames):
                    # Create and display frame
                    frame = self._create_success_frame()
                    progress = f"[bold blue]{frame_num + 1}/{frames}[/]"
                    
                    panel = Panel(
                        frame,
                        title="[bold green]🌟 Mission Success 🌟[/]",
                        subtitle=progress,
                        border_style="bright_blue"
                    )
                    live.update(panel)
                    time.sleep(0.1)
                    
        except Exception as e:
            self.console.print(f"[bold red]Success animation error: {str(e)}[/]")

    def display_error(self, message: str):
        """Display error message with animation."""
        try:
            with Live(console=self.console, refresh_per_second=4) as live:
                for _ in range(20):  # 2 seconds
                    # Create error frame with blinking effect
                    stars = ''.join(random.choice(self.STARS + [self.EMPTY] * 2) 
                                  for _ in range(self.width))
                    
                    frame = [
                        stars,
                        self.EMPTY * self.width,
                        f"{self.EMPTY * ((self.width-len(message))//2)}❌ {message} ❌",
                        self.EMPTY * self.width,
                        stars
                    ]
                    
                    panel = Panel(
                        "\n".join(frame),
                        title="[bold red]Mission Alert[/]",
                        border_style="red"
                    )
                    live.update(panel)
                    time.sleep(0.1)
                    
        except Exception as e:
            self.console.print(f"[bold red]Error animation failed: {str(e)}[/]")
            self.console.print(f"[bold red]Original error: {message}[/]")