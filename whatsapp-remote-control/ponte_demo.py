import requests
import time
import os
import psutil
import subprocess
import unicodedata
import pyautogui
import base64
import io
import google.generativeai as genai
import ctypes
from datetime import datetime
from dotenv import load_dotenv
import sys
import shlex

# Force UTF-8 encoding for stdout (useful on Windows terminal environments)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- PERSISTENCE: PREVENT SYSTEM SLEEP (Windows API) ---
def prevent_sleep():
    try:
        # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000040)
        print("System persistence mode activated (Anti-Sleep).")
    except Exception as e:
        print(f"Could not configure anti-sleep mode: {e}")

prevent_sleep()

# Load local environment variables from .env
load_dotenv()

# --- DATABASE / SUPABASE CONFIGURATION ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TABLE_NAME = os.getenv("TABELA", "comandos_notebook")

# --- WHATSAPP / EVOLUTION API CONFIGURATION ---
EVOLUTION_URL = os.getenv("EVOLUTION_URL")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE")
EVOLUTION_APIKEY = os.getenv("EVOLUTION_APIKEY")

# --- SECURITY ENFORCEMENT ---
AUTHORIZED_PHONES = os.getenv("TELEFONES_AUTORIZADOS", "").split(",")

# --- ARTIFICIAL INTELLIGENCE ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
ia_model = genai.GenerativeModel('gemini-1.5-flash')

def send_whatsapp_text(number, text):
    """Sends a text message using the Evolution API instance."""
    url = f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {
        "apikey": EVOLUTION_APIKEY,
        "Content-Type": "application/json"
    }
    payload = {
        "number": str(number),
        "text": text
    }
    try:
        requests.post(url, headers=headers, json=payload, timeout=30)
    except Exception as e:
        print(f"Error sending text via WhatsApp API: {e}")

def send_whatsapp_media(number, base64_data, caption=""):
    """Sends an image using the Evolution API instance (handles base64 directly)."""
    url = f"{EVOLUTION_URL}/message/sendMedia/{EVOLUTION_INSTANCE}"
    headers = {
        "apikey": EVOLUTION_APIKEY,
        "Content-Type": "application/json"
    }
    payload = {
        "number": str(number),
        "media": base64_data,
        "mediatype": "image",
        "caption": caption
    }
    try:
        requests.post(url, headers=headers, json=payload, timeout=20)
    except Exception as e:
        print(f"Error sending media via WhatsApp API: {e}")

def check_pending_commands():
    """Polls the Supabase real-time database table for pending command records."""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    
    # Select the oldest command that is still pending
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?status=eq.pendente&select=*"
    
    print(".", end="", flush=True)  # Silent loop activity indicator
    try:
        response = requests.get(url, headers=headers, timeout=10)
        commands = response.json()
        
        if commands:
            print("\n")
            cmd = commands[0]
            raw_command = cmd['comando']
            cmd_id = cmd['id']
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Command received: {raw_command[:50]}...")
            execute_action(raw_command, cmd_id, headers)
            
    except Exception as e:
        print(f"\nError connecting to Supabase: {e}")

