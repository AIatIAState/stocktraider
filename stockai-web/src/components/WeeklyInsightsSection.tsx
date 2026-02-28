import { Container, Stack, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import {
  fetchWeeklyInsights,
  type WeeklyInsightsResponse,
} from "../services/api";
// import WeeklyMarketInsightsCard from "./WeeklyMarketInsightsCard";
import WeeklyWorldEventsCard from "./WeeklyWorldEventsCard";

export default function WeeklyInsightsSection() {
  const [data, setData] = useState<WeeklyInsightsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchWeeklyInsights()
      .then((response) => {
        if (!active) {
          return;
        }
        setData(response);
        setError(null);
      })
      .catch((err) => {
        if (!active) {
          return;
        }
        const message =
          err instanceof Error ? err.message : "Failed to load insights.";
        setError(message);
      })
      .finally(() => {
        if (!active) {
          return;
        }
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const modelLabel = data?.model
    ? `AI-generated summary (${data.model}).`
    : "AI summary unavailable.";
  const sourcesLabel =
    data?.sources && data.sources.length
      ? `Sources: ${data.sources.join(", ")}.`
      : "Sources unavailable.";

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>
      <Stack spacing={2}>
        <Typography variant="h4">Weekly Insights</Typography>
            <WeeklyWorldEventsCard
              start={data?.start}
              end={data?.end}
              impacts={data?.event_impacts ?? []}
              events={data?.events ?? []}
              eventsNote={data?.events_note ?? null}
              loading={loading}
              error={error}
            />
          <Typography variant="caption" color="text.secondary">
            {modelLabel} {sourcesLabel}
          </Typography>
      </Stack>
    </Container>
  );
}
