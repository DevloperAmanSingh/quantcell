/**
 * Application sidebar built on the shadcn/ui Sidebar.
 *
 * Sections: workspace navigation, chat agents, and recent conversations
 * (previously hidden in a slide-out sheet). Collapses to an icon rail with
 * tooltips; Cmd/Ctrl+B toggles it via the shadcn SidebarProvider.
 */

import {
  CandlestickChart,
  House,
  MessageSquarePlus,
  MoreHorizontal,
  PanelLeft,
  Settings,
  Store,
  Trash2,
} from "lucide-react";
import { type FC, memo } from "react";
import { useTranslation } from "react-i18next";
import {
  NavLink,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router";
import { useGetAgentList } from "@/api/agent";
import {
  useDeleteConversation,
  useGetConversationList,
} from "@/api/conversation";
import { Logo } from "@/assets/svg";
import AgentAvatar from "@/components/shared/icon/agent-avatar";
import SvgIcon from "@/components/shared/icon/svg-icon";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupAction,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import { QUANTCELL_AGENT } from "@/constants/agent";

/** How many recent conversations to list before the list gets noisy. */
const RECENT_CHAT_LIMIT = 20;
const RECENT_CHAT_SKELETONS = 3;

function useActivePath() {
  const { pathname } = useLocation();
  const [searchParams] = useSearchParams();
  return {
    pathname,
    conversationId: searchParams.get("id") ?? "",
    /** True when the current route is `to` or one of its sub-pages. */
    isActive: (to: string) => pathname === to || pathname.startsWith(`${to}/`),
  };
}

const WorkspaceNav: FC = () => {
  const { t } = useTranslation();
  const { isActive } = useActivePath();
  const items = [
    { to: "/home", label: t("nav.home"), icon: House },
    {
      to: "/agent/StrategyAgent",
      label: t("nav.strategy"),
      icon: CandlestickChart,
    },
    { to: "/market", label: t("nav.market"), icon: Store },
  ];

  return (
    <SidebarGroup>
      <SidebarGroupLabel>{t("nav.workspace")}</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map((item) => (
            <SidebarMenuItem key={item.to}>
              <SidebarMenuButton
                asChild
                isActive={isActive(item.to)}
                tooltip={item.label}
              >
                <NavLink to={item.to}>
                  <item.icon />
                  <span>{item.label}</span>
                </NavLink>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
};

const AgentsNav: FC = () => {
  const { t } = useTranslation();
  const { isActive } = useActivePath();
  const { data: agentList = [] } = useGetAgentList({ enabled_only: "true" });

  const agents = [
    { name: QUANTCELL_AGENT.agent_name, label: t("nav.askQuantCell") },
    ...agentList.map((agent) => ({
      name: agent.agent_name,
      label: agent.display_name,
    })),
  ];

  return (
    <SidebarGroup>
      <SidebarGroupLabel>{t("nav.agents")}</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {agents.map((agent) => {
            const to = `/agent/${agent.name}`;
            return (
              <SidebarMenuItem key={agent.name}>
                <SidebarMenuButton
                  asChild
                  isActive={isActive(to)}
                  tooltip={agent.label}
                >
                  <NavLink to={to}>
                    <AgentAvatar
                      agentName={agent.name}
                      className="size-5 shrink-0 group-data-[collapsible=icon]:size-4"
                    />
                    <span>{agent.label}</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
};

const RecentChats: FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { conversationId } = useActivePath();
  const { data: conversations = [], isLoading } = useGetConversationList();
  const { mutateAsync: deleteConversation } = useDeleteConversation();

  const handleDelete = async (id: string) => {
    await deleteConversation(id);
    if (id === conversationId) navigate("/home");
  };

  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>{t("nav.recentChats")}</SidebarGroupLabel>
      <SidebarGroupAction asChild title={t("nav.newChat")}>
        <NavLink to={`/agent/${QUANTCELL_AGENT.agent_name}`}>
          <MessageSquarePlus />
          <span className="sr-only">{t("nav.newChat")}</span>
        </NavLink>
      </SidebarGroupAction>
      <SidebarGroupContent>
        <SidebarMenu>
          {isLoading &&
            Array.from({ length: RECENT_CHAT_SKELETONS }, (_, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton rows
              <SidebarMenuItem key={i}>
                <SidebarMenuSkeleton />
              </SidebarMenuItem>
            ))}
          {!isLoading && conversations.length === 0 && (
            <p className="px-2 py-1.5 text-muted-foreground text-xs">
              {t("chat.conversationList.empty")}
            </p>
          )}
          {conversations.slice(0, RECENT_CHAT_LIMIT).map((conversation) => (
            <SidebarMenuItem key={conversation.conversation_id}>
              <SidebarMenuButton
                asChild
                isActive={conversation.conversation_id === conversationId}
              >
                <NavLink
                  to={`/agent/${conversation.agent_name}?id=${conversation.conversation_id}`}
                >
                  <span>{conversation.title}</span>
                </NavLink>
              </SidebarMenuButton>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuAction showOnHover>
                    <MoreHorizontal />
                    <span className="sr-only">{t("nav.chatOptions")}</span>
                  </SidebarMenuAction>
                </DropdownMenuTrigger>
                <DropdownMenuContent side="right" align="start">
                  <DropdownMenuItem
                    variant="destructive"
                    onClick={() => handleDelete(conversation.conversation_id)}
                  >
                    <Trash2 />
                    {t("chat.action.delete")}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
};

const AppSidebar: FC = () => {
  const { t } = useTranslation();
  const { isActive } = useActivePath();
  const { toggleSidebar } = useSidebar();

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild size="lg" tooltip="QuantCell">
              <NavLink to="/home">
                <SvgIcon name={Logo} className="size-7! shrink-0" />
                <span className="font-semibold text-base group-data-[collapsible=icon]:hidden">
                  QuantCell
                </span>
              </NavLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <WorkspaceNav />
        <AgentsNav />
        <RecentChats />
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              asChild
              isActive={isActive("/setting")}
              tooltip={t("nav.setting")}
            >
              <NavLink to="/setting">
                <Settings />
                <span>{t("nav.setting")}</span>
              </NavLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton
              onClick={toggleSidebar}
              tooltip={t("nav.toggleSidebar")}
            >
              <PanelLeft />
              <span>{t("nav.toggleSidebar")}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
};

export default memo(AppSidebar);
