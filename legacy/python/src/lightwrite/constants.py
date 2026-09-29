"""Shared constants for Lightwrite."""
import os


VERSION = "1.2.0"


SESSION_RTF = os.path.expanduser("~/.config/lightwrite/session.rtf")


STATUS_DURATION = 1.6


TEXT_WIDTH = 80


MAX_UNDO = 300


BOLD = 1


ITALIC = 2


UNDERLINE = 4


H1 = 8


H2 = 16


H3 = 32


HEADING_MASK = H1 | H2 | H3


ALIGN_LEFT = 0


ALIGN_CENTER = 1


ALIGN_RIGHT = 2


ALIGN_JUSTIFY = 3


PAGE_BREAK = "\x0c"


MENU_SEPARATOR = " │ "


TITLE_ROW = 0


SEP_TITLE_ROW = 1


MENU_ROW = 2


SEP_TOP_ROW = 3


DROPDOWN_ROW = 3


TEXT_TOP = 4


SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


BROWSE_EXTENSIONS = (".rtf", ".txt", ".docx", ".doc")
