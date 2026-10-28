"""
Tokens de design da aplicação (fonte única de verdade para CSS e Plotly).
Nenhuma dependência do Streamlit neste módulo.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class ColorPalette:
    """Paleta de cores para UI e visualizações."""

    primary: str = "#0F172A"  # Azul profundo / Slate 900
    primary_hover: str = "#1E293B"  # Slate 800
    secondary: str = "#2563EB"  # Azul Royal / Blue 600
    secondary_hover: str = "#1D4ED8"  # Blue 700
    background: str = "#F8FAFC"  # Cinza muito claro / Slate 50
    surface: str = "#FFFFFF"  # Branco puro
    surface_alt: str = "#F1F5F9"  # Slate 100
    text_primary: str = "#0F172A"  # Slate 900
    text_secondary: str = "#475569"  # Slate 600
    text_muted: str = "#94A3B8"  # Slate 400
    border: str = "#E2E8F0"  # Slate 200
    border_strong: str = "#CBD5E1"  # Slate 300
    positive: str = "#16A34A"  # Verde / Green 600
    positive_bg: str = "#DCFCE7"  # Green 100
    negative: str = "#DC2626"  # Vermelho / Red 600
    negative_bg: str = "#FEE2E2"  # Red 100
    warning: str = "#D97706"  # Âmbar / Amber 600
    warning_bg: str = "#FEF3C7"  # Amber 100
    info: str = "#0284C7"  # Sky 600
    info_bg: str = "#E0F2FE"  # Sky 100
    
    # Sequência categórica para gráficos Plotly
    categorical_sequence: List[str] = field(
        default_factory=lambda: [
            "#2563EB",  # Blue
            "#0D9488",  # Teal
            "#D97706",  # Amber
            "#7C3AED",  # Violet
            "#E11D48",  # Rose
            "#059669",  # Emerald
            "#EA580C",  # Orange
            "#4F46E5",  # Indigo
        ]
    )


@dataclass(frozen=True)
class Typography:
    """Pilha de fontes e tamanhos."""

    font_family: str = (
        "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    )
    font_code: str = "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace"
    size_xs: str = "0.75rem"   # 12px
    size_sm: str = "0.875rem"  # 14px
    size_md: str = "1rem"      # 16px
    size_lg: str = "1.125rem"  # 18px
    size_xl: str = "1.25rem"   # 20px
    size_2xl: str = "1.5rem"   # 24px
    size_3xl: str = "1.875rem" # 30px


@dataclass(frozen=True)
class Geometry:
    """Raios de borda e espaçamentos."""

    radius_sm: str = "4px"
    radius_md: str = "8px"
    radius_lg: str = "12px"
    radius_xl: str = "16px"
    radius_full: str = "9999px"
    
    space_xs: str = "0.25rem" # 4px
    space_sm: str = "0.5rem"  # 8px
    space_md: str = "1rem"    # 16px
    space_lg: str = "1.5rem"  # 24px
    space_xl: str = "2rem"    # 32px


@dataclass(frozen=True)
class Elevation:
    """Sombras suaves para cards e superfícies."""

    shadow_sm: str = "0 1px 2px 0 rgba(0, 0, 0, 0.05)"
    shadow_md: str = "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)"
    shadow_lg: str = "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)"


COLOR_TOKENS = ColorPalette()
TYPOGRAPHY_TOKENS = Typography()
GEOMETRY_TOKENS = Geometry()
ELEVATION_TOKENS = Elevation()


def generate_css_variables() -> str:
    """Gera bloco CSS :root com variáveis derivadas dos tokens."""
    return f"""
:root {{
  /* Paleta */
  --fx-color-primary: {COLOR_TOKENS.primary};
  --fx-color-primary-hover: {COLOR_TOKENS.primary_hover};
  --fx-color-secondary: {COLOR_TOKENS.secondary};
  --fx-color-secondary-hover: {COLOR_TOKENS.secondary_hover};
  --fx-color-background: {COLOR_TOKENS.background};
  --fx-color-surface: {COLOR_TOKENS.surface};
  --fx-color-surface-alt: {COLOR_TOKENS.surface_alt};
  --fx-color-text-primary: {COLOR_TOKENS.text_primary};
  --fx-color-text-secondary: {COLOR_TOKENS.text_secondary};
  --fx-color-text-muted: {COLOR_TOKENS.text_muted};
  --fx-color-border: {COLOR_TOKENS.border};
  --fx-color-border-strong: {COLOR_TOKENS.border_strong};
  --fx-color-positive: {COLOR_TOKENS.positive};
  --fx-color-positive-bg: {COLOR_TOKENS.positive_bg};
  --fx-color-negative: {COLOR_TOKENS.negative};
  --fx-color-negative-bg: {COLOR_TOKENS.negative_bg};
  --fx-color-warning: {COLOR_TOKENS.warning};
  --fx-color-warning-bg: {COLOR_TOKENS.warning_bg};
  --fx-color-info: {COLOR_TOKENS.info};
  --fx-color-info-bg: {COLOR_TOKENS.info_bg};

  /* Tipografia */
  --fx-font-family: {TYPOGRAPHY_TOKENS.font_family};
  --fx-font-code: {TYPOGRAPHY_TOKENS.font_code};
  --fx-font-size-xs: {TYPOGRAPHY_TOKENS.size_xs};
  --fx-font-size-sm: {TYPOGRAPHY_TOKENS.size_sm};
  --fx-font-size-md: {TYPOGRAPHY_TOKENS.size_md};
  --fx-font-size-lg: {TYPOGRAPHY_TOKENS.size_lg};
  --fx-font-size-xl: {TYPOGRAPHY_TOKENS.size_xl};
  --fx-font-size-2xl: {TYPOGRAPHY_TOKENS.size_2xl};
  --fx-font-size-3xl: {TYPOGRAPHY_TOKENS.size_3xl};

  /* Geometria */
  --fx-radius-sm: {GEOMETRY_TOKENS.radius_sm};
  --fx-radius-md: {GEOMETRY_TOKENS.radius_md};
  --fx-radius-lg: {GEOMETRY_TOKENS.radius_lg};
  --fx-radius-xl: {GEOMETRY_TOKENS.radius_xl};
  --fx-radius-full: {GEOMETRY_TOKENS.radius_full};
  --fx-space-xs: {GEOMETRY_TOKENS.space_xs};
  --fx-space-sm: {GEOMETRY_TOKENS.space_sm};
  --fx-space-md: {GEOMETRY_TOKENS.space_md};
  --fx-space-lg: {GEOMETRY_TOKENS.space_lg};
  --fx-space-xl: {GEOMETRY_TOKENS.space_xl};

  /* Elevacoes */
  --fx-shadow-sm: {ELEVATION_TOKENS.shadow_sm};
  --fx-shadow-md: {ELEVATION_TOKENS.shadow_md};
  --fx-shadow-lg: {ELEVATION_TOKENS.shadow_lg};
}}
""".strip()