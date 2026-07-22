"use client";

import { useEffect, useRef, useState } from "react";
import type { ResearchState } from "@/lib/types";
import { MessageBubble } from "./message-bubble";
import { MessageInput } from "./message-input";
import { InterruptCard } from "./interrupt-card";
import { ProgressTracker } from "./progress-tracker";
import { ErrorDisplay } from "./error-display";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { RotateCcw, Loader2, FileText, Copy, Check, Zap } from "lucide-react";

interface ChatContainerProps {
  state: ResearchState;
  onRespond: (message: string) => void;
  onRetry: () => void;
  onNewResearch: () => void;
}

export function ChatContainer({
  state,
  onRespond,
  onRetry,
  onNewResearch,
}: ChatContainerProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [state.messages, state.pendingInterrupt, state.error, state.finalReport]);

  // Determine input state
  const isWaitingForInput =
    !state.isStreaming &&
    state.pendingInterrupt !== null &&
    state.phase !== "complete" &&
    state.phase !== "error";

  const inputPlaceholder = isWaitingForInput
    ? "Type your response..."
    : state.isStreaming
    ? "Waiting for agent response..."
    : state.phase === "complete"
    ? "Research complete"
    : "Type your message...";

  return (
    <div className="flex flex-col h-full bg-background relative overflow-hidden">
      {/* Background gradients for chat */}
      <div className="absolute top-0 left-0 w-full h-32 bg-gradient-to-b from-[hsl(217,91%,60%,0.03)] to-transparent pointer-events-none" />
      
      {/* Header */}
      <header className="relative z-10 glass border-b border-border/50 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[hsl(217,91%,60%)] to-[hsl(250,80%,65%)] flex items-center justify-center shadow-[0_2px_8px_hsl(217,91%,60%,0.2)]">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-foreground tracking-tight">
              Business Research Agent
            </h1>
            {state.researchId && (
              <span className="text-[10px] text-muted-foreground font-mono flex items-center gap-1 mt-0.5">
                Session: {state.researchId.slice(0, 8)}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={onNewResearch}
          className="flex items-center gap-2 text-xs font-medium text-muted-foreground hover:text-foreground bg-secondary/50 hover:bg-secondary px-3 py-1.5 rounded-full transition-colors border border-border/50"
        >
          <RotateCcw className="w-3 h-3" />
          New Research
        </button>
      </header>

      {/* Progress Tracker */}
      <ProgressTracker phase={state.phase} activeNode={state.activeNode} />

      {/* Messages */}
      <div
        ref={scrollContainerRef}
        className="relative z-10 flex-1 overflow-y-auto px-4 md:px-6 py-6"
      >
        <div className="max-w-4xl mx-auto space-y-6">
          {state.messages.map((msg, idx) => (
            <MessageBubble 
              key={msg.id} 
              message={msg} 
              isLatest={idx === state.messages.length - 1 && !state.isStreaming && !state.pendingInterrupt} 
            />
          ))}

          {/* Pending Interrupt Card */}
          {state.pendingInterrupt && state.phase !== "error" && (
            <div className="animate-fade-in-up">
              <InterruptCard
                interrupt={state.pendingInterrupt}
                onRespond={onRespond}
                disabled={state.isStreaming}
              />
            </div>
          )}

          {/* Error Display */}
          {state.phase === "error" && state.error && (
            <div className="animate-fade-in-up">
              <ErrorDisplay
                message={state.error}
                traceback={state.errorTraceback}
                onRetry={onRetry}
                disabled={state.isStreaming}
              />
            </div>
          )}

          {/* Final Report */}
          {state.phase === "complete" && state.finalReport && (
            <div className="animate-fade-in-up">
              <FinalReportCard report={state.finalReport} />
            </div>
          )}

          {/* Streaming indicator */}
          {state.isStreaming && (
            <div className="flex justify-center py-6 animate-fade-in">
              <div className="flex items-center gap-3 bg-secondary/40 backdrop-blur-md px-4 py-2.5 rounded-full border border-border/50 shadow-sm">
                <div className="relative flex items-center justify-center w-5 h-5">
                  <Loader2 className="w-4 h-4 text-primary animate-spin absolute" />
                  <div className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse-dot" />
                </div>
                <span className="text-xs font-medium text-muted-foreground">
                  Processing research...
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} className="h-4" />
        </div>
      </div>

      {/* Input Area */}
      {state.phase !== "complete" && (
        <div className="relative z-20">
          <MessageInput
            onSend={onRespond}
            disabled={!isWaitingForInput}
            placeholder={inputPlaceholder}
            isWaiting={isWaitingForInput}
          />
        </div>
      )}
    </div>
  );
}

function FinalReportCard({ report }: { report: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(report);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
  }

  return (
    <div className="mb-6 mt-4">
      <div className="glass-strong border-t-2 border-t-[hsl(142,71%,45%)] rounded-2xl p-0 overflow-hidden shadow-[0_8px_30px_rgb(0,0,0,0.12)]">
        
        {/* Header */}
        <div className="bg-secondary/30 px-6 py-4 flex items-center justify-between border-b border-border/50">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-[hsl(142,71%,45%,0.15)] flex items-center justify-center">
              <FileText className="w-4 h-4 text-[hsl(142,71%,45%)]" />
            </div>
            <div>
              <span className="text-xs font-bold text-[hsl(142,71%,45%)] uppercase tracking-wider block">
                Final Report
              </span>
              <span className="text-xs text-muted-foreground">Research completed successfully</span>
            </div>
          </div>
          <button
            onClick={handleCopy}
            className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-all ${
              copied 
                ? "bg-[hsl(142,71%,45%,0.15)] text-[hsl(142,71%,45%)]" 
                : "bg-secondary text-muted-foreground hover:text-foreground hover:bg-secondary/80"
            }`}
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5" />
                Copied
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                Copy
              </>
            )}
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-8 md:px-8">
          <div className="prose-chat">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  );
}
