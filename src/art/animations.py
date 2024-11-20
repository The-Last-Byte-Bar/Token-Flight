import random
import time
from typing import Generator, Dict, Any
from art.ascii_patterns import SpacePatterns, CyberpunkPatterns

class AnimationController:
    def __init__(self):
        self.frame_count = 0
        self.last_update = time.time()
        self.frame_delay = 0.25  # seconds between frames

    def should_update(self) -> bool:
        """Check if enough time has passed to update animation."""
        current_time = time.time()
        if current_time - self.last_update >= self.frame_delay:
            self.last_update = current_time
            self.frame_count += 1
            return True
        return False

class SpaceAnimator(AnimationController):
    def __init__(self):
        super().__init__()
        self.patterns = SpacePatterns()
        self.current_moon = 'full'
        self.current_rocket = 'simple'

    def get_next_frame(self) -> str:
        """Generate next frame of space animation."""
        if not self.should_update():
            return None

        # Cycle through moon phases
        moon_phases = list(self.patterns.MOON_PHASES.keys())
        self.current_moon = moon_phases[self.frame_count % len(moon_phases)]

        # Cycle through rocket types
        rocket_types = list(self.patterns.ROCKETS.keys())
        self.current_rocket = rocket_types[self.frame_count % len(rocket_types)]

        # Combine current moon and rocket
        frame = (
            self.patterns.MOON_PHASES[self.current_moon] +
            "\n" +
            self.patterns.ROCKETS[self.current_rocket]
        )
        return frame

class CyberpunkAnimator(AnimationController):
    def __init__(self):
        super().__init__()
        self.patterns = CyberpunkPatterns()
        self.matrix_chars = "01" * 2 + "アイウエオカキクケコ"  # Mix of binary and katakana
        self.current_grid = 'simple'
        
    def _generate_matrix(self, length: int = 4) -> str:
        """Generate random matrix-style text."""
        return ''.join(random.choice(self.matrix_chars) for _ in range(length))

    def get_next_frame(self) -> str:
        """Generate next frame of cyberpunk animation."""
        if not self.should_update():
            return None

        # Generate random matrix values
        matrix1 = self._generate_matrix()
        matrix2 = self._generate_matrix()

        # Cycle through grid patterns
        grid_types = list(self.patterns.GRID.keys())
        self.current_grid = grid_types[self.frame_count % len(grid_types)]

        # Create frame
        frame = self.patterns.GRID[self.current_grid].format(matrix1, matrix2)
        return frame

    def get_transaction_frame(self, progress: float) -> str:
        """Generate transaction animation frame."""
        if not self.should_update():
            return None

        # Create progress bar
        bar_length = 20
        filled = int(progress * bar_length)
        progress_bar = f"[{'=' * filled}{'>' if filled < bar_length else ''}{'.' * (bar_length - filled - 1)}]"

        # Cycle through animations
        animations = ['>>>>', '═══>', '████>', '---->', '>>>>']
        current_animation = animations[self.frame_count % len(animations)]

        return self.patterns.TRANSACTION['progress'].format(
            animation=current_animation,
            progress_bar=progress_bar
        )