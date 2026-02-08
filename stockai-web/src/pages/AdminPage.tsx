import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useMemo, useState } from "react";
import AppAppBar from "../components/AppAppBar";
import Footer from "../components/Footer";
import {
  fetchAdminUpdateJobs,
  fetchAdminUpdateStatus,
  runAdminUpdate,
} from "../services/api";
import AppTheme from "../themes/AppTheme";

const MS_PER_DAY = 24 * 60 * 60 * 1000;

function toLocalIsoDate(date: Date) {
  const offsetMs = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 10);
}

export default function AdminPage(props: { disableCustomTheme?: boolean }) {
  const today = useMemo(() => new Date(), []);
  const defaultEnd = toLocalIsoDate(today);
  const defaultStart = toLocalIsoDate(
    new Date(today.getTime() - 6 * MS_PER_DAY),
  );

  const [startDate, setStartDate] = useState(defaultStart);
  const [endDate, setEndDate] = useState(defaultEnd);
  const [isRunning, setIsRunning] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmChecked, setConfirmChecked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<{
    symbols: number;
    yf_symbols: number;
    rows_fetched: number;
    rows_inserted: number;
  } | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<
    "running" | "completed" | "failed" | null
  >(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<
    {
      id: string;
      status: "running" | "completed" | "failed";
      created_at: string;
      started_at: string;
      finished_at: string | null;
      summary: {
        symbols: number;
        yf_symbols: number;
        rows_fetched: number;
        rows_inserted: number;
      } | null;
      error: string | null;
      start: string;
      end: string;
    }[]
  >([]);

  const handleRun = async () => {
    setError(null);
    setSummary(null);
    setJobId(null);
    setJobStatus(null);
    setJobError(null);
    setIsRunning(true);
    try {
      const response = await runAdminUpdate({ start: startDate, end: endDate });
      setJobId(response.id);
      setJobStatus(response.status);
      refreshJobs();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to run update.";
      setError(message);
    } finally {
      setIsRunning(false);
    }
  };

  const handleOpenConfirm = () => {
    setError(null);
    if (!startDate || !endDate) {
      setError("Start and end dates are required.");
      return;
    }
    if (startDate > endDate) {
      setError("End date must be on or after the start date.");
      return;
    }
    setConfirmChecked(false);
    setConfirmOpen(true);
  };

  const handleConfirm = async () => {
    setConfirmOpen(false);
    await handleRun();
  };

  const refreshJobs = useCallback(async () => {
    try {
      const response = await fetchAdminUpdateJobs();
      setJobs(response.jobs);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load job history.";
      setJobError(message);
    }
  }, []);

  useEffect(() => {
    if (!jobId || jobStatus !== "running") {
      return;
    }
    let isActive = true;
    const timer = setInterval(async () => {
      try {
        const status = await fetchAdminUpdateStatus(jobId);
        if (!isActive) {
          return;
        }
        setJobStatus(status.status);
        if (status.status === "completed") {
          setSummary(status.summary);
        }
        if (status.status === "failed") {
          setJobError(status.error || "Update failed.");
        }
      } catch (err) {
        if (!isActive) {
          return;
        }
        const message =
          err instanceof Error ? err.message : "Failed to fetch job status.";
        setJobError(message);
        setJobStatus("failed");
      }
    }, 2000);

    return () => {
      isActive = false;
      clearInterval(timer);
    };
  }, [jobId, jobStatus]);

  useEffect(() => {
    refreshJobs();
    const timer = setInterval(() => {
      refreshJobs();
    }, 5000);
    return () => clearInterval(timer);
  }, [refreshJobs]);

  const runningJobs = jobs.filter((job) => job.status === "running");
  const lastJob =
    jobs.find((job) => job.status === "completed" || job.status === "failed") ??
    null;

  return (
    <AppTheme {...props}>
      <AppAppBar />
      <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <Card>
            <CardContent>
              <Stack spacing={1.5}>
                <Typography variant="overline">Admin Tools</Typography>
                <Typography variant="h3">Run a manual data refresh.</Typography>
                <Typography variant="body1" color="text.secondary">
                  Pull daily OHLCV data from yfinance and upsert it into the
                  SQLite database.
                </Typography>
              </Stack>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Stack spacing={2}>
                <Typography variant="h5">Update price data</Typography>
                <Typography variant="body2" color="text.secondary">
                  Select a date range, then confirm the warning before launching
                  the job.
                </Typography>

                <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                  <TextField
                    label="Start date"
                    type="date"
                    value={startDate}
                    onChange={(event) => setStartDate(event.target.value)}
                    InputLabelProps={{ shrink: true }}
                    fullWidth
                  />
                  <TextField
                    label="End date"
                    type="date"
                    value={endDate}
                    onChange={(event) => setEndDate(event.target.value)}
                    InputLabelProps={{ shrink: true }}
                    fullWidth
                  />
                </Stack>

                {error ? (
                  <Alert severity="error">{error}</Alert>
                ) : jobStatus === "running" ? (
                  <Alert severity="info">
                    Update job is running. This may take several minutes.
                  </Alert>
                ) : jobError ? (
                  <Alert severity="error">{jobError}</Alert>
                ) : summary ? (
                  <Alert severity="success">
                    Inserted {summary.rows_inserted} new rows for{" "}
                    {summary.symbols} symbols.
                  </Alert>
                ) : null}

                <Box>
                  <Button
                    variant="contained"
                    onClick={handleOpenConfirm}
                    disabled={isRunning || jobStatus === "running"}
                  >
                    {isRunning || jobStatus === "running"
                      ? "Running update..."
                      : "Run update"}
                  </Button>
                </Box>
              </Stack>
            </CardContent>
          </Card>

          <Card>
            <CardContent>
              <Stack spacing={2}>
                <Typography variant="h5">Job status</Typography>
                <Typography variant="body2" color="text.secondary">
                  Monitor the most recent update and any currently running jobs.
                </Typography>

                {lastJob ? (
                  <Alert
                    severity={
                      lastJob.status === "completed" ? "success" : "error"
                    }
                  >
                    Last job ({lastJob.status}) ran {lastJob.start} to{" "}
                    {lastJob.end}.{" "}
                    {lastJob.summary
                      ? `Inserted ${lastJob.summary.rows_inserted} rows.`
                      : lastJob.error
                        ? lastJob.error
                        : "Summary unavailable."}
                  </Alert>
                ) : (
                  <Alert severity="info">No completed jobs yet.</Alert>
                )}

                {runningJobs.length ? (
                  <Stack spacing={1}>
                    <Typography variant="subtitle1">Running jobs</Typography>
                    {runningJobs.map((job) => (
                      <Alert key={job.id} severity="warning">
                        Job {job.id} running ({job.start} to {job.end}).
                      </Alert>
                    ))}
                  </Stack>
                ) : (
                  <Alert severity="info">No running jobs.</Alert>
                )}
              </Stack>
            </CardContent>
          </Card>
        </Box>
      </Container>

      <Dialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Confirm data refresh</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Alert severity="warning">
              This job writes to the production database and may take several
              minutes. Do not run it during active demos or heavy usage.
            </Alert>
            <FormControlLabel
              control={
                <Checkbox
                  checked={confirmChecked}
                  onChange={(event) => setConfirmChecked(event.target.checked)}
                />
              }
              label="I understand this will modify the database."
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleConfirm}
            disabled={!confirmChecked || isRunning}
          >
            Run update
          </Button>
        </DialogActions>
      </Dialog>
      <Footer />
    </AppTheme>
  );
}
