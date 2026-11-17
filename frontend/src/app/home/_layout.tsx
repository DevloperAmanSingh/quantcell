import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Outlet } from "react-router";
import { Button } from "@/components/ui/button";
import { StockList, StockSearchModal } from "./components";

/**
 * Home shell: scrolling main column plus the watchlist panel.
 *
 * The main column is a size container so its children respond to the space
 * left after the app sidebar and watchlist, not to the whole viewport.
 */
export default function HomeLayout() {
  const { t } = useTranslation();
  return (
    <div className="flex min-w-0 flex-1 overflow-hidden">
      <main className="@container min-w-0 flex-1 overflow-y-auto">
        <Outlet />
      </main>

      <aside className="hidden w-64 shrink-0 flex-col overflow-hidden border-border border-l bg-card md:flex">
        <StockList />
        <StockSearchModal>
          <Button variant="secondary" className="mx-4 mb-4 font-medium text-sm">
            <Plus size={16} />
            {t("home.stock.add")}
          </Button>
        </StockSearchModal>
      </aside>
    </div>
  );
}
