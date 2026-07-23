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

    // Skip human messages
    if (type === "human" || msg.name === "human" || msg.role === "user") {
      continue;
    }

    if (type === "ai" || msg.name) {
      const content =
        typeof msg.content === "string"
          ? msg.content
          : JSON.stringify(msg.content ?? "");
      // We now pass supervisor reflections to the frontend
      // so it can render them as expandable thoughts.
      lastAiContent = content;
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
  
  // Check if the graph stopped due to an error in any task
  if (state.tasks && state.tasks.length > 0) {
    const failedTask = state.tasks.find((t: any) => t.error);
    if (failedTask) {
      onEvent({
        event: "error",
        data: {
          message: `Error in node ${failedTask.name}: ${failedTask.error}`,
        },
      });
      return;
    }
  }

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

export async function pauseResearchApi(threadId: string): Promise<void> {
  const client = getClient();
  try {
    const runs = await client.runs.list(threadId);
    const activeRuns = runs.filter((r: any) => ["pending", "in_progress", "running"].includes(r.status));
    for (const run of activeRuns) {
      await client.runs.cancel(threadId, run.run_id);
    }
  } catch (e) {
    console.error("Failed to pause research:", e);
  }
}

export async function resumeResearch(
  threadId: string,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const client = getClient();
  try {
    const allRuns = await client.runs.list(threadId);
    const runs = allRuns.filter((r: any) => ["pending", "in_progress", "running"].includes(r.status));
    let stream;
    
    if (runs && runs.length > 0) {
      // Join the existing active run
      stream = client.runs.joinStream(threadId, runs[0].run_id);
    } else {
      // Start a new run with no input to continue from current state
      stream = client.runs.stream(
        threadId,
        ASSISTANT_ID,
        {
          input: null,
          streamMode: ["updates"],
        }
      );
    }

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
        message: e.message || "Error resuming research graph",
        traceback: e.stack,
      },
    });
  }
}

export async function getResearchState(
  threadId: string
): Promise<BackendStateResponse | { error: string; traceback?: string }> {
  const client = getClient();
  const state = await client.threads.getState(threadId);
  
  if (state.tasks && state.tasks.length > 0) {
    const failedTask = state.tasks.find((t: any) => t.error);
    if (failedTask) {
      return {
        error: `Error in node ${failedTask.name}: ${failedTask.error}`,
      };
    }
  }

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

export async function fetchArtifacts(researchId: string): Promise<any[]> {
  // Artifact endpoints are hosted on our custom FastAPI Orchestrator, not LangGraph SDK.
  const orchestratorUrl = process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://localhost:8000";

  const response = await fetch(`${orchestratorUrl}/research/${researchId}/artifacts`);
  if (!response.ok) {
    throw new Error("Failed to fetch artifacts");
  }
  const data = await response.json();
  return data.artifacts || [];
}

export async function fetchArtifactData(researchId: string, artifactId: string): Promise<any> {
  const orchestratorUrl = process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://localhost:8000";

  const response = await fetch(`${orchestratorUrl}/research/${researchId}/artifacts/${artifactId}`);
  if (!response.ok) {
    throw new Error("Failed to fetch artifact data");
  }
  const data = await response.json();
  return data.data;
}
