import { describe, expect, test } from "bun:test";
import { batchUpdateAgentConversationsStore } from "@/lib/agent-store";
import type { SSEData } from "@/types/agent";
import { toThreadMessages } from "./thread-messages";

const CONV = "conv-1";

function base(thread: string, task: string, item: string) {
  return {
    conversation_id: CONV,
    thread_id: thread,
    task_id: task,
    item_id: item,
    metadata: {},
  };
}

function buildConversation(events: SSEData[]) {
  return batchUpdateAgentConversationsStore({}, CONV, events)[CONV] ?? null;
}

const userTurn = (thread: string, query: string): SSEData => ({
  event: "thread_started",
  data: {
    ...base(thread, "ask", `${thread}-q`),
    role: "user",
    payload: { content: query },
  },
});

const chunk = (thread: string, item: string, content: string): SSEData => ({
  event: "message_chunk",
  data: {
    ...base(thread, "task-a", item),
    role: "agent",
    payload: { content },
  },
});

describe("toThreadMessages", () => {
  test("returns no messages for an empty conversation", () => {
    expect(toThreadMessages(null, { isStreaming: false })).toEqual([]);
  });

  test("turns one thread into a user and a merged assistant message", () => {
    const conversation = buildConversation([
      userTurn("t1", "Summarize AAPL 10-K"),
      chunk("t1", "m1", "Apple "),
      chunk("t1", "m1", "grew revenue."),
    ]);
    const messages = toThreadMessages(conversation, { isStreaming: false });

    expect(messages).toHaveLength(2);
    expect(messages[0]).toMatchObject({
      role: "user",
      content: [{ type: "text", text: "Summarize AAPL 10-K" }],
    });
    expect(messages[1]).toMatchObject({
      role: "assistant",
      status: { type: "complete" },
      content: [{ type: "text", text: "Apple grew revenue." }],
    });
  });

  test("maps reasoning, tool calls and errors to their own parts", () => {
    const conversation = buildConversation([
      userTurn("t1", "Check filings"),
      {
        event: "reasoning",
        data: {
          ...base("t1", "task-a", "r1"),
          role: "agent",
          payload: { content: "Looking up" },
        },
      },
      {
        event: "tool_call_completed",
        data: {
          ...base("t1", "task-a", "tool-1"),
          role: "agent",
          payload: {
            tool_call_id: "tool-1",
            tool_name: "fetch_10k",
            tool_result: "10-K text",
          },
        },
      },
      {
        event: "tool_call_started",
        data: {
          ...base("t1", "task-a", "tool-2"),
          role: "agent",
          payload: { tool_call_id: "tool-2", tool_name: "fetch_13f" },
        },
      },
      {
        event: "task_failed",
        data: {
          ...base("t1", "task-a", "e1"),
          role: "agent",
          payload: { content: "Rate limited" },
        },
      },
    ]);
    const [, assistant] = toThreadMessages(conversation, {
      isStreaming: false,
    });
    const parts = assistant.content as readonly { type: string }[];

    expect(parts.map((p) => p.type)).toEqual([
      "reasoning",
      "tool-call",
      "tool-call",
      "data-error",
    ]);
    expect(parts[1]).toMatchObject({
      toolName: "fetch_10k",
      result: "10-K text",
    });
    // A tool that never reported back is closed once the turn is over.
    expect(parts[2]).toMatchObject({ toolName: "fetch_13f", result: null });
    expect(parts[3]).toMatchObject({ data: { message: "Rate limited" } });
  });

  test("marks a planner question as its own part", () => {
    const conversation = buildConversation([
      userTurn("t1", "Alert me daily"),
      {
        event: "plan_require_user_input",
        data: {
          ...base("t1", "plan", "p1"),
          role: "agent",
          payload: { content: "Which time?" },
        },
      },
    ]);
    const [, assistant] = toThreadMessages(conversation, {
      isStreaming: false,
    });

    expect(assistant.content).toEqual([
      {
        type: "data-plan_question",
        id: "p1",
        data: { question: "Which time?" },
      },
    ]);
  });

  test("leaves only the latest turn running while streaming", () => {
    const conversation = buildConversation([
      userTurn("t1", "First"),
      chunk("t1", "m1", "Done."),
      userTurn("t2", "Second"),
    ]);
    const messages = toThreadMessages(conversation, { isStreaming: true });

    expect(messages.map((m) => m.role)).toEqual([
      "user",
      "assistant",
      "user",
      "assistant",
    ]);
    expect(messages[1].status).toEqual({ type: "complete", reason: "unknown" });
    // The live turn has no explicit status so assistant-ui derives "running".
    expect(messages[3].status).toBeUndefined();
    expect(messages[3].content).toEqual([]);
  });
});
