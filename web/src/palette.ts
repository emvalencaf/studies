import { useTheme } from './theme'

// Mesmos hexes de src/studies/dashboard.py (LIGHT/DARK) — validados com validate_palette.js
// nos dois temas, para os dois painéis (este e o dashboard Streamlit) renderizarem a
// mesma paleta categórica para os mesmos dados.
export const LIGHT = {
  s1: '#2a78d6', s2: '#eb6834', s3: '#1baf7a', s4: '#eda100',
  muted: '#8d8c87', text: '#0b0b0b', grid: 'rgba(0,0,0,0.08)',
} as const

export const DARK = {
  s1: '#3987e5', s2: '#d95926', s3: '#199e70', s4: '#c98500',
  muted: '#8d8c87', text: '#f0efec', grid: 'rgba(255,255,255,0.10)',
} as const

export type Palette = Record<keyof typeof LIGHT, string>

export function usePalette(): Palette {
  const { theme } = useTheme()
  return theme === 'dark' ? DARK : LIGHT
}
