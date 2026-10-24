"""
theme.py — WontNote Design Tokens
Extracted 1-to-1 from the Google Stitch HTML designs (Material You / M3 palette).
"""

# ── Primary ──────────────────────────────────────────────────────────────────
PRIMARY            = "#493ee5"
PRIMARY_CONT       = "#635bff"
PRIMARY_FIXED      = "#e2dfff"
PRIMARY_FIXED_DIM  = "#c3c0ff"
ON_PRIMARY         = "#ffffff"
ON_PRIMARY_FIXED   = "#0f0069"

# ── Secondary ────────────────────────────────────────────────────────────────
SECONDARY          = "#5841d5"
SECONDARY_CONT     = "#715def"
SECONDARY_FIXED    = "#e5deff"
SECONDARY_FIXED_DIM= "#c7bfff"
ON_SECONDARY       = "#ffffff"

# ── Tertiary ─────────────────────────────────────────────────────────────────
TERTIARY           = "#5b5a6b"
TERTIARY_CONT      = "#747284"
TERTIARY_FIXED     = "#e4e0f5"
TERTIARY_FIXED_DIM = "#c7c4d8"

# ── Surface layers (lightest → darkest) ──────────────────────────────────────
SURFACE_LOWEST     = "#ffffff"
SURFACE_LOW        = "#f5f2fb"
SURFACE            = "#fbf8ff"
SURFACE_CONT       = "#efecf5"
SURFACE_HIGH       = "#eae7ef"
SURFACE_HIGHEST    = "#e4e1ea"
SURFACE_DIM        = "#dbd9e1"
SURFACE_VARIANT    = "#e4e1ea"
SURFACE_BRIGHT     = "#fbf8ff"
INVERSE_SURFACE    = "#303036"
INV_ON_SURFACE     = "#f2eff8"

# ── On-surface (text) ────────────────────────────────────────────────────────
ON_SURFACE         = "#1b1b21"
ON_SURFACE_VAR     = "#464555"

# ── Borders ───────────────────────────────────────────────────────────────────
OUTLINE            = "#777587"
OUTLINE_VAR        = "#c7c4d8"

# ── Error ─────────────────────────────────────────────────────────────────────
ERROR              = "#ba1a1a"
ERROR_CONT         = "#ffdad6"
ON_ERROR           = "#ffffff"
ON_ERROR_CONT      = "#93000a"

# ── Accent ────────────────────────────────────────────────────────────────────
GREEN_SAVED        = "#10b981"
GREEN_DARK         = "#047857"


# ── Font helpers ──────────────────────────────────────────────────────────────
def _pick(*candidates: str) -> str:
    """Return first available font family (requires a Tk root to exist first)."""
    try:
        import tkinter.font as tkf
        available = set(tkf.families())
        for name in candidates:
            if name in available:
                return name
    except Exception:
        pass
    return candidates[-1]


def ui_font(size: int = 10, weight: str = "normal") -> tuple:
    """Return (family, size, weight) tuple using Inter or best fallback."""
    fam = _pick("Inter", "Segoe UI", "SF Pro Text", "Ubuntu", "Arial")
    return (fam, size, weight)


def mono_font(size: int = 9) -> tuple:
    """Return monospace font tuple."""
    fam = _pick("Segoe UI", "Consolas", "SF Mono", "Menlo", "Courier New")
    return (fam, size, "normal")


# Convenience specs matching the HTML design scale
def f_headline_lg() -> tuple: return ui_font(16, "bold")
def f_headline_md() -> tuple: return ui_font(14, "bold")
def f_headline_sm() -> tuple: return ui_font(11, "bold")
def f_body_lg()    -> tuple: return ui_font(11, "normal")
def f_body_md()    -> tuple: return ui_font(10, "normal")
def f_body_sm()    -> tuple: return ui_font(9,  "normal")
def f_label_md()   -> tuple: return ui_font(9,  "normal")
def f_label_sm()   -> tuple: return ui_font(8,  "normal")
def f_mono()       -> tuple: return mono_font(9)
def f_title_win()  -> tuple: return ui_font(9,  "normal")
