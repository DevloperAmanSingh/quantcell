import { MessageCircle, Settings } from "lucide-react";
import { type FC, memo } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import TagGroups from "@/components/shared/button/tag-groups";
import AgentAvatar from "@/components/shared/icon/agent-avatar";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { AgentInfo } from "@/types/agent";

interface ChatConversationHeaderProps {
  agent: AgentInfo;
}

const ChatConversationHeader: FC<ChatConversationHeaderProps> = ({ agent }) => {
  const { t } = useTranslation();
  return (
    <header className="flex h-14 w-full shrink-0 items-center justify-between gap-3 border-border border-b px-4">
      <div className="flex min-w-0 items-center gap-2.5">
        <AgentAvatar agentName={agent.agent_name} className="size-8 shrink-0" />
        <h1 className="truncate font-semibold text-foreground text-sm">
          {agent.display_name}
        </h1>
        <div className="hidden min-w-0 lg:block">
          <TagGroups tags={agent.agent_metadata.tags} />
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-2.5">
        <Link to=".">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="secondary"
                className="size-8 cursor-pointer rounded-lg hover:bg-muted"
                size="icon"
              >
                <MessageCircle size={16} className="text-foreground" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{t("chat.newConversation")}</TooltipContent>
          </Tooltip>
        </Link>
        <Link to="./config">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="secondary"
                className="size-8 cursor-pointer rounded-lg hover:bg-muted"
                size="icon"
              >
                <Settings size={16} className="text-foreground" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{t("chat.settings")}</TooltipContent>
          </Tooltip>
        </Link>
      </div>
    </header>
  );
};

export default memo(ChatConversationHeader);
