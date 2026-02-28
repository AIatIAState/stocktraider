import { Card, CardContent, Stack, Typography } from "@mui/material";

export default function AdminIntroCard() {
  return (
    <Card>
      <CardContent>
        <Stack spacing={1.5}>
          <Typography variant="overline">Admin Tools</Typography>
          <Typography variant="h3">Run a manual data refresh.</Typography>
          <Typography variant="body1" color="text.secondary">
            Pull daily OHLCV data from yfinance and upsert it into the SQLite
            database.
          </Typography>
        </Stack>
      </CardContent>
    </Card>
  );
}
