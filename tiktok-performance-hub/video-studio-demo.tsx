import React, { useEffect, useRef, useState } from "react";
import { useServerFn } from "@tanstack/react-start";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { 
  Film, Upload, Sparkles, Trash2, Download, 
  AlertCircle, Loader2, Zap, Gem 
} from "lucide-react";
import {
  startVideoGeneration,
  pollVideoGeneration,
  listVideoGenerations,
  deleteVideoGeneration,
  getCreatorSettings,
  expandVideoPrompt,
} from "@/lib/video-studio.functions"; // Demo backend connection functions

export default function VideoStudioDemo() {
  const qc = useQueryClient();
  const startFn = useServerFn(startVideoGeneration);
  const listFn = useServerFn(listVideoGenerations);
  const pollFn = useServerFn(pollVideoGeneration);
  const deleteFn = useServerFn(deleteVideoGeneration);
  const settingsFn = useServerFn(getCreatorSettings);
  const expandFn = useServerFn(expandVideoPrompt);

  const [prompt, setPrompt] = useState("");
  const [contextText, setContextText] = useState("");
  const [modelTier, setModelTier] = useState<"fast" | "quality">("fast");
  const [aspectRatio, setAspectRatio] = useState<"9:16" | "16:9">("9:16");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [optimizingPrompt, setOptimizingPrompt] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // IA Script Optimization Engine
  async function handleOptimizePrompt() {
    if (!prompt.trim()) {
      toast.error("Please enter a basic script idea before optimizing.");
      return;
    }
    setOptimizingPrompt(true);
    try {
      const expandedPrompt = await expandFn({ data: { prompt, context: contextText || undefined } });
      setPrompt(expandedPrompt);
      toast.success("Script optimized by AI!", {
        description: "Translated and enriched into English cinematic instructions (Veo 3.0).",
      });
    } catch (e) {
      toast.error("Failed to optimize script prompt.");
    } finally {
      setOptimizingPrompt(false);
    }
  }

  // Fetch client settings & list of generations
  const settings = useQuery({ 
    queryKey: ["creator-settings"], 
    queryFn: () => settingsFn() 
  });
  
  const generations = useQuery({
    queryKey: ["video-generations"],
    queryFn: () => listFn(),
    refetchInterval: (query) => {
      const rows = query.state.data as Array<{ status: string }> | undefined;
      // Faster polling (5s) if there are pending/processing items
      return rows?.some((r) => r.status === "processing" || r.status === "pending") ? 5000 : false;
    },
  });

  const hasOwnKey = Boolean(settings.data?.hasOwnKey);
  const trialRemaining = settings.data?.trialRemaining ?? 0;
  const canGenerate = hasOwnKey || trialRemaining > 0;

  // Active generation tracking thread
  useEffect(() => {
    const rows = generations.data;
    if (!rows) return;
    const active = rows.filter((r) => r.status === "processing" || r.status === "pending");
    if (active.length === 0) return;
    
    const intervalId = setInterval(() => {
      Promise.allSettled(active.map((r) => pollFn({ data: { id: r.id } })))
        .finally(() => {
          qc.invalidateQueries({ queryKey: ["video-generations"] });
          qc.invalidateQueries({ queryKey: ["creator-settings"] });
        });
    }, 6000);
    
    return () => clearInterval(intervalId);
  }, [generations.data, pollFn, qc]);

  function handleFileChange(file: File | null) {
    if (!file) { setImageFile(null); setImagePreview(null); return; }
    if (file.size > 18 * 1024 * 1024) { toast.error("File size exceeds 18MB limit."); return; }
    
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = () => setImagePreview(reader.result as string);
    reader.readAsDataURL(file);
  }

  async function handleFormSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canGenerate) { toast.error("Free trial exhausted. Configure your API Key in Settings."); return; }
    if (prompt.trim().length < 5) { toast.error("Describe your script in more detail."); return; }

    setSubmitting(true);
    try {
      let imageBase64: string | undefined;
      let imageMimeType: string | undefined;
      if (imageFile) {
        imageBase64 = await fileToBase64(imageFile);
        imageMimeType = imageFile.type;
      }
      await startFn({ 
        data: { 
          prompt, 
          context: contextText || undefined, 
          modelTier, 
          aspectRatio, 
          imageBase64, 
          imageMimeType 
        } 
      });
      toast.success("Generation queued! Renders take around 1-3 minutes.");
      
      // Reset Form fields
      setPrompt(""); 
      setContextText(""); 
      setImageFile(null); 
      setImagePreview(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      
      qc.invalidateQueries({ queryKey: ["video-generations"] });
      qc.invalidateQueries({ queryKey: ["creator-settings"] });
    } catch (err) {
      toast.error("Failed to queue video generation.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Are you sure you want to delete this rendering?")) return;
    try {
      await deleteFn({ data: { id } });
      qc.invalidateQueries({ queryKey: ["video-generations"] });
    } catch (e) { 
      toast.error("Failed to delete video record."); 
    }
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-6xl">
      <header>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2">
          <Film className="size-7 text-[var(--neon-pink)]" /> Video Studio IA
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Generate short video assets with Gemini Veo 3.0 from product images and prompts.
        </p>
      </header>

      {/* Trial warnings */}
      {settings.data && !hasOwnKey && trialRemaining > 0 && (
        <Card className="border-cyan-500/40 bg-cyan-500/5">
          <CardContent className="p-4 flex items-start gap-3 text-sm">
            <Sparkles className="size-5 text-cyan-500 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-semibold">{trialRemaining} of {settings.data.trialLimit} free generations remaining</p>
              <p className="text-muted-foreground text-xs mt-1">
                Trial runs on system balance. You can connect your Google AI Studio API Key in configurations at any time.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {settings.data && !canGenerate && (
        <Card className="border-red-500/40 bg-red-500/5">
          <CardContent className="p-4 flex items-start gap-3 text-sm">
            <AlertCircle className="size-5 text-red-500 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-semibold">Free trial limit reached</p>
              <p className="text-muted-foreground text-xs mt-1">
                Configure your own Google AI Studio credentials in settings to unlock unlimited generation.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Creation card */}
        <Card>
          <CardHeader><CardTitle className="text-lg flex items-center gap-2"><Sparkles className="size-4" /> New AI Video</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={handleFormSubmit} className="space-y-4">
              <div>
                <Label>Product Image (Optional - Image-to-Video Mode)</Label>
                <div className="mt-1">
                  <Input 
                    ref={fileInputRef} 
                    type="file" 
                    accept="image/jpeg,image/png,image/webp" 
                    onChange={(e) => handleFileChange(e.target.files?.[0] || null)} 
                  />
                </div>
                {imagePreview && (
                  <img src={imagePreview} alt="preview" className="mt-2 rounded-md max-h-40 border" />
                )}
              </div>

              <div>
                <Label htmlFor="ctx">Product Context / Key Strengths</Label>
                <Input 
                  id="ctx" 
                  placeholder="Ex: running shoes, FlyRun brand, lightweight & comfortable" 
                  value={contextText} 
                  onChange={(e) => setContextText(e.target.value)} 
                  maxLength={500} 
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <Label htmlFor="prompt">Video Script / Directives</Label>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={handleOptimizePrompt}
                    disabled={optimizingPrompt}
                    className="h-7 text-xs font-semibold px-2 text-cyan-500 gap-1 shrink-0"
                  >
                    {optimizingPrompt ? (
                      <>
                        <Loader2 className="size-3 animate-spin" />
                        Optimizing...
                      </>
                    ) : (
                      <>
                        <Sparkles className="size-3 animate-pulse text-cyan-500" />
                        Optimize Script
                      </>
                    )}
                  </Button>
                </div>
                <Textarea 
                  id="prompt" 
                  placeholder="Ex: Cinematic close-up of the sneaker rotating slowly, high-tech background with neon lights, volumetric smoke." 
                  value={prompt} 
                  onChange={(e) => setPrompt(e.target.value)} 
                  maxLength={2000} 
                  className="h-28" 
                  required 
                />
                <p className="text-xs text-muted-foreground mt-1">
                  💡 Note: Gemini Veo works best with script directions detailed in English.
                </p>
              </div>

              <div>
                <Label>Quality Settings</Label>
                <div className="grid grid-cols-2 gap-2 mt-1">
                  <button 
                    type="button" 
                    onClick={() => setModelTier("fast")}
                    className={`px-3 py-3 rounded-md text-left border transition-colors ${
                      modelTier === "fast" 
                        ? "border-cyan-500 bg-cyan-500/10" 
                        : "border-border hover:bg-muted"
                    }`}
                  >
                    <div className="flex items-center gap-1.5 font-medium text-sm"><Zap className="size-3.5" /> Fast Mode</div>
                    <div className="text-xs text-muted-foreground mt-0.5">Veo 3.0 Fast · ~1 min</div>
                  </button>
                  <button 
                    type="button" 
                    onClick={() => setModelTier("quality")}
                    className={`px-3 py-3 rounded-md text-left border transition-colors ${
                      modelTier === "quality" 
                        ? "border-pink-500 bg-pink-500/10" 
                        : "border-border hover:bg-muted"
                    }`}
                  >
                    <div className="flex items-center gap-1.5 font-medium text-sm"><Gem className="size-3.5" /> Quality Mode</div>
                    <div className="text-xs text-muted-foreground mt-0.5">Veo 3.0 High-Res · ~3 min</div>
                  </button>
                </div>
              </div>

              <div>
                <Label>Aspect Ratio</Label>
                <div className="flex gap-2 mt-1">
                  {(["9:16", "16:9"] as const).map((ratio) => (
                    <button 
                      key={ratio} 
                      type="button" 
                      onClick={() => setAspectRatio(ratio)}
                      className={`flex-1 px-3 py-2 rounded-md text-sm border transition-colors ${
                        aspectRatio === ratio 
                          ? "border-pink-500 bg-pink-500/10 text-pink-500" 
                          : "border-border hover:bg-muted"
                      }`}
                    >
                      {ratio === "9:16" ? "Vertical 9:16 (TikTok/Shorts)" : "Horizontal 16:9"}
                    </button>
                  ))}
                </div>
              </div>

              <Button type="submit" disabled={submitting || !canGenerate} className="w-full">
                {submitting ? (
                  <><Loader2 className="size-4 animate-spin mr-2" /> Queueing...</>
                ) : (
                  <><Upload className="size-4 mr-2" /> Render Video</>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* History card */}
        <Card>
          <CardHeader><CardTitle className="text-lg">Generation History</CardTitle></CardHeader>
          <CardContent className="space-y-3 max-h-[600px] overflow-y-auto">
            {generations.isLoading && <p className="text-sm text-muted-foreground">Loading history...</p>}
            {generations.data?.length === 0 && <p className="text-sm text-muted-foreground">No videos rendered yet.</p>}
            
            {generations.data?.map((video: any) => (
              <div key={video.id} className="border rounded-md p-3 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{video.prompt}</p>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <StatusBadge status={video.status} />
                      <span className="text-xs text-muted-foreground">{video.duration}s · {video.aspect_ratio}</span>
                      {video.used_trial_credit && (
                        <Badge variant="outline" className="text-[10px] border-cyan-500/40 text-cyan-400">trial</Badge>
                      )}
                    </div>
                  </div>
                  <button onClick={() => handleDelete(video.id)} className="text-muted-foreground hover:text-red-500 transition-colors">
                    <Trash2 className="size-4" />
                  </button>
                </div>
                {video.status === "completed" && video.videoUrl && (
                  <div className="space-y-2">
                    <video src={video.videoUrl} controls className="w-full rounded-md max-h-80" />
                    <a href={video.videoUrl} download={`video-${video.id}.mp4`} className="text-xs inline-flex items-center gap-1 text-cyan-400 hover:underline">
                      <Download className="size-3" /> Download MP4
                    </a>
                  </div>
                )}
                {video.status === "failed" && video.error_message && (
                  <p className="text-xs text-red-500 break-words">{video.error_message}</p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const badgeMap: Record<string, { label: string; className: string }> = {
    pending: { label: "In Queue", className: "bg-muted text-muted-foreground" },
    processing: { label: "Generating...", className: "bg-cyan-500/20 text-cyan-400 animate-pulse" },
    completed: { label: "Completed", className: "bg-green-500/20 text-green-400" },
    failed: { label: "Failed", className: "bg-red-500/20 text-red-400" },
  };
  const config = badgeMap[status] || badgeMap.pending;
  return <Badge variant="outline" className={config.className}>{config.label}</Badge>;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(",")[1] || "");
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
