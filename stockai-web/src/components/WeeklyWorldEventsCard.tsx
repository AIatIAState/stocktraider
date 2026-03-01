import {
  Alert,
  Box,
  Card,
  CardContent,
  Link,
  List,
  ListItem,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import { type MarketEvent } from "../services/api";
import { GradientCircularProgress } from "./GradientCircularProgress";

type WeeklyWorldEventsCardProps = {
  start?: string;
  end?: string;
  impacts: string[];
  events: MarketEvent[];
  eventsNote?: string | null;
  model?: string | null;
  loading: boolean;
  error?: string | null;
};

function formatEventDate(value?: string | null) {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function EventCard({ event }: { event: MarketEvent }) {
  const metaParts = [formatEventDate(event.date), event.source].filter(Boolean);
  return (
    <Card variant="outlined" sx={{ borderRadius: 2 }}>
      <CardContent sx={{ p: 2, "&:last-child": { pb: 2 } }}>
        <Stack direction="row" spacing={1.5} alignItems="flex-start">
          {event.image_url ? (
            <Box
              component="img"
              src={event.image_url}
              alt={event.title || "News thumbnail"}
              sx={{
                width: 72,
                height: 72,
                borderRadius: 1,
                objectFit: "cover",
                flexShrink: 0,
              }}
            />
          ) : null}
          <Stack spacing={0.5}>
            <Typography variant="subtitle1">
              {event.title || "Untitled event"}
            </Typography>
            {metaParts.length ? (
              <Typography variant="caption" color="text.secondary">
                {metaParts.join(" - ")}
              </Typography>
            ) : null}
            {event.url ? (
              <Link
                href={event.url}
                target="_blank"
                rel="noreferrer"
                underline="hover"
                variant="caption"
              >
                Read source
              </Link>
            ) : null}
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
}

export default function WeeklyWorldEventsCard(
  props: WeeklyWorldEventsCardProps,
) {
  const { impacts, events, eventsNote, model, loading, error } = props;
  const heading = "World News";

  return (
    <Card>
      <CardContent>
        <Stack spacing={1.5}>
          <Typography variant="h5">{heading}</Typography>

          {loading ? (
            <Stack direction="row" spacing={2} alignItems="center">
              <Typography variant="body2" color="text.secondary">
                Summarizing world events...
              </Typography>
              <GradientCircularProgress />
            </Stack>
          ) : error ? (
            <Alert severity="error">{error}</Alert>
          ) : impacts.length ? (
            <>
              <List dense>
                {impacts.map((item, index) => (
                  <ListItem key={`event-impact-${index}`} disableGutters>
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
            <Alert severity="info">No event impact summary available.</Alert>
          )}

          {events.length ? (
            <>
              <Typography variant="subtitle2" color="text.secondary">
                Events in scope
              </Typography>
              <Box sx={{ maxHeight: 360, overflowY: "auto", pr: 1 }}>
                <Stack spacing={1.5}>
                  {events.map((event, index) => (
                    <EventCard key={`event-${index}`} event={event} />
                  ))}
                </Stack>
              </Box>
            </>
          ) : null}

          {eventsNote ? <Alert severity="info">{eventsNote}</Alert> : null}
        </Stack>
      </CardContent>
    </Card>
  );
}
