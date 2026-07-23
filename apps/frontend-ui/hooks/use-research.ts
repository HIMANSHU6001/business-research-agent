"use client";

import { useReducer, useCallback, useRef } from "react";
import type {
  ResearchState,
  ChatMessage,
  ResearchPhase,
  SSEInterruptEvent,
  SSENodeUpdateEvent,
} from "@/lib/types";
import { NODE_DISPLAY_NAMES } from "@/lib/types";
import {
  startResearch as apiStartResearch,
  respondToInterrupt as apiRespondToInterrupt,
  resumeResearch as apiResumeResearch,
  pauseResearchApi,
  getResearchState,
  type SSEEvent,
} from "@/lib/api-client";
import { useResearchHistory } from "./use-research-history";

// ===== Reducer Actions =====

type Action =
  | { type: "SET_THREAD"; threadId: string; researchId: string }
  | { type: "ADD_USER_MESSAGE"; content: string }
  | { type: "NODE_UPDATE"; node: string; data: SSENodeUpdateEvent["data"] }
  | { type: "INTERRUPT"; interrupt: SSEInterruptEvent }
  | {
    type: "COMPLETE";
    finalReport: string;
  }
  | { type: "ERROR"; message: string; traceback?: string }
  | { type: "STREAMING_START" }
  | { type: "STREAMING_END" }
  | { type: "HYDRATE"; state: Partial<ResearchState> }
  | { type: "RESET" };

// ===== Initial State =====

const initialState: ResearchState = {
  threadId: null,
  researchId: null,
  phase: "idle",
  messages: [],
  isStreaming: false,
  error: null,
  errorTraceback: null,
  researchBrief: null,
  selectedFramework: null,
  activeNode: null,
  currentTask: null,
  finalReport: null,
  pendingInterrupt: null,
};

// ===== Helper =====

let messageCounter = 0;
function createMessageId(): string {
  return `msg-${Date.now()}-${messageCounter++}`;
}

function phaseFromNodeName(nodeName: string): ResearchPhase {
  if (
    nodeName.startsWith("clarify") ||
    nodeName.startsWith("write_research") ||
    nodeName.startsWith("review_research")
  ) {
    return "scoping";
  }
  if (
    nodeName.includes("collection") ||
    nodeName === "financial_agent" ||
    nodeName === "macro_agent" ||
    nodeName === "trends_agent"
  ) {
    return "collection";
  }
  if (
    nodeName.includes("analysis") ||
    nodeName === "quantitative_agent" ||
    nodeName === "qualitative_agent"
  ) {
    return "analysis";
  }
  return "scoping";
}

// ===== Reducer =====

