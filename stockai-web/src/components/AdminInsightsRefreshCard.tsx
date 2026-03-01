import { Alert, Button, Card, CardContent, Stack, Typography } from "@mui/material";
import { useState } from "react";
import { refreshWeeklyInsights } from "../services/api";

export default function AdminInsightsRefreshCard() {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRefresh = async () => {
    setLoading(true);
    setMessage(null);
    setError(null);
    try {
      const response = await refreshWeeklyInsights();
      setMessage(
        response.note
          ? response.note
          : "Weekly insights refreshed successfully.",
      );
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to refresh insights.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h5">Weekly Insights</Typography>
          <Typography variant="body2" color="text.secondary">
            Requery OpenAI to regenerate market insights and event impacts.
          </Typography>
          {message ? <Alert severity="success">{message}</Alert> : null}
          {error ? <Alert severity="error">{error}</Alert> : null}
          <Button
            variant="contained"
            onClick={handleRefresh}
            disabled={loading}
          >
            {loading ? "Refreshing..." : "Refresh insights"}
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}
