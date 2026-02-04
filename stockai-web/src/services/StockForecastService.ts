import { API_BASE } from "./api.ts";

export interface StockForecast {
    name: string,
    summary: string,
    forecast: [
        {
            date: number,
            open: number
        }
        ]
}
export async function fetchStockForecasts(stockSymbol: string, timeframe: "daily", forecastLength?: number) : Promise<{results: StockForecast[]}> {
    try {
        const params = new URLSearchParams({
            symbol: stockSymbol,
            timeframe: timeframe,
            forecast_length: forecastLength ? forecastLength.toString() : "7"
        })
        const response = await fetch(`${API_BASE}/api/getForecasts?${params.toString()}`)
        return response.json() as Promise<{results: StockForecast[]}>
    } catch (err) {
        throw new Error(err instanceof Error ? err.message : 'Failed to fetch forecasts');
    }
}