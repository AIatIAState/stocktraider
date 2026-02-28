export function formatSymbol(symbol: string) {
  if (!symbol) {
    return symbol;
  }
  return symbol.replace(/\.US$/i, "");
}
