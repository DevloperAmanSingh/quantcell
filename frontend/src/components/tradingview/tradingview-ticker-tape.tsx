import { memo, useEffect, useMemo, useRef } from "react";

const TICKER_TAPE_SCRIPT_URL =
  "https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js";
const MAX_SYMBOLS = 8;
/** Height of the TradingView ticker iframe (measured: 60px at all widths). */

interface TradingViewTickerTapeProps {
  symbols: string[];
  theme?: "light" | "dark";
  locale?: string;
}

/**
 * TradingView ticker tape embed.
 *
 * Uses TradingView's standard markup: a `tradingview-widget-container` that
 * holds a `__widget` div and the config script. The script is injected on
 * the next tick: React StrictMode mounts effects twice in development, and
 * a script attached by the first (discarded) mount would run after its
 * container was cleared, crashing in TradingView's loader.
 */
function TradingViewTickerTape({
  symbols,
  theme = "light",
  locale = "en",
}: TradingViewTickerTapeProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  const config = useMemo(
    () =>
      JSON.stringify({
        symbols: symbols.slice(0, MAX_SYMBOLS).map((s) => ({ proName: s })),
        showSymbolLogo: true,
        colorTheme: theme,
        isTransparent: false,
        displayMode: "regular",
        locale,
      }),
    [symbols, theme, locale],
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const timer = window.setTimeout(() => {
      const widget = document.createElement("div");
      widget.className = "tradingview-widget-container__widget";
      const script = document.createElement("script");
      script.type = "text/javascript";
      script.async = true;
      script.src = TICKER_TAPE_SCRIPT_URL;
      script.innerHTML = config;
      container.replaceChildren(widget, script);
    }, 0);

    return () => {
      window.clearTimeout(timer);
      container.replaceChildren();
    };
  }, [config]);

  return (
    <div
      ref={containerRef}
      className="tradingview-widget-container h-15 w-full shrink-0 overflow-hidden rounded-xl border border-border"
    />
  );
}

export default memo(TradingViewTickerTape);
