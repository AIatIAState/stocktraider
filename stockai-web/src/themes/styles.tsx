import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import type { ReactNode } from 'react'

/** 135° indigo → teal gradient for inline word highlights in headings */
export const gradientTextSx = {
  background: 'linear-gradient(135deg, #7986CB 0%, #00D3AB 100%)',
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  backgroundClip: 'text',
} as const

/** 90° indigo → teal gradient for overline section labels */
export const gradientOverlineSx = {
  background: 'linear-gradient(90deg, #7986CB 0%, #00D3AB 100%)',
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  backgroundClip: 'text',
  fontWeight: 700,
  letterSpacing: '0.12em',
  display: 'block',
} as const

/** Inline span that applies the brand gradient to text. Accepts optional extra sx via spread. */
export function GradientText({ children, sx }: { children: ReactNode; sx?: object }) {
  return (
    <Box component="span" sx={{ ...gradientTextSx, ...sx }}>
      {children}
    </Box>
  )
}

/** Typography overline with brand gradient — use for section labels above headings. */
export function GradientOverline({ children }: { children: ReactNode }) {
  return (
    <Typography variant="overline" sx={gradientOverlineSx}>
      {children}
    </Typography>
  )
}
