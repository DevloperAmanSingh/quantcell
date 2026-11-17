/**
 * Bridges QuantCell's SSE chat stream to an assistant-ui runtime.
 *
 * The existing agent store and SSE reducer stay the source of truth; this
 * hook only converts that state for assistant-ui (external store runtime)
 * and routes composer submissions back to the backend stream endpoint.
 */

import {
  type AppendMessage,
  type ThreadMessageLike,
  useExternalStoreRuntime,
} from "@assistant-ui/react";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo } from "react";
import { useLocation, useNavigate } from "react-router";
import { toast } from "sonner";
import { useGetConversationHistory, usePollTaskList } from "@/api/conversation";
import { API_QUERY_KEYS } from "@/constants/api";
import useSSE from "@/hooks/use-sse";
import { getServerUrl } from "@/lib/api-client";
import { toThreadMessages } from "@/lib/chat/thread-messages";
import { tracker } from "@/lib/tracker";
import {
  useAgentStoreActions,
  useCurrentConversation,
} from "@/store/agent-store";
import type { AgentStreamRequest, SSEData } from "@/types/agent";

const SYSTEM_ERROR_TOAST_MS = 30_000;

const identity = (message: ThreadMessageLike) => message;

function textOf(message: AppendMessage): string {
  return message.content
    .map((part) => (part.type === "text" ? part.text : ""))
    .join("")
    .trim();
}

interface UseAgentChatRuntimeOptions {
  agentName: string;
  conversationId: string;
}

export function useAgentChatRuntime({
  agentName,
  conversationId,
}: UseAgentChatRuntimeOptions) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const initialQuery: string | undefined = useLocation().state?.inputValue;

  const { curConversation, curConversationId } = useCurrentConversation();
  const {
    dispatchAgentStore,
    dispatchAgentStoreHistory,
    setCurConversationId,
  } = useAgentStoreActions();

  const { data: history } = useGetConversationHistory(conversationId);
  const { data: scheduledResults } = usePollTaskList(conversationId);

  useEffect(() => {
    if (curConversationId !== conversationId) {
      setCurConversationId(conversationId);
    }
  }, [conversationId, curConversationId, setCurConversationId]);

  // Replace local state with the persisted history whenever it (re)loads.
  useEffect(() => {
    if (!conversationId || !history?.length) return;
    dispatchAgentStoreHistory(conversationId, history, true);
  }, [conversationId, history, dispatchAgentStoreHistory]);

  // Scheduled task results arrive by polling, outside the live stream.
  useEffect(() => {
    if (!conversationId || !scheduledResults?.length) return;
    dispatchAgentStoreHistory(conversationId, scheduledResults);
  }, [conversationId, scheduledResults, dispatchAgentStoreHistory]);

  const handleStreamEvent = useCallback(
    (sseData: SSEData) => {
      dispatchAgentStore(sseData);
      const { event, data } = sseData;
      switch (event) {
        case "conversation_started":
          navigate(`/agent/${agentName}?id=${data.conversation_id}`, {
            replace: true,
          });
          queryClient.invalidateQueries({
            queryKey: API_QUERY_KEYS.CONVERSATION.conversationList,
          });
          break;
        case "component_generator":
          if (data.payload.component_type === "subagent_conversation") {
            queryClient.invalidateQueries({
              queryKey: API_QUERY_KEYS.CONVERSATION.conversationList,
            });
          }
          break;
        case "system_failed":
          toast.error(data.payload.content, {
            closeButton: true,
            duration: SYSTEM_ERROR_TOAST_MS,
          });
          break;
        default:
          break;
      }
    },
    [agentName, dispatchAgentStore, navigate, queryClient],
  );

  const { connect, close, isStreaming } = useSSE({
    url: getServerUrl("/agents/stream"),
    handlers: {
      onData: (sseData: SSEData) => {
        handleStreamEvent(sseData);
        if (sseData.event === "done") close();
      },
      onError: (error: Error) => {
        toast.error(`Connection to the agent failed: ${error.message}`);
      },
    },
  });

  const send = useCallback(
    async (query: string) => {
      const request: AgentStreamRequest = {
        query,
        agent_name: agentName,
        conversation_id: conversationId,
      };
      tracker.send("use", { agent_name: agentName });
      await connect(JSON.stringify(request));
    },
    [agentName, conversationId, connect],
  );

  // A query typed on the home page arrives via router state; send it once.
  useEffect(() => {
    if (!initialQuery) return;
    navigate(".", { replace: true, state: {} });
    void send(initialQuery);
  }, [initialQuery, navigate, send]);

  const messages = useMemo(
    () => toThreadMessages(curConversation, { isStreaming }),
    [curConversation, isStreaming],
  );

  const runtime = useExternalStoreRuntime<ThreadMessageLike>({
    messages,
    convertMessage: identity,
    isRunning: isStreaming,
    onNew: async (message) => {
      const query = textOf(message);
      if (query) await send(query);
    },
  });

  return { runtime, conversation: curConversation, isStreaming };
}
