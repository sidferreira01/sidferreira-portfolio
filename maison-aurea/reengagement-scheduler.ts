// Daily retention job: re-engage clients N days after a completed appointment.
// Triggered daily via pg_cron calling this edge function endpoint.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const EVO_URL = Deno.env.get("EVOLUTION_API_URL")!;
const EVO_KEY = Deno.env.get("EVOLUTION_API_KEY")!;
const EVO_INSTANCE = Deno.env.get("EVOLUTION_INSTANCE")!;
const SITE_URL = Deno.env.get("SITE_URL") ?? "https://maisonaurea.com.br";

function formatBrazilianPhone(digits: string) {
  const cleanDigits = digits.replace(/\D/g, "");
  // Ensure the country code '55' prefix is prepended correctly
  return cleanDigits.startsWith("55") ? cleanDigits : `55${cleanDigits}`;
}

async function sendWhatsAppText(number: string, message: string) {
  const url = `${EVO_URL.replace(/\/$/, "")}/message/sendText/${EVO_INSTANCE}`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: EVO_KEY },
    body: JSON.stringify({ 
      number: formatBrazilianPhone(number), 
      text: message, 
      options: { delay: 600 } 
    }),
  });
  return response.ok;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: corsHeaders });
  
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );

  // Get current date localized to Brazilian Time (UTC-3)
  const now = new Date();
  const brTimeOffset = new Date(now.getTime() - 3 * 60 * 60 * 1000);
  const todayDateString = brTimeOffset.toISOString().slice(0, 10);

  // Pull past completed or confirmed appointments that have not yet had a retention message sent
  const { data: appointments, error } = await supabase
    .from("appointments")
    .select("id, client_name, client_whatsapp, appointment_datetime, status, retention_sent_at, services(name, retention_days)")
    .in("status", ["completed", "confirmed"])
    .is("retention_sent_at", null)
    .lt("appointment_datetime", new Date().toISOString());

  if (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const dispatchedAppointments: string[] = [];
  
  for (const appointment of appointments ?? []) {
    const retentionDays = (appointment as any).services?.retention_days as number | null;
    if (!retentionDays) continue;
    
    // Calculate target date: appointment date + retention_days
    const appointmentDate = new Date(appointment.appointment_datetime);
    const targetDate = new Date(appointmentDate.getTime() + retentionDays * 86400000);
    const targetDateString = new Date(targetDate.getTime() - 3 * 60 * 60 * 1000).toISOString().slice(0, 10);
    
    // If target re-engagement day matches today, dispatch reminder
    if (targetDateString === todayDateString) {
      const serviceName = (appointment as any).services.name;
      const messageText = `Olá ${appointment.client_name}! ✨ Faz um tempinho desde a sua última sessão de ${serviceName} com a gente. Que tal reservar um momento especial para seu autocuidado essa semana? Agende de forma simples aqui: ${SITE_URL}`;
      
      const success = await sendWhatsAppText(appointment.client_whatsapp, messageText);
      if (success) {
        // Log send status to database
        await supabase
          .from("appointments")
          .update({ retention_sent_at: new Date().toISOString() })
          .eq("id", appointment.id);
        
        dispatchedAppointments.push(appointment.id);
      }
    }
  }

  return new Response(JSON.stringify({ 
    success: true, 
    sent_count: dispatchedAppointments.length, 
    sent_ids: dispatchedAppointments 
  }), {
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
});
