"""
settings.py — WontNote Preferences dialog.
Modal Toplevel with left-nav + right content panel.
Mirrors the 'Tercihler ve Ayarlar' HTML design.
"""
import tkinter as tk
from datetime import datetime, timezone

from ..theme import (
    SURFACE_LOW, SURFACE_LOWEST, SURFACE_CONT, SURFACE_HIGH, SURFACE_HIGHEST,
    ON_SURFACE, ON_SURFACE_VAR, OUTLINE, OUTLINE_VAR,
    PRIMARY, PRIMARY_FIXED, ON_PRIMARY,
    ERROR, ERROR_CONT, ON_ERROR_CONT,
    f_headline_sm, f_body_md, f_body_sm, f_label_md, f_label_sm, f_mono,
)
from ..widgets import PasswordEntry, PrimaryBtn, SecondaryBtn, HSep, ScrollFrame


class SettingsDialog(tk.Toplevel):
    """
    Modal preferences window (900 × 620).
    Sections: Genel | Görünüm | Güvenlik (active) | Düzenleyici | Yedekleme
    """

    _SECTIONS = [
        ("⚙", "Genel",               "Dil, Sistem Başlangıcı"),
        ("🎨", "Görünüm & Tema",      "Açık, Koyu, Sistem"),
        ("🔐", "Güvenlik & Şifre",    "Kilit ve Şifreleme"),
        ("📝", "Not Düzenleyici",      "Yazı Tipi, Satır Aralığı"),
        ("💾", "Yedekleme & Dışa Aktar","JSON, MD, Şifreli Arşiv"),
    ]

    def __init__(self, parent: tk.Tk, app):
        super().__init__(parent)
        self.app = app
        self.title("WontNote — Tercihler ve Ayarlar")
        self.resizable(True, True)
        self.minsize(780, 520)
        self.configure(bg=SURFACE_LOW)
        self.grab_set()

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = min(920, int(sw * 0.9))
        h = min(640, int(sh * 0.9))
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._active_section = 2  # Güvenlik (0-indexed)
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self):
        # ── Title bar strip ───────────────────────────────────────────────────
        title_bar = tk.Frame(self, bg=SURFACE_HIGH, height=36)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        tk.Label(title_bar, text="🔒 WontNote — Tercihler ve Ayarlar",
                 bg=SURFACE_HIGH, fg=ON_SURFACE,
                 font=f_label_md()).pack(side="left", padx=12, pady=8)

        # ── Two-panel body ────────────────────────────────────────────────────
        body = tk.Frame(self, bg=SURFACE_LOWEST)
        body.pack(fill="both", expand=True)

        # Left nav
        self._nav = tk.Frame(body, bg=SURFACE_LOW, width=220)
        self._nav.pack(side="left", fill="y")
        self._nav.pack_propagate(False)
        self._build_nav()

        HSep(body).pack(side="left", fill="y")

        # Right content
        self._content_host = tk.Frame(body, bg=SURFACE_LOWEST)
        self._content_host.pack(side="left", fill="both", expand=True)
        self._show_section(self._active_section)

        # ── Bottom bar ────────────────────────────────────────────────────────
        HSep(self).pack(fill="x")
        bottom = tk.Frame(self, bg=SURFACE_HIGH, height=44)
        bottom.pack(fill="x")
        bottom.pack_propagate(False)
        tk.Label(bottom, text="✓ Yerel Kasa: Korumalı  •  Argon2id + AES-256-GCM",
                 bg=SURFACE_HIGH, fg=ON_SURFACE_VAR, font=f_label_sm()).pack(
            side="left", padx=12, pady=10)
        tk.Button(bottom, text="Kapat", command=self.destroy,
                   bg=SURFACE_HIGHEST, fg=ON_SURFACE, relief="flat",
                   font=f_label_md(), cursor="hand2", padx=10, pady=4).pack(
            side="right", padx=12, pady=6)

    def _build_nav(self):
        tk.Label(self._nav, text="YAPILANDIRMA", bg=SURFACE_LOW,
                 fg=OUTLINE, font=f_label_sm()).pack(anchor="w", padx=12, pady=(12, 6))

        self._nav_buttons = []
        for idx, (icon, name, desc) in enumerate(self._SECTIONS):
            btn_frame = tk.Frame(self._nav, bg=SURFACE_LOW, cursor="hand2")
            btn_frame.pack(fill="x", padx=4, pady=1)

            accent = tk.Frame(btn_frame, bg=PRIMARY, width=3)
            inner  = tk.Frame(btn_frame, bg=SURFACE_LOW)
            inner.pack(side="left", fill="both", expand=True, padx=4, pady=4)

            tk.Label(inner, text=icon, bg=SURFACE_LOW,
                     font=("Segoe UI Emoji", 13)).pack(side="left", padx=(2, 6))
            txt = tk.Frame(inner, bg=SURFACE_LOW)
            txt.pack(side="left", fill="x", expand=True)
            tk.Label(txt, text=name, bg=SURFACE_LOW, fg=ON_SURFACE,
                     font=f_label_md(), anchor="w").pack(fill="x")
            tk.Label(txt, text=desc, bg=SURFACE_LOW, fg=OUTLINE,
                     font=f_mono(), anchor="w").pack(fill="x")

            self._nav_buttons.append((accent, inner, btn_frame))

            # closure capture
            def _on_click(i=idx):
                self._show_section(i)
            for w in (btn_frame, inner):
                w.bind("<Button-1>", lambda _e, i=idx: _on_click(i))
                for c in w.winfo_children():
                    c.bind("<Button-1>", lambda _e, i=idx: _on_click(i))

        # About card at bottom of nav
        about = tk.Frame(self._nav, bg=SURFACE_CONT)
        about.pack(fill="x", padx=8, pady=(16, 8))
        about_inner = tk.Frame(about, bg=SURFACE_CONT)
        about_inner.pack(fill="x", padx=8, pady=8)
        tk.Label(about_inner, text="ℹ️ Hakkında", bg=SURFACE_CONT,
                 fg=ON_SURFACE, font=f_label_md()).pack(anchor="w")
        for line in ("Sürüm: v1.0", "Python 3.12 + Tkinter",
                     "Argon2id + AES-256-GCM"):
            tk.Label(about_inner, text=line, bg=SURFACE_CONT,
                     fg=OUTLINE, font=f_mono()).pack(anchor="w")

        self._highlight_nav(self._active_section)

    def _highlight_nav(self, idx: int):
        for i, (accent, inner, btn_frame) in enumerate(self._nav_buttons):
            if i == idx:
                accent.pack(side="left", fill="y", before=inner)
                for w in btn_frame.winfo_children():
                    try: w.configure(bg=SURFACE_HIGH)
                    except Exception: pass
                for w in inner.winfo_children():
                    try: w.configure(bg=SURFACE_HIGH)
                    except Exception: pass
                    for c in w.winfo_children():
                        try: c.configure(bg=SURFACE_HIGH)
                        except Exception: pass
                inner.configure(bg=SURFACE_HIGH)
                btn_frame.configure(bg=SURFACE_HIGH)
            else:
                accent.pack_forget()
                for w in btn_frame.winfo_children():
                    try: w.configure(bg=SURFACE_LOW)
                    except Exception: pass
                for w in inner.winfo_children():
                    try: w.configure(bg=SURFACE_LOW)
                    except Exception: pass
                    for c in w.winfo_children():
                        try: c.configure(bg=SURFACE_LOW)
                        except Exception: pass
                inner.configure(bg=SURFACE_LOW)
                btn_frame.configure(bg=SURFACE_LOW)

    def _show_section(self, idx: int):
        self._active_section = idx
        # Rebuild nav highlight
        if hasattr(self, "_nav_buttons"):
            self._highlight_nav(idx)
        # Clear content
        for w in self._content_host.winfo_children():
            w.destroy()
        # Show section
        builders = [
            self._section_general,
            self._section_appearance,
            self._section_security,
            self._section_editor,
            self._section_backup,
        ]
        if idx < len(builders):
            builders[idx]()

    # ── Section: Güvenlik ─────────────────────────────────────────────────────
    def _section_security(self):
        host = self._content_host
        sf = ScrollFrame(host, bg=SURFACE_LOWEST)
        sf.pack(fill="both", expand=True)
        p = sf.inner

        # Header
        hdr = tk.Frame(p, bg=SURFACE_LOWEST)
        hdr.pack(fill="x", padx=24, pady=(16, 0))
        ico_f = tk.Frame(hdr, bg=PRIMARY_FIXED, width=32, height=32)
        ico_f.pack_propagate(False)
        ico_f.pack(side="left")
        tk.Label(ico_f, text="🔐", bg=PRIMARY_FIXED,
                 font=("Segoe UI Emoji", 14)).place(relx=0.5, rely=0.5, anchor="center")
        txt_f = tk.Frame(hdr, bg=SURFACE_LOWEST)
        txt_f.pack(side="left", padx=(10, 0))
        tk.Label(txt_f, text="Güvenlik ve Kilit Ayarları",
                 bg=SURFACE_LOWEST, fg=ON_SURFACE, font=f_headline_sm()).pack(anchor="w")
        tk.Label(txt_f, text="Hassas notlar, yerel veritabanı koruması ve oturum kilitleri",
                 bg=SURFACE_LOWEST, fg=OUTLINE, font=f_body_sm()).pack(anchor="w")
        tk.Label(hdr, text="Argon2id + AES-256-GCM", bg=SURFACE_HIGH,
                 fg=PRIMARY, font=f_mono(), padx=6, pady=2).pack(side="right")

        HSep(p).pack(fill="x", pady=(12, 0))

        # ── Card 1: Change password ───────────────────────────────────────────
        card1 = self._card(p, "🔑 Ana Şifreyi Değiştir")

        tk.Label(card1, text="Mevcut şifre", bg=SURFACE_LOWEST,
                 fg=ON_SURFACE_VAR, font=f_label_sm()).pack(anchor="w", pady=(8, 2))
        self._cur_pwd = PasswordEntry(card1, bg_entry=SURFACE_HIGH)
        self._cur_pwd.pack(fill="x", ipady=2)

        tk.Label(card1, text="Yeni şifre", bg=SURFACE_LOWEST,
                 fg=ON_SURFACE_VAR, font=f_label_sm()).pack(anchor="w", pady=(8, 2))
        self._new_pwd = PasswordEntry(card1, bg_entry=SURFACE_HIGH,
                                       on_change=self._check_pwd_strength)
        self._new_pwd.pack(fill="x", ipady=2)

        # Strength
        sm_row = tk.Frame(card1, bg=SURFACE_LOWEST)
        sm_row.pack(fill="x", pady=(4, 0))
        tk.Label(sm_row, text="Güç:", bg=SURFACE_LOWEST, fg=OUTLINE,
                 font=f_mono()).pack(side="left")
        from ..widgets import StrengthMeter
        self._strength = StrengthMeter(sm_row)
        self._strength.pack(side="left", padx=6)

        tk.Label(card1, text="Yeni şifreyi doğrula", bg=SURFACE_LOWEST,
                 fg=ON_SURFACE_VAR, font=f_label_sm()).pack(anchor="w", pady=(8, 2))
        self._conf_pwd = PasswordEntry(card1, bg_entry=SURFACE_HIGH)
        self._conf_pwd.pack(fill="x", ipady=2)

        self._pwd_err = tk.Label(card1, text="", bg=SURFACE_LOWEST, fg=ERROR,
                                  font=f_body_sm())
        self._pwd_err.pack(anchor="w", pady=(4, 0))
        self._pwd_ok  = tk.Label(card1, text="", bg=SURFACE_LOWEST,
                                  fg="#047857", font=f_body_sm())
        self._pwd_ok.pack(anchor="w")

        btn_row = tk.Frame(card1, bg=SURFACE_LOWEST)
        btn_row.pack(fill="x", pady=(10, 0))
        SecondaryBtn(btn_row, "Vazgeç",
                      command=lambda: [w.clear() for w in
                                       (self._cur_pwd, self._new_pwd, self._conf_pwd)]
                      ).pack(side="left")
        PrimaryBtn(btn_row, "Şifreyi Güncelle",
                    command=self._change_password).pack(side="right")

        # ── Card 2: Auto-lock ─────────────────────────────────────────────────
        card2 = self._card(p, "⏱ Otomatik Kilitleme")

        row1 = tk.Frame(card2, bg=SURFACE_LOWEST)
        row1.pack(fill="x", pady=(8, 0))
        tk.Label(row1, text="Hareketsizlik zaman aşımı",
                 bg=SURFACE_LOWEST, fg=ON_SURFACE, font=f_label_md()).pack(side="left")
        self._timeout_var = tk.StringVar(value="5 dakika")
        opt = tk.OptionMenu(row1, self._timeout_var,
                             "1 dakika", "5 dakika", "15 dakika", "Asla")
        opt.configure(bg=SURFACE_HIGH, fg=ON_SURFACE, relief="flat",
                       font=f_body_md(), highlightthickness=0)
        opt["menu"].configure(bg=SURFACE_HIGH, fg=ON_SURFACE)
        opt.pack(side="right")

        self._min_chk = tk.BooleanVar(value=True)
        self._hide_chk = tk.BooleanVar(value=True)
        for var, text, desc in [
            (self._min_chk,  "Simge durumuna küçültüldüğünde kilitle",
             "Görev çubuğuna indiği an oturumu koru"),
            (self._hide_chk, "Kilit ekranında başlıkları gizle",
             "Kilit ekranında not listesi bulanıklaştırılır"),
        ]:
            chk_row = tk.Frame(card2, bg=SURFACE_LOWEST)
            chk_row.pack(fill="x", pady=(6, 0))
            tk.Checkbutton(chk_row, variable=var, bg=SURFACE_LOWEST,
                            activebackground=SURFACE_LOWEST,
                            fg=ON_SURFACE, selectcolor=PRIMARY_FIXED,
                            font=f_label_md()).pack(side="left")
            tk.Label(chk_row, text=text, bg=SURFACE_LOWEST,
                     fg=ON_SURFACE, font=f_label_md()).pack(side="left")
            tk.Label(chk_row, text=desc, bg=SURFACE_LOWEST,
                     fg=OUTLINE, font=f_label_sm()).pack(side="left", padx=(8, 0))

        # ── Card 3: Recovery key ──────────────────────────────────────────────
        card3 = self._card(p, "🗝 Kurtarma Anahtarı ve Sıfırlama")

        # Warning
        warn = tk.Frame(card3, bg=ERROR_CONT)
        warn.pack(fill="x", pady=(8, 0))
        warn_inner = tk.Frame(warn, bg=ERROR_CONT)
        warn_inner.pack(fill="x", padx=10, pady=8)
        tk.Label(warn_inner, text="⚠", bg=ERROR_CONT, fg=ERROR,
                 font=("Segoe UI Emoji", 14)).pack(side="left", padx=(0, 8))
        txt_f2 = tk.Frame(warn_inner, bg=ERROR_CONT)
        txt_f2.pack(side="left")
        tk.Label(txt_f2, text="Kritik Güvenlik Uyarısı",
                 bg=ERROR_CONT, fg=ERROR, font=f_label_md()).pack(anchor="w")
        tk.Label(
            txt_f2,
            text="Parola ve kurtarma anahtarı kaybolursa, "
                 "yerel kasa geri döndürülemez biçimde kilitli kalır.",
            bg=ERROR_CONT, fg=ON_ERROR_CONT, font=f_body_sm(),
            wraplength=460, justify="left",
        ).pack(anchor="w")

        self._rk_err = tk.Label(card3, text="", bg=SURFACE_LOWEST, fg=ERROR,
                                 font=f_body_sm())
        self._rk_err.pack(anchor="w", pady=(6, 0))
        self._rk_ok  = tk.Label(card3, text="", bg=SURFACE_LOWEST,
                                 fg="#047857", font=f_body_sm())
        self._rk_ok.pack(anchor="w")

        btn_row2 = tk.Frame(card3, bg=SURFACE_LOWEST)
        btn_row2.pack(fill="x", pady=(10, 0))
        SecondaryBtn(btn_row2, "🔄 Yeni Anahtar Üret",
                      command=self._regen_recovery_key).pack(side="left")

    # ── Section: Genel ────────────────────────────────────────────────────────
    def _section_general(self):
        p = self._content_host
        tk.Label(p, text="Genel Ayarlar", bg=SURFACE_LOWEST,
                 fg=ON_SURFACE, font=f_headline_sm()).pack(padx=24, pady=24)
        tk.Label(p, text="Bu bölüm ilerleyen sürümlerde doldurulacaktır.",
                 bg=SURFACE_LOWEST, fg=OUTLINE, font=f_body_md()).pack(padx=24)

    def _section_appearance(self):
        p = self._content_host
        tk.Label(p, text="Görünüm & Tema", bg=SURFACE_LOWEST,
                 fg=ON_SURFACE, font=f_headline_sm()).pack(padx=24, pady=24)
        tk.Label(p, text="Bu bölüm ilerleyen sürümlerde doldurulacaktır.",
                 bg=SURFACE_LOWEST, fg=OUTLINE, font=f_body_md()).pack(padx=24)

    def _section_editor(self):
        p = self._content_host
        tk.Label(p, text="Not Düzenleyici", bg=SURFACE_LOWEST,
                 fg=ON_SURFACE, font=f_headline_sm()).pack(padx=24, pady=24)
        tk.Label(p, text="Bu bölüm ilerleyen sürümlerde doldurulacaktır.",
                 bg=SURFACE_LOWEST, fg=OUTLINE, font=f_body_md()).pack(padx=24)

    def _section_backup(self):
        p = self._content_host
        tk.Label(p, text="Yedekleme & Dışa Aktar", bg=SURFACE_LOWEST,
                 fg=ON_SURFACE, font=f_headline_sm()).pack(padx=24, pady=24)
        tk.Label(p, text="Bu bölüm ilerleyen sürümlerde doldurulacaktır.",
                 bg=SURFACE_LOWEST, fg=OUTLINE, font=f_body_md()).pack(padx=24)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _card(self, parent: tk.Widget, title: str) -> tk.Frame:
        outer = tk.Frame(parent, bg=SURFACE_LOWEST, highlightthickness=1,
                          highlightbackground=OUTLINE_VAR)
        outer.pack(fill="x", padx=24, pady=(12, 0))
        tk.Label(outer, text=title, bg=SURFACE_LOWEST, fg=ON_SURFACE,
                 font=f_headline_sm()).pack(anchor="w", padx=14, pady=(10, 0))
        inner = tk.Frame(outer, bg=SURFACE_LOWEST)
        inner.pack(fill="x", padx=14, pady=(0, 14))
        return inner

    def _check_pwd_strength(self):
        pwd = self._new_pwd.get()
        score = sum([
            len(pwd) >= 12,
            any(c.isalpha() for c in pwd) and any(c.isdigit() for c in pwd),
            len(pwd) >= 16 and not pwd.isalnum(),
        ]) if pwd else 0
        if hasattr(self, "_strength"):
            self._strength.set_level(score)

    def _change_password(self):
        cur  = self._cur_pwd.get()
        new  = self._new_pwd.get()
        conf = self._conf_pwd.get()
        self._pwd_err.configure(text="")
        self._pwd_ok.configure(text="")

        if not cur or not new:
            self._pwd_err.configure(text="Tüm alanları doldurun.")
            return
        if len(new) < 12:
            self._pwd_err.configure(text="Yeni şifre en az 12 karakter olmalı.")
            return
        if new != conf:
            self._pwd_err.configure(text="Yeni şifreler eşleşmiyor.")
            return

        from wontnote.crypto_core import unlock_with_password, change_password, VaultError, _secure_zero
        from wontnote.vault_storage import write_vault
        try:
            temp_mk, _ = unlock_with_password(self.app.vault_bytes, cur)
        except VaultError:
            self._pwd_err.configure(text="Mevcut şifre hatalı.")
            return

        try:
            new_vault = change_password(
                self.app.vault_bytes, temp_mk, new
            )
            write_vault(new_vault, keep_backup=False)
            self.app.vault_bytes = new_vault
            self._cur_pwd.clear()
            self._new_pwd.clear()
            self._conf_pwd.clear()
            self._pwd_ok.configure(text="✓ Şifre başarıyla güncellendi.")
        except VaultError:
            self._pwd_err.configure(text="Could not open vault.")
        except Exception as exc:
            self._pwd_err.configure(text=f"Hata: {exc}")
        finally:
            _secure_zero(temp_mk)

    def _regen_recovery_key(self):
        self._rk_err.configure(text="")
        self._rk_ok.configure(text="")
        from wontnote.crypto_core import regenerate_recovery_key, VaultError
        from wontnote.vault_storage import write_vault
        try:
            new_vault, new_key = regenerate_recovery_key(
                self.app.vault_bytes, self.app.master_key
            )
            write_vault(new_vault, keep_backup=False)
            self.app.vault_bytes = new_vault
            # Show new key
            win = tk.Toplevel(self)
            win.title("Yeni Kurtarma Anahtarı")
            win.resizable(True, True)
            win.minsize(440, 260)
            win.grab_set()
            win.configure(bg=SURFACE_LOW)
            tk.Label(win, text="🗝 Yeni Kurtarma Anahtarınız",
                     bg=SURFACE_LOW, fg=ON_SURFACE,
                     font=f_headline_sm()).pack(padx=24, pady=(16, 4))
            tk.Label(win, text="Bu anahtarı güvenli bir yerde saklayın!",
                     bg=SURFACE_LOW, fg=ERROR,
                     font=f_body_sm()).pack(padx=24)
            e = tk.Entry(win, font=("Consolas", 11, "bold"), bg=SURFACE_HIGH,
                          fg=ON_SURFACE, relief="flat", justify="center",
                          state="readonly")
            e.configure(readonlybackground=SURFACE_HIGH)
            e.pack(fill="x", padx=24, pady=12, ipady=6)
            e.configure(state="normal")
            e.insert(0, new_key)
            e.configure(state="readonly")
            tk.Button(win, text="Kapat", command=win.destroy,
                       bg=PRIMARY, fg=ON_PRIMARY, relief="flat",
                       font=f_label_md(), cursor="hand2",
                       padx=12, pady=5).pack(pady=(0, 16))
            self._rk_ok.configure(text="✓ Yeni kurtarma anahtarı oluşturuldu.")
        except VaultError:
            self._rk_err.configure(text="Could not open vault.")
        except Exception as exc:
            self._rk_err.configure(text=f"Hata: {exc}")
