import AppAppBar from "../components/AppAppBar";
import AppTheme from "../themes/AppTheme";
import Footer from "../components/Footer";
import WeeklyInsightsSection from "../components/WeeklyInsightsSection";
// import WeeklyMovers from "../components/WeeklyMovers";
import WeeklyPriceAlertsCard from "../components/WeeklyPriceAlertsCard";

export default function Dashboard(props: { disableCustomTheme?: boolean }) {
  return (
    <AppTheme {...props}>
      <AppAppBar />
      <WeeklyPriceAlertsCard />
      <WeeklyInsightsSection />
      {/* <WeeklyMovers /> */}
      <Footer />
    </AppTheme>
  );
}
