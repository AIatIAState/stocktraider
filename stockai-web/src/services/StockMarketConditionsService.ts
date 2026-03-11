import { API_BASE } from "./api.ts";

// Feature explanation structure - fixed shape
export interface FeatureExplanation {
    identifier: string;
    name: string;
    description: string;
}

// Market conditions - dynamic keys with numeric values
export interface MarketConditions extends Record<string, number | string> {
    ticker: string;
    Date: string;
    [key: string]: number | string;
}


export interface StockConditionsResponse {
    market_conditions: MarketConditions;
    feature_explanations: FeatureExplanation[];
    prediction: number;
}

// Wrapper response structure
export interface ApiResponse {
    results: StockConditionsResponse;
}

export async function fetchStockConditions(
    stockSymbol: string
): Promise<ApiResponse> {
    try {
        const params = new URLSearchParams({
            symbol: stockSymbol,
        });
        const response = await fetch(
            `${API_BASE}/api/getCurrentTickerConditions?${params.toString()}`
        );

        const rawData = await response.json();
        let data: ApiResponse;

        if (rawData.results) {
            data = rawData as ApiResponse;
        } else if (rawData.market_conditions) {
            data = {
                results: rawData as StockConditionsResponse,
            };
        } else {
            throw new Error(
                `Unexpected response format. Keys: ${Object.keys(rawData).join(", ")}`
            );
        }

        return data;
    } catch (err) {
        throw new Error(
            err instanceof Error ? err.message : "Failed to fetch stock conditions"
        );
    }
}

export function createFeatureExplanationMap(
    explanations: FeatureExplanation[]
): Record<string, FeatureExplanation> {
    return explanations.reduce(
        (acc, exp) => {
            acc[exp.identifier] = exp;
            return acc;
        },
        {} as Record<string, FeatureExplanation>
    );
}