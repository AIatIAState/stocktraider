import {
  Alert,
  Card,
  CardContent,
  FormControlLabel,
  Stack,
  Switch,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import {
  fetchSchedulerStatus,
  setSchedulerEnabled,
  type SchedulerStatus,
} from "../services/api";

function formatInTimeZone(value: string | null, timeZone: string) {
  if (!value) {
    return "N/A";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  try {
    return new Intl.DateTimeFormat(undefined, {
      timeZone,
      dateStyle: "medium",
      timeStyle: "short",
      timeZoneName: "short",
    }).format(parsed);
  } catch {
    return parsed.toLocaleString();
  }
}

export default function AdminSchedulerCard() {
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(
    null,
  );
  const [schedulerError, setSchedulerError] = useState<string | null>(null);
  const [schedulerBusy, setSchedulerBusy] = useState(false);

  const refreshScheduler = useCallback(async () => {
    try {
      const response = await fetchSchedulerStatus();
      setSchedulerStatus(response);
      setSchedulerError(null);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load scheduler status.";
      setSchedulerError(message);
    }
  }, []);

  const handleSchedulerToggle = async (enabled: boolean) => {
    setSchedulerBusy(true);
    setSchedulerError(null);
    try {
      const response = await setSchedulerEnabled(enabled);
      setSchedulerStatus(response);
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Failed to update scheduler setting.";
      setSchedulerError(message);
    } finally {
      setSchedulerBusy(false);
    }
  };

  useEffect(() => {
    refreshScheduler();
    const timer = setInterval(() => {
      refreshScheduler();
    }, 30000);
    return () => clearInterval(timer);
  }, [refreshScheduler]);

  const schedulerTz = schedulerStatus?.timezone ?? "America/Chicago";
  const lastSchedulerUpdate =
    schedulerStatus?.last_finished_at ?? schedulerStatus?.last_started_at ?? null;

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h5">Scheduler</Typography>
          <Typography variant="body2" color="text.secondary">
            Automated refresh runs {schedulerStatus?.schedule ?? "Sundays 03:00"}{" "}
            {schedulerTz}.
          </Typography>

          {schedulerError ? (
            <Alert severity="error">{schedulerError}</Alert>
          ) : null}

          {!schedulerStatus ? (
            <Alert severity="info">Loading scheduler status...</Alert>
          ) : !schedulerStatus.available ? (
            <Alert severity="warning">
              Scheduler is unavailable in this deployment.
            </Alert>
          ) : schedulerStatus.enabled && !schedulerStatus.running ? (
            <Alert severity="warning">
              Scheduler is enabled but not currently running. Check the backend
              logs for startup errors.
            </Alert>
          ) : null}

          <FormControlLabel
            control={
              <Switch
                checked={schedulerStatus?.enabled ?? false}
                onChange={(event) => handleSchedulerToggle(event.target.checked)}
                disabled={
                  schedulerBusy ||
                  !schedulerStatus ||
                  !schedulerStatus.available
                }
              />
            }
            label={schedulerStatus?.enabled ? "Enabled" : "Disabled"}
          />

          <Typography variant="body2">
            Next update:{" "}
            {schedulerStatus?.enabled && schedulerStatus?.next_run_time
              ? formatInTimeZone(schedulerStatus.next_run_time, schedulerTz)
              : "N/A"}
          </Typography>
          <Typography variant="body2">
            Last update:{" "}
            {schedulerStatus
              ? formatInTimeZone(lastSchedulerUpdate, schedulerTz)
              : "N/A"}{" "}
            {schedulerStatus?.last_status
              ? `(${schedulerStatus.last_status})`
              : ""}
          </Typography>
        </Stack>
      </CardContent>
    </Card>
  );
}
