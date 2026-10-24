"""
widgets.py — Reusable WontNote UI components.
"""
import tkinter as tk
from .theme import (
    SURFACE_LOWEST, SURFACE_LOW, SURFACE_CONT, SURFACE_HIGH, SURFACE_HIGHEST,
    ON_SURFACE, ON_SURFACE_VAR, OUTLINE, OUTLINE_VAR,
    PRIMARY, PRIMARY_FIXED, ON_PRIMARY,
    SECONDARY, TERTIARY,
    ERROR, ERROR_CONT, ON_ERROR, ON_ERROR_CONT,
    GREEN_DARK,
    f_body_md, f_body_sm, f_label_md, f_label_sm, f_mono, f_headline_sm,
)


# ── Thin separator ─────────────────────────────────────────────────────────────
def HSep(parent: tk.Widget, **kw) -> tk.Frame:
    """1-pixel horizontal separator."""
    return tk.Frame(parent, bg=OUTLINE_VAR, height=1, **kw)


# ── Scrollable frame ───────────────────────────────────────────────────────────
class ScrollFrame(tk.Frame):
    """A Frame that scrolls vertically with the mouse wheel."""

    def __init__(self, parent: tk.Widget, bg: str = SURFACE_LOWEST, **kw):
        super().__init__(parent, bg=bg, **kw)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.inner  = tk.Frame(self.canvas, bg=bg)

        self.canvas.pack(fill="both", expand=True)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_mousewheel(self.canvas)
        self._bind_mousewheel(self.inner)

    def _on_inner_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._win, width=event.width)

    def _bind_mousewheel(self, widget: tk.Widget):
        widget.bind("<MouseWheel>",
                    lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    def bind_mousewheel(self, widget: tk.Widget):
        """Extend mouse-wheel scrolling to a child widget."""
        self._bind_mousewheel(widget)


# ── Password entry with toggle ─────────────────────────────────────────────────
class PasswordEntry(tk.Frame):
    """
    tk.Entry(show='•') with an eye-button on the right.
    Use .get() to read the current value.
    """

    def __init__(self, parent: tk.Widget, bg_entry: str = SURFACE_LOW,
                 on_change=None, **kw):
        super().__init__(parent, bg=bg_entry, **kw)
        self._shown = False
        self._on_change = on_change

        self.entry = tk.Entry(
            self,
            show="•",
            bg=bg_entry,
            fg=ON_SURFACE,
            insertbackground=ON_SURFACE,
            relief="flat",
            font=f_body_md(),
            bd=0,
        )
        self.entry.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=5)

        self._eye_btn = tk.Label(
            self, text="👁", bg=bg_entry, fg=OUTLINE, cursor="hand2",
            font=("Segoe UI Emoji", 11),
        )
        self._eye_btn.pack(side="right", padx=(0, 6))
        self._eye_btn.bind("<Button-1>", self._toggle)

        if on_change:
            self.entry.bind("<KeyRelease>", lambda _e: on_change())

    def _toggle(self, _event=None):
        self._shown = not self._shown
        self.entry.config(show="" if self._shown else "•")
        self._eye_btn.config(text="🙈" if self._shown else "👁")

    def get(self) -> str:
        return self.entry.get()

    def set(self, value: str):
        self.entry.delete(0, "end")
        self.entry.insert(0, value)

    def clear(self):
        self.entry.delete(0, "end")

    def focus(self):
        self.entry.focus_set()


