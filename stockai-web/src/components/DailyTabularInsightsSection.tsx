
import {Box, Card, CardContent, Container} from "@mui/material";
import {useEffect, useState, type SetStateAction} from "react";
import Typography from "@mui/material/Typography";
import Stack from "@mui/material/Stack";
import {GradientCircularProgress} from "./GradientCircularProgress.tsx";
import Grid from "@mui/material/Grid";
import {fetchPortfolioActions, type PortfolioAction} from "../services/StockMarketPortfolioActionService.ts";
import Button from "@mui/material/Button";


async function getPortfolioActions(setLoading: { (value: SetStateAction<boolean>): void; (arg0: boolean): void; }) {
    setLoading(true);
    const actions = await fetchPortfolioActions();
    setLoading(false);
    return actions;
}

export function DailyTabularInsightsSection() {
    const [loading, setLoading] = useState(false);
    const [actions, setActions] = useState<PortfolioAction[]>([]);
    const [enablePortfolioSearch, setEnablePortfolioSearch] = useState(false)

    useEffect(() => {
        if (enablePortfolioSearch) {
            getPortfolioActions(setLoading).then((response) =>
                setActions(response),
            );
        }
    }, [enablePortfolioSearch]);


    if (loading) {
        return (
            <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>

                <Card sx={{ borderRadius: 3 }}>
                    <CardContent>
                        <Stack direction="row" alignItems="center" spacing={2}>
                            <Typography variant="h4">Daily Portfolio Suggestions</Typography>
                            <GradientCircularProgress />
                        </Stack>
                    </CardContent>
                </Card>
            </Container>
        );
    }

    if (!enablePortfolioSearch){
        return (
            <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>
                <Stack direction="row" alignItems="center" spacing={2} flexWrap="wrap">
                    <Typography variant="h4">Daily Portfolio Suggestions</Typography>
                    <Button onClick={() => setEnablePortfolioSearch(true)} variant="outlined">
                        Run Portfolio Analysis
                    </Button>
                </Stack>
            </Container>
        )
    }
    return (
        <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>
                <Stack direction="row" alignItems="center" spacing={2} flexWrap="wrap">
                    <Typography variant="h4">Daily Portfolio Suggestions</Typography>
                    <Typography variant="h6" color="text.secondary">
                        Tabular predictions for optimal daily portfolio based on the last closing price.
                    </Typography>
                </Stack>
            <Card>
                <CardContent>
                    <Grid container spacing={0}>
                        {actions.map((action) => (
                            <Grid key={action.ticker} width={'20%'}>
                                        <Typography variant="h6" align={'center'}>
                                            {action.ticker + ":   5%"}
                                        </Typography>
                            </Grid>
                        ))}
                    </Grid>
                </CardContent>
            </Card>
    </Container>
    );
}
