import React, { useState, useCallback } from "react";
import {
  DndContext,
  DragEndEvent,
  DragOverEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
} from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/lib/supabaseClient"; // Standardized path
import { useAuth } from "@/hooks/useAuth";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { RefreshButton } from "@/components/ui/RefreshButton";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import {
  Kanban,
  MessageSquare,
  Clock,
  DollarSign,
  TrendingUp,
  CheckCircle,
  XCircle,
  Loader2,
} from "lucide-react";
import { differenceInDays } from "date-fns";

const COLUMNS = [
  {
    id: "active",
    label: "New / Active",
    icon: MessageSquare,
    color: "text-primary",
    bg: "bg-primary/5 border-primary/20",
    badgeVariant: "default" as const,
  },
  {
    id: "pending",
    label: "In Progress",
    icon: Clock,
    color: "text-amber-500",
    bg: "bg-amber-500/5 border-amber-500/20",
    badgeVariant: "outline" as const,
  },
  {
    id: "won",
    label: "Won",
    icon: CheckCircle,
    color: "text-emerald-500",
    bg: "bg-emerald-500/5 border-emerald-500/20",
    badgeVariant: "default" as const,
  },
  {
    id: "lost",
    label: "Lost",
    icon: XCircle,
    color: "text-destructive",
    bg: "bg-destructive/5 border-destructive/20",
    badgeVariant: "destructive" as const,
  },
];

interface PipelineConversation {
  id: string;
  status: string;
  updated_at: string;
  customer: { name: string; phone: string } | null;
  analysis: {
    sentiment: string | null;
    profit_potential: number | null;
    churn_risk_level?: string | null;
  } | null;
}

