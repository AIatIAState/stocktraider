import { Container } from "@mui/material";
import AppAppBar from "../components/AppAppBar";
import Footer from "../components/Footer";
import WeeklyInsightsSection from "../components/WeeklyInsightsSection";
import WeeklyPriceAlertsCard from "../components/WeeklyPriceAlertsCard";
import WeeklyRecommendationCard from "../components/WeeklyRecommendationCard";
import PageHeader from "../components/PageHeader";
import { GradientText } from "../themes/styles";
import {DailyTabularInsightsSection} from "../components/DailyTabularInsightsSection.tsx";

export default function Dashboard() {
  return (
    <>
      <AppAppBar />
      <PageHeader
        overline="Weekly Dashboard"
        title={<>Market <GradientText>Intelligence</GradientText></>}
        description="AI-powered insights on your core watchlist plus the week's biggest movers."
      />
      <WeeklyPriceAlertsCard />
      <Container maxWidth="lg" sx={{ py: { xs: 2, md: 3 } }}>
        <WeeklyRecommendationCard />
      </Container>
      <WeeklyInsightsSection />
        <DailyTabularInsightsSection />
      <Footer />
    </>
  );
}