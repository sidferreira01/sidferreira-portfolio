import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

// Input validation constants
const MAX_MESSAGE_LENGTH = 10000;
const MAX_NAME_LENGTH = 200;
const MAX_PHONE_LENGTH = 50;

/**
 * Downloads WhatsApp media binary using Meta media_id
 */
async function downloadWhatsAppMedia(mediaId: string, accessToken: string): Promise<ArrayBuffer | null> {
  try {
    const metaRes = await fetch(`https://graph.facebook.com/v18.0/${mediaId}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!metaRes.ok) return null;
    const meta = await metaRes.json();
    const mediaRes = await fetch(meta.url, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!mediaRes.ok) return null;
    return await mediaRes.arrayBuffer();
  } catch {
    return null;
  }
}

/**
 * Transcribes audio buffer using OpenAI Whisper API
 */
async function transcribeAudio(audioBuffer: ArrayBuffer, openaiKey: string): Promise<string | null> {
  try {
    const formData = new FormData();
    formData.append("file", new Blob([audioBuffer], { type: "audio/ogg" }), "audio.ogg");
    formData.append("model", "whisper-1");
    formData.append("language", "pt");

    const res = await fetch("https://api.openai.com/v1/audio/transcriptions", {
      method: "POST",
      headers: { Authorization: `Bearer ${openaiKey}` },
      body: formData,
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.text || null;
  } catch {
    return null;
  }
}

/**
 * Triggers AI analysis for a conversation (fire-and-forget, non-blocking)
 */
function triggerAutoAnalysis(conversationId: string, supabaseUrl: string, serviceKey: string): void {
  fetch(`${supabaseUrl}/functions/v1/analyze-conversation`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${serviceKey}`,
    },
    body: JSON.stringify({ conversationId, useServiceRole: true }),
  }).catch((err) => console.error("[AUTO-ANALYSIS] Fire-and-forget failed:", err));
}

function sanitizeString(input: string | undefined | null, maxLength: number): string {
  if (!input) return '';
  return String(input).trim().substring(0, maxLength);
}

function sanitizePhone(phone: string | undefined | null): string {
  if (!phone) return '';
  return String(phone).replace(/[^\d+]/g, '').substring(0, MAX_PHONE_LENGTH);
}

