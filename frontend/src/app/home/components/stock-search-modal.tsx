/**
 * Watchlist search: a cmdk combobox inside a dialog.
 *
 * Filtering happens on the server, so cmdk's own filter is turned off
 * (`shouldFilter={false}`) and it only provides keyboard navigation.
 * Before the user types, a short list of popular assets is offered so the
 * dialog is never an empty box.
 */

import { Check, Plus } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  useAddStockToWatchlist,
  useGetStocksList,
  useGetWatchlist,
} from "@/api/stock";
import { Badge } from "@/components/ui/badge";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { useDebounce } from "@/hooks/use-debounce";
import type { Stock } from "@/types/stock";

const SEARCH_DEBOUNCE_MS = 250;

/** Shown before typing. Tickers and names as returned by the search API. */
const POPULAR_ASSETS: Stock[] = [
  {
    ticker: "NASDAQ:AAPL",
    symbol: "AAPL",
    display_name: "Apple Inc.",
    asset_type: "stock",
    exchange: "NASDAQ",
  },
  {
    ticker: "NASDAQ:NVDA",
    symbol: "NVDA",
    display_name: "NVIDIA Corporation",
    asset_type: "stock",
    exchange: "NASDAQ",
  },
  {
    ticker: "NASDAQ:TSLA",
    symbol: "TSLA",
    display_name: "Tesla Inc.",
    asset_type: "stock",
    exchange: "NASDAQ",
  },
  {
    ticker: "CRYPTO:BTC",
    symbol: "BTC",
    display_name: "Bitcoin",
    asset_type: "crypto",
    exchange: "CRYPTO",
  },
];

const US_EXCHANGES = new Set(["NASDAQ", "NYSE", "AMEX"]);
const CN_EXCHANGES = new Set(["SSE", "SZSE", "HKEX"]);
const JP_EXCHANGES = new Set(["TSE", "JPX", "TYO"]);

/** Keeps the asset kinds and markets the watchlist can price. */
function isSupportedAsset(stock: Stock): boolean {
  const assetType = stock.asset_type?.toLowerCase();
  const exchange = (stock.exchange || "").toUpperCase();
  const prefix = (stock.ticker?.split(":")[0] || "").toUpperCase();
  if (assetType === "crypto" || prefix === "CRYPTO") return true;
  if (assetType !== "stock") return false;
  return [US_EXCHANGES, CN_EXCHANGES, JP_EXCHANGES].some(
    (set) => set.has(exchange) || set.has(prefix),
  );
}

interface AssetRowProps {
  stock: Stock;
  isWatched: boolean;
  isAdding: boolean;
  onAdd: (stock: Stock) => void;
}

function AssetRow({ stock, isWatched, isAdding, onAdd }: AssetRowProps) {
  return (
    <CommandItem
      value={stock.ticker}
      disabled={isWatched}
      onSelect={() => onAdd(stock)}
      className="flex items-center gap-3 px-3 py-2.5"
    >
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-foreground text-sm">
          {stock.display_name}
        </span>
        <span className="text-muted-foreground text-xs">{stock.ticker}</span>
      </div>
      <Badge variant="secondary" className="shrink-0 capitalize">
        {stock.asset_type}
      </Badge>
      <span className="flex size-5 shrink-0 items-center justify-center text-muted-foreground">
        {isAdding ? (
          <Spinner className="size-4" />
        ) : isWatched ? (
          <Check className="size-4 text-emerald-600" />
        ) : (
          <Plus className="size-4" />
        )}
      </span>
    </CommandItem>
  );
}

export default function StockSearchModal({
  children,
}: {
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query.trim(), SEARCH_DEBOUNCE_MS);
  const { data: results = [], isFetching } = useGetStocksList({
    query: debouncedQuery,
  });
  const { data: watchlist = [] } = useGetWatchlist();
  const {
    mutate: addToWatchlist,
    isPending,
    variables,
  } = useAddStockToWatchlist();

  const watched = new Set(
    watchlist.flatMap((list) => list.items.map((item) => item.ticker)),
  );
  const hasQuery = query.trim().length > 0;
  // Results for an older query are hidden while a newer one is in flight.
  const isSearching = query.trim() !== debouncedQuery || isFetching;
  const assets = hasQuery ? results.filter(isSupportedAsset) : POPULAR_ASSETS;

  const renderRow = (stock: Stock) => (
    <AssetRow
      key={stock.ticker}
      stock={stock}
      isWatched={watched.has(stock.ticker)}
      isAdding={isPending && variables?.ticker === stock.ticker}
      onAdd={(s) => addToWatchlist({ ticker: s.ticker })}
    />
  );

  return (
    <Dialog onOpenChange={(open) => !open && setQuery("")}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="gap-0 overflow-hidden p-0 sm:max-w-lg">
        <div className="px-4 pt-4 pb-2">
          <DialogTitle className="font-semibold text-base">
            {t("home.search.title")}
          </DialogTitle>
          <DialogDescription className="text-xs">
            {t("home.search.hint")}
          </DialogDescription>
        </div>
        <Command shouldFilter={false} className="bg-transparent">
          <CommandInput
            value={query}
            onValueChange={setQuery}
            placeholder={t("home.search.placeholder")}
          />
          <CommandList className="max-h-80 min-h-40 p-1">
            {hasQuery && isSearching && (
              <div className="flex items-center gap-2 px-3 py-3 text-muted-foreground text-sm">
                <Spinner className="size-4" />
                {t("home.search.searching")}
              </div>
            )}
            {!(hasQuery && isSearching) && (
              <>
                <CommandEmpty className="px-3 py-6 text-center text-muted-foreground text-sm">
                  {t("home.search.noMatches", { query: debouncedQuery })}
                </CommandEmpty>
                <CommandGroup
                  heading={
                    hasQuery
                      ? t("home.search.results")
                      : t("home.search.popular")
                  }
                >
                  {assets.map(renderRow)}
                </CommandGroup>
              </>
            )}
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
