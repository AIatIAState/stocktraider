import Box from '@mui/material/Box'
import Container from '@mui/material/Container'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import type { ReactNode } from 'react'
import { GradientOverline } from '../themes/styles'

interface PageHeaderProps {
  overline: string
  title: ReactNode
  description?: string
}

export default function PageHeader({ overline, title, description }: PageHeaderProps) {
  return (
    <Box
      sx={{
        position: 'relative',
        overflow: 'hidden',
        background: 'linear-gradient(135deg, #0b0f23 0%, #1B224B 55%, #243066 100%)',
        py: { xs: 5, md: 7 },
        '&::before': {
          content: '""',
          position: 'absolute',
          inset: 0,
          backgroundImage:
            'radial-gradient(ellipse 70% 60% at 50% 0%, rgba(121, 134, 203, 0.2) 0%, transparent 100%)',
          pointerEvents: 'none',
        },
      }}
    >
      <Container maxWidth="lg" sx={{ position: 'relative' }}>
        <Stack spacing={1.5}>
          <GradientOverline>{overline}</GradientOverline>
          <Typography
            variant="h3"
            sx={{ color: 'white', fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1.2 }}
          >
            {title}
          </Typography>
          {description && (
            <Typography
              variant="body1"
              sx={{ color: 'rgba(255,255,255,0.6)', maxWidth: 600, lineHeight: 1.7 }}
            >
              {description}
            </Typography>
          )}
        </Stack>
      </Container>
    </Box>
  )
}
