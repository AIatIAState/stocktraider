import {
  Alert,
  Card,
  CardContent,
  Chip,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import {
  fetchWeeklyRecommendation,
  type WeeklyRecommendationResponse,
} from "../services/api";
import { GradientCircularProgress } from "./GradientCircularProgress";
import { formatSymbol } from "../utils/formatSymbol";

type RiskLevel = "low" | "mid" | "high";

const CONFIDENCE_COLORS: Record<string, "success" | "warning" | "default"> = {
  high: "success",
  medium: "warning",
  low: "default",
};

export default function WeeklyRecommendationCard() {
  const [risk, setRisk] = useState<RiskLevel>("mid");
  const [data, setData] = useState<WeeklyRecommendationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback((riskLevel: RiskLevel) => {
    let active = true;
    setLoading(true);
    setError(null);
    fetchWeeklyRecommendation(riskLevel)
      .then((response) => {
        if (!active) return;
        setData(response);
      })
      .catch((err) => {
        if (!active) return;
        const message =
          err instanceof Error
            ? err.message
            : "Failed to load recommendation.";
        setError(message);
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    return load(risk);
  }, [risk, load]);

  const handleRiskChange = (
    _: React.MouseEvent<HTMLElement>,
    value: RiskLevel | null,
  ) => {
    if (value) setRisk(value);
  };

  return (
    <Card>
      <CardContent>
        <Stack spacing={1.5}>
          <Stack
            direction="row"
            alignItems="center"
            justifyContent="space-between"
            flexWrap="wrap"
            gap={1}
          >
            <Typography variant="h5">Weekly Stock Pick</Typography>
            <ToggleButtonGroup
              value={risk}
              exclusive
              onChange={handleRiskChange}
              size="small"
            >
              <ToggleButton value="low">Low Risk</ToggleButton>
              <ToggleButton value="mid">Mid Risk</ToggleButton>
              <ToggleButton value="high">High Risk</ToggleButton>
            </ToggleButtonGroup>
          </Stack>

          {loading ? (
            <Stack direction="row" spacing={2} alignItems="center">
              <Typography variant="body2" color="text.secondary">
                Generating stock recommendation...
              </Typography>
              <GradientCircularProgress />
            </Stack>
          ) : error ? (
            <Alert severity="error">{error}</Alert>
          ) : data?.note && !data.symbol ? (
            <Alert severity="warning">{data.note}</Alert>
          ) : data?.symbol ? (
            <>
              <Stack direction="row" alignItems="center" spacing={1.5} flexWrap="wrap">
                <Typography variant="h5" fontWeight="bold">
                  {formatSymbol(data.symbol)}
                </Typography>
                <Chip
                  label={data.action ?? "BUY"}
                  color="success"
                  size="small"
                />
                {data.predicted_move && (
                  <Chip
                    label={data.predicted_move}
                    variant="outlined"
                    size="small"
                  />
                )}
                {data.confidence && (
                  <Chip
                    label={`${data.confidence} confidence`}
                    color={CONFIDENCE_COLORS[data.confidence] ?? "default"}
                    variant="outlined"
                    size="small"
                  />
                )}
              </Stack>
              {data.reasoning && (
                <Typography variant="body2" color="text.secondary">
                  {data.reasoning}
                </Typography>
              )}
              {data.note && (
                <Alert severity="info">{data.note}</Alert>
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
            </>
          ) : (
            <Alert severity="info">No recommendation available.</Alert>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
