"""
setup.py — First-time vault creation screen.
Shown when no vault.wnt file exists yet.
"""
import tkinter as tk
import unicodedata

from ..theme import (
    SURFACE, SURFACE_LOW, SURFACE_CONT, SURFACE_HIGH,
    ON_SURFACE, ON_SURFACE_VAR, OUTLINE, OUTLINE_VAR,
    PRIMARY, PRIMARY_FIXED, ON_PRIMARY,
    SECONDARY_FIXED, ERROR, ERROR_CONT, ON_ERROR_CONT,
    f_headline_lg, f_headline_md, f_body_md, f_body_sm,
    f_label_md, f_label_sm, f_mono,
)
from ..widgets import PasswordEntry, StrengthMeter, PrimaryBtn, HSep


class SetupScreen(tk.Frame):
    """
    Full-window frame — creates a new encrypted vault.
    Mirrors the 'Şifreni oluştur' HTML design.
    """

    def __init__(self, parent: tk.Widget, app):
        super().__init__(parent, bg=SURFACE)
        self.app = app
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self):
        # ── Scrollable responsive container ──────────────────────────────────
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

        card = tk.Frame(container, bg=SURFACE_LOW, bd=0, relief="flat",
                        highlightthickness=1, highlightbackground=OUTLINE_VAR)
        card.pack(padx=16, pady=16)

        # ── Top branding ──────────────────────────────────────────────────────
        top = tk.Frame(card, bg=SURFACE_LOW)
        top.pack(fill="x", padx=32, pady=(28, 0))

        icon_frame = tk.Frame(top, bg=SECONDARY_FIXED, width=52, height=52)
        icon_frame.pack_propagate(False)
        icon_frame.pack()
        tk.Label(icon_frame, text="🔐", bg=SECONDARY_FIXED,
                 font=("Segoe UI Emoji", 22)).place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(top, text="WONTNOTE", bg=SURFACE_LOW, fg=ON_SURFACE_VAR,
                 font=f_label_sm()).pack(pady=(10, 0))
        tk.Label(top, text="Şifreni oluştur", bg=SURFACE_LOW, fg=ON_SURFACE,
                 font=f_headline_md()).pack()
        tk.Label(
            top,
            text="Notlarını güvenle saklamak için bir ana şifre belirle.",
            bg=SURFACE_LOW, fg=ON_SURFACE_VAR, font=f_body_sm(),
            wraplength=380, justify="center",
        ).pack(pady=(4, 0))

        # ── Form ──────────────────────────────────────────────────────────────
        form = tk.Frame(card, bg=SURFACE_LOW)
        form.pack(fill="x", padx=32, pady=20)

        # Password field
        tk.Label(form, text="Yeni şifre", bg=SURFACE_LOW, fg=ON_SURFACE,
                 font=f_label_md(), anchor="w").pack(fill="x")
        self._pwd = PasswordEntry(form, bg_entry=SURFACE_HIGH,
                                  on_change=self._validate)
        self._pwd.pack(fill="x", pady=(4, 0), ipady=2,
                       ipadx=0, side="top")

        # Strength meter
        meter_row = tk.Frame(form, bg=SURFACE_LOW)
        meter_row.pack(fill="x", pady=(6, 0))
        tk.Label(meter_row, text="Güç:", bg=SURFACE_LOW, fg=OUTLINE,
                 font=f_mono()).pack(side="left")
        self._meter = StrengthMeter(meter_row)
        self._meter.pack(side="left", padx=(8, 0))

        # Confirm field
        tk.Label(form, text="Şifreyi doğrula", bg=SURFACE_LOW, fg=ON_SURFACE,
                 font=f_label_md(), anchor="w").pack(fill="x", pady=(14, 0))
        self._conf = PasswordEntry(form, bg_entry=SURFACE_HIGH,
                                   on_change=self._validate)
        self._conf.pack(fill="x", pady=(4, 0), ipady=2, side="top")

        # Rules checklist
        rules_frame = tk.Frame(form, bg=SURFACE_CONT)
        rules_frame.pack(fill="x", pady=(14, 0))
        tk.Frame(rules_frame, bg=SURFACE_CONT).pack(padx=10, pady=6,
                                                      fill="x", expand=True)
        inner_rules = tk.Frame(rules_frame, bg=SURFACE_CONT)
        inner_rules.pack(fill="x", padx=10, pady=(0, 8))
        self._r_len   = self._rule(inner_rules, "En az 12 karakter")
        self._r_alnum = self._rule(inner_rules, "Harf ve rakam içermeli")
        self._r_match = self._rule(inner_rules, "Şifreler eşleşmeli")

        # Security notice
        notice = tk.Frame(form, bg=SURFACE_CONT)
        notice.pack(fill="x", pady=(14, 0))
        notice_inner = tk.Frame(notice, bg=SURFACE_CONT)
        notice_inner.pack(fill="x", padx=10, pady=8)
        tk.Label(notice_inner, text="🛡", bg=SURFACE_CONT,
                 font=("Segoe UI Emoji", 14)).pack(side="left", padx=(0, 8))
        txt_frame = tk.Frame(notice_inner, bg=SURFACE_CONT)
        txt_frame.pack(side="left", fill="x", expand=True)
        tk.Label(txt_frame, text="Sıfır Bilgi Mimarisi", bg=SURFACE_CONT,
                 fg=ON_SURFACE, font=f_label_md()).pack(anchor="w")
        tk.Label(
            txt_frame,
            text="Şifreniz yerel kasayı AES-256 ile şifreler. "
                 "Cihaz dışına gönderilmez; unutulursa sıfırlanamaz.",
            bg=SURFACE_CONT, fg=ON_SURFACE_VAR, font=f_body_sm(),
            wraplength=320, justify="left",
        ).pack(anchor="w")

        # Error label
        self._err_lbl = tk.Label(form, text="", bg=SURFACE_LOW, fg=ERROR,
                                  font=f_body_sm())
        self._err_lbl.pack(pady=(8, 0))

        # Submit button
        self._submit_btn = PrimaryBtn(form, "  🔒  Korumalı Kasayı Oluştur  ",
                                       command=self._on_submit)
        self._submit_btn.pack(fill="x", pady=(8, 0), ipady=3)

        # Bottom bar
        bottom = tk.Frame(card, bg=SURFACE_HIGH)
        bottom.pack(fill="x")
        tk.Label(bottom, text="256-Bit Yerel Kasa Şifreleme  •  v1.0",
                 bg=SURFACE_HIGH, fg=OUTLINE, font=f_mono()).pack(pady=6)

        # Keyboard binding
        self._pwd.entry.bind("<Return>", lambda _: self._conf.focus())
        self._conf.entry.bind("<Return>", lambda _: self._on_submit())
        self._bind_wheel_recursive(card, _on_wheel)
        self._pwd.focus()

    def _bind_wheel_recursive(self, widget: tk.Widget, handler):
        widget.bind("<MouseWheel>", handler)
        for child in widget.winfo_children():
            self._bind_wheel_recursive(child, handler)

    # ── Rule row helper ───────────────────────────────────────────────────────
    @staticmethod
    def _rule(parent: tk.Widget, text: str) -> tk.Label:
        row = tk.Frame(parent, bg=parent.cget("bg"))
        row.pack(fill="x", pady=1)
        icon = tk.Label(row, text="○", bg=parent.cget("bg"),
                        fg=OUTLINE, font=f_label_sm(), width=2)
        icon.pack(side="left")
        tk.Label(row, text=text, bg=parent.cget("bg"), fg=ON_SURFACE_VAR,
                 font=f_label_sm()).pack(side="left")
        return icon  # return icon label so we can update it

    # ── Live validation ───────────────────────────────────────────────────────
    def _validate(self):
        pwd  = self._pwd.get()
        conf = self._conf.get()
        ok_len   = len(pwd) >= 12
        ok_alnum = (any(c.isalpha() for c in pwd)
                    and any(c.isdigit() for c in pwd))
        ok_match = bool(pwd) and pwd == conf

        self._set_rule(self._r_len,   ok_len)
        self._set_rule(self._r_alnum, ok_alnum)
        self._set_rule(self._r_match, ok_match)

        score = sum([ok_len, ok_alnum,
                     len(pwd) >= 16 and not pwd.isalnum()])
        self._meter.set_level(score if pwd else 0)
        self._err_lbl.configure(text="")

    @staticmethod
    def _set_rule(icon_lbl: tk.Label, passed: bool):
        if passed:
            icon_lbl.configure(text="✓", fg=PRIMARY)
        else:
            icon_lbl.configure(text="○", fg=OUTLINE)

    # ── Submit ────────────────────────────────────────────────────────────────
    def _on_submit(self):
        pwd  = self._pwd.get()
        conf = self._conf.get()
        if len(pwd) < 12:
            self._err_lbl.configure(text="Şifre en az 12 karakter olmalıdır.")
            self._pwd.focus()
            return
        if pwd != conf:
            self._err_lbl.configure(text="Şifreler eşleşmiyor.")
            self._conf.focus()
            return

        self._submit_btn.configure(state="disabled", text="Oluşturuluyor…")
        self.after(50, lambda: self._do_create(pwd))

    def _do_create(self, pwd: str):
        from wontnote.crypto_core import create_vault
        from wontnote.vault_storage import write_vault
        try:
            vault_bytes, recovery_key = create_vault(pwd)
            write_vault(vault_bytes)
            self.app.vault_bytes    = vault_bytes
            self.app.master_key     = None  # will unlock on login
            self.app.recovery_key   = recovery_key
            # Show recovery key, then go to main
            self._show_recovery_key(recovery_key, vault_bytes, pwd)
        except Exception as exc:
            self._submit_btn.configure(state="normal",
                                        text="  🔒  Korumalı Kasayı Oluştur  ")
            self._err_lbl.configure(text=f"Hata: {exc}")

    def _show_recovery_key(self, key: str, vault_bytes: bytes, pwd: str):
        """Show recovery key in a dialog, then unlock and enter main window."""
        win = tk.Toplevel(self.winfo_toplevel())
        win.title("Kurtarma Anahtarı — Lütfen kaydedin!")
        win.resizable(True, True)
        win.minsize(440, 320)
        win.grab_set()
        win.configure(bg=SURFACE_LOW)

        tk.Label(win, text="⚠ Kurtarma Anahtarınızı Saklayın",
                 bg=SURFACE_LOW, fg=ERROR, font=f_headline_md()).pack(padx=24, pady=(20, 4))
        tk.Label(
            win,
            text="Bu anahtarı şifrenizi unutursanız kullanacaksınız.\n"
                 "Kaybolursa verileriniz kurtarılamaz.",
            bg=SURFACE_LOW, fg=ON_SURFACE_VAR, font=f_body_sm(),
            wraplength=380, justify="center",
        ).pack(padx=24)

        key_frame = tk.Frame(win, bg=SURFACE_CONT, pady=10)
        key_frame.pack(fill="x", padx=24, pady=12)
        key_entry = tk.Entry(key_frame, font=("Consolas", 11, "bold"),
                              bg=SURFACE_CONT, fg=ON_SURFACE, relief="flat",
                              justify="center", state="readonly")
        key_entry.configure(readonlybackground=SURFACE_CONT)
        key_entry.pack(fill="x", padx=10)
        key_entry.configure(state="normal")
        key_entry.insert(0, key)
        key_entry.configure(state="readonly")

        def copy_key():
            win.clipboard_clear()
            win.clipboard_append(key)
            copy_btn.configure(text="✓ Kopyalandı!")
        copy_btn = tk.Button(win, text="📋 Kopyala", command=copy_key,
                              bg=SURFACE_HIGH, fg=ON_SURFACE, relief="flat",
                              font=f_label_md(), cursor="hand2", padx=8, pady=3)
        copy_btn.pack(pady=(0, 4))

        def proceed():
            win.destroy()
            # Unlock immediately with the password we just used
            from wontnote.crypto_core import unlock_with_password
            from wontnote.vault_storage import read_vault
            vb = read_vault()
            mk, notes = unlock_with_password(vb, pwd)
            self.app.vault_bytes  = vb
            self.app.master_key   = mk
            self.app.notes        = notes
            self.app.show_main()

        tk.Button(win, text="  Anladım, Devam Et  ", command=proceed,
                   bg=PRIMARY, fg=ON_PRIMARY, relief="flat",
                   font=f_label_md(), cursor="hand2",
                   padx=12, pady=6).pack(pady=(4, 20))
