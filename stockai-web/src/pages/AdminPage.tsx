import { Box, Container } from "@mui/material";
import AppAppBar from "../components/AppAppBar";
import AdminIntroCard from "../components/AdminIntroCard";
import AdminJobStatusCard from "../components/AdminJobStatusCard";
import AdminSchedulerCard from "../components/AdminSchedulerCard";
import AdminUpdateCard from "../components/AdminUpdateCard";
import DBStatsCard from "../components/DB_Stats";
import Footer from "../components/Footer";
import AppTheme from "../themes/AppTheme";

export default function AdminPage(props: { disableCustomTheme?: boolean }) {
  return (
    <AppTheme {...props}>
      <AppAppBar />
      <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <AdminIntroCard />
          <AdminUpdateCard />
          <AdminSchedulerCard />
          <AdminJobStatusCard />
          <DBStatsCard />
        </Box>
      </Container>
      <Footer />
    </AppTheme>
  );
}