def execute_action(command_with_metadata, cmd_id, headers):
    """Parses and executes the matching Windows/system operation based on whitelist restrictions."""
    response = ""
    phone = None
    
    # Extract recipient phone number if injected into payload command
    if "__number__" in command_with_metadata:
        parts = command_with_metadata.split("__number__")
        command = parts[0].strip()
        phone = parts[1].strip()
    else:
        command = command_with_metadata.strip()
    
    print(f"Processing: {command}")
    
    # 1. READ BATTERY METRICS
    if "bateria" in command.lower():
        battery = psutil.sensors_battery()
        percent = battery.percent if battery else "N/A"
        plugged = "Charging" if battery and battery.power_plugged else "Disconnected"
        response = f"Battery Status: {percent}% ({plugged})"
    
    # 2. READ LOCAL SYSTEM TIME
    elif "hora" in command.lower():
        response = f"Notebook System Time: {datetime.now().strftime('%H:%M:%S')}"
        
    # 3. LAUNCH CALCULATOR
    elif "calculadora" in command.lower():
        os.system("calc")
        response = "Calculator launched successfully!"

    # 4. CAPTURE & SEND SCREENSHOT
    elif "print" in command.lower() or "screenshot" in command.lower():
        try:
            print("Taking screenshot...")
            screenshot = pyautogui.screenshot()
            img_byte_arr = io.BytesIO()
            screenshot.save(img_byte_arr, format='PNG')
            base64_img = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
            
            if phone:
                print("Uploading media to client...")
                send_whatsapp_media(phone, "data:image/png;base64," + base64_img, "📸 Desktop Screenshot!")
            
            response = "Screenshot captured and dispatched successfully!"
        except Exception as e:
            response = f"🚨 Failed to capture screen: {e}"
        
    # 5. MULTIMODAL INBOUND MEDIA HANDLING (via Gemini API)
    elif command.upper().startswith("[MEDIA]"):
        if phone in AUTHORIZED_PHONES:
            try:
                # Protocol format: [MEDIA]__mime__[MIME_TYPE]__data__[BASE64_DATA]__caption__[CAPTION_TEXT]
                parts_media = command.split("__")
                mime = parts_media[2]
                base64_data = parts_media[4]
                caption = parts_media[6] if len(parts_media) > 6 else "none"
                
                if base64_data == "NO_BASE64" or base64_data == "undefined" or not base64_data:
                    response = "🚨 No base64 content received. Verify if Evolution API webhook 'Base64' box is checked."
                else:
                    prompt = "Incoming media received via WhatsApp."
                    if caption and caption != "none":
                        prompt += f" User attached this caption: {caption}"
                    prompt += "\nPlease transcribe/translate if audio, or describe if it is an image. Be friendly. Never use double asterisks (**) for bold (use single * instead) and do not use asterisks for lists (use dash - instead)."
                    
                    print(f"Analyzing multimodal media with Gemini API: {mime}")
                    parts = [
                        prompt,
                        {"mime_type": mime, "data": base64_data}
                    ]
                    res_ia = ia_model.generate_content(parts)
                    response = res_ia.text.replace("**", "*")
            except Exception as e:
                response = f"🤖 Binary Media Read Error: {e}"
        else:
            response = "⛔ *Access Denied* for media analysis tasks."
        
    # 6. SECURE TERMINAL EXECUTION (CMD)
    elif command.lower().startswith("cmd "):
        if phone in AUTHORIZED_PHONES:
            command_os = command.replace("cmd ", "", 1).strip()
            
            # --- SECURITY LAYER: CMD WHITELIST & SANITIZATION ---
            ALLOWED_SHELL_COMMANDS = [
                'dir', 'ipconfig', 'systeminfo', 'whoami', 
                'tasklist', 'netstat', 'ping', 'hostname', 
                'uptime', 'get-process', 'ls'
            ]
            
            base_bin = command_os.split(' ')[0].lower()
            
            # Prevent command chaining/redirection injection (A05:Injection vulnerability mitigation)
            if any(char in command_os for char in [';', '&', '|', '>', '<', '`', '$', '(', ')']):
                response = "🚨 *Security Alert*: Chaining characters blocked to prevent command injection."
            elif base_bin not in ALLOWED_SHELL_COMMANDS:
                response = f"⛔ *Command Blocked*: '{base_bin}' is not allowed under system whitelist restrictions."
            else:
                try:
                    # Tokenize safely keeping quotation rules intact
                    cmd_parts = shlex.split(command_os)
                    print(f"Executing secure command: {cmd_parts}")
                    
                    # Execute with shell=False (mitigates raw shell execution vulnerabilities)
                    raw_result = subprocess.check_output(
                        cmd_parts, 
                        shell=False, 
                        stderr=subprocess.STDOUT, 
                        timeout=15
                    ).decode('latin-1')
                    
                    response = f"💻 *Terminal Result*\n\n{raw_result}"[:3500]
                    if not response.strip():
                        response = "✅ Command executed successfully (Empty Output)."
                except subprocess.TimeoutExpired:
                    response = "⏳ *Timeout Error*: The operation took too long to return a response."
                except Exception as e:
                    response = f"🚨 *System Error*: {e}"
        else:
            response = "⛔ *Access Denied*: You do not have permissions to execute console commands."
    
    # 7. LOCK COMPUTER SCREEN
    elif "lock" in command.lower() and "note" in command.lower():
        try:
            print("Locking Windows workstation...")
            ctypes.windll.user32.LockWorkStation()
            response = "🔒 Screen locked successfully!"
        except Exception as e:
            response = f"🚨 Error locking screen: {e}"
    
    # 8. OUTBOUND MARKETING TRIGGERS (Passthrough)
    elif command.lower().startswith("postar "):
        response = command.replace("postar ", "", 1)
    
    elif command.lower().startswith("postar_media "):
        try:
            partes_media = command.replace("postar_media ", "", 1).split("__caption__")
            url_media = partes_media[0].strip()
            texto_legenda = partes_media[1].strip() if len(partes_media) > 1 else ""
            
            if phone:
                print(f"📸 Disbursing promotional media to {phone}...")
                send_whatsapp_media(phone, url_media, texto_legenda)
                response = "Media campaign dispatched successfully!"
            else:
                response = "🚨 Error: Recipient phone number missing for postar_media."
        except Exception as e:
            response = f"🚨 Failed to execute postar_media: {e}"
    
    # DEFAULT IA CONVERSATIONAL FALLBACK
    else:
        try:
            prompt = (
                f"User text message via WhatsApp Remote Control: {command}\n\n"
                f"Formatting Rules:\n"
                f"1. You are communicating on WhatsApp. Never use double asterisks (**) for bold. Use single asterisks (*) to make words bold (e.g. *word*).\n"
                f"2. Use dashes (-) for bullet points, not asterisks.\n"
            )
            res_ia = ia_model.generate_content(prompt)
            response = res_ia.text.replace("**", "*")
        except Exception as e:
            response = f"🤖 AI brain failure: {e}"
        
    def strip_accents(text_str):
        try:
            return ''.join(c for c in unicodedata.normalize('NFD', str(text_str)) if unicodedata.category(c) != 'Mn')
        except:
            return text_str
            
    # Normalize accents for system CMD results to prevent character glitches on WhatsApp
    system_commands = ["cmd ", "bateria", "hora", "calculadora", "print", "screenshot"]
    if any(c in command.lower() for c in system_commands):
        response = strip_accents(response)

    # Patch the Supabase record status to 'completed' with system output
    update_url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?id=eq.{cmd_id}"
    requests.patch(update_url, headers=headers, json={"status": "concluido", "resposta": response})
    print("Record patched on Supabase.")
    
    # Return the response directly to the user on WhatsApp
    if phone:
        print("Sending reply text on WhatsApp...")
        send_whatsapp_text(phone, response)

# --- HEARTBEAT THREAD ---
LAST_HEARTBEAT_TIME = 0
HEARTBEAT_INTERVAL_SEC = 60

def send_heartbeat():
    """Updates status_sistema table in Supabase to declare the local bridge is alive."""
    global LAST_HEARTBEAT_TIME
    now = time.time()
    
    if now - LAST_HEARTBEAT_TIME >= HEARTBEAT_INTERVAL_SEC:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        url = f"{SUPABASE_URL}/rest/v1/status_sistema?id=eq.meu_notebook"
        payload = {
            "ultima_vez_visto": datetime.now().isoformat(),
            "online": True
        }
        try:
            requests.patch(url, headers=headers, json=payload, timeout=5)
            LAST_HEARTBEAT_TIME = now
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Heartbeat sent.")
        except Exception as e:
            print(f"Error sending heartbeat: {e}")

print(">>> BRIDGE ACTIVE: Listening for Supabase queue records...")

while True:
    send_heartbeat()
    check_pending_commands()
    time.sleep(5)