# ── Sidebar navigation item ────────────────────────────────────────────────────
class SidebarItem(tk.Frame):
    """
    A sidebar navigation row: [icon_label  text_label  count_label].
    Handles hover highlight and active state (left primary border).
    """

    def __init__(self, parent: tk.Widget, icon: str, label: str,
                 count: int | None = None,
                 command=None,
                 bg: str = SURFACE_LOW,
                 **kw):
        super().__init__(parent, bg=bg, cursor="hand2", **kw)
        self._bg    = bg
        self._command = command
        self._active  = False

        # Left accent border (hidden by default, shown when active)
        self._accent = tk.Frame(self, bg=PRIMARY, width=3)
        self._accent.pack(side="left", fill="y")
        self._accent.pack_forget()

        inner = tk.Frame(self, bg=bg)
        inner.pack(side="left", fill="both", expand=True, padx=4, pady=3)

        lbl_icon = tk.Label(inner, text=icon, bg=bg, fg=OUTLINE,
                            font=("Segoe UI Emoji", 11), width=2)
        lbl_icon.pack(side="left")

        lbl_text = tk.Label(inner, text=label, bg=bg, fg=ON_SURFACE_VAR,
                            font=f_body_md(), anchor="w")
        lbl_text.pack(side="left", fill="x", expand=True, padx=(4, 0))

        self._icon_lbl = lbl_icon
        self._text_lbl = lbl_text

        if count is not None:
            self._count_lbl = tk.Label(
                inner, text=str(count), bg=bg, fg=OUTLINE,
                font=f_mono(), padx=4,
            )
            self._count_lbl.pack(side="right")
        else:
            self._count_lbl = None

        for widget in (self, inner, lbl_icon, lbl_text):
            widget.bind("<Button-1>", self._on_click)
            widget.bind("<Enter>",    self._on_enter)
            widget.bind("<Leave>",    self._on_leave)
        if self._count_lbl:
            self._count_lbl.bind("<Button-1>", self._on_click)

    def _on_click(self, _event=None):
        if self._command:
            self._command()

    def _on_enter(self, _event=None):
        if not self._active:
            self._set_bg(SURFACE_CONT)

    def _on_leave(self, _event=None):
        if not self._active:
            self._set_bg(self._bg)

    def _set_bg(self, color: str):
        for w in self.winfo_children():
            w.configure(bg=color)
            for c in w.winfo_children():
                c.configure(bg=color)
        self.configure(bg=color)

    def set_active(self, active: bool):
        self._active = active
        if active:
            self._accent.pack(side="left", fill="y", before=self.winfo_children()[1])
            self._set_bg(SURFACE_CONT)
            self._text_lbl.configure(fg=PRIMARY, font=f_label_md() + ("bold",)
                                     if False else f_body_md())
            self._text_lbl.configure(fg=PRIMARY)
            self._icon_lbl.configure(fg=PRIMARY)
        else:
            self._accent.pack_forget()
            self._set_bg(self._bg)
            self._text_lbl.configure(fg=ON_SURFACE_VAR)
            self._icon_lbl.configure(fg=OUTLINE)

    def update_count(self, count: int):
        if self._count_lbl:
            self._count_lbl.configure(text=str(count))


