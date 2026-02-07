import { AppBar, Box, Button, Container, Stack, Toolbar, Typography } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'

export default function AppAppBar() {
  return (
    <AppBar position="static">
      <Container maxWidth="lg">
        <Toolbar disableGutters sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Box>
              <Typography variant="h6">StockTrAIder</Typography>
              <Typography variant="body2" color="text.secondary">
                Learn markets from past, present, and future.
              </Typography>
            </Box>
          </Stack>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
            <Button component={RouterLink} to="/" color="inherit">
              Home
            </Button>
            <Button component={RouterLink} to="/data" color="inherit">
              Data Explorer
            </Button>
            <Button component={RouterLink} to="/dashboard" color="inherit">
              Weekly Dashboard
            </Button>
          </Stack>
        </Toolbar>
      </Container>
    </AppBar>
  )
}
