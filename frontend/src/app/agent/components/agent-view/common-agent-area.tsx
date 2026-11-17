import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { type FC, memo } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useSearchParams } from "react-router";
import { useGetAgentInfo } from "@/api/agent";
import { Thread } from "@/components/chat/thread";
import { useAgentChatRuntime } from "@/hooks/use-agent-chat-runtime";
import {
  MultiSectionProvider,
  useMultiSection,
} from "@/provider/multi-section-provider";
import type {
  AgentInfo,
  AgentViewProps,
  MultiSectionComponentType,
  SectionComponentType,
} from "@/types/agent";
import {
  ChatConversationHeader,
  ChatMultiSectionComponent,
  ChatSectionComponent,
} from "../chat-conversation";

interface AgentChatProps {
  agent: AgentInfo;
}

const AgentChat: FC<AgentChatProps> = ({ agent }) => {
  const { t } = useTranslation();
  const conversationId = useSearchParams()[0].get("id") ?? "";
  const { runtime, conversation } = useAgentChatRuntime({
    agentName: agent.agent_name,
    conversationId,
  });
  const { currentSection } = useMultiSection();

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <section className="flex min-w-0 flex-1 flex-col">
          <ChatConversationHeader agent={agent} />
          <div className="min-h-0 flex-1">
            <Thread
              agentName={agent.agent_name}
              welcomeTitle={t("agent.welcome", { name: agent.display_name })}
              welcomeDescription={agent.description}
            />
          </div>
        </section>

        {/* Scheduled task results live beside the chat, not inside it. */}
        {conversation &&
          Object.entries(conversation.sections).map(
            ([componentType, threadView]) => (
              <ChatSectionComponent
                key={componentType}
                componentType={componentType as SectionComponentType}
                threadView={threadView}
              />
            ),
          )}

        {currentSection && (
          <section className="flex flex-1 flex-col border-border border-l py-4">
            <div className="scroll-container px-5">
              <ChatMultiSectionComponent
                componentType={
                  currentSection.component_type as MultiSectionComponentType
                }
                content={currentSection.payload.content}
              />
            </div>
          </section>
        )}
      </div>
    </AssistantRuntimeProvider>
  );
};

const CommonAgentArea: FC<AgentViewProps> = ({ agentName }) => {
  const { data: agent, isLoading } = useGetAgentInfo({ agentName });

  if (isLoading) return null;
  if (!agent) return <Navigate to="/" replace />;

  return (
    <MultiSectionProvider>
      <AgentChat agent={agent} />
    </MultiSectionProvider>
  );
};

export default memo(CommonAgentArea);
