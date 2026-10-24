"""
main_window.py — WontNote three-column main interface.
Layout: [Sidebar 224px] | [Notes List 310px] | [Editor ∞]
Mirrors the 'Kişisel Notlar' HTML design.
"""
import json
import tkinter as tk
from datetime import datetime, timezone

from ..theme import (
    SURFACE_LOWEST, SURFACE_LOW, SURFACE, SURFACE_CONT, SURFACE_HIGH, SURFACE_HIGHEST,
    ON_SURFACE, ON_SURFACE_VAR, OUTLINE, OUTLINE_VAR,
    PRIMARY, PRIMARY_FIXED, PRIMARY_FIXED_DIM, ON_PRIMARY,
    SECONDARY, TERTIARY,
    ERROR, ERROR_CONT, ON_ERROR_CONT,
    GREEN_SAVED, GREEN_DARK,
    f_headline_lg, f_headline_md, f_headline_sm,
    f_body_lg, f_body_md, f_body_sm,
    f_label_md, f_label_sm, f_mono, f_title_win,
)
from ..widgets import (
    ScrollFrame, SidebarItem, NoteCard,
    PrimaryBtn, SecondaryBtn, DangerBtn, HSep,
)

_FOLDERS = ["Kişisel", "Okul & Eğitim", "İş & Projeler", "Fikirler & Taslaklar"]
_FOLDER_ICONS = ["🟣", "🔵", "🟠", "⚪"]


