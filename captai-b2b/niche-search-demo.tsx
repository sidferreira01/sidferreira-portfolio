import React, { useState } from "react";
import { Search, Sparkles, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

interface NicheSearchProps {
  // Callback dispatched to the parent component carrying search parameters
  onSearch: (niche: string, location: string) => Promise<void> | void;
}

export function NicheSearchDemo({ onSearch }: NicheSearchProps) {
  const [niche, setNiche] = useState("");
  const [location, setLocation] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!niche.trim()) return;
    
    setLoading(true);
    try {
      // Execute the search hook/server-function
      await onSearch(niche.trim(), location.trim());
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="relative overflow-hidden border-border/60 bg-gradient-subtle p-6 shadow-elegant">
      <div className="absolute inset-0 bg-primary/5 opacity-[0.04]" />
      <div className="relative">
        <div className="mb-4 flex items-center gap-2">
          <div className="rounded-lg bg-primary/10 p-2 text-primary">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">B2B Niche Scanning</h2>
            <p className="text-xs text-muted-foreground">
              Trigger a geo-targeted lead search and let AI analyze business weaknesses.
            </p>
          </div>
        </div>
        
        <form onSubmit={handleSubmit} className="grid gap-3 md:grid-cols-[1.4fr_1fr_auto]">
          <div className="space-y-1.5">
            <Label htmlFor="niche" className="text-xs font-medium">
              Niche / Industry Keyword
            </Label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="niche"
                placeholder="Ex: dentist, bakery, local stores..."
                className="pl-9 bg-background"
                value={niche}
                onChange={(e) => setNiche(e.target.value)}
              />
            </div>
          </div>
          
          <div className="space-y-1.5">
            <Label htmlFor="location" className="text-xs font-medium">
              Location / City
            </Label>
            <Input
              id="location"
              placeholder="Ex: São Paulo, SP"
              className="bg-background"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
            />
          </div>
          
          <div className="flex items-end">
            <Button
              type="submit"
              disabled={loading || !niche.trim()}
              className="w-full shadow-md hover:opacity-90 md:w-auto"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Scanning...
                </>
              ) : (
                <>
                  <Sparkles className="mr-2 h-4 w-4" />
                  Scan Niche
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </Card>
  );
}
