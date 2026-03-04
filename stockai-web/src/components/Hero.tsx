import { Box, Button, Chip, Container, Stack, Typography } from '@mui/material'
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded'
import { Link as RouterLink } from 'react-router-dom'
import { GradientText } from '../themes/styles'

const stats = [
  { value: '50+', label: 'Years of data' },
  { value: '10k+', label: 'Stocks tracked' },
  { value: 'Free', label: 'Always open' },
]

export default function Hero() {
  return (
    <Box
      sx={{
        position: 'relative',
        overflow: 'hidden',
        background: 'linear-gradient(135deg, #0b0f23 0%, #1B224B 55%, #243066 100%)',
        py: { xs: 10, md: 14 },
        '&::before': {
          content: '""',
          position: 'absolute',
          inset: 0,
          backgroundImage:
            'radial-gradient(ellipse 70% 40% at 50% 0%, rgba(121, 134, 203, 0.25) 0%, transparent 100%)',
          pointerEvents: 'none',
        },
      }}
    >
      <Container maxWidth="md" sx={{ position: 'relative' }}>
        <Stack spacing={3.5} alignItems="center" textAlign="center">
          <Chip
            icon={
              <AutoAwesomeRoundedIcon
                sx={{ fontSize: '0.9rem !important', color: '#00D3AB !important' }}
              />
            }
            label="AI-Powered Market Intelligence"
            size="small"
            sx={{
              background: 'rgba(0, 211, 171, 0.1)',
              border: '1px solid rgba(0, 211, 171, 0.3)',
              color: '#00D3AB',
              fontWeight: 600,
              letterSpacing: '0.02em',
            }}
          />

          <Typography
            variant="h2"
            sx={{
              color: 'white',
              fontWeight: 800,
              lineHeight: 1.15,
              letterSpacing: '-0.03em',
            }}
          >
            Learn markets from{' '}
            <GradientText>past, present, and future.</GradientText>
          </Typography>

          <Typography
            variant="h6"
            sx={{ color: 'rgba(255,255,255,0.6)', fontWeight: 400, lineHeight: 1.6, maxWidth: 560 }}
          >
            StockTr<GradientText sx={{ fontWeight: 700 }}>AI</GradientText>der is your friendly
            companion for exploring stock history, spotting patterns, and building confidence before
            you trade.
          </Typography>

          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <Button
              variant="contained"
              size="large"
              component={RouterLink}
              to="/data"
              sx={{
                bgcolor: '#00D3AB',
                color: '#0b0f23',
                fontWeight: 700,
                px: 3.5,
                '&:hover': { bgcolor: '#00b896' },
              }}
            >
              Explore data
            </Button>
            <Button
              variant="outlined"
              size="large"
              component={RouterLink}
              to="/dashboard"
              sx={{
                color: 'rgba(255,255,255,0.85)',
                borderColor: 'rgba(255,255,255,0.25)',
                '&:hover': {
                  borderColor: 'rgba(255,255,255,0.6)',
                  bgcolor: 'rgba(255,255,255,0.05)',
                },
              }}
            >
              Weekly Dashboard
            </Button>
          </Stack>

          {/* Stats row */}
          <Stack direction="row" spacing={6} sx={{ pt: 1 }}>
            {stats.map((stat) => (
              <Box key={stat.label}>
                <Typography variant="h5" sx={{ color: 'white', fontWeight: 700, lineHeight: 1.1 }}>
                  {stat.value}
                </Typography>
                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.45)' }}>
                  {stat.label}
                </Typography>
              </Box>
            ))}
          </Stack>
        </Stack>
      </Container>
    </Box>
  )
}
