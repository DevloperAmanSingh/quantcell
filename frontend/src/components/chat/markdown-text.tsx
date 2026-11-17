import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import { memo } from "react";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

/**
 * Markdown renderer for streamed assistant text.
 *
 * Raw HTML is intentionally not enabled (no rehype-raw): model output is
 * untrusted, and inside the Tauri shell injected markup would run with
 * access to the app's IPC bridge.
 */
function MarkdownTextImpl() {
  return (
    <MarkdownTextPrimitive
      remarkPlugins={[remarkGfm]}
      smooth
      className={cn(
        "prose prose-sm dark:prose-invert max-w-none",
        "prose-a:text-sky-600 dark:prose-a:text-sky-300",
        "prose-pre:bg-muted prose-pre:text-foreground",
        "prose-th:text-left prose-table:text-sm",
      )}
    />
  );
}

export const MarkdownText = memo(MarkdownTextImpl);
