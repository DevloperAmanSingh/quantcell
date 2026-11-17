import { Brain, Cpu, Settings } from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useLocation } from "react-router";
import { cn } from "@/lib/utils";

/**
 * Settings shell: a title row with section tabs above the active page.
 *
 * Tabs (rather than a third column) leave the full width to the page, which
 * matters for the Models page's provider list + detail split.
 */
export default function SettingLayout() {
  const { t } = useTranslation();
  const { pathname } = useLocation();

  const tabs = [
    { path: "/setting", icon: Cpu, label: t("settings.nav.models") },
    {
      path: "/setting/general",
      icon: Settings,
      label: t("settings.nav.general"),
    },
    { path: "/setting/memory", icon: Brain, label: t("settings.nav.memory") },
  ];

  return (
    <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
      <header className="shrink-0 border-border border-b px-6 pt-5">
        <h1 className="font-semibold text-foreground text-xl">
          {t("settings.title")}
        </h1>
        <nav
          className="mt-3 -mb-px flex gap-1"
          aria-label={t("settings.title")}
        >
          {tabs.map((tab) => {
            const isActive = pathname === tab.path;
            return (
              <NavLink
                key={tab.path}
                to={tab.path}
                end
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 border-b-2 px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "border-foreground font-medium text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                <tab.icon className="size-4" />
                {tab.label}
              </NavLink>
            );
          })}
        </nav>
      </header>

      <main className="flex min-h-0 flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
