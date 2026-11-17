import { ArrowUp, CandlestickChart, FileSearch, Newspaper } from "lucide-react";
import { useTheme } from "next-themes";
import { type FormEvent, type KeyboardEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, useNavigate } from "react-router";
import { useAllPollTaskList } from "@/api/conversation";
import TradingViewTickerTape from "@/components/tradingview/tradingview-ticker-tape";
import { Button } from "@/components/ui/button";
import { QUANTCELL_AGENT } from "@/constants/agent";
import { AgentTaskCards } from "./components";

const INDEX_SYMBOLS = [
  "FOREXCOM:SPXUSD",
  "INDEX:HSI",
  "SSE:000001",
  "BINANCE:BTCUSDT",
  "BINANCE:ETHUSDT",
];

const MORNING_END_HOUR = 12;
const AFTERNOON_END_HOUR = 18;

function greetingKey(hour: number): string {
  if (hour < MORNING_END_HOUR) return "home.greeting.morning";
  if (hour < AFTERNOON_END_HOUR) return "home.greeting.afternoon";
  return "home.greeting.evening";
}

/** Sends the first message to the QuantCell super agent's chat page. */
function HomeComposer() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [value, setValue] = useState("");
  const query = value.trim();

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (!query) return;
    navigate(`/agent/${QUANTCELL_AGENT.agent_name}`, {
      state: { inputValue: query },
    });
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      submit(event);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="flex w-full flex-col rounded-2xl border border-border bg-card shadow-sm focus-within:ring-2 focus-within:ring-ring/30"
    >
      <textarea
        rows={2}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder={t("home.composerPlaceholder")}
        className="w-full resize-none bg-transparent px-4 pt-3.5 text-foreground text-sm outline-none placeholder:text-muted-foreground"
      />
      <div className="flex justify-end px-2.5 pb-2.5">
        <Button
          type="submit"
          size="icon"
          disabled={!query}
          aria-label={t("chat.send")}
          className="size-8 rounded-full"
        >
          <ArrowUp className="size-4" />
        </Button>
      </div>
    </form>
  );
}

function QuickActions() {
  const { t } = useTranslation();
  const actions = [
    { to: "/agent/ResearchAgent", icon: FileSearch, key: "research" },
    { to: "/agent/StrategyAgent", icon: CandlestickChart, key: "strategy" },
    { to: "/agent/NewsAgent", icon: Newspaper, key: "news" },
  ];

  return (
    <section className="space-y-3">
      <h2 className="font-medium text-muted-foreground text-sm">
        {t("home.quickActions")}
      </h2>
      <div className="grid @md:grid-cols-3 gap-3">
        {actions.map((action) => (
          <NavLink
            key={action.key}
            to={action.to}
            className="group flex flex-col gap-2 rounded-xl border border-border bg-card p-4 transition-colors hover:bg-muted"
          >
            <action.icon className="size-5 text-muted-foreground group-hover:text-foreground" />
            <span className="font-medium text-foreground text-sm">
              {t(`home.suggestions.${action.key}.title`)}
            </span>
            <span className="text-muted-foreground text-xs leading-relaxed">
              {t(`home.suggestions.${action.key}.description`)}
            </span>
          </NavLink>
        ))}
      </div>
    </section>
  );
}

function Home() {
  const { t, i18n } = useTranslation();
  const { resolvedTheme } = useTheme();
  const { data: scheduledResults = [] } = useAllPollTaskList();

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-10 @xl:px-6 px-4 py-6">
      <TradingViewTickerTape
        symbols={INDEX_SYMBOLS}
        theme={resolvedTheme === "dark" ? "dark" : "light"}
        locale={i18n.language}
      />

      <section className="flex flex-col gap-5 pt-4">
        <div className="space-y-1.5">
          <h1 className="font-semibold @xl:text-3xl text-2xl text-foreground">
            {t(greetingKey(new Date().getHours()))}
          </h1>
          <p className="text-muted-foreground text-sm">{t("home.subtitle")}</p>
        </div>
        <HomeComposer />
      </section>

      <QuickActions />

      {scheduledResults.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-medium text-muted-foreground text-sm">
            {t("home.latestResults")}
          </h2>
          <AgentTaskCards tasks={scheduledResults} />
        </section>
      )}
    </div>
  );
}

export default Home;
