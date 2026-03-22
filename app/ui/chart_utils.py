"""Shared matplotlib figure factory — Midnight Indigo dark theme."""

from matplotlib.figure import Figure
from matplotlib.axes import Axes

# Midnight Indigo palette — deep navy blacks, vibrant accents
BG      = "#0d0d1f"   # page / chart background
SURFACE = "#181830"   # card surface
TEXT    = "#e4e5f8"   # primary text
SUBTEXT = "#7a7ca0"   # muted labels / captions
BLUE    = "#7c9eff"   # primary accent — vivid indigo blue
GREEN   = "#50dba8"   # teal-green
PEACH   = "#ffa06a"   # warm orange
RED     = "#ff6b8a"   # soft neon red
MAUVE   = "#c07cff"   # vivid purple
TEAL    = "#42dce5"   # bright cyan
GRID    = "#1e1e38"   # subtle grid lines

ACCENT_CYCLE = [BLUE, GREEN, PEACH, RED, MAUVE, TEAL]


def make_figure(
    width_in: float = 7,
    height_in: float = 3.5,
    tight: bool = True,
) -> tuple[Figure, Axes]:
    """Return a styled (fig, ax) pair ready for embedding."""
    fig = Figure(figsize=(width_in, height_in), facecolor=BG, dpi=96)
    ax = fig.add_subplot(111, facecolor=BG)
    _style_axes(ax)
    if tight:
        fig.tight_layout(pad=2.0)
    return fig, ax


def make_figure_rows(
    n_rows: int,
    width_in: float = 7,
    height_in: float = 6,
) -> tuple[Figure, list[Axes]]:
    """Return a styled figure with n_rows vertically stacked axes."""
    fig = Figure(figsize=(width_in, height_in), facecolor=BG, dpi=96)
    axes = []
    for i in range(1, n_rows + 1):
        ax = fig.add_subplot(n_rows, 1, i, facecolor=BG)
        _style_axes(ax)
        axes.append(ax)
    fig.tight_layout(pad=2.5, h_pad=3.0)
    return fig, axes


def make_figure_grid(
    width_in: float = 12,
    height_in: float = 7,
) -> Figure:
    """Return a bare Figure for use with GridSpec (caller adds subplots)."""
    return Figure(figsize=(width_in, height_in), facecolor=BG, dpi=96)


def style_axes(ax: Axes) -> None:
    """Apply Midnight Indigo styling to an axes object."""
    ax.tick_params(colors=SUBTEXT, labelsize=7, which="both")
    ax.xaxis.label.set_color(SUBTEXT)
    ax.yaxis.label.set_color(SUBTEXT)
    ax.title.set_color(TEXT)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.grid(color=GRID, linewidth=0.4, linestyle="--", alpha=0.6)
    ax.set_axisbelow(True)


# Keep private alias for backwards compat
def _style_axes(ax: Axes) -> None:
    style_axes(ax)
