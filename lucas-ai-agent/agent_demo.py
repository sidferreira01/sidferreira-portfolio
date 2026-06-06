import os
import sys
import time
import json
import sqlite3
import threading
import urllib.request
import urllib.error
import io
import base64
from datetime import datetime

# Force UTF-8 encoding for stdout (useful on Windows command prompt environments)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Custom lightweight .env parser to avoid third-party library dependency issues
def load_env_file(filepath=".env"):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, val = line.split("=", 1)
                        os.environ[key.strip()] = val.strip()

# Initialize environment variables
load_env_file()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "5005"))
FOLLOWUP_INTERVAL_MINUTES = float(os.getenv("FOLLOWUP_INTERVAL_MINUTES", "2"))
MAX_FOLLOWUPS = int(os.getenv("MAX_FOLLOWUPS", "2"))

# Initialize Gemini 2.5 Flash
try:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.5-flash')
    print("🤖 Gemini 2.5 Flash initialized successfully.")
except Exception as e:
    print(f"🚨 Error initializing Gemini API: {e}")
    gemini_model = None

# Thread-safe SQLite access control
db_lock = threading.Lock()
DB_FILE = "agent_memory.db"

def get_db_connection():
    # check_same_thread=False allows cross-thread dispatching inside our locked context
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes local relational tables for persistent conversation memories."""
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create conversations master table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                phone TEXT PRIMARY KEY,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_interaction_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                followup_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active'
            )
        """)
        
        # Create messages history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT,
                sender TEXT,
                msg_type TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(phone) REFERENCES conversations(phone)
            )
        """)
        conn.commit()
        conn.close()
        print("💾 SQLite database tables initialized.")

init_db()

# --- WHATSAPP / EVOLUTION API HELPERS ---

def send_chat_state(phone, state="composing"):
    """Sends presence states like 'composing' or 'recording' to WhatsApp."""
    url = f"{EVOLUTION_API_URL}/chat/updateChatState/{EVOLUTION_INSTANCE}"
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "number": str(phone),
        "state": state
    }
    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode('utf-8'), 
            headers=headers, 
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            pass
    except Exception as e:
        print(f"⚠️ Error updating WhatsApp state: {e}")

def send_whatsapp_message(phone, text):
    """Sends a final text message back to WhatsApp."""
    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "number": str(phone),
        "text": text,
        "options": {
            "delay": 1200,
            "presence": "composing"
        }
    }
    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode('utf-8'), 
            headers=headers, 
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"🚨 Error dispatching WhatsApp message: {e}")
        return None

# --- DATABASE / SQLITE OPERATIONS ---

def save_or_update_conversation(phone, name=""):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT phone, followup_count FROM conversations WHERE phone = ?", (phone,))
        row = cursor.fetchone()
        
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if row:
            # Refresh timestamps and reset active counters upon user incoming message
            cursor.execute("""
                UPDATE conversations 
                SET last_interaction_at = ?, followup_count = 0, status = 'active'
                WHERE phone = ?
            """, (now_str, phone))
        else:
            # Create a new conversation thread record
            cursor.execute("""
                INSERT INTO conversations (phone, name, created_at, last_interaction_at, followup_count, status)
                VALUES (?, ?, ?, ?, 0, 'active')
            """, (phone, name, now_str, now_str))
            
        conn.commit()
        conn.close()

def save_message(phone, sender, msg_type, content):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            INSERT INTO messages (phone, sender, msg_type, content, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (phone, sender, msg_type, content, now_str))
        
        cursor.execute("""
            UPDATE conversations 
            SET last_interaction_at = ?
            WHERE phone = ?
        """, (now_str, phone))
        
        conn.commit()
        conn.close()

def get_chat_history(phone, limit=15):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sender, content FROM messages 
            WHERE phone = ? 
            ORDER BY id DESC 
            LIMIT ?
        """, (phone, limit))
        rows = cursor.fetchall()
        conn.close()
        
        # Reverse to ensure chronological order
        return [{"sender": r["sender"], "content": r["content"]} for r in reversed(rows)]

# --- GEMINI AGENT RESPONDER ---