function ConversationCard({
  conversation,
  isDragging = false,
}: {
  conversation: PipelineConversation;
  isDragging?: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging: isSortDragging } =
    useSortable({ id: conversation.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isSortDragging ? 0.4 : 1,
  };

  const daysSince = differenceInDays(new Date(), new Date(conversation.updated_at));

  const sentimentEmoji: Record<string, string> = {
    positive: "😊",
    negative: "😟",
    neutral: "😐",
    mixed: "🤔",
  };

  const potential = conversation.analysis?.profit_potential;
  const sentiment = conversation.analysis?.sentiment || "neutral";
  const churnRisk = conversation.analysis?.churn_risk_level;

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <Link to={`/conversation/${conversation.id}`} onClick={(e) => isSortDragging && e.preventDefault()}>
        <Card
          className={`cursor-grab active:cursor-grabbing hover:shadow-md transition-all select-none ${
            isDragging ? "shadow-xl rotate-1" : ""
          }`}
        >
          <CardContent className="p-3 space-y-2">
            <div className="flex items-start justify-between gap-2">
              <p className="font-medium text-foreground text-sm leading-tight">
                {conversation.customer?.name || "Client"}
              </p>
              <span className="text-base flex-shrink-0">
                {sentimentEmoji[sentiment]}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              {conversation.customer?.phone || ""}
            </p>
            
            {/* Realtime AI analysis badges */}
            <div className="flex flex-wrap gap-1.5 pt-0.5">
              {potential !== null && potential !== undefined && potential >= 9 && (
                <Badge variant="outline" className="bg-amber-500/10 text-amber-500 border-amber-500/30 text-[9px] py-0.5 px-1.5 font-extrabold uppercase tracking-wide">
                  🔥 Hot Lead
                </Badge>
              )}
              {churnRisk === "critical" && (
                <Badge variant="outline" className="bg-destructive/15 text-destructive border-destructive/45 text-[9px] py-0.5 px-1.5 font-extrabold uppercase tracking-wide animate-pulse">
                  🚨 Churn Risk
                </Badge>
              )}
            </div>
            
            <div className="flex items-center justify-between pt-1">
              <Badge variant="secondary" className="text-xs gap-1 px-1.5">
                <Clock className="h-2.5 w-2.5" />
                {daysSince === 0 ? "Today" : `${daysSince}d`}
              </Badge>
              {potential !== null && potential !== undefined && (
                <div className="flex items-center gap-1 text-xs font-semibold text-emerald-500">
                  <DollarSign className="h-3 w-3" />
                  Score: {potential}/10
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </Link>
    </div>
  );
}

function PipelineColumn({
  column,
  conversations,
  isOver,
}: {
  column: (typeof COLUMNS)[0];
  conversations: PipelineConversation[];
  isOver?: boolean;
}) {
  const Icon = column.icon;
  return (
    <div
      className={`flex flex-col rounded-xl border-2 min-h-[400px] w-full transition-all duration-150 ${
        isOver
          ? `${column.bg} ring-2 ring-offset-1 ring-primary/50 scale-[1.01]`
          : column.bg
      }`}
    >
      <div className="p-3 border-b border-border/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className={`h-4 w-4 ${column.color}`} />
            <span className="font-semibold text-sm text-foreground">{column.label}</span>
          </div>
          <Badge variant={column.badgeVariant} className="text-xs">
            {conversations.length}
          </Badge>
        </div>
      </div>
      <div className={`p-2 flex-1 space-y-2 transition-colors duration-150 ${isOver ? 'bg-primary/5 rounded-b-xl' : ''}`}>
        <SortableContext items={conversations.map((c) => c.id)} strategy={verticalListSortingStrategy}>
          {conversations.map((conv) => (
            <ConversationCard key={conv.id} conversation={conv} />
          ))}
        </SortableContext>
        {conversations.length === 0 && (
          <div className={`flex items-center justify-center h-24 text-xs ${
            isOver ? 'text-primary font-medium' : 'text-muted-foreground'
          }`}>
            {isOver ? 'Drop here' : 'No conversations'}
          </div>
        )}
      </div>
    </div>
  );
}

export default function KanbanPipeline() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [activeCard, setActiveCard] = useState<PipelineConversation | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [activeColumnId, setActiveColumnId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  const { data: conversations, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["pipeline-conversations", user?.id],
    queryFn: async (): Promise<PipelineConversation[]> => {
      const { data, error } = await supabase
        .from("conversations")
        .select(`
          id,
          status,
          updated_at,
          customer:customers(name, phone),
          analysis:ai_analyses(sentiment, profit_potential, churn_risk_level)
        `)
        .order("updated_at", { ascending: false });

      if (error) throw error;

      return (data || []).map((conv: any) => ({
        id: conv.id,
        status: conv.status,
        updated_at: conv.updated_at,
        customer: Array.isArray(conv.customer) ? conv.customer[0] : conv.customer,
        analysis: Array.isArray(conv.analysis) ? conv.analysis[0] : conv.analysis,
      }));
    },
    enabled: !!user,
  });

  const grouped = COLUMNS.reduce(
    (acc, col) => {
      acc[col.id] = (conversations || []).filter((c) => c.status === col.id);
      return acc;
    },
    {} as Record<string, PipelineConversation[]>
  );

  const findColumn = useCallback(
    (id: string) => {
      for (const col of COLUMNS) {
        if ((grouped[col.id] || []).some((c) => c.id === id)) return col.id;
      }
      return null;
    },
    [grouped]
  );

  const handleDragStart = (event: DragStartEvent) => {
    const conv = (conversations || []).find((c) => c.id === event.active.id);
    setActiveCard(conv || null);
  };

  const handleDragOver = (event: DragOverEvent) => {
    const { over } = event;
    if (!over) {
      setActiveColumnId(null);
      return;
    }
    const isColumn = COLUMNS.some((c) => c.id === over.id);
    const colId = isColumn ? (over.id as string) : findColumn(over.id as string);
    setActiveColumnId(colId);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    setActiveCard(null);
    setActiveColumnId(null);
    const { active, over } = event;
    if (!over) return;

    const targetColId = COLUMNS.some((c) => c.id === over.id)
      ? (over.id as string)
      : findColumn(over.id as string);

    if (!targetColId) return;

    const currentColId = findColumn(active.id as string);
    if (currentColId === targetColId) return;

    setIsUpdating(true);
    try {
      const { error } = await supabase
        .from("conversations")
        .update({ status: targetColId })
        .eq("id", active.id);

      if (error) throw error;

      // Optimistic cache update
      queryClient.setQueryData(
        ["pipeline-conversations", user?.id],
        (old: PipelineConversation[] | undefined) =>
          (old || []).map((c) =>
            c.id === active.id ? { ...c, status: targetColId } : c
          )
      );

      const colLabel = COLUMNS.find((c) => c.id === targetColId)?.label;
      toast.success(`Conversation moved to "${colLabel}"`);
    } catch (err: any) {
      toast.error("Error moving conversation", { description: err.message });
      queryClient.invalidateQueries({ queryKey: ["pipeline-conversations"] });
    } finally {
      setIsUpdating(false);
    }
  };

  const total = (conversations || []).length;
  const wonCount = grouped["won"]?.length || 0;
  const conversionRate = total > 0 ? Math.round((wonCount / total) * 100) : 0;

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Kanban className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Sales Pipeline</h1>
            <p className="text-sm text-muted-foreground">Drag and drop conversations to change status</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {isUpdating && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
          <RefreshButton onClick={refetch} isLoading={isFetching} />
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="bg-primary/5 border-primary/20">
          <CardContent className="pt-4 pb-3 flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground">Total Leads</p>
              <p className="text-2xl font-bold text-primary">{total}</p>
            </div>
            <MessageSquare className="h-7 w-7 text-primary/30" />
          </CardContent>
        </Card>
        <Card className="bg-emerald-500/5 border-emerald-500/20">
          <CardContent className="pt-4 pb-3 flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground">Won Deals</p>
              <p className="text-2xl font-bold text-emerald-500">{wonCount}</p>
            </div>
            <CheckCircle className="h-7 w-7 text-emerald-500/30" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground">Conversion Rate</p>
              <p className="text-2xl font-bold">{conversionRate}%</p>
            </div>
            <TrendingUp className="h-7 w-7 text-muted-foreground/30" />
          </CardContent>
        </Card>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-96 rounded-xl" />
          ))}
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDragEnd={handleDragEnd}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {COLUMNS.map((col) => (
              <PipelineColumn
                key={col.id}
                column={col}
                conversations={grouped[col.id] || []}
                isOver={activeColumnId === col.id}
              />
            ))}
          </div>

          <DragOverlay>
            {activeCard && (
              <div className="rotate-2 shadow-2xl">
                <ConversationCard conversation={activeCard} isDragging />
              </div>
            )}
          </DragOverlay>
        </DndContext>
      )}
    </div>
  );
}