function researchReducer(
  state: ResearchState,
  action: Action
): ResearchState {
  switch (action.type) {
    case "SET_THREAD":
      return {
        ...state,
        threadId: action.threadId,
        researchId: action.researchId,
        phase: "scoping",
      };

    case "ADD_USER_MESSAGE":
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: createMessageId(),
            role: "user",
            content: action.content,
            timestamp: new Date(),
          },
        ],
        pendingInterrupt: null,
      };

    case "NODE_UPDATE": {
      const newMessages: ChatMessage[] = [];
      const nodeData = action.data;

      // Extract AI messages from the node update
      if (nodeData.messages) {
        for (const msg of nodeData.messages) {
          if (msg.type === "ai" && msg.content) {
            // Normalize content to string to avoid TypeError
            const contentStr = typeof msg.content === "string"
              ? msg.content
              : Array.isArray(msg.content)
                ? msg.content.map((c: any) => c.text || JSON.stringify(c)).join("\n")
                : JSON.stringify(msg.content);

            // Check for supervisor reflection messages
            if (contentStr.startsWith("[Supervisor reflection]")) {
              const thoughtContent = contentStr.replace("[Supervisor reflection]", "").trim();
              newMessages.push({
                id: createMessageId(),
                role: "thought",
                content: thoughtContent,
                agentName: msg.name || action.node,
                timestamp: new Date(),
                metadata: { node: action.node },
              });
            } else {
              newMessages.push({
                id: createMessageId(),
                role: "assistant",
                content: contentStr,
                agentName: msg.name || action.node,
                timestamp: new Date(),
                metadata: { node: action.node },
              });
            }
          }
        }
      }

      // Add a progress message for the node itself (if no AI message was added)
      if (newMessages.length === 0) {
        const displayName =
          NODE_DISPLAY_NAMES[action.node] || action.node;
        newMessages.push({
          id: createMessageId(),
          role: "progress",
          content: `${displayName} is processing...`,
          agentName: action.node,
          timestamp: new Date(),
          metadata: { node: action.node },
        });
      }

      // Determine new phase from node name or state data
      let newPhase = state.phase;
      if (nodeData.current_phase) {
        const cp = nodeData.current_phase;
        if (cp === "collection") newPhase = "collection";
        else if (cp === "analysis") newPhase = "analysis";
        else if (cp === "scoping_review") newPhase = "scoping_review";
        else if (cp === "complete") newPhase = "complete";
        else if (cp === "scoping") newPhase = "scoping";
      } else {
        newPhase = phaseFromNodeName(action.node);
      }

      return {
        ...state,
        messages: [...state.messages, ...newMessages],
        activeNode: action.node,
        currentTask: nodeData.agent_task || nodeData.next_agent || state.currentTask,
        phase: newPhase,
        researchBrief: nodeData.research_brief || state.researchBrief,
        selectedFramework:
          nodeData.selected_framework || state.selectedFramework,
      };
    }

    case "INTERRUPT":
      return {
        ...state,
        pendingInterrupt: action.interrupt,
        isStreaming: false,
        phase:
          action.interrupt.type === "brief_review"
            ? "scoping_review"
            : state.phase,
      };

    case "COMPLETE":
      return {
        ...state,
        phase: "complete",
        isStreaming: false,
        finalReport: action.finalReport,
        activeNode: null,
        currentTask: null,
        pendingInterrupt: null,
      };

    case "ERROR":
      return {
        ...state,
        phase: "error",
        isStreaming: false,
        error: action.message,
        errorTraceback: action.traceback || null,
        activeNode: null,
        currentTask: null,
      };

    case "STREAMING_START":
      return {
        ...state,
        isStreaming: true,
        error: null,
        errorTraceback: null,
      };

    case "STREAMING_END":
      return {
        ...state,
        isStreaming: false,
      };

    case "HYDRATE":
      return {
        ...state,
        ...action.state,
      };

    case "RESET":
      return { ...initialState };

    default:
      return state;
  }
}

// ===== Hook =====

import { useEffect } from "react";

