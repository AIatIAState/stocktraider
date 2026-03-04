import { Box, Card, CardContent, Container, Stack, Typography } from '@mui/material'
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded'
import TravelExploreRoundedIcon from '@mui/icons-material/TravelExploreRounded'
import SchoolRoundedIcon from '@mui/icons-material/SchoolRounded'
import { GradientOverline } from '../themes/styles'

const features = [
  {
    Icon: AutoAwesomeRoundedIcon,
    color: '#7986CB',
    bg: 'rgba(121, 134, 203, 0.12)',
    title: 'AI-Powered Insights',
    description:
      'Weekly AI summaries surface what is moving in the market and explain the context behind each move.',
  },
  {
    Icon: TravelExploreRoundedIcon,
    color: '#00D3AB',
    bg: 'rgba(0, 211, 171, 0.1)',
    title: 'Historical Search',
    description:
      'Explore 50+ years of price data filtered by symbol, timeframe, and date range to uncover real trends.',
  },
  {
    Icon: SchoolRoundedIcon,
    color: '#FF8C1A',
    bg: 'rgba(255, 140, 26, 0.1)',
    title: 'Practice Mode',
    description:
      'Simulate trades, review past positions, and build real intuition without risking any capital.',
  },
]

export default function Features() {
  return (
    <Container maxWidth="lg" sx={{ py: { xs: 6, md: 10 } }}>
      <Stack spacing={1} sx={{ mb: 6 }}>
        <GradientOverline>What you get</GradientOverline>
        <Typography variant="h3" sx={{ fontWeight: 700, letterSpacing: '-0.02em' }}>
          Built to learn from
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 480 }}>
          Three focused tools that give you real market literacy. No noise. No paywalls.
        </Typography>
      </Stack>

      <Box
        sx={{
          display: 'grid',
          gap: 3,
          gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' },
        }}
      >
        {features.map((feature) => (
          <Card
            key={feature.title}
            variant="outlined"
            sx={{
              p: 0.5,
              transition: 'box-shadow 0.2s, border-color 0.2s',
              '&:hover': {
                boxShadow: (theme) =>
                  theme.palette.mode === 'dark'
                    ? '0 0 0 1px rgba(121,134,203,0.3), 0 8px 24px rgba(0,0,0,0.4)'
                    : '0 8px 24px rgba(27,34,75,0.1)',
                borderColor: feature.color,
              },
            }}
          >
            <CardContent sx={{ p: 3 }}>
              <Box
                sx={{
                  width: 44,
                  height: 44,
                  borderRadius: 2,
                  bgcolor: feature.bg,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  mb: 2.5,
                }}
              >
                <feature.Icon sx={{ color: feature.color, fontSize: '1.4rem' }} />
              </Box>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1, letterSpacing: '-0.01em' }}>
                {feature.title}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.7 }}>
                {feature.description}
              </Typography>
            </CardContent>
          </Card>
        ))}
      </Box>
    </Container>
  )
}
