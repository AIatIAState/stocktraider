import AppAppBar from "../components/AppAppBar";
import Footer from "../components/Footer";
import WeeklyInsightsSection from "../components/WeeklyInsightsSection";
import WeeklyPriceAlertsCard from "../components/WeeklyPriceAlertsCard";
import PageHeader from "../components/PageHeader";
import { GradientText } from "../themes/styles";

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
      <WeeklyInsightsSection />
      <Footer />
    </>
  );
}