import {
  Alert,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import { GradientCircularProgress } from "./GradientCircularProgress";

type WeeklyMarketInsightsCardProps = {
  start?: string;
  end?: string;
  insights: string[];
  note?: string | null;
  model?: string | null;
  loading: boolean;
  error?: string | null;
};

export default function WeeklyMarketInsightsCard(
  props: WeeklyMarketInsightsCardProps,
) {
  const { insights, note, model, loading, error } = props;
  const heading = "Market Insights";

  return (
    <Card>
      <CardContent>
        <Stack spacing={1.5}>
          <Typography variant="h5">{heading}</Typography>

          {loading ? (
            <Stack direction="row" spacing={2} alignItems="center">
              <Typography variant="body2" color="text.secondary">
                Generating weekly insights...
              </Typography>
              <GradientCircularProgress />
            </Stack>
          ) : error ? (
            <Alert severity="error">{error}</Alert>
          ) : insights.length ? (
            <>
              <List dense>
                {insights.map((item, index) => (
                  <ListItem key={`market-insight-${index}`} disableGutters>
                    <ListItemText primary={item} />
                  </ListItem>
                ))}
              </List>
              {model ? (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  align="right"
                >
                  Generated with {model}.
                </Typography>
              ) : null}
            </>
          ) : (
            <Alert severity="info">No market insights available.</Alert>
          )}

          {note ? <Alert severity="info">{note}</Alert> : null}
        </Stack>
      </CardContent>
    </Card>
  );
}