class MainWindow(tk.Frame):
    """Three-column desktop workstation — note list + rich text editor."""

    def __init__(self, parent: tk.Widget, app):
        super().__init__(parent, bg=SURFACE_LOW)
        self.app = app
        self._active_note_id: str | None = None
        self._autosave_id   = None
        self._filter_query  = ""
        self._active_view   = "all"   # all | pinned | locked | trash
        self._note_cards: dict[str, NoteCard] = {}
        self._build()
        self._refresh_note_list()

    # ═════════════════════════════════════════════════════════════════════════
    # LAYOUT BUILD
    # ═════════════════════════════════════════════════════════════════════════
    def _build(self):
        self.pack(fill="both", expand=True)

        # ── Inner header (status + breadcrumb) ────────────────────────────────
        self._build_inner_header()

        # ── Three columns ─────────────────────────────────────────────────────
        columns = tk.Frame(self, bg=SURFACE_LOW)
        columns.pack(fill="both", expand=True)

        # Left sidebar
        self._sidebar = tk.Frame(columns, bg=SURFACE_LOW, width=224)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        self._build_sidebar()

        HSep(columns).pack(side="left", fill="y")

        # Middle notes list
        self._mid = tk.Frame(columns, bg=SURFACE, width=310)
        self._mid.pack(side="left", fill="y")
        self._mid.pack_propagate(False)
        self._build_notes_list()

        HSep(columns).pack(side="left", fill="y")

        # Right editor
        self._editor_host = tk.Frame(columns, bg=SURFACE_LOWEST)
        self._editor_host.pack(side="left", fill="both", expand=True)
        self._build_editor_placeholder()

        # ── Keyboard shortcuts ────────────────────────────────────────────────
        root = self.winfo_toplevel()
        root.bind("<Control-n>", lambda _e: self._new_note())
        root.bind("<Control-N>", lambda _e: self._new_note())
        root.bind("<Control-f>", lambda _e: self._focus_search())
        root.bind("<Control-F>", lambda _e: self._focus_search())
        root.bind("<Control-l>", lambda _e: self.app.lock())
        root.bind("<Control-L>", lambda _e: self.app.lock())
        root.bind("<Control-comma>", lambda _e: self._open_settings())

    # ── Inner header ──────────────────────────────────────────────────────────
    def _build_inner_header(self):
        hdr = tk.Frame(self, bg=SURFACE_LOW, height=32)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Left
        left = tk.Frame(hdr, bg=SURFACE_LOW)
        left.pack(side="left", fill="y", padx=8)
        tk.Label(left, text="📝", bg=SURFACE_LOW,
                 font=("Segoe UI Emoji", 12)).pack(side="left", pady=6)
        tk.Label(left, text=" WontNote", bg=SURFACE_LOW, fg=ON_SURFACE,
                 font=f_title_win()).pack(side="left")
        tk.Label(left, text=" — ", bg=SURFACE_LOW, fg=OUTLINE,
                 font=f_title_win()).pack(side="left")
        self._breadcrumb = tk.Label(left, text="Yerel Depolama",
                                     bg=SURFACE_LOW, fg=ON_SURFACE_VAR,
                                     font=f_title_win())
        self._breadcrumb.pack(side="left")

        # Right
        right = tk.Frame(hdr, bg=SURFACE_LOW)
        right.pack(side="right", fill="y", padx=8)
        self._save_dot = tk.Label(right, text="●", bg=SURFACE_LOW,
                                   fg=GREEN_SAVED, font=("Segoe UI Emoji", 8))
        self._save_dot.pack(side="left", pady=10)
        self._save_lbl = tk.Label(right, text="Tüm değişiklikler kaydedildi",
                                   bg=SURFACE_LOW, fg=GREEN_DARK,
                                   font=f_mono())
        self._save_lbl.pack(side="left", padx=(4, 0))

        HSep(self).pack(fill="x")

        # ── Menu bar strip ────────────────────────────────────────────────────
        menubar = tk.Frame(self, bg=SURFACE_LOW, height=24)
        menubar.pack(fill="x")
        menubar.pack_propagate(False)
        for item in ("Dosya", "Düzenle", "Görünüm", "Yardım"):
            lbl = tk.Label(menubar, text=item, bg=SURFACE_LOW,
                           fg=ON_SURFACE_VAR, font=f_label_sm(), padx=8)
            lbl.pack(side="left", fill="y")
            lbl.bind("<Enter>", lambda e: e.widget.configure(fg=ON_SURFACE))
            lbl.bind("<Leave>", lambda e: e.widget.configure(fg=ON_SURFACE_VAR))

        shortcut = tk.Label(menubar, text="Ctrl+N  Yeni Not",
                             bg=SURFACE_LOW, fg=OUTLINE, font=f_mono())
        shortcut.pack(side="right", padx=8)

        HSep(self).pack(fill="x")

    # ── Sidebar ───────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = self._sidebar
        inner = tk.Frame(sb, bg=SURFACE_LOW)
        inner.pack(fill="both", expand=True, padx=4, pady=6)

        # New note button
        new_btn = tk.Button(
            inner, text="  +  Yeni not    Ctrl+N",
            command=self._new_note,
            bg=PRIMARY, fg=ON_PRIMARY, activebackground=SECONDARY,
            activeforeground=ON_PRIMARY,
            relief="flat", cursor="hand2", font=f_label_md(),
            padx=8, pady=5, anchor="w",
        )
        new_btn.pack(fill="x", pady=(0, 6))

        # Navigation items
        self._nav_items: dict[str, SidebarItem] = {}
        views = [
            ("all",    "📄", "Tüm notlar",    len(self.app.notes)),
            ("pinned", "📌", "Sabitlenenler", sum(1 for n in self.app.notes if n.get("pinned"))),
            ("trash",  "🗑",  "Çöp Kutusu",   sum(1 for n in self.app.notes if n.get("deleted"))),
        ]
        for key, icon, label, count in views:
            item = SidebarItem(
                inner, icon, label, count=count,
                command=lambda k=key: self._switch_view(k),
                bg=SURFACE_LOW,
            )
            item.pack(fill="x", pady=1)
            self._nav_items[key] = item

        self._nav_items["all"].set_active(True)

        HSep(inner).pack(fill="x", pady=8)

        # Folders
        folders_hdr = tk.Frame(inner, bg=SURFACE_LOW)
        folders_hdr.pack(fill="x", padx=4)
        tk.Label(folders_hdr, text="KLASÖRLER", bg=SURFACE_LOW,
                 fg=OUTLINE, font=f_label_sm()).pack(side="left")

        for icon, folder in zip(_FOLDER_ICONS, _FOLDERS):
            count = sum(1 for n in self.app.notes
                        if n.get("folder") == folder and not n.get("deleted"))
            fi = SidebarItem(
                inner, icon, folder, count=count,
                command=lambda f=folder: self._filter_by_folder(f),
                bg=SURFACE_LOW,
            )
            fi.pack(fill="x", pady=1)

        HSep(inner).pack(fill="x", pady=8)

        # Bottom controls
        bottom = tk.Frame(sb, bg=SURFACE_LOW)
        bottom.pack(fill="x", padx=4, pady=(0, 6), side="bottom")
        HSep(bottom).pack(fill="x", pady=(0, 4))

        settings_item = SidebarItem(
            bottom, "⚙", "Ayarlar",
            command=self._open_settings, bg=SURFACE_LOW,
        )
        settings_item.pack(fill="x", pady=1)

        lock_item = SidebarItem(
            bottom, "🔒", "Uygulamayı kilitle",
            command=self.app.lock, bg=SURFACE_LOW,
        )
        lock_item.pack(fill="x", pady=1)

    # ── Notes list (middle panel) ─────────────────────────────────────────────
    def _build_notes_list(self):
        mid = self._mid

        # Header
        hdr = tk.Frame(mid, bg=SURFACE_LOWEST)
        hdr.pack(fill="x", padx=8, pady=(8, 0))

        hdr_row = tk.Frame(hdr, bg=SURFACE_LOWEST)
        hdr_row.pack(fill="x")
        self._list_title = tk.Label(hdr_row, text="Tüm notlar",
                                     bg=SURFACE_LOWEST, fg=ON_SURFACE,
                                     font=f_headline_sm())
        self._list_title.pack(side="left")
        self._count_badge = tk.Label(hdr_row, text="0 not",
                                      bg=SURFACE_HIGH, fg=ON_SURFACE_VAR,
                                      font=f_label_sm(), padx=6, pady=1)
        self._count_badge.pack(side="left", padx=(6, 0))

        # Search
        search_frame = tk.Frame(hdr, bg=SURFACE_CONT,
                                 highlightthickness=1,
                                 highlightbackground=OUTLINE_VAR)
        search_frame.pack(fill="x", pady=(8, 0))
        tk.Label(search_frame, text="🔍", bg=SURFACE_CONT,
                 font=("Segoe UI Emoji", 10)).pack(side="left", padx=(6, 2), pady=3)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search())
        search_entry = tk.Entry(
            search_frame, textvariable=self._search_var,
            bg=SURFACE_CONT, fg=ON_SURFACE,
            insertbackground=ON_SURFACE,
            relief="flat", font=f_body_sm(),
        )
        search_entry.pack(side="left", fill="x", expand=True, pady=3)
        self._search_entry = search_entry
        tk.Label(search_frame, text="Ctrl+F", bg=SURFACE_CONT,
                 fg=OUTLINE, font=f_mono()).pack(side="right", padx=6)

        HSep(hdr).pack(fill="x", pady=(6, 0))

        # Scrollable note cards
        self._notes_sf = ScrollFrame(mid, bg=SURFACE_LOWEST)
        self._notes_sf.pack(fill="both", expand=True)

    # ── Editor (right panel) ──────────────────────────────────────────────────
    def _build_editor_placeholder(self):
        for w in self._editor_host.winfo_children():
            w.destroy()
        placeholder = tk.Frame(self._editor_host, bg=SURFACE_LOWEST)
        placeholder.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(placeholder, text="📝", bg=SURFACE_LOWEST,
                 font=("Segoe UI Emoji", 36), fg=OUTLINE_VAR).pack()
        tk.Label(placeholder, text="Bir not seçin veya yeni not oluşturun",
                 bg=SURFACE_LOWEST, fg=OUTLINE, font=f_body_md()).pack(pady=(8, 0))
        tk.Label(placeholder, text="Ctrl+N — Yeni not",
                 bg=SURFACE_LOWEST, fg=OUTLINE_VAR, font=f_mono()).pack(pady=(2, 0))

    def _build_editor(self, note: dict):
        """Build the full editor for a selected note."""
        for w in self._editor_host.winfo_children():
            w.destroy()

        host = self._editor_host

        # ── Editor header ─────────────────────────────────────────────────────
        ehdr = tk.Frame(host, bg=SURFACE_LOWEST, height=44)
        ehdr.pack(fill="x")
        ehdr.pack_propagate(False)
        HSep(ehdr).pack(side="bottom", fill="x")

        # Breadcrumb
        bc_frame = tk.Frame(ehdr, bg=SURFACE_LOWEST)
        bc_frame.pack(side="left", fill="y", padx=12)
        folder = note.get("folder", "")
        if folder:
            tk.Label(bc_frame, text=folder, bg=SURFACE_LOWEST,
                     fg=TERTIARY, font=f_label_sm(), cursor="hand2").pack(
                side="left", pady=14)
            tk.Label(bc_frame, text=" › ", bg=SURFACE_LOWEST,
                     fg=OUTLINE, font=f_label_sm()).pack(side="left")
        title_preview = (note.get("title") or "Başlıksız")[:30]
        tk.Label(bc_frame, text=title_preview, bg=SURFACE_LOWEST,
                 fg=PRIMARY, font=f_label_sm()).pack(side="left")

        # Right actions
        actions = tk.Frame(ehdr, bg=SURFACE_LOWEST)
        actions.pack(side="right", fill="y", padx=8)

        # Save status
        self._save_dot2 = tk.Label(actions, text="●", bg=SURFACE_LOWEST,
                                    fg=GREEN_SAVED, font=("Segoe UI Emoji", 8))
        self._save_dot2.pack(side="left", pady=14, padx=(0, 2))
        self._save_lbl2 = tk.Label(actions, text="Kaydedildi",
                                    bg=SURFACE_LOWEST, fg=GREEN_DARK, font=f_mono())
        self._save_lbl2.pack(side="left", padx=(0, 8))

        # Action buttons
        for icon, tip, cmd in [
            ("📌", "Sabitle / Kaldır",    lambda: self._toggle_pin(note)),
            ("🗑",  "Çöp Kutusuna Taşı",  lambda: self._delete_note(note)),
        ]:
            btn = tk.Label(actions, text=icon, bg=SURFACE_LOWEST,
                           fg=ON_SURFACE_VAR, font=("Segoe UI Emoji", 13),
                           cursor="hand2")
            btn.pack(side="left", padx=2, pady=10)
            btn.bind("<Button-1>", lambda _e, c=cmd: c())

        # ── Format toolbar ────────────────────────────────────────────────────
        toolbar = tk.Frame(host, bg=SURFACE_LOW, height=32)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)
        HSep(toolbar).pack(side="bottom", fill="x")

        def fmt_btn(text: str, tip: str, cmd):
            b = tk.Label(toolbar, text=text, bg=SURFACE_LOW, fg=ON_SURFACE,
                         font=f_label_md(), cursor="hand2", width=3)
            b.pack(side="left", padx=1, pady=3)
            b.bind("<Button-1>", lambda _e: cmd())
            b.bind("<Enter>", lambda e: e.widget.configure(bg=SURFACE_CONT))
            b.bind("<Leave>", lambda e: e.widget.configure(bg=SURFACE_LOW))
            return b

        self._txt: tk.Text  # forward declaration

        fmt_btn("B",  "Kalın (Ctrl+B)",     lambda: self._fmt_toggle("bold"))
        fmt_btn("I",  "İtalik (Ctrl+I)",    lambda: self._fmt_toggle("italic"))
        fmt_btn("U",  "Altı Çizili",        lambda: self._fmt_toggle("underline"))
        fmt_btn("S̶",  "Üstü Çizili",        lambda: self._fmt_toggle("overstrike"))

        tk.Frame(toolbar, bg=OUTLINE_VAR, width=1).pack(side="left", fill="y",
                                                          pady=6, padx=4)

        fmt_btn("≡",  "Madde İmleri",    lambda: self._insert_bullet())
        fmt_btn("1.",  "Numaralı Liste", lambda: self._insert_numbered())

        tk.Frame(toolbar, bg=OUTLINE_VAR, width=1).pack(side="left", fill="y",
                                                          pady=6, padx=4)

        fmt_btn("↩", "Geri Al (Ctrl+Z)",  lambda: self._txt.edit_undo())
        fmt_btn("↪", "Yinele (Ctrl+Y)",   lambda: self._txt.edit_redo())

        # ── Document canvas ───────────────────────────────────────────────────
        doc = tk.Frame(host, bg=SURFACE_LOWEST)
        doc.pack(fill="both", expand=True)

        # Scrollbar (hidden per design)
        scrollbar = tk.Scrollbar(doc)
        scrollbar.pack(side="right", fill="y")

        # Title entry
        title_frame = tk.Frame(doc, bg=SURFACE_LOWEST)
        title_frame.pack(fill="x", padx=32, pady=(20, 0))
        self._title_var = tk.StringVar(value=note.get("title") or "")
        title_entry = tk.Entry(
            title_frame,
            textvariable=self._title_var,
            bg=SURFACE_LOWEST, fg=ON_SURFACE,
            insertbackground=ON_SURFACE,
            font=f_headline_lg(), relief="flat", bd=0,
        )
        title_entry.pack(fill="x", ipady=4)
        self._title_entry = title_entry

        HSep(title_frame).pack(fill="x", pady=(6, 0))

        # Metadata strip
        meta = tk.Frame(doc, bg=SURFACE_LOWEST)
        meta.pack(fill="x", padx=32, pady=(6, 0))
        modified = note.get("modified") or note.get("created") or ""
        mod_str = _format_date_long(modified)
        self._meta_lbl = tk.Label(
            meta,
            text=f"Klasör: {folder or 'Yok'}  •  {mod_str}",
            bg=SURFACE_LOWEST, fg=OUTLINE, font=f_mono(),
        )
        self._meta_lbl.pack(side="left")
        self._wc_lbl = tk.Label(meta, text="0 kelime, 0 karakter",
                                 bg=SURFACE_LOWEST, fg=OUTLINE, font=f_mono())
        self._wc_lbl.pack(side="right")

        HSep(doc).pack(fill="x", padx=32, pady=(6, 0))

        # Text widget
        self._txt = tk.Text(
            doc,
            bg=SURFACE_LOWEST, fg=ON_SURFACE,
            insertbackground=ON_SURFACE,
            font=f_body_lg(), relief="flat", bd=0,
            padx=32, pady=12,
            yscrollcommand=scrollbar.set,
            undo=True,
            wrap="word",
        )
        self._txt.pack(fill="both", expand=True)
        scrollbar.config(command=self._txt.yview)

        # Configure formatting tags
        ui_fam = f_body_lg()[0]
        ui_sz  = f_body_lg()[1]
        self._txt.tag_configure("bold",        font=(ui_fam, ui_sz, "bold"))
        self._txt.tag_configure("italic",      font=(ui_fam, ui_sz, "italic"))
        self._txt.tag_configure("underline",   underline=True)
        self._txt.tag_configure("overstrike",  overstrike=True)
        self._txt.tag_configure("bullet",      lmargin1=20, lmargin2=30)

        # Load content
        content = note.get("content") or ""
        self._txt.insert("1.0", content)
        self._txt.edit_reset()

        # Bindings
        self._txt.bind("<KeyRelease>",    self._on_text_change)
        self._title_entry.bind("<KeyRelease>", self._on_text_change)
        self._txt.bind("<Control-b>",     lambda _e: self._fmt_toggle("bold"))
        self._txt.bind("<Control-i>",     lambda _e: self._fmt_toggle("italic"))
        self._txt.bind("<Control-u>",     lambda _e: self._fmt_toggle("underline"))

        # ── Status bar ────────────────────────────────────────────────────────
        statusbar = tk.Frame(host, bg=SURFACE_LOW, height=22)
        statusbar.pack(fill="x", side="bottom")
        statusbar.pack_propagate(False)
        HSep(statusbar).pack(fill="x", side="top")
        sb_inner = tk.Frame(statusbar, bg=SURFACE_LOW)
        sb_inner.pack(fill="x", padx=8)
        self._status_left = tk.Label(sb_inner, text="Durum: Hazır",
                                      bg=SURFACE_LOW, fg=GREEN_DARK, font=f_mono())
        self._status_left.pack(side="left", pady=3)
        tk.Label(sb_inner, text="UTF-8  •  Windows",
                 bg=SURFACE_LOW, fg=OUTLINE, font=f_mono()).pack(side="right", pady=3)

        self._update_word_count()

    # ═════════════════════════════════════════════════════════════════════════
    # NOTE LIST MANAGEMENT
    # ═════════════════════════════════════════════════════════════════════════
    def _refresh_note_list(self):
        """Clear and rebuild the note card list."""
        for w in self._notes_sf.inner.winfo_children():
            w.destroy()
        self._note_cards.clear()

        notes = self._get_filtered_notes()
        # Pinned first
        pinned   = [n for n in notes if n.get("pinned")]
        unpinned = [n for n in notes if not n.get("pinned")]
        sorted_notes = pinned + unpinned

        for note in sorted_notes:
            card = NoteCard(
                self._notes_sf.inner,
                note,
                on_select=self._on_note_select,
                bg=SURFACE_LOWEST,
            )
            card.pack(fill="x")
            self._note_cards[note["id"]] = card
            self._notes_sf.bind_mousewheel(card)

        # Update count badge
        total = len(self._get_current_view_notes())
        self._count_badge.configure(text=f"{total} not")

        # Re-highlight active
        if self._active_note_id and self._active_note_id in self._note_cards:
            self._note_cards[self._active_note_id].set_selected(True)

        # Update sidebar nav counts
        all_notes = [n for n in self.app.notes if not n.get("deleted")]
        pinned_count = sum(1 for n in all_notes if n.get("pinned"))
        trash_count  = sum(1 for n in self.app.notes if n.get("deleted"))
        if "all"    in self._nav_items: self._nav_items["all"].update_count(len(all_notes))
        if "pinned" in self._nav_items: self._nav_items["pinned"].update_count(pinned_count)
        if "trash"  in self._nav_items: self._nav_items["trash"].update_count(trash_count)

    def _get_current_view_notes(self) -> list[dict]:
        """Notes for the current view before text search filter."""
        if self._active_view == "pinned":
            return [n for n in self.app.notes if n.get("pinned") and not n.get("deleted")]
        if self._active_view == "trash":
            return [n for n in self.app.notes if n.get("deleted")]
        if self._active_view.startswith("folder:"):
            folder = self._active_view[7:]
            return [n for n in self.app.notes
                    if n.get("folder") == folder and not n.get("deleted")]
        return [n for n in self.app.notes if not n.get("deleted")]

    def _get_filtered_notes(self) -> list[dict]:
        notes = self._get_current_view_notes()
        q = self._filter_query.lower()
        if not q:
            return notes
        return [n for n in notes
                if q in (n.get("title") or "").lower()
                or q in (n.get("content") or "").lower()]

    # ═════════════════════════════════════════════════════════════════════════
    # EVENT HANDLERS
    # ═════════════════════════════════════════════════════════════════════════
    def _on_note_select(self, note_id: str):
        # Save current before switching
        if self._active_note_id:
            self._flush_to_note(self._active_note_id)

        # Deselect previous
        if self._active_note_id and self._active_note_id in self._note_cards:
            self._note_cards[self._active_note_id].set_selected(False)

        self._active_note_id = note_id

        if note_id in self._note_cards:
            self._note_cards[note_id].set_selected(True)

        note = self._find_note(note_id)
        if note:
            self._build_editor(note)
            # Update breadcrumb
            title = (note.get("title") or "Başlıksız")[:40]
            self._breadcrumb.configure(text=title)

    def _on_text_change(self, _event=None):
        self._mark_unsaved()
        if self._autosave_id:
            self.after_cancel(self._autosave_id)
        self._autosave_id = self.after(2000, self._autosave)
        self._update_word_count()

    def _on_search(self):
        self._filter_query = self._search_var.get()
        self._refresh_note_list()

    def _switch_view(self, key: str):
        self._active_view = key
        for k, item in self._nav_items.items():
            item.set_active(k == key)
        titles = {"all": "Tüm notlar", "pinned": "Sabitlenenler",
                  "trash": "Çöp Kutusu"}
        self._list_title.configure(text=titles.get(key, key))
        self._filter_query = ""
        self._search_var.set("")
        self._refresh_note_list()

    def _filter_by_folder(self, folder: str):
        self._active_view = f"folder:{folder}"
        for item in self._nav_items.values():
            item.set_active(False)
        self._list_title.configure(text=folder)
        self._refresh_note_list()

    def _focus_search(self):
        self._search_entry.focus_set()

    # ═════════════════════════════════════════════════════════════════════════
    # NOTE CRUD
    # ═════════════════════════════════════════════════════════════════════════
    def _new_note(self):
        from wontnote.notes import create_note
        note = create_note("", "")
        note["folder"] = ""
        note["pinned"] = False
        note["deleted"] = False
        self.app.notes.insert(0, note)
        self._active_view = "all"
        for k, item in self._nav_items.items():
            item.set_active(k == "all")
        self._list_title.configure(text="Tüm notlar")
        self._refresh_note_list()
        self._on_note_select(note["id"])
        if hasattr(self, "_title_entry"):
            self._title_entry.focus_set()

    def _flush_to_note(self, note_id: str):
        """Write editor state back to the note dict (no save)."""
        note = self._find_note(note_id)
        if note is None:
            return
        if hasattr(self, "_title_var"):
            note["title"] = self._title_var.get().strip()
        if hasattr(self, "_txt"):
            note["content"] = self._txt.get("1.0", "end-1c")
        # Update modified timestamp
        note["modified"] = datetime.now(timezone.utc).isoformat()

    def _toggle_pin(self, note: dict):
        note["pinned"] = not note.get("pinned", False)
        self._flush_to_note(note["id"])
        self._autosave()
        self._refresh_note_list()

    def _delete_note(self, note: dict):
        if note.get("deleted"):
            # Permanently delete
            self.app.notes = [n for n in self.app.notes if n["id"] != note["id"]]
        else:
            note["deleted"] = True
        self._active_note_id = None
        self._autosave()
        self._refresh_note_list()
        self._build_editor_placeholder()
        self._breadcrumb.configure(text="Yerel Depolama")

    def _find_note(self, note_id: str) -> dict | None:
        return next((n for n in self.app.notes if n["id"] == note_id), None)

    # ═════════════════════════════════════════════════════════════════════════
    # SAVE
    # ═════════════════════════════════════════════════════════════════════════
    def _autosave(self):
        """Flush editor → note dict → encrypt → write vault."""
        if self._active_note_id:
            self._flush_to_note(self._active_note_id)
        try:
            from wontnote.crypto_core import save_notes
            from wontnote.vault_storage import write_vault
            new_vault = save_notes(
                self.app.vault_bytes,
                self.app.master_key,
                self.app.notes,
            )
            write_vault(new_vault)
            self.app.vault_bytes = new_vault
            ts = datetime.now().strftime("%H:%M")
            self._mark_saved(ts)
            self._refresh_note_list()
        except Exception as exc:
            self._mark_error(str(exc))

    def _mark_unsaved(self):
        self._save_dot.configure(fg="#f59e0b")
        self._save_lbl.configure(text="Kaydediliyor…", fg="#b45309")
        if hasattr(self, "_save_dot2"):
            self._save_dot2.configure(fg="#f59e0b")
            self._save_lbl2.configure(text="Kaydedilmedi…", fg="#b45309")

    def _mark_saved(self, ts: str):
        self._save_dot.configure(fg=GREEN_SAVED)
        self._save_lbl.configure(text=f"Kaydedildi ({ts})", fg=GREEN_DARK)
        if hasattr(self, "_save_dot2"):
            self._save_dot2.configure(fg=GREEN_SAVED)
            self._save_lbl2.configure(text=f"Kaydedildi ({ts})", fg=GREEN_DARK)

    def _mark_error(self, msg: str):
        self._save_dot.configure(fg=ERROR)
        self._save_lbl.configure(text=f"Hata: {msg}", fg=ERROR)

    # ═════════════════════════════════════════════════════════════════════════
    # FORMATTING HELPERS
    # ═════════════════════════════════════════════════════════════════════════
    def _fmt_toggle(self, tag: str):
        if not hasattr(self, "_txt"):
            return
        try:
            current_tags = self._txt.tag_names("sel.first")
            if tag in current_tags:
                self._txt.tag_remove(tag, "sel.first", "sel.last")
            else:
                self._txt.tag_add(tag, "sel.first", "sel.last")
        except tk.TclError:
            pass  # no selection

    def _insert_bullet(self):
        if not hasattr(self, "_txt"):
            return
        self._txt.insert("insert", "\n• ")
        self._txt.tag_add("bullet", "insert linestart", "insert")

    def _insert_numbered(self):
        if not hasattr(self, "_txt"):
            return
        # Count existing numbered lines to auto-increment
        line_no = int(self._txt.index("insert").split(".")[0])
        self._txt.insert("insert", f"\n{line_no}. ")

    def _update_word_count(self):
        if not hasattr(self, "_txt"):
            return
        content = self._txt.get("1.0", "end-1c")
        words = len(content.split()) if content.strip() else 0
        chars = len(content)
        if hasattr(self, "_wc_lbl"):
            self._wc_lbl.configure(text=f"{words} kelime, {chars} karakter")
        # Status bar line/col
        try:
            idx = self._txt.index("insert")
            line, col = idx.split(".")
            if hasattr(self, "_status_left"):
                self._status_left.configure(
                    text=f"Satır {line}, Sütun {int(col)+1}")
        except Exception:
            pass

    # ═════════════════════════════════════════════════════════════════════════
    # SETTINGS
    # ═════════════════════════════════════════════════════════════════════════
    def _open_settings(self):
        from .settings import SettingsDialog
        SettingsDialog(self.winfo_toplevel(), self.app)


# ── Date helpers ──────────────────────────────────────────────────────────────
def _format_date_long(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return f"Son düzenleme: {dt.astimezone().strftime('%d %b %Y %H:%M')}"
    except Exception:
        return iso[:10]
