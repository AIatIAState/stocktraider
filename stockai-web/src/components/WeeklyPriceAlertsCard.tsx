import {
  Alert,
  Card,
  CardContent,
  Chip,
  Container,
  Grid,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TableContainer,
  Typography,
} from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import {
  fetchWeeklyAlerts,
  fetchWeeklyInsights,
  type WeeklyAlert,
  type WeeklyAlertFeatured,
} from "../services/api";
import { GradientCircularProgress } from "./GradientCircularProgress";
import StatCard from "./charts/StatCard";
import { formatSymbol } from "../utils/formatSymbol";
import WeeklyMarketInsightsCard from "./WeeklyMarketInsightsCard";
import { GradientOverline } from "../themes/styles";

function formatPct(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatPrice(value: number) {
  return value.toFixed(2);
}

function sourceLabel(source: WeeklyAlert["source"]) {
  if (source === "core") {
    return { label: "Core watchlist", color: "primary" as const };
  }
  if (source === "top") {
    return { label: "Top gainer", color: "success" as const };
  }
  return { label: "Top loser", color: "error" as const };
}

function alertTrend(value: number) {
  if (value > 0) {
    return "up" as const;
  }
  if (value < 0) {
    return "down" as const;
  }
  return "neutral" as const;
}

function featuredSeries(alert: WeeklyAlertFeatured) {
  if (alert.series && alert.series.length > 1) {
    return alert.series;
  }
  return [alert.first_close, alert.last_close].filter(
    (value) => Number.isFinite(value) && value >= 0,
  );
}

function FeaturedAlertCard({ alert }: { alert: WeeklyAlertFeatured }) {
  const data = featuredSeries(alert);
  const trend = alertTrend(alert.pct_change);
  const source = sourceLabel(alert.source);
  const showSourceChip = alert.source !== "core";
  return (
    <Card
      variant="outlined"
      sx={{
        height: "100%",
        borderRadius: 3,
        transition: 'border-color 0.2s',
        '&:hover': { borderColor: 'primary.light' },
      }}
    >
      <CardContent>
        <Stack spacing={1.5}>
          <Stack
            direction="row"
            alignItems="center"
            spacing={1}
            sx={{ justifyContent: "space-between" }}
          >
            <Typography variant="subtitle1">
              {formatSymbol(alert.symbol)}
            </Typography>
            {showSourceChip ? (
              <Chip label={source.label} color={source.color} size="small" />
            ) : null}
          </Stack>
          {data.length ? (
            <StatCard
              title=""
              value={formatPct(alert.pct_change)}
              interval={`${formatPrice(alert.first_close)} -> ${formatPrice(
                alert.last_close,
              )}`}
              trend={trend}
              data={data}
            />
          ) : (
            <Typography variant="body2" color="text.secondary">
              No chart data available.
            </Typography>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}

export default function WeeklyPriceAlertsCard() {
  const [alerts, setAlerts] = useState<WeeklyAlert[]>([]);
  const [featured, setFeatured] = useState<WeeklyAlertFeatured[]>([]);
  const [range, setRange] = useState<{ start: string; end: string } | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [insights, setInsights] = useState<string[]>([]);
  const [insightsNote, setInsightsNote] = useState<string | null>(null);
  const [insightsModel, setInsightsModel] = useState<string | null>(null);
  const [insightsError, setInsightsError] = useState<string | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchWeeklyAlerts()
      .then((response) => {
        if (!active) {
          return;
        }
        setAlerts(response.alerts);
        setFeatured(response.featured ?? []);
        setRange({ start: response.start, end: response.end });
        setError(null);
      })
      .catch((err) => {
        if (!active) {
          return;
        }
        const message =
          err instanceof Error ? err.message : "Failed to load price alerts.";
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

  useEffect(() => {
    let active = true;
    setInsightsLoading(true);
    fetchWeeklyInsights()
      .then((response) => {
        if (!active) {
          return;
        }
        setInsights(response.market_insights ?? []);
        setInsightsNote(response.note ?? null);
        setInsightsModel(response.model ?? null);
        setInsightsError(null);
      })
      .catch((err) => {
        if (!active) {
          return;
        }
        const message =
          err instanceof Error ? err.message : "Failed to load insights.";
        setInsightsError(message);
      })
      .finally(() => {
        if (!active) {
          return;
        }
        setInsightsLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const latestDates = useMemo(() => {
    if (!range) {
      return "Error fetching dates.";
    }
    return `${range.start} -> ${range.end}`;
  }, [range]);

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>
      <Card>
        <CardContent>
          <Stack spacing={2}>
            <Typography variant="h4">Market Overview</Typography>
            <Typography variant="body2" color="text.secondary">
              Core watchlist names plus the week's biggest gainers and losers. Data from {latestDates}.
            </Typography>

            {loading ? (
              <Stack direction="row" spacing={2} alignItems="center">
                <Typography variant="body2" color="text.secondary">
                  Loading alerts...
                </Typography>
                <GradientCircularProgress />
              </Stack>
            ) : error ? (
              <Alert severity="error">{error}</Alert>
            ) : alerts.length ? (
              <Stack spacing={3}>
                {featured.length ? (
                  <Stack spacing={1.5}>
                    <GradientOverline>Weekly Spotlight</GradientOverline>
                    <Grid container spacing={2}>
                      {featured.map((alert) => (
                        <Grid
                          key={`${alert.source}-${alert.symbol}`}
                          size={{ xs: 12, sm: 6, md: 4 }}
                        >
                          <FeaturedAlertCard alert={alert} />
                        </Grid>
                      ))}
                    </Grid>
                  </Stack>
                ) : null}
                <WeeklyMarketInsightsCard
                  insights={insights}
                  note={insightsNote}
                  model={insightsModel}
                  loading={insightsLoading}
                  error={insightsError}
                />
                <Stack spacing={1}>
                  <GradientOverline>All price alerts (20)</GradientOverline>
                  <TableContainer sx={{ maxHeight: 360 }}>
                    <Table size="small" stickyHeader>
                      <TableHead>
                        <TableRow>
                          <TableCell>Symbol</TableCell>
                          <TableCell>Weekly change</TableCell>
                          <TableCell>Start</TableCell>
                          <TableCell>End</TableCell>
                        <TableCell>Source</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {alerts.map((alert) => {
                          const source = sourceLabel(alert.source);
                          const tone =
                            alert.pct_change >= 0 ? "success.main" : "error.main";
                          return (
                            <TableRow key={`${alert.source}-${alert.symbol}`}>
                              <TableCell>
                                <Typography variant="subtitle2">
                                  {formatSymbol(alert.symbol)}
                                </Typography>
                              </TableCell>
                              <TableCell>
                                <Typography variant="body2" color={tone}>
                                  {formatPct(alert.pct_change)}
                                </Typography>
                              </TableCell>
                              <TableCell>
                                <Typography variant="body2">
                                  {formatPrice(alert.first_close)}
                                </Typography>
                              </TableCell>
                              <TableCell>
                                <Typography variant="body2">
                                  {formatPrice(alert.last_close)}
                                </Typography>
                              </TableCell>
                              <TableCell>
                                <Chip
                                  label={source.label}
                                  color={source.color}
                                  size="small"
                                />
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Stack>
              </Stack>
            ) : (
              <Alert severity="info">No alerts available.</Alert>
            )}
          </Stack>
        </CardContent>
      </Card>
    </Container>
  );
}
