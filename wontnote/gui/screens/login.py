"""
login.py — Vault unlock / login screen.
Shown every time the app starts when a vault already exists,
or when the user locks the app via Ctrl+L.
"""
import tkinter as tk

from ..theme import (
    SURFACE, SURFACE_LOW, SURFACE_CONT, SURFACE_HIGH, SURFACE_HIGHEST,
    ON_SURFACE, ON_SURFACE_VAR, OUTLINE, OUTLINE_VAR,
    PRIMARY, PRIMARY_FIXED, PRIMARY_FIXED_DIM, ON_PRIMARY,
    SECONDARY_FIXED, ERROR, ERROR_CONT, ON_ERROR_CONT,
    INVERSE_SURFACE, INV_ON_SURFACE,
    f_headline_lg, f_headline_md, f_headline_sm,
    f_body_md, f_body_sm, f_label_md, f_label_sm, f_mono,
)
from ..widgets import PasswordEntry, PrimaryBtn, SecondaryBtn, HSep


class LoginScreen(tk.Frame):
    """
    Centered login card — mirrors the 'Tekrar hoş geldin' HTML design.
    """

    def __init__(self, parent: tk.Widget, app):
        super().__init__(parent, bg=SURFACE)
        self.app = app
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self):
        self.pack(fill="both", expand=True)
        self.configure(bg=SURFACE)

        canvas = tk.Canvas(self, bg=SURFACE, highlightthickness=0, bd=0)
        vbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)

        container = tk.Frame(canvas, bg=SURFACE)
        win_id = canvas.create_window((0, 0), window=container, anchor="nw")

        def _update_layout(_event=None):
            self.update_idletasks()
            c_w = canvas.winfo_width()
            c_h = canvas.winfo_height()
            req_w = card.winfo_reqwidth()
            req_h = card.winfo_reqheight()

            x = max(10, (c_w - req_w) // 2) if c_w > req_w else 10
            y = max(16, (c_h - req_h) // 2) if c_h > req_h else 16

            canvas.coords(win_id, x, y)
            tot_w = max(c_w, req_w + x * 2)
            tot_h = max(c_h, req_h + y * 2)
            canvas.configure(scrollregion=(0, 0, tot_w, tot_h))

            if req_h + 32 > c_h:
                if not vbar.winfo_ismapped():
                    vbar.pack(side="right", fill="y")
            else:
                if vbar.winfo_ismapped():
                    vbar.pack_forget()

        canvas.pack(side="left", fill="both", expand=True)
        canvas.bind("<Configure>", _update_layout)
        container.bind("<Configure>", _update_layout)

        def _on_wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _on_wheel)
        container.bind("<MouseWheel>", _on_wheel)

        # ── Card ──────────────────────────────────────────────────────────────
        card = tk.Frame(container, bg=SURFACE_LOW, bd=0, relief="flat",
                        highlightthickness=1, highlightbackground=OUTLINE_VAR)
        card.pack(padx=16, pady=16)

        # ── Icon + branding ───────────────────────────────────────────────────
        top = tk.Frame(card, bg=SURFACE_LOW)
        top.pack(fill="x", padx=36, pady=(28, 0))

        icon_frame = tk.Frame(top, bg=PRIMARY_FIXED, width=56, height=56)
        icon_frame.pack_propagate(False)
        icon_frame.pack()
        tk.Label(icon_frame, text="🔒", bg=PRIMARY_FIXED,
                 font=("Segoe UI Emoji", 24)).place(relx=0.5, rely=0.5, anchor="center")

        badge = tk.Frame(top, bg=SURFACE_HIGH)
        badge.pack(pady=(10, 0))
        dot = tk.Label(badge, text="●", bg=SURFACE_HIGH, fg=PRIMARY,
                       font=("Segoe UI Emoji", 6))
        dot.pack(side="left", padx=(6, 2), pady=3)
        tk.Label(badge, text="WontNote  •  v1.0", bg=SURFACE_HIGH,
                 fg=ON_SURFACE_VAR, font=f_label_sm()).pack(side="left", padx=(0, 6))

        tk.Label(top, text="Tekrar hoş geldin", bg=SURFACE_LOW, fg=ON_SURFACE,
                 font=f_headline_lg()).pack(pady=(8, 0))
        tk.Label(top, text="Notlarına erişmek için şifreni gir.",
                 bg=SURFACE_LOW, fg=ON_SURFACE_VAR, font=f_body_md()).pack(pady=(3, 0))

        # ── Form ──────────────────────────────────────────────────────────────
        form = tk.Frame(card, bg=SURFACE_LOW)
        form.pack(fill="x", padx=36, pady=20)

        # Label row (Şifre + Caps Lock warning)
        lbl_row = tk.Frame(form, bg=SURFACE_LOW)
        lbl_row.pack(fill="x")
        tk.Label(lbl_row, text="Şifre", bg=SURFACE_LOW, fg=ON_SURFACE,
                 font=f_label_md()).pack(side="left")
        self._caps_lbl = tk.Label(lbl_row, text="⚠ Caps Lock Açık",
                                   bg=SURFACE_LOW, fg=ERROR, font=f_label_sm())
        # not packed yet — shown dynamically

        # Password entry
        self._pwd = PasswordEntry(form, bg_entry=SURFACE_HIGH)
        self._pwd.pack(fill="x", pady=(4, 0), ipady=2)
        self._pwd.entry.bind("<Return>", lambda _: self._on_unlock())
        self._pwd.entry.bind("<KeyRelease>", self._on_key_up)

        # Char count / hint
        hint_row = tk.Frame(form, bg=SURFACE_LOW)
        hint_row.pack(fill="x", pady=(4, 0))
        tk.Label(hint_row, text="↵ Enter ile hızlı açın",
                 bg=SURFACE_LOW, fg=ON_SURFACE_VAR, font=f_label_sm()).pack(side="left")
        self._char_lbl = tk.Label(hint_row, text="0 karakter",
                                   bg=SURFACE_LOW, fg=ON_SURFACE_VAR, font=f_mono())
        self._char_lbl.pack(side="right")

        # Error message
        self._err_frame = tk.Frame(form, bg=ERROR_CONT)
        self._err_inner  = tk.Frame(self._err_frame, bg=ERROR_CONT)
        self._err_inner.pack(fill="x", padx=8, pady=6)
        tk.Label(self._err_inner, text="⚠", bg=ERROR_CONT, fg=ERROR,
                 font=f_label_md()).pack(side="left")
        self._err_txt = tk.Label(
            self._err_inner,
            text="Hatalı şifre. Lütfen kasanızın şifresini kontrol edin.",
            bg=ERROR_CONT, fg=ON_ERROR_CONT, font=f_label_md(),
            wraplength=340, justify="left",
        )
        self._err_txt.pack(side="left", padx=(4, 0))

        # Submit button
        self._unlock_btn = PrimaryBtn(
            form, "  🔓  Kilidi Aç  ", command=self._on_unlock,
        )
        self._unlock_btn.pack(fill="x", pady=(10, 0), ipady=3)

        # Links row
        links = tk.Frame(form, bg=SURFACE_LOW)
        links.pack(fill="x", pady=(10, 0))
        recovery_btn = tk.Label(
            links, text="🗝 Kurtarma Anahtarı ile Aç",
            bg=SURFACE_LOW, fg=PRIMARY, font=f_label_md(), cursor="hand2",
        )
        recovery_btn.pack(side="left")
        recovery_btn.bind("<Button-1>", lambda _: self._open_recovery_modal())

        # Bottom status bar
        bottom = tk.Frame(card, bg=SURFACE_HIGH)
        bottom.pack(fill="x")
        bottom_inner = tk.Frame(bottom, bg=SURFACE_HIGH)
        bottom_inner.pack(fill="x", padx=12, pady=6)
        tk.Label(bottom_inner, text="✓", bg=SURFACE_HIGH, fg=PRIMARY,
                 font=f_label_md()).pack(side="left")
        tk.Label(bottom_inner, text=" Yerel Kasa Durumu: Korumalı",
                 bg=SURFACE_HIGH, fg=ON_SURFACE_VAR, font=f_label_sm()).pack(side="left")
        tk.Label(bottom_inner, text="AES-256-GCM",
                 bg=SURFACE_HIGH, fg=ON_SURFACE_VAR, font=f_mono()).pack(side="right")

        self._bind_wheel_recursive(card, _on_wheel)
        self._pwd.focus()

    def _bind_wheel_recursive(self, widget: tk.Widget, handler):
        widget.bind("<MouseWheel>", handler)
        for child in widget.winfo_children():
            self._bind_wheel_recursive(child, handler)

    # ── Event handlers ────────────────────────────────────────────────────────
    def _on_key_up(self, event):
        val = self._pwd.get()
        self._char_lbl.configure(text=f"{len(val)} karakter")
        self._err_frame.pack_forget()

        # Caps Lock detection
        try:
            if event.state & 0x2:  # CapsLock bit
                self._caps_lbl.pack(side="right")
            else:
                self._caps_lbl.pack_forget()
        except Exception:
            pass

    def _on_unlock(self):
        pwd = self._pwd.get()
        if not pwd:
            self._show_error()
            return
        self._unlock_btn.configure(state="disabled", text="⏳ Şifre çözülüyor…")
        self.after(50, lambda: self._do_unlock(pwd))

    def _do_unlock(self, pwd: str):
        from wontnote.crypto_core import unlock_with_password, VaultError
        try:
            mk, notes = unlock_with_password(self.app.vault_bytes, pwd)
            self.app.master_key = mk
            self.app.notes      = notes
            self.app.show_main()
        except VaultError:
            self._unlock_btn.configure(state="normal", text="  🔓  Kilidi Aç  ")
            self._show_error()
            self._pwd.clear()
            self._pwd.focus()
        except Exception as exc:
            self._unlock_btn.configure(state="normal", text="  🔓  Kilidi Aç  ")
            self._show_error(f"Hata: {exc}")

    def _show_error(self, msg: str | None = None):
        if msg:
            self._err_txt.configure(text=msg)
        self._err_frame.pack(fill="x", pady=(8, 0))

    def _open_recovery_modal(self):
        win = tk.Toplevel(self.winfo_toplevel())
        win.title("Kurtarma Anahtarı ile Aç")
        win.resizable(True, True)
        win.minsize(420, 320)
        win.grab_set()
        win.configure(bg=SURFACE_LOW)

        tk.Label(win, text="🗝 Kurtarma Anahtarı", bg=SURFACE_LOW,
                 fg=ON_SURFACE, font=f_headline_sm()).pack(padx=24, pady=(16, 4))
        tk.Label(
            win,
            text="Kurulum sırasında aldığınız kurtarma anahtarını girin.",
            bg=SURFACE_LOW, fg=ON_SURFACE_VAR, font=f_body_sm(),
            wraplength=340, justify="center",
        ).pack(padx=24)

        tk.Label(win, text="Kurtarma Anahtarı", bg=SURFACE_LOW, fg=ON_SURFACE,
                 font=f_label_md(), anchor="w").pack(fill="x", padx=24, pady=(12, 2))
        key_entry = tk.Entry(win, font=("Consolas", 11), bg=SURFACE_HIGH,
                              fg=ON_SURFACE, relief="flat", justify="center")
        key_entry.pack(fill="x", padx=24, ipady=6)

        info = tk.Frame(win, bg=SURFACE_CONT)
        info.pack(fill="x", padx=24, pady=10)
        tk.Label(info, text="ℹ️", bg=SURFACE_CONT,
                 font=("Segoe UI Emoji", 11)).pack(side="left", padx=(8, 4), pady=6)
        tk.Label(
            info,
            text="Kurtarma anahtarı olmadan şifrelenmiş veriler açılamaz.",
            bg=SURFACE_CONT, fg=ON_SURFACE_VAR, font=f_label_sm(),
            wraplength=280, justify="left",
        ).pack(side="left", pady=6, padx=(0, 8))

        err_lbl = tk.Label(win, text="", bg=SURFACE_LOW, fg=ERROR,
                            font=f_body_sm())
        err_lbl.pack()

        def do_recovery():
            key = key_entry.get().strip()
            if not key:
                err_lbl.configure(text="Lütfen kurtarma anahtarını girin.")
                return
            from wontnote.crypto_core import unlock_with_recovery_key, VaultError
            try:
                mk, notes = unlock_with_recovery_key(
                    self.app.vault_bytes, key
                )
                self.app.master_key = mk
                self.app.notes      = notes
                win.destroy()
                self.app.show_main()
            except VaultError:
                err_lbl.configure(text="Could not open vault.")
            except Exception as exc:
                err_lbl.configure(text=f"Hata: {exc}")

        btn_row = tk.Frame(win, bg=SURFACE_LOW)
        btn_row.pack(fill="x", padx=24, pady=(0, 16))
        tk.Button(btn_row, text="Vazgeç", command=win.destroy,
                   bg=SURFACE_HIGH, fg=ON_SURFACE, relief="flat",
                   font=f_label_md(), cursor="hand2",
                   padx=10, pady=4).pack(side="left")
        tk.Button(btn_row, text="Doğrula ve Aç", command=do_recovery,
                   bg=PRIMARY, fg=ON_PRIMARY, relief="flat",
                   font=f_label_md(), cursor="hand2",
                   padx=10, pady=4).pack(side="right")
        key_entry.bind("<Return>", lambda _: do_recovery())
        key_entry.focus_set()
