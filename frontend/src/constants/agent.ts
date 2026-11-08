import {
  NewsAgentPng,
  QuantCellAgentPng,
  ResearchAgentPng,
  StrategyAgentPng,
} from "@/assets/png";
import {
  ChatConversationRenderer,
  MarkdownRenderer,
  ReasoningRenderer,
  ReportRenderer,
  ScheduledTaskControllerRenderer,
  ScheduledTaskRenderer,
  ToolCallRenderer,
} from "@/components/shared/renderer";
import { TimeUtils } from "@/lib/time";
import type { AgentComponentType, AgentInfo } from "@/types/agent";
import type { RendererComponent } from "@/types/renderer";

// component_type to section type
export const AGENT_SECTION_COMPONENT_TYPE = ["scheduled_task_result"] as const;

// multi section component type
export const AGENT_MULTI_SECTION_COMPONENT_TYPE = ["report"] as const;

// agent component type
export const AGENT_COMPONENT_TYPE = [
  "markdown",
  "reasoning",
  "tool_call",
  "subagent_conversation",
  "scheduled_task_controller",
  ...AGENT_SECTION_COMPONENT_TYPE,
  ...AGENT_MULTI_SECTION_COMPONENT_TYPE,
] as const;

/**
 * Component renderer mapping with automatic type inference
 */
export const COMPONENT_RENDERER_MAP: {
  [K in AgentComponentType]: RendererComponent<K>;
} = {
  scheduled_task_result: ScheduledTaskRenderer,
  scheduled_task_controller: ScheduledTaskControllerRenderer,
  report: ReportRenderer,
  reasoning: ReasoningRenderer,
  markdown: MarkdownRenderer,
  tool_call: ToolCallRenderer,
  subagent_conversation: ChatConversationRenderer,
};

export const AGENT_AVATAR_MAP: Record<string, string> = {
  QuantCellAgent: QuantCellAgentPng,
  ResearchAgent: ResearchAgentPng,
  NewsAgent: NewsAgentPng,
  StrategyAgent: StrategyAgentPng,
};

export const QUANTCELL_AGENT: AgentInfo = {
  agent_name: "QuantCellAgent",
  display_name: "QuantCell Agent",
  enabled: true,
  description:
    "QuantCell Agent is a super-agent that can help you manage different agents and tasks",
  created_at: TimeUtils.nowUTC().toISOString(),
  updated_at: TimeUtils.nowUTC().toISOString(),
  agent_metadata: {
    version: "1.0.0",
    author: "QuantCell",
    tags: ["quantcell", "super-agent"],
  },
};

// Trading symbols options
export const TRADING_SYMBOLS: string[] = [
  "BTC/USDT",
  "ETH/USDT",
  "SOL/USDT",
  "DOGE/USDT",
  "XRP/USDT",
];
