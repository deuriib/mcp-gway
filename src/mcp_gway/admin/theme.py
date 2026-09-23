"""DESIGN.md tokens — Spotify-inspired dark design system.

Single source of truth for the admin dashboard palette, shadows and fonts.
Components consume these via f-strings inside Tailwind arbitrary values;
shadow tokens use underscore form (Tailwind bracket syntax), `INSET_BORDER`
is raw CSS (real spaces) for inline `box-shadow`.
"""

from __future__ import annotations

# Primary brand — functional only: play, active states, primary CTAs
GREEN = "#1ed760"

# Surfaces (depth through shade variation)
BG = "#121212"  # deepest background, page base
SURFACE = "#181818"  # cards, containers
SURFACE_MID = "#1f1f1f"  # buttons, inputs, interactive
CARD = "#252525"  # elevated card, badge ground
LIGHT_SURFACE = "#eeeeee"  # rare light CTA

# Text
TEXT = "#ffffff"
TEXT_SILVER = "#b3b3b3"  # secondary, inactive nav
TEXT_SECONDARY = "#cbcbcb"

# Semantic
NEGATIVE = "#f3727f"  # errors
WARNING = "#ffa42b"  # warnings
ANNOUNCEMENT = "#539df5"  # info

# Borders and code surfaces
BORDER = "#4d4d4d"
BORDER_LIGHT = "#7c7c7c"
CODE_BG = "#0d0d0d"

# Derived interaction shades (hover/pressed siblings of the base tokens)
HOVER_SURFACE = "#2a2a2a"
HOVER_GREEN = "#3be477"
SCROLLBAR_THUMB = "#333333"

# Shadows — heavy by design; light shadows are invisible on dark.
# Underscore form for Tailwind `shadow-[...]` arbitrary values.
SHADOW_HEAVY = "rgba(0,0,0,0.5)_0px_8px_24px"
SHADOW_MEDIUM = "rgba(0,0,0,0.3)_0px_8px_8px"
# Raw CSS (spaces) for inline style box-shadow combos.
INSET_BORDER = "rgb(18,18,18) 0px 1px 0px, rgb(124,124,124) 0px 0px 0px 1px inset"

# Typography — compact app range (10px–24px), bold/regular binary
FONT_STACK = (
    "SpotifyMixUITitle, SpotifyMixUI, CircularSp-Arab, CircularSp-Hebr, "
    "CircularSp-Cyrl, CircularSp-Grek, CircularSp-Deva, 'Helvetica Neue', "
    "helvetica, arial, 'Hiragino Sans', 'Hiragino Kaku Gothic ProN', Meiryo, "
    "'MS Gothic', sans-serif"
)
