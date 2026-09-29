"""Mutable editor session state shared by the main loop and handlers."""
from __future__ import annotations

from lightwrite.constants import TEXT_WIDTH
from lightwrite.layout import LayoutCache, set_layout_version
from lightwrite.model import DocVersion, PlainTextCache
from lightwrite.undo import push_insert, push_undo


class EditorState:
    """All loop-persistent editor fields live here.

    Handlers receive ``ed`` and read/write attributes. The three helpers that
    used to be nested closures are methods so they share the same object.
    """

    __slots__ = (
        "document", "formatting", "alignments", "current_path",
        "typing_attrs", "cursor_line", "cursor_col",
        "selection_start", "selection_end", "selecting",
        "status_message", "status_time",
        "scroll_row", "auto_scroll",
        "mode", "prompt_buffer", "prompt_label",
        "search_term", "replace_term", "help_scroll",
        "pending_overwrite_path", "pending_overwrite_docx",
        "search_active", "search_matches", "search_index",
        "undo_stack",
        "menu_open", "menu_selected", "pending_key",
        "browse_dir", "browse_entries", "browse_index", "browse_scroll",
        "export_state", "export_kind", "export_frames",
        "spell_check_active", "spell_positions", "spell_dirty",
        "spell_last_change", "spell_suggestions", "spell_suggest_cache",
        "spell_unavailable_msg",
        "plain_cache", "doc_version", "layout_cache",
        "doc_dirty", "full_redraw", "pending_quit",
        "last_spell_doc_str",
        "chapter_headings", "chapter_index", "chapter_scroll",
        "SCROLL_LINES",
        "width", "height", "text_width", "text_x", "visible_rows",
        "top", "bottom",
    )

    def __init__(self, document, formatting, alignments, current_path):
        self.document = document
        self.formatting = formatting
        self.alignments = alignments
        self.current_path = current_path

        self.typing_attrs = 0
        self.cursor_line = 0
        self.cursor_col = 0

        self.selection_start = None
        self.selection_end = None
        self.selecting = False

        self.status_message = ""
        self.status_time = 0

        self.scroll_row = 0
        self.auto_scroll = True

        self.mode = "normal"
        self.prompt_buffer = ""
        self.prompt_label = ""
        self.search_term = ""
        self.replace_term = ""
        self.help_scroll = 0
        self.pending_overwrite_path = ""
        self.pending_overwrite_docx = False

        self.search_active = False
        self.search_matches = []
        self.search_index = 0

        self.undo_stack = []

        self.menu_open = -1
        self.menu_selected = 0
        self.pending_key = None

        self.browse_dir = ""
        self.browse_entries = []
        self.browse_index = 0
        self.browse_scroll = 0

        self.export_state = None
        self.export_kind = None
        self.export_frames = 0

        self.spell_check_active = False
        self.spell_positions = []
        self.spell_dirty = False
        self.spell_last_change = 0.0
        self.spell_suggestions = []
        self.spell_suggest_cache = {}
        self.spell_unavailable_msg = ""

        self.plain_cache = PlainTextCache()
        self.plain_cache.get(document)
        self.doc_version = DocVersion()
        self.layout_cache = LayoutCache()
        set_layout_version(self.doc_version.n)
        self.doc_dirty = False
        self.full_redraw = True
        self.pending_quit = False
        self.last_spell_doc_str = self.plain_cache.get(document)

        self.chapter_headings = []
        self.chapter_index = 0
        self.chapter_scroll = 0

        self.SCROLL_LINES = 3

        self.width = 0
        self.height = 0
        self.text_width = TEXT_WIDTH
        self.text_x = 0
        self.visible_rows = 1
        self.top = 0
        self.bottom = 1

    def touch_document(self):
        self.plain_cache.invalidate()
        self.layout_cache.invalidate()
        self.doc_version.bump()
        set_layout_version(self.doc_version.n)

    def record_undo(self, start=None, end=None):
        push_undo(
            self.undo_stack, self.document, self.formatting, self.alignments,
            start, end,
        )
        self.touch_document()
        self.doc_dirty = True

    def record_insert(self, line, col, text):
        push_insert(self.undo_stack, line, col, text)
        self.touch_document()
        self.doc_dirty = True
