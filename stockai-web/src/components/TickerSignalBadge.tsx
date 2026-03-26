import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  Collapse,
  Link,
  List,
  ListItem,
  ListItemText,
  Popover,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import TrendingDownIcon from "@mui/icons-material/TrendingDown";
import { useEffect, useRef, useState } from "react";
import {
  fetchTickerSignal,
  type TickerSignalResponse,
} from "../services/api";
import { GradientCircularProgress } from "./GradientCircularProgress";
import { formatSymbol } from "../utils/formatSymbol";
import { GradientText } from "../themes/styles";

const CONFIDENCE_COLORS: Record<string, "success" | "warning" | "default"> = {
  high: "success",
  medium: "warning",
  low: "default",
};

export default function TickerSignalBadge({ symbol }: { symbol: string }) {
  const [data, setData] = useState<TickerSignalResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [showInsights, setShowInsights] = useState(false);
  const chipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!symbol) {
      setData(null);
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    fetchTickerSignal(symbol)
      .then((response) => {
        if (!active) return;
        setData(response);
      })
      .catch((err) => {
        if (!active) return;
        const message =
          err instanceof Error ? err.message : "Failed to load signal.";
        setError(message);
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [symbol]);

  if (!symbol) return null;

  return (
    <Card>
      <CardContent>
        <Stack spacing={1.5}>
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Typography variant="h4" component="p">
              {formatSymbol(symbol)}{" "}
              {!loading && !error && data ? (
                <Tooltip title={showInsights ? "Hide insights" : "View more"}>
                  <Link
                    component="span"
                    underline="hover"
                    onClick={() => setShowInsights((prev) => !prev)}
                    sx={{ cursor: "pointer" }}
                  >
                    <GradientText>Insights</GradientText>
                  </Link>
                </Tooltip>
              ) : (
                <GradientText>Insights</GradientText>
              )}
            </Typography>
            {!loading && !error && data ? (
              <Box
                ref={chipRef}
                onMouseEnter={() => setPopoverOpen(true)}
                onMouseLeave={() => setPopoverOpen(false)}
                sx={{ display: "inline-flex", flexShrink: 0 }}
              >
                <Chip
                  icon={data.signal === "BUY" ? <TrendingUpIcon /> : <TrendingDownIcon />}
                  label={data.signal}
                  color={data.signal === "BUY" ? "success" : "error"}
                  sx={{ cursor: "default", fontWeight: "bold" }}
                />
              </Box>
            ) : null}
          </Stack>

          {loading ? (
            <Stack direction="row" spacing={2} alignItems="center">
              <Typography variant="body2" color="text.secondary">
                Generating ticker analysis...
              </Typography>
              <GradientCircularProgress />
            </Stack>
          ) : error ? (
            <Alert severity="error">{error}</Alert>
          ) : data ? (
            <>
              <Collapse in={showInsights}>
                <Stack spacing={1}>
                  {data.reasoning && (
                    <Typography variant="body2" color="text.secondary">
                      {data.reasoning}
                    </Typography>
                  )}
                  {data.model ? (
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      align="right"
                    >
                      Generated with {data.model}.
                    </Typography>
                  ) : null}
                </Stack>
              </Collapse>

              {/* Hover popover on BUY/SELL chip — shows key factors + confidence */}
              <Popover
                open={popoverOpen}
                anchorEl={chipRef.current}
                onClose={() => setPopoverOpen(false)}
                anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
                transformOrigin={{ vertical: "top", horizontal: "right" }}
                disableRestoreFocus
                sx={{ pointerEvents: "none" }}
                slotProps={{
                  paper: {
                    sx: { p: 2, maxWidth: 340, pointerEvents: "auto" },
                    onMouseEnter: () => setPopoverOpen(true),
                    onMouseLeave: () => setPopoverOpen(false),
                  },
                }}
              >
                <Stack spacing={1}>
                  {data.confidence && (
                    <Chip
                      label={`${data.confidence} confidence`}
                      color={CONFIDENCE_COLORS[data.confidence] ?? "default"}
                      variant="outlined"
                      size="small"
                      sx={{ alignSelf: "flex-start" }}
                    />
                  )}
                  {data.key_factors.length > 0 && (
                    <>
                      <Typography variant="subtitle2">Key Factors</Typography>
                      <List dense disablePadding>
                        {data.key_factors.map((factor, i) => (
                          <ListItem key={i} disableGutters sx={{ py: 0 }}>
                            <ListItemText
                              primary={`• ${factor}`}
                              primaryTypographyProps={{ variant: "body2" }}
                            />
                          </ListItem>
                        ))}
                      </List>
                    </>
                  )}
                </Stack>
              </Popover>
            </>
          ) : (
            <Alert severity="info">No signal available.</Alert>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
