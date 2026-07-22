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
  type SSEEvent,
} from "@/lib/api-client";

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
            // Skip supervisor reflection messages (internal reasoning)
            if (msg.content.startsWith("[Supervisor reflection]")) {
              continue;
            }
            newMessages.push({
              id: createMessageId(),
              role: "assistant",
              content: msg.content,
              agentName: msg.name || action.node,
              timestamp: new Date(),
              metadata: { node: action.node },
            });
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

    case "RESET":
      return { ...initialState };

    default:
      return state;
  }
}

// ===== Hook =====

export function useResearch() {
  const [state, dispatch] = useReducer(researchReducer, initialState);
  const abortControllerRef = useRef<AbortController | null>(null);

  const handleEvent = useCallback(
    (event: SSEEvent) => {
      switch (event.event) {
        case "init":
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

  return { state, startResearch, respond, retry, reset };
}
