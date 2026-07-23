import { useResearchHistory } from "@/hooks/use-research-history";
import { Loader, Check, Trash2, Plus, Zap, TriangleAlert } from "lucide-react";

interface ResearchSidebarProps {
  onSelectSession: (threadId: string) => void;
  onNewSession: () => void;
  activeThreadId: string | null;
}

export function ResearchSidebar({ onSelectSession, onNewSession, activeThreadId }: ResearchSidebarProps) {
  const { sessions, deleteSession } = useResearchHistory();

  return (
    <div className="w-72 h-full border-r border-border/50 bg-secondary/20 flex flex-col relative z-20">
      <div className="p-4 border-b border-border/50">
        <button
          onClick={onNewSession}
          className="w-full flex items-center justify-center gap-2 bg-gradient-to-br from-[hsl(262,83%,58%)] to-[hsl(280,80%,65%)] text-white px-4 py-2.5 rounded-xl text-sm font-medium hover:opacity-90 transition-all hover:shadow-[0_4px_16px_hsl(262,83%,58%,0.3)]"
        >
          <Plus className="w-4 h-4" />
          New Research
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        <SessionList
          title="Working"
          icon={<Loader className="w-3.5 h-3.5 text-blue-400" />}
          sessions={sessions.filter((s) => s.status === "working")}
          onSelect={onSelectSession}
          onDelete={deleteSession}
          activeThreadId={activeThreadId}
        />

        <SessionList
          title="Completed"
          icon={<Check className="w-3.5 h-3.5 text-[hsl(142,71%,45%)]" />}
          sessions={sessions.filter((s) => s.status === "completed")}
          onSelect={onSelectSession}
          onDelete={deleteSession}
          activeThreadId={activeThreadId}
        />

        <SessionList
          title="Error"
          icon={<TriangleAlert className="w-3.5 h-3.5 text-red-500" />}
          sessions={sessions.filter((s) => s.status === "error")}
          onSelect={onSelectSession}
          onDelete={deleteSession}
          activeThreadId={activeThreadId}
        />
      </div>
    </div>
  );
}

function SessionList({
  title,
  icon,
  sessions,
  onSelect,
  onDelete,
  activeThreadId,
}: {
  title: string;
  icon: React.ReactNode;
  sessions: any[];
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  activeThreadId: string | null;
}) {
  if (sessions.length === 0) return null;

  return (
    <div>
      <div className="flex items-center gap-2 mb-3 px-2">
        {icon}
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          {title}
        </h3>
      </div>
      <div className="space-y-1">
        {sessions.map((session) => {
          const isActive = session.threadId === activeThreadId;
          return (
            <div
              key={session.threadId}
              className={`group flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition-all ${isActive
                ? "bg-secondary text-foreground"
                : "hover:bg-secondary/50 text-muted-foreground"
                }`}
              onClick={() => onSelect(session.threadId)}
            >
              <div className="truncate text-sm flex-1 mr-2 font-medium">
                {session.query}
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(session.threadId);
                  if (isActive) {
                    onNewSession();
                  }
                }}
                className={`p-1.5 rounded-md hover:bg-destructive/10 hover:text-destructive transition-colors ${isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                  }`}
                title="Delete session"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
