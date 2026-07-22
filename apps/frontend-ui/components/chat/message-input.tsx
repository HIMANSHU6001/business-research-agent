"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Sparkles } from "lucide-react";

interface MessageInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
  isWaiting?: boolean;
}

export function MessageInput({
  onSend,
  disabled = false,
  placeholder = "Type your message...",
  isWaiting = false,
}: MessageInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isFocused, setIsFocused] = useState(false);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
    }
  }, [value]);

  function handleSubmit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    
    // Reset height after sending
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <div className="glass border-t border-border/50 p-4 relative">
      {/* Decorative top gradient edge when waiting for input */}
      {isWaiting && (
        <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-primary to-transparent opacity-50" />
      )}
      
      <div className="max-w-4xl mx-auto">
        <div 
          className={`relative flex items-end gap-3 rounded-2xl transition-all duration-300 ${
            isFocused ? (isWaiting ? "glow-primary" : "shadow-[0_0_0_1px_hsl(var(--border))]") : ""
          }`}
        >
          <div className={`flex-1 flex items-end bg-secondary/60 backdrop-blur-md rounded-2xl border transition-colors ${
            isFocused ? "border-primary/50" : "border-border/60"
          }`}>
            {isWaiting && (
              <div className="absolute -top-3 left-6 bg-primary text-primary-foreground text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full flex items-center gap-1 shadow-sm">
                <Sparkles className="w-2.5 h-2.5" />
                Response Needed
              </div>
            )}
            
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={disabled}
              rows={1}
              className="flex-1 resize-none bg-transparent px-5 py-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed leading-relaxed"
            />
          </div>
          
          <button
            onClick={handleSubmit}
            disabled={disabled || !value.trim()}
            className={`flex-shrink-0 w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-200 ${
              isWaiting
                ? "bg-gradient-to-br from-[hsl(var(--gradient-start))] to-[hsl(var(--gradient-mid))] text-white shadow-[0_2px_10px_hsl(var(--primary)/0.25)] hover:shadow-[0_4px_16px_hsl(var(--primary)/0.4)]"
                : "bg-primary text-primary-foreground hover:bg-primary/90"
            } disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none`}
          >
            <Send className="w-5 h-5 ml-0.5" />
          </button>
        </div>
        
        <div className="text-center mt-2">
          <span className="text-[10px] text-muted-foreground/60">
            Press <kbd className="font-mono bg-secondary px-1 rounded text-muted-foreground">Enter</kbd> to send, <kbd className="font-mono bg-secondary px-1 rounded text-muted-foreground">Shift + Enter</kbd> for new line
          </span>
        </div>
      </div>
    </div>
  );
}
