import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface ResearchSession {
  threadId: string;
  researchId: string;
  query: string;
  status: "working" | "completed" | "error";
  updatedAt: number;
}

interface ResearchHistoryState {
  sessions: ResearchSession[];
  addSession: (session: ResearchSession) => void;
  updateSessionStatus: (threadId: string, status: ResearchSession["status"]) => void;
  deleteSession: (threadId: string) => void;
}

export const useResearchHistory = create<ResearchHistoryState>()(
  persist(
    (set) => ({
      sessions: [],
      addSession: (session) =>
        set((state) => {
          // Remove existing session if same threadId is re-added
          const filtered = state.sessions.filter((s) => s.threadId !== session.threadId);
          return { sessions: [session, ...filtered] };
        }),
      updateSessionStatus: (threadId, status) =>
        set((state) => ({
          sessions: state.sessions.map((session) =>
            session.threadId === threadId
              ? { ...session, status, updatedAt: Date.now() }
              : session
          ),
        })),
      deleteSession: (threadId) =>
        set((state) => ({
          sessions: state.sessions.filter((session) => session.threadId !== threadId),
        })),
    }),
    {
      name: 'research-history-storage',
    }
  )
);