export function useResearch() {
  const [state, dispatch] = useReducer(researchReducer, initialState);
  const abortControllerRef = useRef<AbortController | null>(null);

  const addSession = useResearchHistory((s) => s.addSession);
  const updateSessionStatus = useResearchHistory((s) => s.updateSessionStatus);
  const currentQueryRef = useRef<string>("");

  useEffect(() => {
    if (state.threadId) {
      if (state.phase === "complete") {
        updateSessionStatus(state.threadId, "completed");
      } else if (state.phase === "error") {
        updateSessionStatus(state.threadId, "error");
      }
    }
  }, [state.threadId, state.phase, updateSessionStatus]);

  const handleEvent = useCallback(
    (event: SSEEvent) => {
      switch (event.event) {
        case "init":
          addSession({
            threadId: event.data.thread_id,
            researchId: event.data.research_id,
            query: currentQueryRef.current,
            status: "working",
            updatedAt: Date.now(),
          });
          dispatch({
            type: "SET_THREAD",
            threadId: event.data.thread_id,
            researchId: event.data.research_id,
          });
          break;

        case "node_update":
          dispatch({
            type: "NODE_UPDATE",
            node: event.data.node,
            data: event.data.data,
          });
          break;

        case "interrupt":
          dispatch({ type: "INTERRUPT", interrupt: event.data });
          break;

        case "error":
          dispatch({
            type: "ERROR",
            message: event.data.message,
            traceback: event.data.traceback,
          });
          break;

        case "complete":
          dispatch({
            type: "COMPLETE",
            finalReport: event.data.final_report,
          });
          break;
      }
    },
    []
  );

  const startResearch = useCallback(
    async (query: string) => {
      // Cancel any existing stream
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      currentQueryRef.current = query;

      dispatch({ type: "RESET" });
      dispatch({ type: "ADD_USER_MESSAGE", content: query });
      dispatch({ type: "STREAMING_START" });

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        await apiStartResearch(query, handleEvent, controller.signal);
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          dispatch({
            type: "ERROR",
            message: (err as Error).message,
          });
        }
      } finally {
        dispatch({ type: "STREAMING_END" });
        abortControllerRef.current = null;
      }
    },
    [handleEvent]
  );

  const respond = useCallback(
    async (message: string) => {
      if (!state.threadId) return;

      dispatch({ type: "ADD_USER_MESSAGE", content: message });
      dispatch({ type: "STREAMING_START" });

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        await apiRespondToInterrupt(
          state.threadId,
          message,
          handleEvent,
          controller.signal
        );
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          dispatch({
            type: "ERROR",
            message: (err as Error).message,
          });
        }
      } finally {
        dispatch({ type: "STREAMING_END" });
        abortControllerRef.current = null;
      }
    },
    [state.threadId, handleEvent]
  );

  const retry = useCallback(async () => {
    // Retry by re-sending the last user message
    const lastUserMessage = [...state.messages]
      .reverse()
      .find((m) => m.role === "user");
    if (!lastUserMessage) return;

    if (state.threadId) {
      // Research was started, retry by responding
      dispatch({
        type: "STREAMING_START",
      });
      // Clear error
      dispatch({
        type: "NODE_UPDATE",
        node: "retry",
        data: {},
      });

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        await apiRespondToInterrupt(
          state.threadId,
          lastUserMessage.content,
          handleEvent,
          controller.signal
        );
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          dispatch({
            type: "ERROR",
            message: (err as Error).message,
          });
        }
      } finally {
        dispatch({ type: "STREAMING_END" });
        abortControllerRef.current = null;
      }
    } else {
      // No thread yet — retry start
      await startResearch(lastUserMessage.content);
    }
  }, [state.messages, state.threadId, handleEvent, startResearch]);

  const reset = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    dispatch({ type: "RESET" });
  }, []);

  const loadResearch = useCallback(async (threadId: string) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Instead of RESET, immediately put into a loading state within ChatContainer
    dispatch({
      type: "HYDRATE",
      state: {
        threadId,
        phase: "scoping",
        messages: [],
        isStreaming: true,
        error: null,
        finalReport: null,
        activeNode: null,
        currentTask: null,
        pendingInterrupt: null
      }
    });

    try {
      const backendState = await getResearchState(threadId);

      if ("error" in backendState) {
        dispatch({ type: "ERROR", message: backendState.error as string, traceback: backendState.traceback });
        return;
      }

      let mappedMessages: ChatMessage[] = backendState.messages.map((m: any, i: number) => {
        const isThought = typeof m.content === "string" && m.content.startsWith("[Supervisor reflection]");
        const content = isThought ? m.content.replace("[Supervisor reflection]", "").trim() : m.content;

        return {
          id: `hydrated-${i}`,
          role: m.type === "human" ? "user" : (isThought ? "thought" : "assistant"),
          content: content,
          agentName: m.name || undefined,
          timestamp: new Date(),
        };
      });

      // If no messages were returned (e.g. graph failed early), try to reconstruct the user message
      if (mappedMessages.length === 0) {
        const historySession = useResearchHistory.getState().sessions.find(s => s.threadId === threadId);
        if (historySession) {
          mappedMessages.push({
            id: `hydrated-fallback`,
            role: "user",
            content: historySession.query,
            timestamp: new Date(),
          });
        }
      }

      let phase = (backendState.current_phase as ResearchPhase) || "scoping";
      if (backendState.is_interrupted) {
        phase = backendState.interrupt_info?.type === "brief_review" ? "scoping_review" : phase;
      }

      dispatch({
        type: "HYDRATE",
        state: {
          threadId: backendState.thread_id,
          researchId: backendState.research_id,
          phase: phase,
          messages: mappedMessages,
          activeNode: null,
          currentTask: null,
          researchBrief: backendState.research_brief,
          selectedFramework: backendState.selected_framework,
          pendingInterrupt: backendState.interrupt_info,
          finalReport: backendState.analysis_reports?.[backendState.analysis_reports.length - 1] || null,
        }
      });
    } catch (err) {
      dispatch({ type: "ERROR", message: (err as Error).message });
    } finally {
      dispatch({ type: "STREAMING_END" });
    }
  }, []);

  const pauseResearch = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (state.threadId) {
      pauseResearchApi(state.threadId).catch(console.error);
    }
    dispatch({ type: "STREAMING_END" });
  }, [state.threadId]);

  const resumeResearch = useCallback(async () => {
    if (!state.threadId) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    dispatch({ type: "STREAMING_START" });
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await apiResumeResearch(state.threadId, handleEvent, controller.signal);
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        dispatch({ type: "ERROR", message: (err as Error).message });
      }
    } finally {
      dispatch({ type: "STREAMING_END" });
      abortControllerRef.current = null;
    }
  }, [state.threadId, handleEvent]);

  return { state, startResearch, respond, retry, reset, loadResearch, pauseResearch, resumeResearch };
}
