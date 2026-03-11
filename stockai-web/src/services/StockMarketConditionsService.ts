import { API_BASE } from "./api.ts";

// Feature explanation structure - fixed shape
export interface FeatureExplanation {
    identifier: string;
    name: string;
    description: string;
}

// Market conditions - dynamic keys with numeric values
// This allows any string key with numeric values
export interface MarketConditions extends Record<string, number | string> {
    ticker: string;
    Date: string;
    // Other fields are dynamic numeric values
    [key: string]: number | string;
}

// Main response structure
export interface StockConditionsResponse {
    market_conditions: MarketConditions;
    feature_explanations: FeatureExplanation[];
}

// Wrapper response structure
export interface ApiResponse {
    results: StockConditionsResponse;
}

export async function fetchStockConditions(
    stockSymbol: string
): Promise<ApiResponse> {
    console.log("FETCHING STOCK CONDITIONS");
    try {
        const params = new URLSearchParams({
            symbol: stockSymbol,
        });
        const response = await fetch(
            `${API_BASE}/api/getCurrentTickerConditions?${params.toString()}`
        );
        console.log("GOT RESPONSE STATUS:", response.status);

        const rawData = await response.json();
        console.log("RAW API RESPONSE:", rawData);

        // Handle different response formats
        let data: ApiResponse;

        if (rawData.results) {
            // Response has results wrapper
            data = rawData as ApiResponse;
        } else if (rawData.market_conditions) {
            // Response is the data directly (no wrapper)
            data = {
                results: rawData as StockConditionsResponse,
            };
        } else {
            throw new Error(
                `Unexpected response format. Keys: ${Object.keys(rawData).join(", ")}`
            );
        }

        // Console log the parsed response
        console.log("=== STOCK CONDITIONS RESPONSE ===");
        console.log("Market Conditions:", data.results.market_conditions);
        console.log("Feature Explanations count:", data.results.feature_explanations.length);
        console.log("===================================");

        // Optional: Log specific market condition values
        console.log("\n=== SAMPLE MARKET CONDITIONS ===");
        console.log("Ticker:", data.results.market_conditions.ticker);
        console.log("Date:", data.results.market_conditions.Date);
        console.log("1-Day Returns:", data.results.market_conditions.ret_1d);
        console.log("60-Day Returns:", data.results.market_conditions.ret_60d);
        console.log("VIX 20d Change:", data.results.market_conditions.VIX_20d_chg);
        console.log("================================\n");

        return data;
    } catch (err) {
        throw new Error(
            err instanceof Error ? err.message : "Failed to fetch stock conditions"
        );
    }
}

// Utility function to safely access market conditions with type safety
export function getMarketConditionValue(
    conditions: MarketConditions,
    key: string
): number | string | undefined {
    return conditions[key];
}

// Utility function to get feature explanation by identifier
export function getFeatureExplanation(
    explanations: FeatureExplanation[],
    identifier: string
): FeatureExplanation | undefined {
    return explanations.find((exp) => exp.identifier === identifier);
}

// Utility function to create a lookup map for feature explanations
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

// Example usage with strong typing:
export async function exampleUsage(stockSymbol: string) {
    const response = await fetchStockConditions(stockSymbol);
    const { market_conditions, feature_explanations } = response.results;

    // Create feature lookup for easy access
    const featureLookup = createFeatureExplanationMap(feature_explanations);

    // Strongly typed access
    const returnValue = market_conditions.ret_1d as number;
    const momentumFeature = featureLookup["momentum_12_1"];

    console.log(`\n1-Day Return: ${returnValue}`);
    console.log(`Momentum Feature: ${momentumFeature?.name}`);

    // Iterate over all market conditions
    console.log("\n=== ALL MARKET CONDITIONS ===");
    Object.entries(market_conditions).forEach(([key, value]) => {
        const feature = featureLookup[key];
        const description = feature ? ` (${feature.description})` : "";
        console.log(`${key}: ${value}${description}`);
    });
}