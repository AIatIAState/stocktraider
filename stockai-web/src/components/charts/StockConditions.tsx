import { useEffect, useState } from "react";
import {
    fetchStockConditions,
    type ApiResponse,
    type StockConditionsResponse,
    createFeatureExplanationMap,
} from "../../services/StockMarketConditionsService.ts";
import {
    Box,
    Card,
    CardContent,
    Grid,
    Typography,
    Alert,
    Tooltip,
    useTheme,
    useMediaQuery,
    Container, AccordionSummary, AccordionDetails, Accordion,
} from "@mui/material";
import { styled } from "@mui/material/styles";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import VolatilityIcon from "@mui/icons-material/ChangeCircle";
import VolumeIcon from "@mui/icons-material/ShowChart";
import CircleIcon from "@mui/icons-material/Circle";
import Stack from "@mui/material/Stack";
import {GradientCircularProgress} from "../GradientCircularProgress.tsx";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import {formatSymbol} from "../../utils/formatSymbol.ts";

interface StockConditionsProps {
    symbol: string;
}

interface LoadingState {
    data: StockConditionsResponse | null;
    loading: boolean;
    error: Error | null;
}

interface MetricCategory {
    title: string;
    icon: React.ReactNode;
    color: string;
    metrics: Array<{
        key: string;
        label: string;
    }>;
}

// Styled Components
const GlassCard = styled(Card)(({ }) => ({
    background: "rgba(255, 255, 255, 0.05)",
    backdropFilter: "blur(10px)",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    borderRadius: "12px",
    transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
    "&:hover": {
        background: "rgba(255, 255, 255, 0.08)",
        border: "1px solid rgba(255, 255, 255, 0.15)",
        transform: "translateY(-2px)",
        boxShadow: "0 8px 32px 0 rgba(31, 38, 135, 0.2)",
    },
}));

const MetricValue = styled(Typography)(({ }) => ({
    fontFamily: "'IBM Plex Mono', monospace",
    fontWeight: 600,
    fontSize: "1.25rem",
    letterSpacing: "0.5px",
    background: "linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%)",
    backgroundClip: "text",
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
    cursor: "pointer",
    transition: "all 0.2s ease",
    "&:hover": {
        transform: "scale(1.05)",
    },
}));

const CategoryHeader = styled(Box)(({ }) => ({
    display: "flex",
    alignItems: "center",
    gap: "12px",
    marginBottom: "20px",
    paddingBottom: "16px",
    borderBottom: "2px solid rgba(255, 255, 255, 0.1)",
}));

const MetricContainer = styled(Box)(({ }) => ({
    padding: "16px",
    borderRadius: "8px",
    background: "rgba(255, 255, 255, 0.02)",
    border: "1px solid rgba(255, 255, 255, 0.05)",
    transition: "all 0.2s ease",
    "&:hover": {
        background: "rgba(255, 255, 255, 0.04)",
        border: "1px solid rgba(255, 255, 255, 0.1)",
    },
}));


const CategorySection = styled(Box)(({ }) => ({
    animation: "fadeInUp 0.6s ease-out",
    "@keyframes fadeInUp": {
        from: {
            opacity: 0,
            transform: "translateY(20px)",
        },
        to: {
            opacity: 1,
            transform: "translateY(0)",
        },
    },
}));

// Format value for display
const formatValue = (value: any): string => {
    if (typeof value === "number") {
        if (Math.abs(value) < 0.01 && value !== 0) {
            return value.toExponential(4);
        }
        if (value < 1 && value > 0) {
            return (value * 100).toFixed(2) + "%";
        }
        return value.toFixed(4);
    }
    return String(value);
};

// Determine color based on value
const getValueColor = (value: any): string => {
    if (typeof value !== "number") return "rgba(255, 255, 255, 0.7)";
    if (value > 0) return "#4ade80";
    if (value < 0) return "#f87171";
    return "rgba(255, 255, 255, 0.7)";
};

