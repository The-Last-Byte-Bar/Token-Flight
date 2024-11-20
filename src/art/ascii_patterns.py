class SpacePatterns:
    MOON_PHASES = {
        'full': """
           🌕
      *   .-""-,  *
    *    /      \\    *
        |        |
         \\      /
     *    `-..-'   *
        """,
        'waning': """
           🌖
      *   .-""-,  *
    *    /      \\    *
        |     _  |
         \\   /  /
     *    `-'.-'   *
        """,
        'half': """
           🌗
      *   .-""-,  *
    *    /    _ \\    *
        |    /  |
         \\  /  /
     *    `-..'   *
        """
    }

    ROCKETS = {
        'simple': """
           🚀
          /|\\
         /_|_\\
        |     |
        |_____|
          | |
         /___\\
        """,
        'launch': """
           🚀
          /|\\
         /_|_\\
        |     |
        |_____|
         |^^^|
        /_____\\
        """
    }

class CyberpunkPatterns:
    GRID = {
        'simple': """
    ╔════╗ ╔════╗
    ║ {0} ║ ║ {1} ║
    ╚════╝ ╚════╝
    """,
        'complex': """
    ┌─[{0}]─┐ ┌─[{1}]─┐
    │ NODE │ │ NODE │
    └──╥───┘ └──╥───┘
       ║        ║
    ╔══╩══╗  ╔══╩══╗
    """
    }

    TRANSACTION = {
        'progress': """
    ╔══════ TRANSACTION IN PROGRESS ══════╗
    ║   {animation} Sending Tokens {animation}   ║
    ║     {progress_bar}     ║
    ╚═══════════════════════════════════╝
    """
    }

    HEADERS = [
        "╔═══[ SIGMANAUTS CYBERDROP v1.0 ]═══╗",
        "║   SECURE TOKEN DISTRIBUTION UNIT   ║",
        "╚════════════════════════════════════╝"
    ]