import { AppBar, Box, Button, Container, Stack, Toolbar, Typography } from '@mui/material'
import ShowChartRoundedIcon from '@mui/icons-material/ShowChartRounded'
import { Link as RouterLink } from 'react-router-dom'
import ColorModeIconDropdown from '../themes/ColorModeIconDropdown'
import { GradientText } from '../themes/styles'

function BrandLogo() {
  return (
    <Box
      sx={{
        width: 36,
        height: 36,
        borderRadius: '10px',
        background: 'linear-gradient(135deg, #1B224B 0%, #3a4a8a 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        boxShadow: '0 2px 8px rgba(27, 34, 75, 0.5)',
      }}
    >
      <ShowChartRoundedIcon sx={{ color: '#00D3AB', fontSize: '1.2rem' }} />
    </Box>
  )
}

export default function AppAppBar() {
  return (
    <AppBar
      position="sticky"
      elevation={0}
      color="default"
      sx={{
        backdropFilter: 'blur(20px)',
        bgcolor: (theme) =>
          theme.palette.mode === 'dark'
            ? 'rgba(13, 17, 23, 0.85)'
            : 'rgba(248, 249, 250, 0.9)',
        borderBottom: '1px solid',
        borderColor: 'divider',
        backgroundImage: 'none',
        zIndex: (theme) => theme.zIndex.appBar,
      }}
    >
      <Container maxWidth="lg">
        <Toolbar
          disableGutters
          sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, py: 0.75 }}
        >
          <Stack direction="row" spacing={1.5} alignItems="center">
            <BrandLogo />
            <Box>
              <Typography
                variant="h6"
                sx={{ lineHeight: 1.2, fontWeight: 700, letterSpacing: '-0.02em' }}
              >
                StockTr<GradientText sx={{ fontWeight: 800 }}>AI</GradientText>der
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  background: 'linear-gradient(90deg, #7986CB 0%, #00D3AB 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                  fontWeight: 500,
                  letterSpacing: '0.01em',
                  display: 'block',
                  lineHeight: 1.3,
                }}
              >
                Learn markets from past, present, and future.
              </Typography>
            </Box>
          </Stack>

          <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap">
            <Button component={RouterLink} to="/" color="inherit" size="small">
              Home
            </Button>
            <Button component={RouterLink} to="/data" color="inherit" size="small">
              Search
            </Button>
            <Button component={RouterLink} to="/dashboard" color="inherit" size="small">
              Dashboard
            </Button>
            <ColorModeIconDropdown />
          </Stack>
        </Toolbar>
      </Container>
    </AppBar>
  )
}