def get_human_response(phone, name, text_message, media_data=None):
    """Processes message history + multimodal media inputs to return a humanized response."""
    if not gemini_model:
        return "Desculpe, meu cérebro de IA está inativo no momento."
        
    history = get_chat_history(phone, limit=12)
    
    # Custom system instructions for Brazilian localized human conversational style
    system_instruction = (
        "Você é a Miriam, uma assistente virtual de demonstração extremamente humanizada, inteligente e prestativa.\n"
        f"Você está conversando no WhatsApp com {name or 'cliente'}.\n\n"
        "REGRAS DE COMPORTAMENTO E TOM DE VOZ:\n"
        "1. Escreva como um brasileiro comum fala no WhatsApp: informal, caloroso, natural e direto.\n"
        "2. NUNCA use formatação pesada do tipo markdown robótico. NÃO use `**` para negrito (se precisar destacar algo, envolva em APENAS UM asterisco de cada lado: *palavra*).\n"
        "3. Não use asteriscos para marcadores de lista. Use traços (-) ou emojis de forma moderada.\n"
        "4. Escreva respostas curtas (geralmente de 2 a 4 linhas) para parecer uma pessoa digitando de verdade no celular.\n"
        "5. Você tem memória das mensagens anteriores. Mostre que se lembra do que foi discutido acima se o cliente fizer referência a algo já dito.\n"
        "6. Use gírias leves (como 'cara', 'beleza', 'tranquilo', 'valeu', 'né') se fizer sentido, mas sem exageros.\n"
        "7. Se receber um áudio, transcreva ou resuma o que compreendeu do áudio na sua resposta e responda à pergunta dele amigavelmente.\n"
        "8. Se receber uma imagem, descreva o que vê ou responda à pergunta do cliente sobre ela com naturalidade.\n"
    )
    
    formatted_prompt = "Conversational History:\n"
    for msg in history:
        sender_label = "Você (Miriam)" if msg["sender"] == "agent" else (name or "Cliente")
        formatted_prompt += f"- {sender_label}: {msg['content']}\n"
    
    formatted_prompt += f"\nLatest customer message:\n"
    if text_message:
        formatted_prompt += f"\"{text_message}\"\n"
    else:
        formatted_prompt += "[Media attachment]\n"
        
    formatted_prompt += "\nFormulate a brief response matching the rules and tone of voice guidelines."
    
    parts = [system_instruction, formatted_prompt]
    
    # Append Base64 binary media object for native multimodal processing
    if media_data:
        parts.append({
            "mime_type": media_data["mime"],
            "data": media_data["data"]
        })
        print(f"📷 Appending native multimodal media block: {media_data['mime']}")

    try:
        response = gemini_model.generate_content(parts)
        # Normalize text and strip markdown bulleting conventions
        cleaned_text = response.text.replace("**", "*").strip()
        return cleaned_text
    except Exception as e:
        print(f"🚨 Error generating LLM response: {e}")
        return "Tive um pequeno problema para processar agora. Pode repetir? 😅"

# --- WEBHOOK HTTP SERVER ---

from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class WebhookHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        # Override to keep terminal clean
        pass

    def do_POST(self):
        if self.path == "/webhook":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                payload = json.loads(post_data.decode('utf-8'))
                
                # Execute webhook processing inside a separate thread to reply HTTP 200 instantly
                threading.Thread(target=self.process_webhook_payload, args=(payload,)).start()
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "received"}).encode('utf-8'))
            except Exception as e:
                print(f"🚨 Webhook request error: {e}")
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def process_webhook_payload(self, payload):
        try:
            body = payload
            if "body" in payload:
                body = payload["body"]
            if "data" in body:
                body = body["data"]
            
            key = body.get("key", {})
            remote_jid = key.get("remoteJid", "") or body.get("sender", "")
                
            if not remote_jid or "@g.us" in remote_jid:
                # Bypass group messages or empty IDs
                return
                
            phone = remote_jid.split("@")[0]
            name = body.get("pushName", "") or f"Client {phone[-4:]}"
            
            message = body.get("message", {})
            if not message:
                return
                
            text = message.get("conversation", "")
            if not text:
                text = message.get("extendedTextMessage", {}).get("text", "")
                
            audio_msg = message.get("audioMessage")
            image_msg = message.get("imageMessage")
            
            has_media = bool(audio_msg or image_msg)
            media_data = None
            msg_type = "text"
            
            if has_media:
                # Read Base64 directly from incoming message payload
                base64_str = body.get("base64") or body.get("message_base64") or payload.get("base64")
                if base64_str:
                    mime = audio_msg.get("mimetype") if audio_msg else image_msg.get("mimetype")
                    msg_type = "audio" if audio_msg else "image"
                    
                    if ";base64," in base64_str:
                        base64_str = base64_str.split(";base64,")[1]
                        
                    try:
                        media_data = {
                            "mime": mime,
                            "data": base64.b64decode(base64_str)
                        }
                        text = "🎙️ [Voice note]" if audio_msg else "📸 [Image attachment]"
                    except Exception as e:
                        print(f"🚨 Failed decoding base64 payload: {e}")
            
            if not text and not media_data:
                return

            print(f"\n📩 Inbound message from {name} ({phone}): {text}")
            
            save_or_update_conversation(phone, name)
            save_message(phone, "user", msg_type, text)
            
            # Simulated typing animation state trigger
            send_chat_state(phone, "composing")
            
            # Fetch AI generation
            reply = get_human_response(phone, name, text if msg_type == "text" else None, media_data)
            
            # Introduce typing delay based on reply length (40ms per character)
            typing_delay = min(max(len(reply) * 0.04, 1.5), 5.0)
            time.sleep(typing_delay)
            
            save_message(phone, "agent", "text", reply)
            send_whatsapp_message(phone, reply)
            print(f"📤 Agent: {reply}")
            
        except Exception as e:
            print(f"🚨 Error processing webhook thread: {e}")

