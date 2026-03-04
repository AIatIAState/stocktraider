import { Box, Container, Divider, Stack, Typography } from '@mui/material'
import ShowChartRoundedIcon from '@mui/icons-material/ShowChartRounded'
import { GradientText } from '../themes/styles'

export default function Footer() {
  return (
    <Box component="footer">
      <Divider />
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          spacing={2}
          justifyContent="space-between"
          alignItems={{ xs: 'flex-start', md: 'center' }}
        >
          {/* Brand */}
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Box
              sx={{
                width: 28,
                height: 28,
                borderRadius: '8px',
                background: 'linear-gradient(135deg, #1B224B 0%, #3a4a8a 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <ShowChartRoundedIcon sx={{ color: '#00D3AB', fontSize: '1rem' }} />
            </Box>
            <Box>
              <Typography variant="body2" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                StockTr<GradientText>AI</GradientText>der
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Built for practical learning.
              </Typography>
            </Box>
          </Stack>

          <Typography variant="body2" color="text.secondary">
            © 2026 Gru-Man. Made to learn, not to paywall.
          </Typography>
        </Stack>
      </Container>
    </Box>
  )
}
