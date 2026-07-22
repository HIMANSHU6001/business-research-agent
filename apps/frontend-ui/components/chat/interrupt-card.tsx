"use client";

import { useState } from "react";
import type { SSEInterruptEvent } from "@/lib/types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  CheckCircle,
  Edit3,
  MessageSquare,
  Send,
  Sparkles,
  AlertCircle
} from "lucide-react";

interface InterruptCardProps {
  interrupt: SSEInterruptEvent;
  onRespond: (message: string) => void;
  disabled?: boolean;
}

export function InterruptCard({
  interrupt,
  onRespond,
  disabled = false,
}: InterruptCardProps) {
  switch (interrupt.type) {
    case "clarification":
      return (
        <ClarificationCard
          interrupt={interrupt}
          onRespond={onRespond}
          disabled={disabled}
        />
      );
    case "brief_review":
      return (
        <BriefReviewCard
          interrupt={interrupt}
          onRespond={onRespond}
          disabled={disabled}
        />
      );
    case "ask_human":
      return (
        <AskHumanCard
          interrupt={interrupt}
          onRespond={onRespond}
          disabled={disabled}
        />
      );
    default:
      return null;
  }
}

function ClarificationCard({
  interrupt,
  onRespond,
  disabled,
}: {
  interrupt: SSEInterruptEvent;
  onRespond: (message: string) => void;
  disabled?: boolean;
}) {
  const [response, setResponse] = useState("");

  return (
    <div className="flex justify-start mb-6">
      <div className="max-w-[85%] ml-13">
        <div className="glass-strong border-t-2 border-t-[hsl(var(--primary))] rounded-2xl p-0 overflow-hidden shadow-lg shadow-primary/5">
          <div className="bg-primary/10 px-5 py-3 border-b border-primary/20 flex items-center gap-2.5">
            <Sparkles className="w-4 h-4 text-primary" />
            <span className="text-xs font-bold text-primary uppercase tracking-wider">
              Clarification Needed
            </span>
          </div>
          
          <div className="p-5">
            <p className="text-sm text-foreground/90 mb-5 leading-relaxed">{interrupt.message}</p>
            
            <div className="flex flex-col sm:flex-row items-end sm:items-center gap-3">
              <input
                type="text"
                value={response}
                onChange={(e) => setResponse(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && response.trim()) {
                    onRespond(response.trim());
                    setResponse("");
                  }
                }}
                placeholder="Type your answer..."
                disabled={disabled}
                className="w-full sm:flex-1 bg-secondary/50 border border-border/50 rounded-xl px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary disabled:opacity-50 transition-all"
              />
              <button
                onClick={() => {
                  if (response.trim()) {
                    onRespond(response.trim());
                    setResponse("");
                  }
                }}
                disabled={disabled || !response.trim()}
                className="w-full sm:w-auto flex-shrink-0 px-5 py-2.5 rounded-xl bg-gradient-to-r from-primary to-[hsl(250,80%,65%)] text-white font-medium text-sm flex items-center justify-center gap-2 hover:opacity-90 disabled:opacity-50 transition-all shadow-md shadow-primary/20"
              >
                <span>Submit</span>
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function BriefReviewCard({
  interrupt,
  onRespond,
  disabled,
}: {
  interrupt: SSEInterruptEvent;
  onRespond: (message: string) => void;
  disabled?: boolean;
}) {
  const [mode, setMode] = useState<"view" | "revise">("view");
  const [feedback, setFeedback] = useState("");

  return (
    <div className="flex justify-start mb-6">
      <div className="max-w-[95%] sm:max-w-[90%] ml-13">
        <div className="glass-strong border-t-2 border-t-[hsl(var(--primary))] rounded-2xl p-0 overflow-hidden shadow-lg shadow-primary/5">
          <div className="bg-primary/10 px-5 py-3 border-b border-primary/20 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <CheckCircle className="w-4 h-4 text-primary" />
              <span className="text-xs font-bold text-primary uppercase tracking-wider">
                Research Brief — Review Required
              </span>
            </div>
            
            {interrupt.selected_framework && (
              <div className="flex items-center gap-2 hidden sm:flex">
                <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Framework:</span>
                <span className="bg-background/50 border border-border text-primary text-[10px] font-bold px-2 py-1 rounded-md">
                  {interrupt.selected_framework}
                </span>
              </div>
            )}
          </div>

          <div className="p-5">
            {/* Brief content */}
            <div className="bg-background/40 border border-border/50 rounded-xl p-5 mb-5 max-h-96 overflow-y-auto">
              <div className="prose-chat text-foreground/90">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {interrupt.research_brief || interrupt.message}
                </ReactMarkdown>
              </div>
            </div>

            {/* Mobile framework badge */}
            {interrupt.selected_framework && (
              <div className="flex items-center gap-2 sm:hidden mb-4">
                <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Framework:</span>
                <span className="bg-background/50 border border-border text-primary text-[10px] font-bold px-2 py-1 rounded-md">
                  {interrupt.selected_framework}
                </span>
              </div>
            )}

            {mode === "view" ? (
              <div className="flex flex-col sm:flex-row gap-3">
                <button
                  onClick={() => onRespond("Approved. Proceed with data collection.")}
                  disabled={disabled}
                  className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-[hsl(142,71%,45%)] hover:bg-[hsl(142,71%,40%)] text-white text-sm font-semibold px-6 py-2.5 rounded-xl disabled:opacity-50 transition-all shadow-md shadow-[hsl(142,71%,45%,0.2)]"
                >
                  <CheckCircle className="w-4 h-4" />
                  Approve & Proceed
                </button>
                <button
                  onClick={() => setMode("revise")}
                  disabled={disabled}
                  className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-secondary border border-border/50 hover:bg-secondary/80 text-foreground text-sm font-medium px-6 py-2.5 rounded-xl disabled:opacity-50 transition-all"
                >
                  <Edit3 className="w-4 h-4" />
                  Request Changes
                </button>
              </div>
            ) : (
              <div className="animate-fade-in">
                <textarea
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  placeholder="Describe the changes you'd like to make to the brief..."
                  disabled={disabled}
                  rows={3}
                  className="w-full bg-secondary/50 border border-border/50 rounded-xl px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary disabled:opacity-50 resize-none mb-4 transition-all leading-relaxed"
                />
                <div className="flex flex-col sm:flex-row gap-3">
                  <button
                    onClick={() => {
                      if (feedback.trim()) {
                        onRespond(feedback.trim());
                        setFeedback("");
                      }
                    }}
                    disabled={disabled || !feedback.trim()}
                    className="flex items-center justify-center gap-2 bg-gradient-to-r from-primary to-[hsl(250,80%,65%)] hover:opacity-90 text-white text-sm font-semibold px-6 py-2.5 rounded-xl disabled:opacity-50 transition-all shadow-md shadow-primary/20"
                  >
                    <Send className="w-4 h-4" />
                    Submit Feedback
                  </button>
                  <button
                    onClick={() => setMode("view")}
                    disabled={disabled}
                    className="flex items-center justify-center text-sm text-muted-foreground hover:text-foreground font-medium px-4 py-2.5 rounded-xl hover:bg-secondary/50 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function AskHumanCard({
  interrupt,
  onRespond,
  disabled,
}: {
  interrupt: SSEInterruptEvent;
  onRespond: (message: string) => void;
  disabled?: boolean;
}) {
  const [response, setResponse] = useState("");

  return (
    <div className="flex justify-start mb-6">
      <div className="max-w-[85%] ml-13">
        <div className="glass-strong border-t-2 border-t-[hsl(38,92%,50%)] rounded-2xl p-0 overflow-hidden shadow-lg shadow-[hsl(38,92%,50%,0.05)]">
          <div className="bg-[hsl(38,92%,50%,0.1)] px-5 py-3 border-b border-[hsl(38,92%,50%,0.2)] flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 text-[hsl(38,92%,50%)]" />
            <span className="text-xs font-bold text-[hsl(38,92%,50%)] uppercase tracking-wider">
              Agent Needs Your Input
            </span>
          </div>
          
          <div className="p-5">
            <p className="text-sm text-foreground/90 mb-5 leading-relaxed">{interrupt.message}</p>
            
            <div className="flex flex-col sm:flex-row items-end sm:items-center gap-3">
              <input
                type="text"
                value={response}
                onChange={(e) => setResponse(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && response.trim()) {
                    onRespond(response.trim());
                    setResponse("");
                  }
                }}
                placeholder="Type your response..."
                disabled={disabled}
                className="w-full sm:flex-1 bg-secondary/50 border border-border/50 rounded-xl px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-[hsl(38,92%,50%)] focus:border-[hsl(38,92%,50%)] disabled:opacity-50 transition-all"
              />
              <button
                onClick={() => {
                  if (response.trim()) {
                    onRespond(response.trim());
                    setResponse("");
                  }
                }}
                disabled={disabled || !response.trim()}
                className="w-full sm:w-auto flex-shrink-0 px-5 py-2.5 rounded-xl bg-[hsl(38,92%,50%)] text-black font-semibold text-sm flex items-center justify-center gap-2 hover:bg-[hsl(38,92%,45%)] disabled:opacity-50 transition-all shadow-md shadow-[hsl(38,92%,50%,0.2)]"
              >
                <span>Respond</span>
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