# --- PROACTIVE FOLLOW-UP SCANNERS ---

def proactive_followup_runner():
    """Background thread checking database for quiet threads to trigger follow-up pings."""
    print("⏳ Proactive follow-up runner active.")
    
    while True:
        try:
            interval_seconds = FOLLOWUP_INTERVAL_MINUTES * 60
            now = datetime.now()
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT phone, name, last_interaction_at, followup_count, status 
                FROM conversations 
                WHERE status != 'paused' AND followup_count < ?
            """, (MAX_FOLLOWUPS,))
            
            conversations = cursor.fetchall()
            conn.close()
            
            for conv in conversations:
                phone = conv["phone"]
                name = conv["name"]
                last_interaction = datetime.strptime(conv["last_interaction_at"], "%Y-%m-%d %H:%M:%S")
                elapsed = (now - last_interaction).total_seconds()
                
                # If silent duration is greater than interval config
                if elapsed >= interval_seconds:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT sender FROM messages WHERE phone = ? ORDER BY id DESC LIMIT 1", (phone,))
                    last_msg = cursor.fetchone()
                    conn.close()
                    
                    # Ensure agent was indeed the last speaker
                    if last_msg and last_msg["sender"] == "agent":
                        followup_msg = generate_followup_content(phone, name)
                        
                        if followup_msg:
                            print(f"\n⏰ Follow-up triggered for {name} ({phone}) - Silent for {elapsed/60:.1f} mins.")
                            
                            send_chat_state(phone, "composing")
                            time.sleep(3)
                            
                            save_message(phone, "agent", "text", followup_msg)
                            send_whatsapp_message(phone, followup_msg)
                            
                            with db_lock:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE conversations 
                                    SET followup_count = followup_count + 1, status = 'followup_sent'
                                    WHERE phone = ?
                                """, (phone,))
                                conn.commit()
                                conn.close()
                                
                            print(f"📤 Agent Follow-up: {followup_msg}")
                            
        except Exception as e:
            print(f"🚨 Error in follow-up thread: {e}")
            
        time.sleep(10)

def generate_followup_content(phone, name):
    if not gemini_model:
        return None
        
    history = get_chat_history(phone, limit=10)
    if not history:
        return None
        
    system_instruction = (
        "Você é a Miriam, a mesma assistente virtual conversacional no WhatsApp.\n"
        f"O cliente {name or 'cliente'} parou de te responder no meio da conversa.\n"
        "Crie um ping de follow-up amigável, curto e natural de no máximo 1 ou 2 linhas "
        "baseado no histórico recente da conversa. Seja informal e amigável."
    )
    
    formatted_prompt = "Conversational History:\n"
    for msg in history:
        sender_label = "Você (Miriam)" if msg["sender"] == "agent" else (name or "Cliente")
        formatted_prompt += f"- {sender_label}: {msg['content']}\n"
        
    formatted_prompt += "\nCreate a short follow-up."
    
    try:
        response = gemini_model.generate_content([system_instruction, formatted_prompt])
        return response.text.replace("**", "*").strip()
    except Exception as e:
        print(f"🚨 Error generating follow-up text: {e}")
        return None

# --- RUNTIME ENTRYPOINT ---

def main():
    print("=" * 60)
    print("      🚀 STANDALONE WHATSAPP AI AGENT DEMO RUNNING     ")
    print("=" * 60)
    print(f"📍 Instance: {EVOLUTION_INSTANCE}")
    print(f"📍 Webhook Port: {WEBHOOK_PORT}")
    print(f"📍 Follow-up Interval: {FOLLOWUP_INTERVAL_MINUTES} minutes")
    print(f"📍 Database File: {DB_FILE}")
    print("-" * 60)
    
    # 1. Run the Proactive Follow-up scanner thread
    followup_thread = threading.Thread(target=proactive_followup_runner, daemon=True)
    followup_thread.start()
    
    # 2. Run Webhook HTTP Server
    server_address = ('', WEBHOOK_PORT)
    httpd = ThreadedHTTPServer(server_address, WebhookHandler)
    
    print(f"🌐 Webhook Server listening on port {WEBHOOK_PORT} (POST /webhook)...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down agent.")
        sys.exit(0)

if __name__ == "__main__":
    main()