const metricCategories: MetricCategory[] = [
    {
        title: "Momentum",
        icon: <TrendingUpIcon sx={{ fontSize: 24 }} />,
        color: "#60a5fa",
        metrics: [
            { key: "ret_1d", label: "1-Day Return" },
            { key: "ret_5d", label: "5-Day Return" },
            { key: "ret_10d", label: "10-Day Return" },
            { key: "ret_20d", label: "20-Day Return" },
            { key: "ret_60d", label: "60-Day Return" },
            { key: "ret_120d", label: "120-Day Return" },
            { key: "ret_252d", label: "252-Day Return" },
            { key: "momentum_12_1", label: "12M-1M Momentum" },
        ],
    },
    {
        title: "Volatility",
        icon: <VolatilityIcon sx={{ fontSize: 24 }} />,
        color: "#f97316",
        metrics: [
            { key: "realized_vol_20d", label: "20-Day Realized Vol" },
            { key: "realized_vol_60d", label: "60-Day Realized Vol" },
            { key: "realized_vol_120d", label: "120-Day Realized Vol" },
            { key: "downside_vol_60d", label: "60-Day Downside Vol" },
            { key: "atr_14d", label: "14-Day ATR" },
            { key: "hl_range_10d", label: "10-Day High-Low Range" },
        ],
    },
    {
        title: "Macro Indicators",
        icon: <CircleIcon sx={{ fontSize: 24 }} />,
        color: "#14b8a6",
        metrics: [
            { key: "TY10Y", label: "10-Year Treasury Yield" },
            { key: "TY2Y", label: "2-Year Treasury Yield" },
            { key: "CPI", label: "CPI" },
            { key: "UnemploymentRate", label: "Unemployment Rate" },
            { key: "FedFunds", label: "Federal Funds Rate" },
            { key: "IndustrialProduction", label: "Industrial Production" },
            { key: "RetailMoneyMarketFunds", label: "Money Market Funds" },
        ],
    },
    {
        title: "Moving Averages",
        icon: <CircleIcon sx={{ fontSize: 24 }} />,
        color: "#a78bfa",
        metrics: [
            { key: "ma_dist_20d", label: "20-Day MA Distance" },
            { key: "ma_dist_60d", label: "60-Day MA Distance" },
            { key: "ma_dist_200d", label: "200-Day MA Distance" },
            { key: "pct_above_50d", label: "% Above 50-Day MA" },
            { key: "pct_above_200d", label: "% Above 200-Day MA" },
        ],
    },
    {
        title: "Volume & Liquidity",
        icon: <VolumeIcon sx={{ fontSize: 24 }} />,
        color: "#06b6d4",
        metrics: [
            { key: "volume_zscore_20d", label: "Volume Z-Score (20d)" },
            { key: "volume_trend_slope_60d", label: "Volume Trend Slope" },
            { key: "dollar_vol_20d", label: "Dollar Volume Ratio" },
            { key: "volume_spike_ratio_20d", label: "Volume Spike Ratio" },
        ],
    },
    {
        title: "Market Metrics",
        icon: <CircleIcon sx={{ fontSize: 24 }} />,
        color: "#ec4899",
        metrics: [
            { key: "beta_spy_60d", label: "Beta vs SPY (60d)" },
            { key: "put_call_ratio", label: "Put/Call Ratio" },
            { key: "adv_decl_ratio", label: "Advance/Decline Ratio" },
            { key: "new_52w_high_low", label: "52-Week High/Low" },
        ],
    },
    {
        title: "Market Conditions",
        icon: <CircleIcon sx={{ fontSize: 24 }} />,
        color: "#8b5cf6",
        metrics: [
            { key: "VIX_5d_chg", label: "VIX 5-Day Change" },
            { key: "VIX_20d_chg", label: "VIX 20-Day Change" },
            { key: "VIX_term_structure", label: "VIX Term Structure" },
            { key: "VIX_realized_vol_ratio_20d", label: "VIX/Realized Vol Ratio" },
        ],
    },
];

