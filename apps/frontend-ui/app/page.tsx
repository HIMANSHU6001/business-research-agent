"use client";

import { useState } from "react";
import { useResearch } from "@/hooks/use-research";
import { ChatContainer } from "@/components/chat/chat-container";
import {
  Search,
  ArrowRight,
  Sparkles,
  BarChart3,
  Globe,
  TrendingUp,
  Zap,
} from "lucide-react";

const EXAMPLE_QUERIES = [
  {
    icon: BarChart3,
    label: "Financial Analysis",
    query:
      "Research the financial performance of Microsoft (MSFT) and its macroeconomic environment in the United States over the last 5 years.",
  },
  {
    icon: Globe,
    label: "Competitive Analysis",
    query:
      "Analyze Apple's (AAPL) competitive position using Porter's Five Forces framework.",
  },
  {
    icon: TrendingUp,
    label: "Industry Research",
    query:
      "Research the impact of inflation on the Indian IT industry (TCS, INFY) from 2020 to 2024.",
  },
];

const CAPABILITIES = [
  { icon: BarChart3, label: "Financial Intelligence", desc: "Company fundamentals, earnings, market data" },
  { icon: Globe, label: "Macro Economics", desc: "GDP, inflation, trade, demographics" },
  { icon: TrendingUp, label: "Trend Analysis", desc: "Consumer search interest & demand signals" },
];

export default function Home() {
  const { state, startResearch, respond, retry, reset } = useResearch();

  if (state.phase === "idle") {
    return <LandingView onSubmit={startResearch} />;
  }

  return (
    <div className="h-screen flex flex-col">
      <ChatContainer
        state={state}
        onRespond={respond}
        onRetry={retry}
        onNewResearch={reset}
      />
    </div>
  );
}

function LandingView({ onSubmit }: { onSubmit: (query: string) => void }) {
  const [query, setQuery] = useState("");
  const [isFocused, setIsFocused] = useState(false);

  function handleSubmit() {
    const trimmed = query.trim();
    if (trimmed) {
      onSubmit(trimmed);
    }
  }

  return (
    <div className="min-h-screen flex flex-col relative overflow-hidden">
      {/* Background gradient orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full bg-[hsl(217,91%,60%,0.06)] blur-[120px] animate-float" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[500px] h-[500px] rounded-full bg-[hsl(250,80%,65%,0.05)] blur-[100px] animate-float" style={{ animationDelay: "1.5s" }} />
        <div className="absolute top-[40%] right-[20%] w-[300px] h-[300px] rounded-full bg-[hsl(280,70%,55%,0.04)] blur-[80px] animate-float" style={{ animationDelay: "3s" }} />
      </div>

      {/* Header */}
      <header className="relative z-10 px-6 py-5 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[hsl(217,91%,60%)] to-[hsl(250,80%,65%)] flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="text-sm font-semibold text-foreground tracking-tight">
            BRA
          </span>
        </div>
      </header>

      {/* Hero */}
      <main className="relative z-10 flex-1 flex items-center justify-center px-6 pb-16">
        <div className="w-full max-w-2xl animate-fade-in-up">
          {/* Title */}
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 bg-[hsl(var(--primary)/0.1)] text-primary text-xs font-medium px-3 py-1.5 rounded-full mb-5 border border-[hsl(var(--primary)/0.15)]">
              <Sparkles className="w-3.5 h-3.5" />
              Multi-Agent Research System
            </div>
            <h1 className="text-4xl sm:text-5xl font-bold tracking-tight mb-4 leading-[1.15]">
              <span className="text-foreground">Research </span>
              <span className="gradient-text">any business</span>
              <br />
              <span className="text-foreground">with AI agents</span>
            </h1>
            <p className="text-base text-muted-foreground max-w-md mx-auto leading-relaxed">
              Get evidence-backed research reports powered by financial data,
              macroeconomic indicators, and trend analysis.
            </p>
          </div>

          {/* Search Input */}
          <div className="mb-8">
            <div
              className={`relative rounded-2xl transition-all duration-300 ${
                isFocused ? "glow-primary" : ""
              }`}
            >
              <div className="flex items-start glass-strong rounded-2xl overflow-hidden">
                <Search className="w-5 h-5 text-muted-foreground mt-4 ml-5 flex-shrink-0" />
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onFocus={() => setIsFocused(true)}
                  onBlur={() => setIsFocused(false)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmit();
                    }
                  }}
                  placeholder="What would you like to research?"
                  rows={2}
                  className="flex-1 bg-transparent px-4 py-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none resize-none leading-relaxed"
                />
                <button
                  onClick={handleSubmit}
                  disabled={!query.trim()}
                  className="flex-shrink-0 m-2.5 w-10 h-10 rounded-xl bg-gradient-to-br from-[hsl(217,91%,60%)] to-[hsl(250,80%,65%)] text-white flex items-center justify-center hover:opacity-90 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-200 hover:shadow-[0_4px_16px_hsl(217,91%,60%,0.3)]"
                >
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {/* Example Queries */}
          <div className="mb-12">
            <p className="text-xs text-muted-foreground mb-3 text-center font-medium uppercase tracking-wider">
              Try an example
            </p>
            <div className="grid gap-2.5">
              {EXAMPLE_QUERIES.map((eq, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setQuery(eq.query);
                    onSubmit(eq.query);
                  }}
                  className="group w-full text-left glass rounded-xl px-4 py-3 transition-all duration-200 hover:bg-[hsl(var(--card)/0.9)] hover:border-[hsl(var(--primary)/0.3)] hover:shadow-[0_2px_12px_hsl(217,91%,60%,0.08)]"
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-[hsl(var(--secondary))] flex items-center justify-center mt-0.5 group-hover:bg-[hsl(var(--primary)/0.15)] transition-colors">
                      <eq.icon className="w-3.5 h-3.5 text-muted-foreground group-hover:text-primary transition-colors" />
                    </div>
                    <div>
                      <span className="text-xs font-medium text-foreground/70 group-hover:text-primary transition-colors">
                        {eq.label}
                      </span>
                      <p className="text-xs text-muted-foreground leading-relaxed mt-0.5">
                        {eq.query}
                      </p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Capabilities */}
          <div className="grid grid-cols-3 gap-3">
            {CAPABILITIES.map((cap, i) => (
              <div
                key={i}
                className="text-center px-3 py-4 rounded-xl border border-[hsl(var(--border)/0.5)] bg-[hsl(var(--card)/0.3)]"
              >
                <div className="w-9 h-9 rounded-lg bg-[hsl(var(--secondary))] flex items-center justify-center mx-auto mb-2.5">
                  <cap.icon className="w-4 h-4 text-muted-foreground" />
                </div>
                <p className="text-xs font-medium text-foreground mb-1">{cap.label}</p>
                <p className="text-[10px] text-muted-foreground leading-relaxed">{cap.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