# ── Note card for the middle list ──────────────────────────────────────────────
class NoteCard(tk.Frame):
    """
    Compact note preview card: title + 2-line preview + date + folder tag.
    Selected state draws a left colored border.
    """
    PREVIEW_LEN = 120

    def __init__(self, parent: tk.Widget, note: dict,
                 on_select=None, bg: str = SURFACE_LOWEST, **kw):
        super().__init__(parent, bg=bg, cursor="hand2", **kw)
        self._bg = bg
        self._selected = False
        self._on_select = on_select
        self.note_id = note.get("id", "")

        # ── Left accent ───────────────────────────────────────────────────────
        self._accent = tk.Frame(self, bg=PRIMARY, width=3)

        # ── Content frame ─────────────────────────────────────────────────────
        content = tk.Frame(self, bg=bg)
        content.pack(side="left", fill="both", expand=True, padx=6, pady=5)

        # ── Title row ─────────────────────────────────────────────────────────
        title_row = tk.Frame(content, bg=bg)
        title_row.pack(fill="x")

        title_text = note.get("title") or "Başlıksız Not"
        title_lbl = tk.Label(
            title_row, text=title_text, bg=bg, fg=ON_SURFACE,
            font=f_headline_sm(), anchor="w",
        )
        title_lbl.pack(side="left", fill="x", expand=True)

        if note.get("pinned"):
            pin_lbl = tk.Label(title_row, text="📌", bg=bg, fg=PRIMARY,
                               font=("Segoe UI Emoji", 9))
            pin_lbl.pack(side="right")
            self._bind_all(pin_lbl)

        # ── Preview ───────────────────────────────────────────────────────────
        preview = (note.get("content") or "").replace("\n", " ")[:self.PREVIEW_LEN]
        if len(note.get("content") or "") > self.PREVIEW_LEN:
            preview += "…"
        if not preview:
            preview = "İçerik yok."
        preview_lbl = tk.Label(
            content, text=preview, bg=bg, fg=ON_SURFACE_VAR,
            font=f_body_sm(), anchor="w", justify="left", wraplength=260,
        )
        preview_lbl.pack(fill="x", pady=(1, 0))

        # ── Meta row ──────────────────────────────────────────────────────────
        meta_row = tk.Frame(content, bg=bg)
        meta_row.pack(fill="x", pady=(3, 0))

        date_str = _format_date(note.get("modified") or note.get("created") or "")
        date_lbl = tk.Label(meta_row, text=date_str, bg=bg, fg=OUTLINE,
                            font=f_mono())
        date_lbl.pack(side="left")

        folder = note.get("folder")
        if folder:
            folder_lbl = tk.Label(
                meta_row, text=folder, bg=SURFACE_HIGH, fg=TERTIARY,
                font=f_label_sm(), padx=4, pady=1,
            )
            folder_lbl.pack(side="right")
            self._bind_all(folder_lbl)

        # ── Bottom separator ──────────────────────────────────────────────────
        tk.Frame(self, bg=OUTLINE_VAR, height=1).pack(fill="x", side="bottom")

        # ── Bindings ──────────────────────────────────────────────────────────
        self._bind_all(self, content, title_row, title_lbl, preview_lbl,
                        meta_row, date_lbl)

    def _bind_all(self, *widgets):
        for w in widgets:
            w.bind("<Button-1>", self._on_click)
            w.bind("<Enter>",    self._on_enter)
            w.bind("<Leave>",    self._on_leave)
            w.bind("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        p = self.master
        while p is not None:
            if hasattr(p, "canvas") and isinstance(p.canvas, tk.Canvas):
                p.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                break
            p = getattr(p, "master", None)

    def _on_click(self, _event=None):
        if self._on_select:
            self._on_select(self.note_id)

    def _on_enter(self, _event=None):
        if not self._selected:
            self._set_bg(SURFACE_LOW)

    def _on_leave(self, _event=None):
        if not self._selected:
            self._set_bg(self._bg)

    def _set_bg(self, color: str):
        self.configure(bg=color)
        for w in self.winfo_descendants():
            try:
                w.configure(bg=color)
            except tk.TclError:
                pass

    def set_selected(self, selected: bool):
        self._selected = selected
        if selected:
            self._accent.place(x=0, y=0, relheight=1.0, width=3)
            self._set_bg(PRIMARY_FIXED)
        else:
            self._accent.place_forget()
            self._set_bg(self._bg)


def _format_date(iso: str) -> str:
    """Convert ISO timestamp to human-friendly Turkish string."""
    if not iso:
        return ""
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - dt
        if delta.days == 0:
            return f"Bugün {dt.astimezone().strftime('%H:%M')}"
        if delta.days == 1:
            return f"Dün {dt.astimezone().strftime('%H:%M')}"
        return dt.astimezone().strftime("%d %b")
    except Exception:
        return iso[:10]


# ── Rounded button factory ─────────────────────────────────────────────────────
def PrimaryBtn(parent: tk.Widget, text: str, command=None, **kw) -> tk.Button:
    return tk.Button(
        parent, text=text, command=command,
        bg=PRIMARY, fg=ON_PRIMARY, activebackground=SECONDARY,
        activeforeground=ON_PRIMARY, relief="flat", cursor="hand2",
        font=f_label_md(), padx=12, pady=5, bd=0, **kw,
    )


def SecondaryBtn(parent: tk.Widget, text: str, command=None, **kw) -> tk.Button:
    return tk.Button(
        parent, text=text, command=command,
        bg=SURFACE_HIGH, fg=ON_SURFACE, activebackground=SURFACE_HIGHEST,
        activeforeground=ON_SURFACE, relief="flat", cursor="hand2",
        font=f_label_md(), padx=12, pady=5, bd=0, **kw,
    )


def DangerBtn(parent: tk.Widget, text: str, command=None, **kw) -> tk.Button:
    return tk.Button(
        parent, text=text, command=command,
        bg=ERROR, fg=ON_ERROR, activebackground="#8b0000",
        activeforeground=ON_ERROR, relief="flat", cursor="hand2",
        font=f_label_md(), padx=12, pady=5, bd=0, **kw,
    )


# ── Strength meter (3 segments) ────────────────────────────────────────────────
class StrengthMeter(tk.Frame):
    """Three-segment password strength indicator."""

    _COLORS = {
        0: ("#dbd9e1", "#dbd9e1", "#dbd9e1", ""),
        1: (ERROR,     "#dbd9e1", "#dbd9e1", "Zayıf"),
        2: ("#f59e0b", "#f59e0b", "#dbd9e1", "Orta"),
        3: ("#10b981", "#10b981", "#10b981", "Güçlü"),
    }

    def __init__(self, parent: tk.Widget, **kw):
        super().__init__(parent, bg=parent.cget("bg"), **kw)
        self._segs = []
        for _ in range(3):
            seg = tk.Frame(self, bg=SURFACE_HIGH, height=4, width=60)
            seg.pack(side="left", padx=2)
            self._segs.append(seg)
        self._lbl = tk.Label(self, text="", bg=parent.cget("bg"),
                             fg=OUTLINE, font=f_mono())
        self._lbl.pack(side="left", padx=(4, 0))
        self.set_level(0)

    def set_level(self, level: int):
        c1, c2, c3, txt = self._COLORS.get(min(level, 3), self._COLORS[0])
        for seg, color in zip(self._segs, (c1, c2, c3)):
            seg.configure(bg=color)
        self._lbl.configure(
            text=txt,
            fg=ERROR if level == 1 else ("#f59e0b" if level == 2 else GREEN_DARK
                                         if level == 3 else OUTLINE),
        )
