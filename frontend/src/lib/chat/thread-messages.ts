/**
 * Converts QuantCell's conversation store into assistant-ui messages.
 *
 * The backend streams a conversation as threads (one per user turn), each
 * holding tasks (one per agent run) that hold render items. assistant-ui
 * expects a flat list of user/assistant messages made of typed parts, so
 * every thread becomes one user message plus one assistant message.
 */

import type { ThreadMessageLike } from "@assistant-ui/react";
import { parse } from "best-effort-json-parser";
import type { ChatItem, ConversationView, ThreadView } from "@/types/agent";

type MessagePart = Exclude<ThreadMessageLike["content"], string>[number];

/** Names of the custom data parts rendered by the chat UI. */
export const CHAT_DATA_PART = {
  error: "error",
  planQuestion: "plan_question",
  report: "report",
  subagentConversation: "subagent_conversation",
  scheduledTaskController: "scheduled_task_controller",
} as const;

const ERROR_EVENTS = new Set(["task_failed", "plan_failed", "system_failed"]);

const COMPLETE_STATUS = { type: "complete", reason: "unknown" } as const;

export interface ToThreadMessagesOptions {
  /** True while the SSE stream for the latest turn is open. */
  isStreaming: boolean;
}

function parseJson<T>(raw: string): Partial<T> {
  const parsed: unknown = parse(raw);
  return parsed && typeof parsed === "object" ? (parsed as Partial<T>) : {};
}

function markdownItemToPart(item: ChatItem): MessagePart | null {
  const content = item.payload.content;
  if (item.source_event && ERROR_EVENTS.has(item.source_event)) {
    return {
      type: `data-${CHAT_DATA_PART.error}`,
      id: item.item_id,
      data: { message: content },
    };
  }
  if (item.source_event === "plan_require_user_input") {
    return {
      type: `data-${CHAT_DATA_PART.planQuestion}`,
      id: item.item_id,
      data: { question: content },
    };
  }
  if (!content) return null;
  return { type: "text", text: content };
}

function toolCallItemToPart(item: ChatItem, isRunning: boolean): MessagePart {
  const payload = parseJson<{ tool_name: string; tool_result: string }>(
    item.payload.content,
  );
  const hasResult = payload.tool_result !== undefined;
  return {
    type: "tool-call",
    toolCallId: item.item_id,
    toolName: payload.tool_name ?? "tool",
    args: {},
    // A missing result means "still running" to assistant-ui. Once the turn
    // has finished, a tool that never reported back is closed with null so
    // it is not shown as waiting for user action.
    result: hasResult ? payload.tool_result : isRunning ? undefined : null,
  };
}

function itemToPart(item: ChatItem, isRunning: boolean): MessagePart | null {
  if (!item.payload) return null;
  switch (item.component_type) {
    case "markdown":
      return markdownItemToPart(item);
    case "reasoning": {
      const { content } = parseJson<{ content: string }>(item.payload.content);
      return content ? { type: "reasoning", text: content } : null;
    }
    case "tool_call":
      return toolCallItemToPart(item, isRunning);
    case "report":
      return {
        type: `data-${CHAT_DATA_PART.report}`,
        id: item.item_id,
        data: item,
      };
    case "subagent_conversation":
      return {
        type: `data-${CHAT_DATA_PART.subagentConversation}`,
        id: item.item_id,
        data: { content: item.payload.content },
      };
    case "scheduled_task_controller":
      return {
        type: `data-${CHAT_DATA_PART.scheduledTaskController}`,
        id: item.item_id,
        data: { content: item.payload.content },
      };
    default:
      return null;
  }
}

function threadToMessages(
  threadId: string,
  thread: ThreadView,
  isRunning: boolean,
): ThreadMessageLike[] {
  const userParts: MessagePart[] = [];
  const assistantParts: MessagePart[] = [];

  for (const task of Object.values(thread.tasks)) {
    for (const item of task.items) {
      if (item.role === "user") {
        if (item.payload?.content) {
          userParts.push({ type: "text", text: item.payload.content });
        }
        continue;
      }
      const part = itemToPart(item, isRunning);
      if (part) assistantParts.push(part);
    }
  }

  const messages: ThreadMessageLike[] = [];
  if (userParts.length > 0) {
    messages.push({ id: `${threadId}:user`, role: "user", content: userParts });
  }
  // While running, keep an (possibly empty) assistant message so the UI can
  // show a thinking indicator before the first token arrives.
  if (assistantParts.length > 0 || isRunning) {
    messages.push({
      id: `${threadId}:assistant`,
      role: "assistant",
      content: assistantParts,
      // Leave status unset on the live turn so assistant-ui derives
      // "running" from isRunning; finished turns are marked complete.
      ...(isRunning ? {} : { status: COMPLETE_STATUS }),
    });
  }
  return messages;
}

export function toThreadMessages(
  conversation: ConversationView | null,
  { isStreaming }: ToThreadMessagesOptions,
): ThreadMessageLike[] {
  if (!conversation) return [];
  const threadEntries = Object.entries(conversation.threads);
  return threadEntries.flatMap(([threadId, thread], index) =>
    threadToMessages(
      threadId,
      thread,
      isStreaming && index === threadEntries.length - 1,
    ),
  );
}
