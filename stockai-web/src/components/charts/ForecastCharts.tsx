import { useEffect, useState } from "react";
import Stack from "@mui/material/Stack";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Card,
  CardContent,
  Typography,
} from "@mui/material";
import { GradientCircularProgress } from "../GradientCircularProgress.tsx";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import { fetchStockForecasts, type StockForecast } from "../../services/StockForecastService.ts";
import StockScatterChart from "./StockScatterChart.tsx";
import Grid from "@mui/material/Grid";
import { formatSymbol } from "../../utils/formatSymbol";

interface ForecastChartsProps {
  symbol: string;
}

async function getForecasts(
  symbol: string,
  forecastLength: number,
  setLoading: (data: boolean) => void,
) {
  setLoading(true);
  const response = await fetchStockForecasts(symbol, "daily", forecastLength);
  const forecasts: StockForecast[] = response["results"];
  setLoading(false);
  return forecasts;
}

export function ForecastCharts(props: ForecastChartsProps) {
  const [loading, setLoading] = useState(false);
  const [forecasts, setForecasts] = useState<StockForecast[]>([]);
  const forecastLength = 7;

  useEffect(() => {
    if (props.symbol === "") return;
    getForecasts(props.symbol, forecastLength, setLoading).then((response) =>
      setForecasts(response),
    );
  }, [props.symbol]);

  if (props.symbol === "") return <></>;

  if (loading) {
    return (
      <Card sx={{ borderRadius: 3 }}>
        <CardContent>
          <Stack direction="row" alignItems="center" spacing={2}>
            <Typography variant="h4">Stock Price Forecasting</Typography>
            <GradientCircularProgress />
          </Stack>
        </CardContent>
      </Card>
    );
  }

  return (
    <Accordion
      disableGutters
      elevation={0}
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: '12px !important',
        '&::before': { display: 'none' },
      }}
    >
      <AccordionSummary
        expandIcon={<ExpandMoreRoundedIcon sx={{ color: 'text.secondary' }} />}
        sx={{ px: 3, py: 1 }}
      >
        <Stack direction="row" alignItems="center" spacing={2} flexWrap="wrap">
          <Typography variant="h4">Stock Price Forecasting</Typography>
          <Typography variant="h6" color="text.secondary">
            Predictions for {formatSymbol(props.symbol)}'s prices next week.
          </Typography>
        </Stack>
      </AccordionSummary>
      <AccordionDetails sx={{ px: 3, pb: 3 }}>
        <Grid container spacing={2}>
          {forecasts.slice(0, 9).map((forecast) => (
            <Grid key={forecast.name} size={{ xs: 12, sm: 6, md: 4 }}>
              <StockScatterChart
                title={forecast.name}
                desc={forecast.summary}
                bars={forecast.forecast}
                symbol={props.symbol}
              />
            </Grid>
          ))}
        </Grid>
      </AccordionDetails>
    </Accordion>
  );
}
