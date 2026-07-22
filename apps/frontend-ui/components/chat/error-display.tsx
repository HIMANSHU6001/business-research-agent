"use client";

import { AlertTriangle, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

interface ErrorDisplayProps {
  message: string;
  traceback?: string | null;
  onRetry: () => void;
  disabled?: boolean;
}

export function ErrorDisplay({
  message,
  traceback,
  onRetry,
  disabled = false,
}: ErrorDisplayProps) {
  const [showTraceback, setShowTraceback] = useState(false);

  return (
    <div className="flex justify-start mb-6">
      <div className="max-w-[85%] ml-13">
        <div className="glass-strong border-t-2 border-t-[hsl(0,63%,50%)] rounded-2xl p-0 overflow-hidden shadow-lg shadow-[hsl(0,63%,50%,0.05)]">
          <div className="bg-[hsl(0,63%,50%,0.1)] px-5 py-3 border-b border-[hsl(0,63%,50%,0.2)] flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <AlertTriangle className="w-4 h-4 text-[hsl(0,63%,60%)]" />
              <span className="text-xs font-bold text-[hsl(0,63%,60%)] uppercase tracking-wider">
                Error Occurred
              </span>
            </div>
          </div>
          
          <div className="p-5">
            <p className="text-sm text-foreground/90 mb-5 leading-relaxed bg-[hsl(0,63%,50%,0.05)] p-4 rounded-xl border border-[hsl(0,63%,50%,0.1)] font-mono text-[13px]">
              {message}
            </p>

            {traceback && (
              <div className="mb-5">
                <button
                  onClick={() => setShowTraceback(!showTraceback)}
                  className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors bg-secondary/50 hover:bg-secondary px-3 py-1.5 rounded-lg border border-border/50"
                >
                  {showTraceback ? (
                    <ChevronUp className="w-3 h-3" />
                  ) : (
                    <ChevronDown className="w-3 h-3" />
                  )}
                  {showTraceback ? "Hide Stack Trace" : "Show Stack Trace"}
                </button>
                
                {showTraceback && (
                  <div className="mt-3 animate-fade-in-up">
                    <pre className="p-4 bg-background/80 border border-border/50 rounded-xl text-[11px] text-muted-foreground overflow-x-auto max-h-60 overflow-y-auto custom-scrollbar">
                      <code>{traceback}</code>
                    </pre>
                  </div>
                )}
              </div>
            )}

            <button
              onClick={onRetry}
              disabled={disabled}
              className="flex items-center justify-center gap-2 bg-[hsl(0,63%,45%)] hover:bg-[hsl(0,63%,55%)] text-white text-sm font-semibold px-6 py-2.5 rounded-xl disabled:opacity-50 transition-all shadow-md shadow-[hsl(0,63%,50%,0.2)]"
            >
              <RefreshCw className="w-4 h-4" />
              Retry Task
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
