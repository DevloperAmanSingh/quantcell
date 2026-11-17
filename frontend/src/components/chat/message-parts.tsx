/**
 * Renderers for the non-text parts of an assistant message: reasoning,
 * tool calls, and QuantCell's custom data parts (errors, planner questions,
 * reports, sub-agent conversations, scheduled task controls).
 */

import type {
  DataMessagePartComponent,
  ReasoningMessagePartComponent,
  ToolCallMessagePartComponent,
} from "@assistant-ui/react";
import {
  AlertCircle,
  Brain,
  Check,
  ChevronDown,
  MessageCircleQuestion,
  Wrench,
} from "lucide-react";
import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ChatConversationRenderer,
  ReportRenderer,
  ScheduledTaskControllerRenderer,
} from "@/components/shared/renderer";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Spinner } from "@/components/ui/spinner";
import { CHAT_DATA_PART } from "@/lib/chat/thread-messages";
import { cn } from "@/lib/utils";
import { useMultiSection } from "@/provider/multi-section-provider";
import type { ChatItem } from "@/types/agent";

interface StepProps {
  icon: ReactNode;
  label: string;
  children?: ReactNode;
}

/** A compact, collapsible row used for both reasoning and tool steps. */
function Step({ icon, label, children }: StepProps) {
  const [open, setOpen] = useState(false);
  const hasDetails = children !== undefined && children !== null;

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className="my-1.5 rounded-lg border border-border bg-muted/40 text-sm"
    >
      <CollapsibleTrigger
        disabled={!hasDetails}
        className={cn(
          "flex w-full items-center gap-2 px-3 py-2 text-muted-foreground",
          hasDetails && "cursor-pointer hover:text-foreground",
        )}
      >
        {icon}
        <span className="flex-1 truncate text-left">{label}</span>
        {hasDetails && (
          <ChevronDown
            className={cn("size-4 transition-transform", open && "rotate-180")}
          />
        )}
      </CollapsibleTrigger>
      {hasDetails && (
        <CollapsibleContent className="border-border border-t px-3 py-2">
          {children}
        </CollapsibleContent>
      )}
    </Collapsible>
  );
}

export const ReasoningPart: ReasoningMessagePartComponent = ({
  text,
  status,
}) => {
  const { t } = useTranslation();
  const isRunning = status.type === "running";
  return (
    <Step
      icon={
        isRunning ? (
          <Spinner className="size-4" />
        ) : (
          <Brain className="size-4" />
        )
      }
      label={isRunning ? t("chat.reasoning.running") : t("chat.reasoning.done")}
    >
      <p className="whitespace-pre-wrap text-muted-foreground">{text}</p>
    </Step>
  );
};

function formatToolResult(result: unknown): string {
  if (typeof result === "string") return result;
  return JSON.stringify(result, null, 2);
}

export const ToolCallPart: ToolCallMessagePartComponent = ({
  toolName,
  result,
  status,
}) => {
  const { t } = useTranslation();
  const isRunning = status.type === "running";
  const hasOutput = result !== undefined && result !== null && result !== "";

  return (
    <Step
      icon={
        isRunning ? (
          <Spinner className="size-4" />
        ) : hasOutput ? (
          <Check className="size-4" />
        ) : (
          <Wrench className="size-4" />
        )
      }
      label={
        isRunning
          ? t("chat.tool.running", { name: toolName })
          : t("chat.tool.done", { name: toolName })
      }
    >
      {hasOutput ? (
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words text-muted-foreground text-xs">
          {formatToolResult(result)}
        </pre>
      ) : null}
    </Step>
  );
};

const ErrorPart: DataMessagePartComponent<{ message: string }> = ({ data }) => {
  const { t } = useTranslation();
  return (
    <Alert variant="destructive" className="my-2">
      <AlertCircle />
      <AlertTitle>{t("chat.error")}</AlertTitle>
      <AlertDescription>{data.message}</AlertDescription>
    </Alert>
  );
};

const PlanQuestionPart: DataMessagePartComponent<{ question: string }> = ({
  data,
}) => {
  const { t } = useTranslation();
  return (
    <div className="my-2 rounded-xl border border-sky-300/60 bg-sky-50 p-4 dark:border-sky-800 dark:bg-sky-950/40">
      <div className="mb-1.5 flex items-center gap-2 font-medium text-sky-900 text-sm dark:text-sky-200">
        <MessageCircleQuestion className="size-4" />
        {t("chat.planQuestion")}
      </div>
      <p className="whitespace-pre-wrap text-foreground text-sm">
        {data.question}
      </p>
      <p className="mt-2 text-muted-foreground text-xs">
        {t("chat.planQuestionHint")}
      </p>
    </div>
  );
};

const ReportPart: DataMessagePartComponent<ChatItem> = ({ data }) => {
  const { currentSection, openSection } = useMultiSection();
  return (
    <div className="my-2">
      <ReportRenderer
        content={data.payload.content}
        onOpen={() => openSection(data)}
        isActive={currentSection?.item_id === data.item_id}
      />
    </div>
  );
};

const SubagentConversationPart: DataMessagePartComponent<{
  content: string;
}> = ({ data }) => <ChatConversationRenderer content={data.content} />;

const ScheduledTaskControllerPart: DataMessagePartComponent<{
  content: string;
}> = ({ data }) => <ScheduledTaskControllerRenderer content={data.content} />;

export const DATA_PART_COMPONENTS = {
  [CHAT_DATA_PART.error]: ErrorPart,
  [CHAT_DATA_PART.planQuestion]: PlanQuestionPart,
  [CHAT_DATA_PART.report]: ReportPart,
  [CHAT_DATA_PART.subagentConversation]: SubagentConversationPart,
  [CHAT_DATA_PART.scheduledTaskController]: ScheduledTaskControllerPart,
} satisfies Record<string, DataMessagePartComponent>;
