/**
 * QuantCell chat thread built on assistant-ui primitives.
 *
 * Structure follows assistant-ui's documented thread layout: a scrolling
 * viewport with an empty-state welcome, the message list, and a sticky
 * footer holding the composer.
 */

import {
  ActionBarPrimitive,
  AuiIf,
  ComposerPrimitive,
  type EmptyMessagePartComponent,
  MessagePrimitive,
  type TextMessagePartComponent,
  ThreadPrimitive,
} from "@assistant-ui/react";
import { ArrowDown, ArrowUp, Check, Copy } from "lucide-react";
import type { FC } from "react";
import { useTranslation } from "react-i18next";
import AgentAvatar from "@/components/shared/icon/agent-avatar";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { MarkdownText } from "./markdown-text";
import {
  DATA_PART_COMPONENTS,
  ReasoningPart,
  ToolCallPart,
} from "./message-parts";

/** Readable column width shared by messages and the composer. */
const COLUMN = "mx-auto w-full max-w-3xl px-4";

interface ThreadProps {
  agentName: string;
  welcomeTitle: string;
  welcomeDescription?: string;
}

export const Thread: FC<ThreadProps> = ({
  agentName,
  welcomeTitle,
  welcomeDescription,
}) => {
  return (
    <ThreadPrimitive.Root className="flex h-full min-h-0 flex-col bg-background">
      <ThreadPrimitive.Viewport className="flex flex-1 flex-col overflow-y-auto">
        <AuiIf condition={(s) => s.thread.isEmpty}>
          <Welcome
            agentName={agentName}
            title={welcomeTitle}
            description={welcomeDescription}
          />
        </AuiIf>

        <div className={cn(COLUMN, "flex flex-col gap-6 py-6")}>
          <ThreadPrimitive.Messages>
            {({ message }) =>
              message.role === "user" ? (
                <UserMessage />
              ) : (
                <AssistantMessage agentName={agentName} />
              )
            }
          </ThreadPrimitive.Messages>
        </div>

        <ThreadPrimitive.ViewportFooter className="sticky bottom-0 mt-auto bg-linear-to-t from-60% from-background to-transparent pt-6 pb-4">
          <div className={cn(COLUMN, "relative flex flex-col gap-2")}>
            <ScrollToBottom />
            <Composer />
            <Disclaimer />
          </div>
        </ThreadPrimitive.ViewportFooter>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
};

interface WelcomeProps {
  agentName: string;
  title: string;
  description?: string;
}

const Welcome: FC<WelcomeProps> = ({ agentName, title, description }) => {
  const { t } = useTranslation();
  const suggestions = t(`chat.suggestions.${agentName}`, {
    returnObjects: true,
    defaultValue: [],
  }) as string[];

  return (
    <div
      className={cn(
        COLUMN,
        "flex flex-1 flex-col items-center justify-center gap-6 pt-16 text-center",
      )}
    >
      <AgentAvatar agentName={agentName} className="size-14" />
      <div className="space-y-2">
        <h1 className="font-semibold text-2xl text-foreground">{title}</h1>
        {description && (
          <p className="mx-auto line-clamp-2 max-w-lg text-muted-foreground text-sm">
            {description}
          </p>
        )}
      </div>
      {Array.isArray(suggestions) && suggestions.length > 0 && (
        <div className="grid w-full gap-2 sm:grid-cols-3">
          {suggestions.map((prompt) => (
            <ThreadPrimitive.Suggestion
              key={prompt}
              prompt={prompt}
              send
              className="rounded-xl border border-border bg-card px-4 py-3 text-left text-foreground text-sm transition-colors hover:bg-muted"
            >
              {prompt}
            </ThreadPrimitive.Suggestion>
          ))}
        </div>
      )}
    </div>
  );
};

const Composer: FC = () => {
  const { t } = useTranslation();
  return (
    <ComposerPrimitive.Root className="flex w-full flex-col rounded-2xl border border-border bg-card shadow-sm focus-within:ring-2 focus-within:ring-ring/30">
      <ComposerPrimitive.Input
        rows={1}
        autoFocus
        placeholder={t("chat.input.placeholder")}
        className="max-h-48 min-h-12 w-full resize-none bg-transparent px-4 pt-3.5 pb-1 text-foreground text-sm outline-none placeholder:text-muted-foreground"
      />
      <div className="flex items-center justify-end px-2.5 pb-2.5">
        <ComposerPrimitive.Send asChild>
          <Button
            size="icon"
            className="size-8 rounded-full"
            aria-label={t("chat.send")}
          >
            <ArrowUp className="size-4" />
          </Button>
        </ComposerPrimitive.Send>
      </div>
    </ComposerPrimitive.Root>
  );
};

const ScrollToBottom: FC = () => {
  const { t } = useTranslation();
  return (
    <ThreadPrimitive.ScrollToBottom asChild>
      <Button
        variant="outline"
        size="icon"
        aria-label={t("chat.scrollToBottom")}
        className="absolute -top-12 left-1/2 size-8 -translate-x-1/2 rounded-full shadow-sm disabled:invisible"
      >
        <ArrowDown className="size-4" />
      </Button>
    </ThreadPrimitive.ScrollToBottom>
  );
};

const Disclaimer: FC = () => {
  const { t } = useTranslation();
  return (
    <p className="text-center text-muted-foreground text-xs">
      {t("chat.disclaimer")}
    </p>
  );
};

const UserText: TextMessagePartComponent = ({ text }) => (
  <p className="whitespace-pre-wrap">{text}</p>
);

const UserMessage: FC = () => (
  <MessagePrimitive.Root className="flex justify-end">
    <div className="max-w-[80%] rounded-2xl bg-muted px-4 py-2.5 text-foreground text-sm">
      <MessagePrimitive.Parts components={{ Text: UserText }} />
    </div>
  </MessagePrimitive.Root>
);

/** Shown in an empty assistant message while the agent is still working. */
const Thinking: EmptyMessagePartComponent = ({ status }) => {
  const { t } = useTranslation();
  if (status.type !== "running") return null;
  return (
    <div className="flex items-center gap-2 py-1 text-muted-foreground text-sm">
      <span className="flex gap-1">
        <span className="size-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.3s]" />
        <span className="size-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.15s]" />
        <span className="size-1.5 animate-bounce rounded-full bg-current" />
      </span>
      {t("chat.thinking")}
    </div>
  );
};

const AssistantMessage: FC<{ agentName: string }> = ({ agentName }) => (
  <MessagePrimitive.Root className="group flex gap-3">
    <AgentAvatar agentName={agentName} className="mt-0.5 size-7 shrink-0" />
    <div className="min-w-0 flex-1 text-foreground text-sm">
      <MessagePrimitive.Parts
        components={{
          Text: MarkdownText,
          Reasoning: ReasoningPart,
          Empty: Thinking,
          tools: { Fallback: ToolCallPart },
          data: { by_name: DATA_PART_COMPONENTS },
        }}
      />
      <AssistantActionBar />
    </div>
  </MessagePrimitive.Root>
);

const AssistantActionBar: FC = () => {
  const { t } = useTranslation();
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      className="mt-1 flex gap-1 text-muted-foreground"
    >
      <Tooltip>
        <TooltipTrigger asChild>
          <ActionBarPrimitive.Copy asChild>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t("chat.copy")}
              className="group/copy size-7"
            >
              <Copy className="size-3.5 group-data-[copied]/copy:hidden" />
              <Check className="hidden size-3.5 group-data-[copied]/copy:block" />
            </Button>
          </ActionBarPrimitive.Copy>
        </TooltipTrigger>
        <TooltipContent>{t("chat.copy")}</TooltipContent>
      </Tooltip>
    </ActionBarPrimitive.Root>
  );
};
