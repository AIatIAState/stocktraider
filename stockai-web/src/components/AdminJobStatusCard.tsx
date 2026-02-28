import { Alert, Card, CardContent, Stack, Typography } from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import { fetchAdminUpdateJobs, type UpdateJob } from "../services/api";

export default function AdminJobStatusCard() {
  const [jobs, setJobs] = useState<UpdateJob[]>([]);
  const [jobError, setJobError] = useState<string | null>(null);

  const refreshJobs = useCallback(async () => {
    try {
      const response = await fetchAdminUpdateJobs();
      setJobs(response.jobs);
      setJobError(null);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load job history.";
      setJobError(message);
    }
  }, []);

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
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h5">Job status</Typography>
          <Typography variant="body2" color="text.secondary">
            Monitor the most recent update and any currently running jobs.
          </Typography>

          {jobError ? <Alert severity="error">{jobError}</Alert> : null}

          {lastJob ? (
            <Alert severity={lastJob.status === "completed" ? "success" : "error"}>
              Last job ({lastJob.status}) ran {lastJob.start} to {lastJob.end}.{" "}
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
  );
}
