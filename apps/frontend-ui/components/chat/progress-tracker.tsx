"use client";

import type { ResearchPhase } from "@/lib/types";
import { NODE_DISPLAY_NAMES } from "@/lib/types";
import { Check, Compass, Database, ActivitySquare, Flag } from "lucide-react";
import { cn } from "@/lib/utils";

interface ProgressTrackerProps {
  phase: ResearchPhase;
  activeNode: string | null;
  currentTask?: string | null;
}

const PHASES = [
  { key: "scoping" as const, label: "Scoping", icon: Compass },
  { key: "collection" as const, label: "Collection", icon: Database },
  { key: "analysis" as const, label: "Analysis", icon: ActivitySquare },
  { key: "complete" as const, label: "Complete", icon: Flag },
];

function getPhaseIndex(phase: ResearchPhase): number {
  if (phase === "scoping" || phase === "scoping_review") return 0;
  if (phase === "collection") return 1;
  if (phase === "analysis") return 2;
  if (phase === "complete") return 3;
  return -1;
}

export function ProgressTracker({ phase, activeNode, currentTask }: ProgressTrackerProps) {
  const currentIndex = getPhaseIndex(phase);

  if (phase === "idle" || phase === "error") return null;

  return (
    <div className="relative z-10 glass border-b border-border/50 px-4 md:px-8 py-3.5 shadow-sm">
      <div className="flex items-center justify-between max-w-4xl mx-auto">
        {PHASES.map((p, i) => {
          const isComplete = i < currentIndex;
          const isCurrent = i === currentIndex;
          const isPending = i > currentIndex;
          
          const Icon = p.icon;

          return (
            <div key={p.key} className="flex items-center flex-1 last:flex-none">
              {/* Step indicator */}
              <div className="flex items-center gap-3">
                <div
                  className={cn(
                    "w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-300 relative",
                    isComplete && "bg-[hsl(142,71%,45%,0.15)] text-[hsl(142,71%,45%)] border border-[hsl(142,71%,45%,0.3)] shadow-[0_0_10px_hsl(142,71%,45%,0.1)]",
                    isCurrent && "bg-gradient-to-br from-[hsl(217,91%,60%)] to-[hsl(250,80%,65%)] text-white shadow-[0_2px_10px_hsl(217,91%,60%,0.3)]",
                    isPending && "bg-secondary text-muted-foreground border border-border/50"
                  )}
                >
                  {isComplete ? (
                    <Check className="w-4 h-4" />
                  ) : (
                    <Icon className="w-4 h-4" />
                  )}
                  
                  {/* Ping animation for current step */}
                  {isCurrent && (
                    <div className="absolute inset-0 rounded-xl bg-primary opacity-20 animate-[ping_2s_cubic-bezier(0,0,0.2,1)_infinite]" />
                  )}
                </div>
                
                <div className="hidden sm:block">
                  <span
                    className={cn(
                      "text-xs font-bold uppercase tracking-wider block transition-colors",
                      isComplete && "text-[hsl(142,71%,45%)]",
                      isCurrent && "text-primary",
                      isPending && "text-muted-foreground/60"
                    )}
                  >
                    {p.label}
                  </span>
                  
                  <div className="h-4 sm:h-5 overflow-hidden">
                    {isCurrent && activeNode ? (
                      <span className="text-[10px] text-muted-foreground truncate max-w-[140px] block animate-fade-in-up">
                        {currentTask ? (
                          <span className="flex items-center gap-1.5" title={currentTask as string}>
                            <ActivitySquare className="w-2.5 h-2.5 opacity-70 animate-pulse" />
                            {currentTask}
                          </span>
                        ) : (
                          <span className="opacity-80">
                            {NODE_DISPLAY_NAMES[activeNode] || activeNode}
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="text-[10px] text-transparent">_</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Connector line */}
              {i < PHASES.length - 1 && (
                <div className="flex-1 mx-4 sm:mx-6 flex items-center">
                  <div className="h-[2px] w-full rounded-full overflow-hidden bg-secondary relative">
                    <div 
                      className="absolute top-0 left-0 h-full bg-gradient-to-r from-[hsl(142,71%,45%)] to-[hsl(217,91%,60%)] transition-all duration-700 ease-in-out"
                      style={{ 
                        width: isComplete ? '100%' : '0%',
                      }}
                    />
                    
                    {/* Animated shimmer on active line segment */}
                    {isCurrent && (
                      <div 
                        className="absolute top-0 left-0 h-full bg-gradient-to-r from-transparent via-[hsl(217,91%,60%)] to-transparent w-1/2 opacity-50"
                        style={{ animation: 'shimmer 1.5s infinite linear' }}
                      />
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