export function StockConditions(props: StockConditionsProps) {
    const [conditions, setConditions] = useState<LoadingState>({
        data: null,
        loading: false,
        error: null,
    });

    const theme = useTheme();
    useMediaQuery(theme.breakpoints.down("md"));
    useEffect(() => {
        if (props.symbol === "") {
            setConditions({ data: null, loading: false, error: null });
            return;
        }

        setConditions((prev) => ({ ...prev, loading: true, error: null }));

        fetchStockConditions(props.symbol)
            .then((response: ApiResponse) => {
                setConditions({
                    data: response.results,
                    loading: false,
                    error: null,
                });
            })
            .catch((error: Error) => {
                setConditions({
                    data: null,
                    loading: false,
                    error,
                });
                console.error("Failed to fetch stock conditions:", error);
            });
    }, [props.symbol]);

    if (conditions.loading) {
        return (
            <Card sx={{ borderRadius: 3 }}>
                <CardContent>
                    <Stack direction="row" alignItems="center" spacing={2}>
                        <Typography variant="h4">Stock Indicators</Typography>
                        <GradientCircularProgress />
                    </Stack>
                </CardContent>
            </Card>
        );
    }

    if (conditions.error) {
        return (
            <Card sx={{ borderRadius: 3 }}>
                <CardContent>
                    <Stack direction="row" alignItems="center" spacing={2}>
                        <Typography variant="h4">Stock Indicators</Typography>
                        <Alert severity="error">
                            Error loading stock conditions: {conditions.error.message}
                        </Alert>
                    </Stack>
                </CardContent>
            </Card>
        );
    }

    if (!conditions.data) {
        return (<></>);
    }

    const { market_conditions, feature_explanations } = conditions.data;
    const featureLookup = createFeatureExplanationMap(feature_explanations);

    const renderMetricRow = (metric: { key: string; label: string }) => {
        const value = market_conditions[metric.key];
        const feature = featureLookup[metric.key];
        const formattedValue = formatValue(value);
        const color = getValueColor(value);

        return (
            <Tooltip
                key={metric.key}
                title={
                    feature ? (
                        <Box sx={{ p: 1 }}>
                            <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.5 }}>
                                {feature.name}
                            </Typography>
                            <Typography variant="caption" sx={{ lineHeight: 1.6 }}>
                                {feature.description}
                            </Typography>
                        </Box>
                    ) : (
                        "No description available"
                    )
                }
                arrow
                placement="right"
                sx={{
                    "& .MuiTooltip-tooltip": {
                        background: "rgba(0, 0, 0, 0.9)",
                        backdropFilter: "blur(10px)",
                        border: "1px solid rgba(255, 255, 255, 0.1)",
                        borderRadius: "8px",
                        maxWidth: "300px",
                    },
                }}
            >
                <MetricContainer>
                    <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <Typography
                            variant="body2"
                            sx={{
                                color: "rgba(255, 255, 255, 0.7)",
                                fontSize: "0.9rem",
                                textTransform: "uppercase",
                                letterSpacing: "0.5px",
                                fontWeight: 500,
                            }}
                        >
                            {metric.label}
                        </Typography>
                        <MetricValue sx={{ color }}>
                            {formattedValue}
                        </MetricValue>
                    </Box>
                </MetricContainer>
            </Tooltip>
        );
    };

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
                    <Typography variant="h4">Stock Indicators</Typography>
                    <Typography variant="h6" color="text.secondary">
                        Stock indicators for {formatSymbol(props.symbol)}'s prices.
                    </Typography>
                </Stack>
            </AccordionSummary>
            <AccordionDetails sx={{ px: 3, pb: 3 }}>
            <Container maxWidth="xl" sx={{ py: 4, pb: 8 }}>
                <Grid container spacing={2} direction={'row'}>
                    {metricCategories.map((category, idx) => (
                        <Grid key={idx}>
                            <CategorySection style={{ animationDelay: `${idx * 0.05}s` }}>
                                <GlassCard>
                                    <CardContent sx={{ p: 3 }}>
                                        {/* Category Header */}
                                        <CategoryHeader sx={{ color: category.color }}>
                                            {category.icon}
                                            <Typography
                                                variant="h6"
                                                sx={{
                                                    fontWeight: 600,
                                                    fontSize: "1.1rem",
                                                    letterSpacing: "0.5px",
                                                }}
                                            >
                                                {category.title}
                                            </Typography>
                                        </CategoryHeader>

                                        {/* Metrics */}
                                        <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
                                            {category.metrics.map((metric) =>
                                                renderMetricRow(metric)
                                            )}
                                        </Box>
                                    </CardContent>
                                </GlassCard>
                            </CategorySection>
                        </Grid>
                    ))}
                </Grid>
            </Container>
            </AccordionDetails>
        </Accordion>
    );
}