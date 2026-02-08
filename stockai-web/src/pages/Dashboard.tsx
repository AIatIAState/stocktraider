import AppAppBar from "../components/AppAppBar";
import AppTheme from "../themes/AppTheme";
import Footer from "../components/Footer";
import WeeklyMovers from "../components/WeeklyMovers";

export default function Dashboard(props: { disableCustomTheme?: boolean }) {
  return (
    <AppTheme {...props}>
      <AppAppBar />
      <WeeklyMovers />
      <Footer />
    </AppTheme>
  );
}
