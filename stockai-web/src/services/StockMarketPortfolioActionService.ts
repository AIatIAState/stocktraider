import { API_BASE } from "./api.ts";
export interface PortfolioActionsResponse {
    tickers: string[];
    predictions: number[];
}

export type PortfolioAction = {
    ticker: string;
    prediction: number
}
function buildPortfolioActions(
    tickers: string[],
    predictions: number[]
): PortfolioAction[] {
    if (tickers.length !== predictions.length) {
        throw new Error("Arrays must be of equal length");
    }

    return tickers.map((ticker, i) => ({
        ticker: ticker,
        prediction: predictions[i],
    }));
}
export async function fetchPortfolioActions(): Promise<PortfolioAction[]> {
    try {

        const response = await fetch(
            `${API_BASE}/api/getPortfolioActions?`
        );
        const rawData = await response.json();
        const actions = buildPortfolioActions(rawData.tickers, rawData.predictions);
        console.log(actions)
        return actions;
    } catch (err) {
        throw new Error(
            err instanceof Error ? err.message : "Failed to fetch stock conditions"
        );
    }
}
