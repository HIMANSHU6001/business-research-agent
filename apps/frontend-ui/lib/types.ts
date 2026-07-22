// ===== Research State Types =====

export type ResearchPhase =
  | "idle"
  | "scoping"
  | "scoping_review"
  | "collection"
  | "analysis"
  | "complete"
  | "error";

export type InterruptType = "clarification" | "brief_review" | "ask_human";

// ===== Chat Message =====

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system" | "progress";
  content: string;
  agentName?: string;
  timestamp: Date;
  interruptType?: InterruptType;
  metadata?: {
    researchBrief?: string;
    selectedFramework?: string;
    node?: string;
  };
}

// ===== SSE Events (from backend) =====

export interface SSEInitEvent {
  thread_id: string;
  research_id: string;
}

export interface SSENodeUpdateEvent {
  node: string;
  data: {
    messages?: Array<{
      type: string;
      content: string;
      name: string | null;
    }>;
    current_phase?: string;
    next_agent?: string;
    agent_task?: string;
    research_brief?: string;
    selected_framework?: string;
    analysis_reports?: string[];
    [key: string]: unknown;
  };
}

export interface SSEInterruptEvent {
  type: InterruptType;
  message: string;
  agent?: string;
  research_brief?: string;
  selected_framework?: string;
}

export interface SSEErrorEvent {
  message: string;
  traceback?: string;
}

export interface SSECompleteEvent {
  status: string;
  final_report: string;
}

// ===== Research State (frontend) =====

export interface ResearchState {
  threadId: string | null;
  researchId: string | null;
  phase: ResearchPhase;
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  errorTraceback: string | null;
  researchBrief: string | null;
  selectedFramework: string | null;
  activeNode: string | null;
  finalReport: string | null;
  pendingInterrupt: SSEInterruptEvent | null;
}

// ===== Agent Display Names =====

export const AGENT_DISPLAY_NAMES: Record<string, string> = {
  scoping_agent: "Scoping Agent",
  collection_supervisor: "Collection Supervisor",
  financial_agent: "Financial Agent",
  macro_agent: "Macro Economic Agent",
  trends_agent: "Trends Agent",
  data_collection_supervisor: "Collection Supervisor",
  data_analysis_supervisor: "Analysis Supervisor",
  quantitative_agent: "Quantitative Agent",
  qualitative_agent: "Qualitative Agent",
  analysis_synthesizer: "Analysis Synthesizer",
  collection_synthesizer: "Collection Synthesizer",
};

export const NODE_DISPLAY_NAMES: Record<string, string> = {
  clarify_with_user: "Scoping — Clarification",
  write_research_brief: "Scoping — Writing Brief",
  review_research_brief: "Scoping — Reviewing Brief",
  data_collection_supervisor: "Collection — Supervisor",
  financial_agent: "Collection — Financial Data",
  macro_agent: "Collection — Macro Data",
  trends_agent: "Collection — Trends Data",
  collection_synthesizer: "Collection — Synthesizing",
  data_analysis_supervisor: "Analysis — Supervisor",
  quantitative_agent: "Analysis — Quantitative",
  qualitative_agent: "Analysis — Qualitative",
  analysis_synthesizer: "Analysis — Final Synthesis",
};

// ===== Backend State Response =====

export interface BackendStateResponse {
  thread_id: string;
  research_id: string;
  current_phase: string;
  next_agent: string | null;
  research_brief: string | null;
  selected_framework: string | null;
  messages: Array<{
    type: string;
    content: string;
    name: string | null;
  }>;
  is_interrupted: boolean;
  interrupt_info: SSEInterruptEvent | null;
  analysis_reports: string[];
}
