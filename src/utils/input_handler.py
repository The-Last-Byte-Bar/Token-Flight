import sys
import select
import tty
import termios

class InputHandler:
    """Cross-platform keyboard input handler."""
    
    @staticmethod
    def init_terminal():
        """Initialize terminal for input handling."""
        if sys.platform != "win32":
            fd = sys.stdin.fileno()
            return termios.tcgetattr(fd)
        return None

    @staticmethod
    def restore_terminal(old_settings):
        """Restore terminal settings."""
        if sys.platform != "win32" and old_settings:
            fd = sys.stdin.fileno()
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    @staticmethod
    def getch():
        """Read a single character from input."""
        if sys.platform == "win32":
            import msvcrt
            return msvcrt.getch().decode().lower()
        else:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return ch.lower()

    @staticmethod
    def kbhit():
        """Check if a keyboard key has been pressed."""
        if sys.platform == "win32":
            import msvcrt
            return msvcrt.kbhit()
        else:
            dr, dw, de = select.select([sys.stdin], [], [], 0)
            return dr != []