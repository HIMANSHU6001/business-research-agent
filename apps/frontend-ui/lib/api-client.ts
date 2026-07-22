import { Client } from "@langchain/langgraph-sdk";
import type {
  SSEInitEvent,
  SSENodeUpdateEvent,
  SSEInterruptEvent,
  SSEErrorEvent,
  SSECompleteEvent,
  BackendStateResponse,
} from "./types";

export type SSEEvent =
  | { event: "init"; data: SSEInitEvent }
  | { event: "node_update"; data: SSENodeUpdateEvent }
  | { event: "interrupt"; data: SSEInterruptEvent }
  | { event: "error"; data: SSEErrorEvent }
  | { event: "complete"; data: SSECompleteEvent };

const ASSISTANT_ID = "research";

function getClient(): Client {
  // Use relative '/api' endpoint when running in browser (Next.js proxy rewrite)
  // or fall back to process.env.NEXT_PUBLIC_LANGGRAPH_API_URL or http://localhost:8123
  const apiUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/api`
      : process.env.NEXT_PUBLIC_LANGGRAPH_API_URL || "http://localhost:2024";

  return new Client({ apiUrl });
}

function detectInterruptType(values: Record<string, any>): SSEInterruptEvent {
  const currentPhase = values.current_phase || "scoping";
  const nextAgent = values.next_agent || null;
  const messages = (values.messages || []) as Array<{
    type?: string;
    role?: string;
    content?: any;
    name?: string;
  }>;

  let lastAiContent = "";
  let lastAiName = "";

  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    const type = msg.type || (msg.role === "assistant" ? "ai" : "");
    if (type === "ai" || msg.name) {
      lastAiContent =
        typeof msg.content === "string"
          ? msg.content
          : JSON.stringify(msg.content ?? "");
      lastAiName = msg.name || "";
      break;
    }
  }

  if (currentPhase === "scoping_review") {
    return {
      type: "brief_review",
      message: lastAiContent,
      research_brief: values.research_brief || "",
      selected_framework: values.selected_framework || "",
    };
  } else if (nextAgent === "ask_human") {
    return {
      type: "ask_human",
      message: lastAiContent,
      agent: lastAiName,
    };
  } else {
    return {
      type: "clarification",
      message: lastAiContent,
      agent: lastAiName,
    };
  }
}

async function checkAndEmitThreadState(
  client: Client,
  threadId: string,
  onEvent: (event: SSEEvent) => void
): Promise<void> {
  const state = await client.threads.getState(threadId);
  const values = (state.values as Record<string, any>) || {};
  const currentPhase = values.current_phase || "";

  if (currentPhase === "complete") {
    const reports = values.analysis_reports || [];
    const finalReport = reports[reports.length - 1] || "No report generated.";
    onEvent({
      event: "complete",
      data: { status: "complete", final_report: finalReport },
    });
  } else {
    const interruptInfo = detectInterruptType(values);
    onEvent({
      event: "interrupt",
      data: interruptInfo,
    });
  }
}

/**
 * Start a new research session using @langchain/langgraph-sdk.
 */
export async function startResearch(
  query: string,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const client = getClient();
  const thread = await client.threads.create();
  const threadId = thread.thread_id;
  const researchId =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `res-${Date.now()}`;

  onEvent({
    event: "init",
    data: { thread_id: threadId, research_id: researchId },
  });

  try {
    const stream = client.runs.stream(
      threadId,
      ASSISTANT_ID,
      {
        input: {
          messages: [{ type: "human", name: "human", content: query }],
          research_id: researchId,
        },
        streamMode: ["updates"],
      }
    );

    for await (const chunk of stream) {
      if (signal?.aborted) break;
      if (chunk.event === "updates" && chunk.data) {
        for (const [nodeName, nodeData] of Object.entries(
          chunk.data as Record<string, any>
        )) {
          onEvent({
            event: "node_update",
            data: {
              node: nodeName,
              data: nodeData,
            },
          });
        }
      }
    }

    if (!signal?.aborted) {
      await checkAndEmitThreadState(client, threadId, onEvent);
    }
  } catch (e: any) {
    if (signal?.aborted) return;
    onEvent({
      event: "error",
      data: {
        message: e.message || "Error running research graph",
        traceback: e.stack,
      },
    });
  }
}

/**
 * Send a human response to resume a paused research graph using @langchain/langgraph-sdk.
 */
export async function respondToInterrupt(
  threadId: string,
  message: string,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const client = getClient();

  try {
    const stream = client.runs.stream(
      threadId,
      ASSISTANT_ID,
      {
        input: {
          messages: [{ type: "human", name: "human", content: message }],
        },
        streamMode: ["updates"],
      }
    );

    for await (const chunk of stream) {
      if (signal?.aborted) break;
      if (chunk.event === "updates" && chunk.data) {
        for (const [nodeName, nodeData] of Object.entries(
          chunk.data as Record<string, any>
        )) {
          onEvent({
            event: "node_update",
            data: {
              node: nodeName,
              data: nodeData,
            },
          });
        }
      }
    }

    if (!signal?.aborted) {
      await checkAndEmitThreadState(client, threadId, onEvent);
    }
  } catch (e: any) {
    if (signal?.aborted) return;
    onEvent({
      event: "error",
      data: {
        message: e.message || "Error responding to graph",
        traceback: e.stack,
      },
    });
  }
}

/**
 * Get the current state of a research thread (for page refresh/reconnection).
 */
export async function getResearchState(
  threadId: string
): Promise<BackendStateResponse> {
  const client = getClient();
  const state = await client.threads.getState(threadId);
  const values = (state.values as Record<string, any>) || {};
  const messages = (values.messages || []) as Array<any>;

  const isInterrupted =
    Boolean(state.next?.length) ||
    (values.current_phase !== "complete" &&
      values.current_phase !== "collection" &&
      values.current_phase !== "analysis");

  const interruptInfo = isInterrupted ? detectInterruptType(values) : null;

  return {
    thread_id: threadId,
    research_id: values.research_id || "",
    current_phase: values.current_phase || "scoping",
    next_agent: values.next_agent || null,
    research_brief: values.research_brief || null,
    selected_framework: values.selected_framework || null,
    messages: messages.map((m: any) => ({
      type: m.type || m._type || (m.role === "assistant" ? "ai" : "human"),
      content:
        typeof m.content === "string"
          ? m.content
          : JSON.stringify(m.content ?? ""),
      name: m.name || null,
    })),
    is_interrupted: isInterrupted,
    interrupt_info: interruptInfo,
    analysis_reports: values.analysis_reports || [],
  };
}
