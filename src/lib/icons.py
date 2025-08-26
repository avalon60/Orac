# icons.py
__author__ = "Clive Bostock"
__date__ = "2025-10-07"
__description__ = "Icon library, implemented as a Mnemonics class"

class Icons:
    """
    Mnemonics for emoji and icon usage throughout the project.

    Example:
        from icons import Icons
        print(f"{Icons.folder} Loading configuration files...")
        print(f"{Icons.tick} All tests passed successfully!")
        print(f"{Icons.warn} Disk usage at 95%!")
        print(f"{Icons.error} Failed to connect to database.")
    """

    # General symbols
    bullet = '•'
    right_arrow = '➤'

    # Status / indicators
    tick = '✅'
    star = '⭐'
    rocket = '🚀'
    fire = '🔥'
    idea = '💡'
    clock = '⏰'

    # Info levels
    info = 'ℹ️'
    note = '❕'
    question = '❓'
    warn = '⚠️'
    error = '❌'
    critical = '❗'

    # Project-specific Orac mnemonics
    robot = '🤖'
    settings = '⚙️'
    wave = '👋'
    stop = '🛑'

    # Files / docs
    folder = '📂'
    docs = '📘'

    @classmethod
    def list_all(cls):
        """Return a dictionary of all icons."""
        return {
            k: v for k, v in cls.__dict__.items()
            if not k.startswith("__") and not callable(v)
        }

