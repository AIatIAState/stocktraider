import { Alert, Card, CardContent, Stack, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { fetchDbInfo, type DbInfo } from "../services/api";

export default function DBStatsCard() {
  const [dbInfo, setDbInfo] = useState<DbInfo | null>(null);
  const [dbInfoError, setDbInfoError] = useState<string | null>(null);

  useEffect(() => {
    fetchDbInfo()
      .then(setDbInfo)
      .catch((err) =>
        setDbInfoError(
          err instanceof Error ? err.message : "Failed to load DB info.",
        ),
      );
  }, []);

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h5">Database</Typography>
          <Typography variant="body2" color="text.secondary">
            Mount path, size, and data coverage for the SQLite database.
          </Typography>

          {dbInfoError ? (
            <Alert severity="error">{dbInfoError}</Alert>
          ) : !dbInfo ? (
            <Alert severity="info">Loading database info...</Alert>
          ) : !dbInfo.exists ? (
            <Alert severity="error">
              Database file not found at {dbInfo.db_path_resolved}.
            </Alert>
          ) : (
            <>
              {!dbInfo.writable && (
                <Alert severity="warning">
                  Database is read-only. Scheduled updates and admin jobs will
                  fail.
                </Alert>
              )}
              <Stack spacing={0.5}>
                <Typography variant="body2">
                  <strong>Path (env):</strong>{" "}
                  {dbInfo.db_path_env ?? <em>not set</em>}
                </Typography>
                <Typography variant="body2">
                  <strong>Resolved:</strong> {dbInfo.db_path_resolved}
                </Typography>
                <Typography variant="body2">
                  <strong>Size:</strong>{" "}
                  {dbInfo.size_bytes !== null
                    ? `${(dbInfo.size_bytes / 1024 / 1024).toFixed(1)} MB`
                    : "N/A"}
                </Typography>
                <Typography variant="body2">
                  <strong>Last modified:</strong>{" "}
                  {dbInfo.mtime
                    ? new Date(dbInfo.mtime).toLocaleString()
                    : "N/A"}
                </Typography>
                <Typography variant="body2">
                  <strong>Writable:</strong> {dbInfo.writable ? "Yes" : "No"}
                </Typography>
                <Typography variant="body2">
                  <strong>Daily bars:</strong>{" "}
                  {dbInfo.daily_min_date && dbInfo.daily_max_date
                    ? `${dbInfo.daily_min_date} -> ${dbInfo.daily_max_date}`
                    : "No data"}
                </Typography>
                <Typography variant="body2">
                  <strong>Bootstrap enabled:</strong>{" "}
                  {dbInfo.bootstrap_enabled ? "Yes" : "No"}
                </Typography>
                {dbInfo.bootstrap_enabled && (
                  <Typography variant="body2">
                    <strong>Bootstrap start:</strong>{" "}
                    {dbInfo.bootstrap_start ?? "N/A"}{" "}
                    {dbInfo.bootstrap_has_data === true
                      ? "(data present)"
                      : dbInfo.bootstrap_has_data === false
                        ? "(no data for this date)"
                        : ""}
                  </Typography>
                )}
              </Stack>
            </>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
