import { API_BASE } from "./api.ts";

export interface StockPattern {
    starting_date: number,
    similarity_score: number,
}
export async function fetchStockPatterns(stockSymbol: string, timeframe: "daily", trendLength?: number, similarityScore?: number) : Promise<{results: StockPattern[]}> {
    try {
        const params = new URLSearchParams({
            symbol: stockSymbol,
            timeframe: timeframe,
            trend_length: trendLength ? trendLength.toString() : "7",
            similarity_score: similarityScore ? similarityScore.toString() : "80"
        })
        const response = await fetch(`${API_BASE}/api/getPatterns?${params.toString()}`)
        return response.json() as Promise<{results: StockPattern[]}>
    } catch (err) {
        throw new Error(err instanceof Error ? err.message : 'Failed to fetch patterns');
    }
}