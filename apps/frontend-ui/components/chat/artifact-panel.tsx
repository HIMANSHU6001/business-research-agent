"use client";

import { useEffect, useState } from "react";
import { X, Database, Download, FileJson, Loader2 } from "lucide-react";
import { fetchArtifacts, fetchArtifactData } from "@/lib/api-client";
import type { Artifact } from "@/lib/types";

interface ArtifactPanelProps {
  researchId: string | null;
  isOpen: boolean;
  onClose: () => void;
}

export function ArtifactPanel({ researchId, isOpen, onClose }: ArtifactPanelProps) {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);
  const [artifactData, setArtifactData] = useState<any>(null);
  const [loadingData, setLoadingData] = useState(false);

  async function loadArtifacts() {
    if (!researchId) return;
    setLoading(true);
    try {
      const data = await fetchArtifacts(researchId);
      setArtifacts(data);
    } catch (err) {
      console.error("Failed to load artifacts", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (isOpen && researchId) {
      loadArtifacts();
    }
  }, [isOpen, researchId]);

  async function loadArtifactData(artifact: Artifact) {
    if (!researchId) return;
    setSelectedArtifact(artifact);
    setLoadingData(true);
    try {
      const data = await fetchArtifactData(researchId, artifact.artifact_id);
      setArtifactData(data);
    } catch (err) {
      console.error("Failed to load artifact data", err);
      setArtifactData({ error: "Failed to load data." });
    } finally {
      setLoadingData(false);
    }
  }

  function handleDownloadJson(artifact: Artifact, data: any) {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${artifact.artifact_id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-md bg-background/95 backdrop-blur-xl border-l border-border/50 shadow-2xl z-50 flex flex-col transform transition-transform duration-300">
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/50">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[hsl(217,91%,60%,0.15)] flex items-center justify-center">
            <Database className="w-4 h-4 text-primary" />
          </div>
          <h2 className="text-sm font-semibold text-foreground tracking-tight">
            Collected Artifacts
          </h2>
        </div>
        <button
          onClick={onClose}
          className="p-2 rounded-full hover:bg-secondary/80 text-muted-foreground hover:text-foreground transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-6 h-6 text-primary animate-spin" />
          </div>
        ) : artifacts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-3 opacity-60">
            <Database className="w-8 h-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">No artifacts collected yet.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {artifacts.map((a) => (
              <div key={a.id} className="glass rounded-xl border border-border/50 overflow-hidden transition-all hover:border-primary/30">
                <div 
                  className="px-4 py-3 cursor-pointer hover:bg-secondary/30"
                  onClick={() => loadArtifactData(a)}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-foreground truncate">{a.artifact_id}</span>
                    <span className="text-[10px] bg-secondary px-2 py-0.5 rounded text-muted-foreground uppercase">{a.source_mcp}</span>
                  </div>
                  <p className="text-[10px] text-muted-foreground line-clamp-2">{a.description}</p>
                  <div className="mt-2 text-[10px] text-muted-foreground/80 flex items-center gap-2">
                    <span>Rows: {a.row_count}</span>
                  </div>
                </div>
                
                {selectedArtifact?.id === a.id && (
                  <div className="border-t border-border/50 bg-secondary/10 p-4">
                    <div className="flex justify-between items-center mb-3">
                      <span className="text-xs font-medium text-foreground">Data Preview</span>
                      <button 
                        onClick={() => handleDownloadJson(a, artifactData)}
                        disabled={loadingData || !artifactData || artifactData.error}
                        className="flex items-center gap-1.5 text-[10px] font-medium bg-primary text-primary-foreground px-2.5 py-1.5 rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors"
                      >
                        <Download className="w-3 h-3" />
                        Download JSON
                      </button>
                    </div>
                    
                    <div className="bg-background rounded-lg border border-border/50 p-3 max-h-60 overflow-y-auto">
                      {loadingData ? (
                        <div className="flex justify-center p-4">
                          <Loader2 className="w-4 h-4 text-primary animate-spin" />
                        </div>
                      ) : artifactData?.error ? (
                        <div className="text-xs text-destructive">{artifactData.error}</div>
                      ) : (
                        <pre className="text-[10px] text-muted-foreground font-mono">
                          {JSON.stringify(artifactData, null, 2)}
                        </pre>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
