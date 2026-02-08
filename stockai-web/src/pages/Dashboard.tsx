import CssBaseline from '@mui/material/CssBaseline';
import Footer from '../components/Footer';
import AppAppBar from '../components/AppAppBar.tsx';

export default function Dashboard() {
  return (
      <>
      <CssBaseline enableColorScheme />
      <AppAppBar />
      {/* <Box sx={{ display: 'flex' }}>
        <Box
          component="main"
          sx={(theme) => ({
            flexGrow: 1,
            backgroundColor: theme.vars
              ? `rgba(${theme.vars.palette.background.defaultChannel} / 1)`
              : alpha(theme.palette.background.default, 1),
            overflow: 'auto',
          })}
        >
          <Stack
            spacing={2}
            sx={{
              alignItems: 'center',
              mx: 3,
              pb: 5,
              mt: { xs: 8, md: 0 },
            }}
          >
            <Header />
            <MainGrid />
          </Stack>
        </Box>
      </Box> */}
      <Footer />
    </>
  );
}