serve(async (req) => {
  // Handle CORS
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  // Handle WhatsApp API verification challenge (GET)
  if (req.method === "GET") {
    const url = new URL(req.url);
    const mode = url.searchParams.get("hub.mode");
    const token = url.searchParams.get("hub.verify_token");
    const challenge = url.searchParams.get("hub.challenge");

    const VERIFY_TOKEN = Deno.env.get("WHATSAPP_VERIFY_TOKEN");

    if (mode === "subscribe" && token === VERIFY_TOKEN) {
      return new Response(challenge, {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "text/plain" },
      });
    } else {
      return new Response("Forbidden", { status: 403, headers: corsHeaders });
    }
  }

  // Handle inbound webhook events (POST)
  if (req.method === "POST") {
    try {
      const body = await req.json();

      const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
      const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
      const supabase = createClient(supabaseUrl, supabaseKey);

      if (body.object === "whatsapp_business_account") {
        for (const entry of body.entry || []) {
          for (const change of entry.changes || []) {
            if (change.field === "messages") {
              const value = change.value;
              const metadata = value.metadata;
              const phoneNumberId = metadata?.phone_number_id;

              if (!phoneNumberId) continue;

              // Routing message to correct Tenant/Company
              const { data: companySecret } = await supabase
                .from("company_secrets")
                .select("company_id")
                .eq("whatsapp_phone_number_id", phoneNumberId)
                .maybeSingle();

              if (!companySecret) continue;

              const companyId = companySecret.company_id;

              for (const message of value.messages || []) {
                const senderPhone = sanitizePhone(message.from);
                if (!senderPhone) continue;

                // Handle Multimodal Inbound Voice Note Transcription
                let messageText: string;
                if (message.type === "audio" && message.audio?.id) {
                  const openaiKey = Deno.env.get("OPENAI_API_KEY");
                  const whatsappToken = Deno.env.get("WHATSAPP_ACCESS_TOKEN");

                  if (openaiKey && whatsappToken) {
                    const audioBuffer = await downloadWhatsAppMedia(message.audio.id, whatsappToken);
                    if (audioBuffer) {
                      const transcript = await transcribeAudio(audioBuffer, openaiKey);
                      messageText = transcript ? `🎙️ [Audio]: ${transcript}` : "[Audio — transcription unavailable]";
                    } else {
                      messageText = "[Audio — download failed]";
                    }
                  } else {
                    messageText = "[Audio]";
                  }
                } else {
                  messageText = sanitizeString(
                    message.text?.body || message.caption || "[Media]",
                    MAX_MESSAGE_LENGTH
                  );
                }

                const rawTimestamp = parseInt(message.timestamp);
                const timestamp = isNaN(rawTimestamp) 
                  ? new Date().toISOString() 
                  : new Date(rawTimestamp * 1000).toISOString();

                // Find or create customer
                let { data: customer } = await supabase
                  .from("customers")
                  .select("id")
                  .eq("phone", senderPhone)
                  .eq("company_id", companyId)
                  .maybeSingle();

                if (!customer) {
                  const contact = value.contacts?.find((c: any) => c.wa_id === message.from);
                  const rawName = contact?.profile?.name || `Client ${senderPhone.slice(-4)}`;
                  const customerName = sanitizeString(rawName, MAX_NAME_LENGTH);

                  const { data: newCustomer, error: insertError } = await supabase
                    .from("customers")
                    .insert({
                      company_id: companyId,
                      name: customerName,
                      phone: senderPhone,
                    })
                    .select("id")
                    .single();

                  if (insertError) {
                    // Fallback to prevent race-condition insert duplication
                    const { data: retryCustomer } = await supabase
                      .from("customers")
                      .select("id")
                      .eq("phone", senderPhone)
                      .eq("company_id", companyId)
                      .single();
                    customer = retryCustomer;
                  } else {
                    customer = newCustomer;
                  }
                }

                if (!customer) continue;

                // Fetch or instantiate active thread
                let { data: conversation } = await supabase
                  .from("conversations")
                  .select("id")
                  .eq("customer_id", customer.id)
                  .eq("company_id", companyId)
                  .in("status", ["active", "pending"])
                  .maybeSingle();

                if (!conversation) {
                  const { data: newConversation } = await supabase
                    .from("conversations")
                    .insert({
                      company_id: companyId,
                      customer_id: customer.id,
                      status: "active",
                    })
                    .select("id")
                    .single();
                  conversation = newConversation;
                }

                if (!conversation) continue;

                // Save inbound message
                const { error: msgError } = await supabase
                  .from("messages")
                  .insert({
                    conversation_id: conversation.id,
                    sender_type: "customer",
                    content: messageText,
                    sent_at: timestamp,
                  });

                if (!msgError) {
                  // Count thread records to trigger analysis after 3rd message
                  const { count: msgCount } = await supabase
                    .from("messages")
                    .select("id", { count: "exact", head: true })
                    .eq("conversation_id", conversation.id);

                  if ((msgCount || 0) >= 3) {
                    triggerAutoAnalysis(conversation.id, supabaseUrl, supabaseKey);
                  }
                }

                // Update customer activity heartbeat
                await supabase
                  .from("customers")
                  .update({ last_contact_at: timestamp })
                  .eq("id", customer.id);
              }
            }
          }
        }
      }

      return new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    } catch (error) {
      return new Response(JSON.stringify({ error: "Internal Server Error" }), {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
  }

  return new Response("Method not allowed", { status: 405, headers: corsHeaders });
});
