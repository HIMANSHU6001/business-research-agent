"use client";

import { AGENT_DISPLAY_NAMES } from "@/lib/types";
import type { ChatMessage } from "@/lib/types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Cpu, CircleUser, Activity, Network } from "lucide-react";

interface MessageBubbleProps {
  message: ChatMessage;
  isLatest?: boolean;
}

export function MessageBubble({ message, isLatest = false }: MessageBubbleProps) {
  if (message.role === "user") {
    return <UserBubble message={message} isLatest={isLatest} />;
  }

  if (message.role === "progress") {
    return <ProgressBubble message={message} />;
  }

  if (message.role === "thought") {
    return <ThoughtBubble message={message} isLatest={isLatest} />;
  }

  return <AssistantBubble message={message} isLatest={isLatest} />;
}

function UserBubble({ message, isLatest }: { message: ChatMessage; isLatest: boolean }) {
  return (
    <div className={`flex justify-end mb-6 ${isLatest ? "animate-fade-in-up" : ""}`}>
      <div className="flex items-start gap-3 max-w-[85%] sm:max-w-[75%]">
        <div className="bg-gradient-to-br from-secondary to-secondary/80 border border-border/50 text-foreground rounded-2xl rounded-tr-sm px-5 py-3.5 shadow-sm">
          <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
        </div>
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-secondary border border-border/60 flex items-center justify-center mt-1">
          <CircleUser className="w-4 h-4 text-muted-foreground" />
        </div>
      </div>
    </div>
  );
}

function AssistantBubble({ message, isLatest }: { message: ChatMessage; isLatest: boolean }) {
  const displayName =
    AGENT_DISPLAY_NAMES[message.agentName || ""] || message.agentName || "Agent";
    
  // Check if this is the orchestrator/supervisor
  const isSupervisor = message.agentName?.includes("supervisor") || message.agentName === "scoping_agent";

  return (
    <div className={`flex justify-start mb-6 ${isLatest ? "animate-fade-in-up" : ""}`}>
      <div className="flex items-start gap-4 max-w-[95%] sm:max-w-[85%]">
        <div className={`flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center shadow-sm mt-1 border ${
          isSupervisor 
            ? "bg-gradient-to-br from-[hsl(262,83%,58%,0.15)] to-[hsl(280,80%,65%,0.15)] border-[hsl(262,83%,58%,0.3)] text-primary" 
            : "bg-secondary border-border/60 text-muted-foreground"
        }`}>
          {isSupervisor ? <Network className="w-4 h-4" /> : <Cpu className="w-4.5 h-4.5" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5 ml-1">
            <span className="text-xs font-semibold text-foreground/80 tracking-wide">
              {displayName}
            </span>
            <span className="text-[10px] text-muted-foreground/60">
              {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
          <div className="bg-card/60 backdrop-blur-sm border border-border/60 rounded-2xl rounded-tl-sm px-5 py-4 shadow-[0_2px_10px_rgb(0,0,0,0.02)]">
            <div className="prose-chat text-foreground/90">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ProgressBubble({ message }: { message: ChatMessage }) {
  return (
    <div className="flex justify-center mb-5 animate-fade-in">
      <div className="flex items-center gap-2.5 text-xs font-medium text-muted-foreground bg-secondary/40 backdrop-blur-sm border border-border/40 px-4 py-2 rounded-full shadow-sm">
        <Activity className="w-3.5 h-3.5 text-primary animate-pulse-dot" />
        <span>{message.content}</span>
      </div>
    </div>
  );
}

function ThoughtBubble({ message, isLatest }: { message: ChatMessage; isLatest: boolean }) {
  const displayName =
    AGENT_DISPLAY_NAMES[message.agentName || ""] || message.agentName || "Agent";

  return (
    <div className={`flex justify-start mb-6 ${isLatest ? "animate-fade-in-up" : ""}`}>
      <div className="flex items-start gap-4 max-w-[95%] sm:max-w-[85%]">
        <div className="flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center shadow-sm mt-1 border bg-secondary/30 border-border/40 text-muted-foreground">
          <Network className="w-4 h-4 opacity-70" />
        </div>
        <div className="flex-1 min-w-0">
          <details className="group [&_summary::-webkit-details-marker]:hidden">
            <summary className="flex items-center gap-2 cursor-pointer select-none mb-1.5 ml-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors">
              <span className="bg-secondary/50 px-2 py-0.5 rounded text-[10px] uppercase tracking-wider font-bold">
                {displayName} Thought Process
              </span>
              <span className="text-[10px] opacity-60">
                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
              <span className="ml-1 transition duration-300 group-open:-rotate-180">
                ▼
              </span>
            </summary>
            
            <div className="bg-secondary/20 border border-border/30 rounded-xl rounded-tl-sm px-4 py-3 shadow-inner mt-1">
              <div className="prose-chat text-muted-foreground text-sm">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              </div>
            </div>
          </details>
        </div>
      </div>
    </div>
  );
}
