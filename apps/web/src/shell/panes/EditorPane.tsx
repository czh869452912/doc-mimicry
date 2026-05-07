import { X } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { ArtifactTab } from "../editor/tabs/ArtifactTab";
import { DiffTab } from "../editor/tabs/DiffTab";
import { DraftTab } from "../editor/tabs/DraftTab";
import { FileTab } from "../editor/tabs/FileTab";
import { VersionTab } from "../editor/tabs/VersionTab";
import type { EditorTab } from "../editor/useTabs";

interface EditorPaneProps {
  activeSessionId: string | null;
  activeTabId: string;
  draft: string;
  draftAutoSaveEnabled?: boolean;
  tabs: EditorTab[];
  taskId: string | null;
  onCloseTab: (tabId: string) => void;
  onDraftChange: (draft: string) => void;
  onReviseSelection?: (selectedText: string) => void;
  onSendSelectionToChat?: (selectedText: string) => void;
  onTabChange: (tabId: string) => void;
}

export function EditorPane({
  activeSessionId,
  activeTabId,
  draft,
  draftAutoSaveEnabled = true,
  onCloseTab,
  onDraftChange,
  onReviseSelection,
  onSendSelectionToChat,
  onTabChange,
  tabs,
  taskId,
}: EditorPaneProps) {
  return (
    <Tabs className="editor-pane" value={activeTabId} onValueChange={onTabChange}>
      <TabsList className="editor-tabs" aria-label="Editor tabs">
        {tabs.map((tab) => (
          <TabsTrigger className="editor-tab-trigger" key={tab.id} value={tab.id}>
            <span>{tab.id === "draft" ? "📌 " : ""}</span>
            <span>{tab.title}</span>
            {tab.id !== "draft" && (
              <button
                className="tab-close"
                type="button"
                aria-label={`Close ${tab.title}`}
                onClick={(event) => {
                  event.stopPropagation();
                  onCloseTab(tab.id);
                }}
              >
                <X size={12} />
              </button>
            )}
          </TabsTrigger>
        ))}
      </TabsList>
      {tabs.map((tab) => (
        <TabsContent className="editor-tab-content" key={tab.id} value={tab.id}>
          {renderTab(tab, {
            activeSessionId,
            draft,
            draftAutoSaveEnabled,
            onDraftChange,
            onReviseSelection,
            onSendSelectionToChat,
            taskId,
          })}
        </TabsContent>
      ))}
    </Tabs>
  );
}

function renderTab(
  tab: EditorTab,
  props: Pick<
    EditorPaneProps,
    | "activeSessionId"
    | "draft"
    | "draftAutoSaveEnabled"
    | "onDraftChange"
    | "onReviseSelection"
    | "onSendSelectionToChat"
    | "taskId"
  >,
) {
  if (tab.kind === "draft") {
    return (
      <DraftTab
        activeSessionId={props.activeSessionId}
        autoSaveEnabled={props.draftAutoSaveEnabled}
        draft={props.draft}
        taskId={props.taskId}
        onDraftChange={props.onDraftChange}
        onReviseSelection={props.onReviseSelection}
        onSendSelectionToChat={props.onSendSelectionToChat}
      />
    );
  }
  if (tab.kind === "file") return <FileTab content={tab.content} path={tab.path} />;
  if (tab.kind === "version") return <VersionTab content={tab.content} />;
  if (tab.kind === "artifact") return <ArtifactTab content={tab.content} path={tab.path} />;
  return <DiffTab left={tab.left} leftTitle={tab.leftTitle} right={tab.right} rightTitle={tab.rightTitle} />;
}
