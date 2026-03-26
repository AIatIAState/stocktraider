// Get weekly movers (top 3 gainers and bottom 3 laggards) based on daily close prices.

import {
  Accordion,
  AccordionSummary,
  Alert,
  Box,
  Card,
  CardContent,
  Container,
  FormControlLabel,
  Paper,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchWeeklyMovers, type WeeklyMover } from "../services/api";
import { GradientCircularProgress } from "./GradientCircularProgress";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import StatCard from "./charts/StatCard";
import { formatSymbol } from "../utils/formatSymbol";

const DEFAULT_MIN_VOLUME = 2_000_000;

function formatPct(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatPrice(value: number) {
  return value.toFixed(2);
}

function MoverCell(props: { mover?: WeeklyMover; tone: "success" | "error" }) {
  const { mover, tone } = props;
  if (!mover) {
    return (
      <Typography variant="body2" color="text.secondary">
        No data
      </Typography>
    );
  }
  const trend =
    mover.pct_change > 0 ? "up" : mover.pct_change < 0 ? "down" : "neutral";
  const series = mover.series && mover.series.length > 1 ? mover.series : null;
  return (
    <Stack spacing={1}>
      <Typography variant="subtitle1">{formatSymbol(mover.symbol)}</Typography>
      {series ? (
        <StatCard
          title=""
          value={formatPct(mover.pct_change)}
          interval={`${formatPrice(mover.first_close)} to ${formatPrice(mover.last_close)}`}
          trend={trend}
          data={series}
        />
      ) : (
        <>
          <Typography
            variant="subtitle2"
            color={tone === "success" ? "success.main" : "error.main"}
          >
            {formatPct(mover.pct_change)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {formatPrice(mover.first_close)} to {formatPrice(mover.last_close)}
          </Typography>
        </>
      )}
    </Stack>
  );
}

export default function WeeklyMovers() {
  const [topMovers, setTopMovers] = useState<WeeklyMover[]>([]);
  const [bottomMovers, setBottomMovers] = useState<WeeklyMover[]>([]);
  const [range, setRange] = useState<{ start: string; end: string } | null>(
    null,
  );
  const [topError, setTopError] = useState<string | null>(null);
  const [bottomError, setBottomError] = useState<string | null>(null);
  const [isTopLoading, setIsTopLoading] = useState(true);
  const [isBottomLoading, setIsBottomLoading] = useState(true);
  const [volumeFilter, setVolumeFilter] = useState(true);

  const loadMovers = useCallback((useVolumeFilter: boolean) => {
    const minVolume = useVolumeFilter ? DEFAULT_MIN_VOLUME : undefined;
    let active = true;
    setIsTopLoading(true);
    setIsBottomLoading(true);
    setTopError(null);
    setBottomError(null);

    fetchWeeklyMovers("top", minVolume)
      .then((response) => {
        if (!active) return;
        setTopMovers(response.movers);
        setRange({ start: response.start, end: response.end });
      })
      .catch((err) => {
        if (!active) return;
        const raw =
          err instanceof Error ? err.message : "Failed to load top movers.";
        const message =
          raw.includes("<html") || raw.includes("Gateway Time-out")
            ? "Top movers request timed out. Try again in a moment."
            : raw;
        setTopError(message);
      })
      .finally(() => {
        if (!active) return;
        setIsTopLoading(false);
      });

    fetchWeeklyMovers("bottom", minVolume)
      .then((response) => {
        if (!active) return;
        setBottomMovers(response.movers);
        setRange(
          (current) => current ?? { start: response.start, end: response.end },
        );
      })
      .catch((err) => {
        if (!active) return;
        const raw =
          err instanceof Error ? err.message : "Failed to load bottom movers.";
        const message =
          raw.includes("<html") || raw.includes("Gateway Time-out")
            ? "Bottom movers request timed out. Try again in a moment."
            : raw;
        setBottomError(message);
      })
      .finally(() => {
        if (!active) return;
        setIsBottomLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    return loadMovers(volumeFilter);
  }, [volumeFilter, loadMovers]);

  const latestDates = useMemo(() => {
    if (!range) {
      return "Error in fetching dates.";
    }
    return `${range.start} -> ${range.end}`;
  }, [range]);

  const maxRows = Math.max(topMovers.length, bottomMovers.length);

  const volumeToggle = (
    <Tooltip title="Filter out small companies (< 2M avg daily volume)">
      <FormControlLabel
        control={
          <Switch
            checked={volumeFilter}
            onChange={(_, checked) => setVolumeFilter(checked)}
            size="small"
          />
        }
        label={
          <Typography variant="caption" color="text.secondary">
            Filter out small companies
          </Typography>
        }
        sx={{ ml: 1 }}
        onClick={(e) => e.stopPropagation()}
      />
    </Tooltip>
  );

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>
      {isTopLoading || isBottomLoading ? (
        <Card>
          <CardContent>
            <Stack spacing={1.5}>
              <Typography variant="h5">Weekly Movers</Typography>
              <Stack direction="row" spacing={2} alignItems="center">
                <Typography variant="body2" color="text.secondary">
                  Loading weekly movers...
                </Typography>
                <GradientCircularProgress />
              </Stack>
            </Stack>
          </CardContent>
        </Card>
      ) : topError || bottomError ? (
        <Card>
          <CardContent>
            <Stack spacing={1.5}>
              <Stack direction="row" alignItems="center" spacing={2}>
                <Typography variant="h5">Weekly Movers</Typography>
                {volumeToggle}
              </Stack>
              {topError ? <Alert severity="error">{topError}</Alert> : null}
              {bottomError ? (
                <Alert severity="error">{bottomError}</Alert>
              ) : null}
            </Stack>
          </CardContent>
        </Card>
      ) : (
        <Accordion style={{ padding: "16px" }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Stack direction="row" alignItems="center" spacing={2}>
              <Typography variant="h5">Weekly Movers</Typography>
              <Typography variant="h6">
                Top and bottom performers from daily close prices.
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Data from: {latestDates}
              </Typography>
              {volumeToggle}
            </Stack>
          </AccordionSummary>
          <TableContainer component={Paper}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <Box
                    sx={{
                      display: "grid",
                      gridTemplateColumns: "2fr 2fr",
                      gap: 2,
                    }}
                    style={{ paddingTop: "16px" }}
                    alignItems="end"
                  >
                    <TableCell>
                      <Typography variant="h6">Top 3 Gainers</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="h6">Bottom 3 Losers</Typography>
                    </TableCell>
                  </Box>
                </TableRow>
              </TableHead>
              <TableBody>
                {Array.from({ length: Math.max(maxRows, 3) }).map(
                  (_, index) => (
                    <TableRow key={`movers-${index}`}>
                      <Box
                        sx={{
                          display: "grid",
                          gridTemplateColumns: "2fr 2fr",
                          gap: 2,
                        }}
                        style={{ paddingTop: "12px", paddingBottom: "12px" }}
                        alignItems="center"
                      >
                        <TableCell>
                          <MoverCell mover={topMovers[index]} tone="success" />
                        </TableCell>
                        <TableCell>
                          <MoverCell mover={bottomMovers[index]} tone="error" />
                        </TableCell>
                      </Box>
                    </TableRow>
                  ),
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Accordion>
      )}
    </Container>
  );
}
