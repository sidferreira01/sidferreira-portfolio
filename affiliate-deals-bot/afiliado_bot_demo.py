import requests
from bs4 import BeautifulSoup
import schedule
import time
import json
import os
import sys
import io
import re
import hmac
import hashlib
from datetime import datetime
import google.generativeai as genai
import pytz

# Force UTF-8 encoding for stdout (helps preventing character printing bugs with emojis on Windows)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load local environment variables from .env
# Configuration defaults/placeholders are resolved dynamically
EVOLUTION_URL = os.getenv("EVOLUTION_URL")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE")
EVOLUTION_APIKEY = os.getenv("EVOLUTION_APIKEY")
GROUP_JID = os.getenv("GRUPO_JID", "120363425128736293@g.us")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_TABLE = os.getenv("TABELA", "comandos_notebook")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-flash-lite-latest')
else:
    gemini_model = None

HISTORY_FILE = "post_history.json"
NIGHT_QUEUE_FILE = "night_queue.json"
TZ = os.getenv("TZ", "America/Sao_Paulo")

# --- PARTNER MONETIZATION SERVICE (Shopee Open API V2) ---

class ShopeeAffiliateService:
    def __init__(self):
        self.partner_id = os.getenv("SHOPEE_PARTNER_ID")
        self.app_id = os.getenv("SHOPEE_APP_ID")
        self.secret_key = os.getenv("SHOPEE_SECRET_KEY")
        self.base_url = "https://open-api.affiliate.shopee.com.br"

    def _generate_signature(self, path, timestamp):
        """Generates required HMAC-SHA256 signature for Shopee V2 API."""
        if not self.secret_key or not self.partner_id:
            return ""
        base_string = f"{self.partner_id}{path}{timestamp}"
        return hmac.new(
            self.secret_key.encode('utf-8'),
            base_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def convert_link(self, origin_url):
        """Converts raw Shopee URL to monetized affiliate short_link and app_link."""
        if not all([self.partner_id, self.app_id, self.secret_key]):
            print("ℹ️ [SHOPEE API] Credentials missing. Returning original URL.")
            return None

        path = "/api/v2/affiliate/generate_link"
        timestamp = int(time.time())
        sign = self._generate_signature(path, timestamp)
        
        params = {
            "partner_id": self.partner_id,
            "timestamp": timestamp,
            "sign": sign,
            "app_id": self.app_id
        }
        
        payload = {
            "origin_urls": [origin_url]
        }
        
        try:
            url = f"{self.base_url}{path}"
            response = requests.post(url, params=params, json=payload, timeout=20)
            data = response.json()
            
            if data.get("error"):
                print(f"❌ Shopee API Error: {data.get('message')}")
                return None
                
            links = data.get("data", {}).get("links", [])
            if links:
                return {
                    "short_link": links[0].get("short_link"),
                    "app_link": links[0].get("app_link")
                }
        except Exception as e:
            print(f"🚨 Critical Shopee API connection failed: {e}")
        return None

shopee_service = ShopeeAffiliateService()

# --- OTHER PLATFORMS CODES (Amazon & Mercado Livre regex converters) ---

AMAZON_ASSOCIATE_ID = os.getenv("AMAZON_ASSOCIATE_ID", "associado-20")
ML_PUBLISHER_ID = os.getenv("ML_PUBLISHER_ID", "12345678")
ML_PUBLISHER_USER = os.getenv("ML_PUBLISHER_USER", "defaultuser")

def convert_link_to_affiliate(original_url):
    """Parses raw store link and converts to monetized associate URL."""
    if not original_url:
        return original_url

    # Amazon Conversion
    if "amazon.com.br" in original_url:
        tag = AMAZON_ASSOCIATE_ID
        match = re.search(r"/(dp|gp/product)/([A-Z0-9]{10})", original_url, re.IGNORECASE)
        if match:
            asin = match.group(2)
            return f"https://www.amazon.com.br/dp/{asin}?tag={tag}"
        if "tag=" in original_url:
            return re.sub(r"tag=[^&]+", f"tag={tag}", original_url)
        connector = "&" if "?" in original_url else "?"
        return f"{original_url}{connector}tag={tag}"

    # Mercado Livre Conversion
    elif "mercadolivre.com.br" in original_url or "mali.li" in original_url:
        url_clean = original_url.split("#")[0]
        if "?" in url_clean:
            base, params_str = url_clean.split("?", 1)
            # Strip tags that might conflict with tracking publisher IDs
            params_filtered = [
                p for p in params_str.split("&")
                if not any(p.startswith(k) for k in ["matt_", "forceInApp", "ref", "origin", "sid"])
            ]
            final_base = base + "?" + "&".join(params_filtered) if params_filtered else base
        else:
            final_base = url_clean

        sep = "&" if "?" in final_base else "?"
        return f"{final_base}{sep}matt_tool={ML_PUBLISHER_ID}&matt_word={ML_PUBLISHER_USER}&matt_source=afiliados"

    return original_url

# --- UTILITIES ---

def load_local_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_local_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to save local history: {e}")

def load_night_queue():
    if os.path.exists(NIGHT_QUEUE_FILE):
        try:
            with open(NIGHT_QUEUE_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_night_queue(queue):
    try:
        with open(NIGHT_QUEUE_FILE, "w", encoding='utf-8') as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to save night queue: {e}")

def generate_deal_id(title, link, price):
    base = f"{title}{link}{price}"
    return hashlib.md5(base.encode()).hexdigest()

def resolve_target_redirect(redirect_url):
    """Traverses HTTP redirections to extract final clean product landing page URL."""
    if not redirect_url or not redirect_url.startswith("http"):
        return redirect_url
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(redirect_url, headers=headers, allow_redirects=True, timeout=15)
        return res.url
    except Exception as e:
        print(f"⚠️ Error resolving redirect: {e}")
        return redirect_url

def check_duplicate_in_supabase(title):
    """Checks remote Supabase table to verify if product has been published."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    
    import urllib.parse
    url = f"{SUPABASE_URL}/rest/v1/historico_afiliado?titulo=eq.{urllib.parse.quote(title)}&select=id"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            return len(res.json()) > 0
    except Exception as e:
        print(f"⚠️ Failed to check remote duplicate registry: {e}")
    return False

def register_published_in_supabase(title):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    url = f"{SUPABASE_URL}/rest/v1/historico_afiliado"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(url, headers=headers, json={"titulo": title}, timeout=10)
        return res.status_code in [200, 201, 204]
    except Exception as e:
        print(f"⚠️ Failed logging remote published record: {e}")
    return False

def send_to_supabase_queue(text, number, image=None, short_link=None, app_link=None):
    """Pushes formatted command execution task into local bridge's Supabase queue."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
        
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    if image:
        formatted_cmd = f"postar_media {image} __caption__ {text} __number__ {number}"
    else:
        formatted_cmd = f"postar {text} __number__ {number}"
    
    payload = {
        "comando": formatted_cmd,
        "status": "pendente",
        "short_link": short_link,
        "app_link": app_link
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        return res.status_code in [200, 201, 204]
    except Exception as e:
        print(f"⚠️ Supabase queue enqueuing failed: {e}")
        return False

# --- GEMINI COPYWRITING GENERATION ---

def generate_ai_deal_copy(title, price, link):
    """Asks Gemini to write high-conversion copy matching WhatsApp formatting constraints."""
    if not gemini_model:
        return None
        
    prompt = (
        f"Você é um especialista em Copywriting de ALTA PERFORMANCE para WhatsApp.\n"
        f"Sua missão é criar uma oferta IRRESISTÍVEL para o produto abaixo.\n\n"
        f"DADOS DO PRODUTO:\n- Título: {title}\n- Preço Atual: {price}\n- Link de Compra: {link}\n\n"
        f"ESTRUTURA DA MENSAGEM:\n"
        f"1. TÍTULO IMPACTANTE: Use emojis de fogo, alerta ou oferta (ex: 🔥 MEGA OFERTA DETECTADA!)\n"
        f"2. BENEFÍCIO RÁPIDO: Uma frase curta destacando por que vale a pena.\n"
        f"3. PREÇO DESTACADO: Formato 'R$ 99,90' (Sempre use R$ com espaço).\n"
        f"4. CHAMADA PARA AÇÃO (CTA): 'Garanta o seu aqui 👇' ou similar.\n"
        f"5. LINK: O link deve ficar sozinho na última linha.\n\n"
        f"REGRAS CRÍTICAS:\n"
        f"- NUNCA use negrito com dois asteriscos (**). Use APENAS UM asterisco para negrito (*texto*).\n"
        f"- NUNCA use listas com asteriscos. Use traços (-) ou emojis.\n"
        f"- Linguagem direta, escassa e urgente.\n"
        f"- Não use palavras como 'olá', 'tudo bem' ou 'atenciosamente'. Vá direto aos fatos.\n"
    )
    try:
        response = gemini_model.generate_content(prompt)
        text = response.text.replace("**", "*")
        if "R$" in text and "R$ " not in text:
            text = text.replace("R$", "R$ ")
        return text.strip()
    except Exception as e:
        print(f"🚨 Gemini execution failed: {e}")
        return None

# --- WINDOW SCHEDULER & WINDOW VALIDATION ---

def is_active_business_hours():
    """Validates if timezone matched current local hour is between 8 AM and 8 PM."""
    try:
        fuso = pytz.timezone(TZ)
        now = datetime.now(fuso)
        return 8 <= now.hour < 20
    except Exception as e:
        print(f"⚠️ Local time verification failed: {e}")
        return True

def scrape_deals_from_source():
    """Scrapes products listings from public deals page."""
    print("🌐 Scraping deals portal...")
    url = "https://gatry.com/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        deals = []
        articles = soup.find_all('article')
        
        for container in articles:
            try:
                title_tag = container.find('h3')
                if not title_tag:
                    continue
                title = title_tag.get_text().strip()
                
                price_tag = container.find('p', class_='price')
                price = price_tag.get_text().strip() if price_tag else "Consulte o site"
                
                link_tag = container.find('a', class_='btn-promocao') or container.find('a', href=True)
                link = link_tag['href'] if link_tag else "#"
                if link and not link.startswith('http'):
                    link = "https://gatry.com" + link

                img_tag = container.find('img')
                img_url = img_tag['src'] if img_tag else None
                if img_url:
                    if img_url.startswith('//'):
                        img_url = "https:" + img_url
                    elif img_url.startswith('/'):
                        img_url = "https://gatry.com" + img_url

                deals.append({
                    "titulo": title,
                    "preco": price,
                    "link": link,
                    "imagem": img_url
                })
            except Exception:
                continue
        return deals
    except Exception as e:
        print(f"⚠️ Scraper failed: {e}")
        return []

# --- MAIN DISPATCH ROUTINE ---

def process_and_post_deals():
    print(f"\n[{time.strftime('%H:%M:%S')}] 🚀 Executing deals curating routine...")
    
    active_window = is_active_business_hours()
    history = load_local_history()
    night_queue = load_night_queue()
    
    candidates = []
    
    # 1. Prioritize dispatching night-queue accumulated items during business hours
    if active_window and night_queue:
        print(f"📦 Night queue has {len(night_queue)} items pending. Disbursing first...")
        for item in night_queue:
            item["origem"] = "fila_noturna"
            candidates.append(item)
            
    # 2. Add scraped deals
    scraped = scrape_deals_from_source()
    for item in scraped:
        item["origem"] = "scraped"
        candidates.append(item)
        
    if not candidates:
        print("⚠️ No items to process.")
        return

    posted_count = 0
    cycle_limit = 3 if active_window else 5
    
    for deal in candidates:
        # Resolve target redirect if freshly scraped
        if deal["origem"] == "scraped":
            deal['link'] = resolve_target_redirect(deal['link'])
            
        deal_id = generate_deal_id(deal['titulo'], deal['link'], deal['preco'])
        
        # Symmetrical double check against duplication
        if deal_id in history:
            continue
        if check_duplicate_in_supabase(deal['titulo']):
            history[deal_id] = datetime.now().isoformat()
            continue
            
        print(f"🆕 Processing new deal: {deal['titulo'][:50]}...")
        
        # Commercial active hours: Process and enqueue immediately
        if active_window:
            short_link = None
            app_link = None
            
            # API V2 link monetization check
            if "shopee.com" in deal['link']:
                links_conv = shopee_service.convert_link(deal['link'])
                if links_conv:
                    short_link = links_conv.get('short_link')
                    app_link = links_conv.get('app_link')
                    deal['link'] = short_link or deal['link']
            else:
                deal['link'] = convert_link_to_affiliate(deal['link'])

            ai_copy = generate_ai_deal_copy(deal['titulo'], deal['preco'], deal['link'])
            if not ai_copy:
                continue
                
            print("📤 Dispatching to Supabase local bridge queue...")
            success = send_to_supabase_queue(
                ai_copy, 
                GROUP_JID, 
                image=deal.get('imagem'),
                short_link=short_link,
                app_link=app_link
            )

            if success:
                register_published_in_supabase(deal['titulo'])
                history[deal_id] = datetime.now().isoformat()
                posted_count += 1
                
                if deal["origem"] == "fila_noturna":
                    night_queue = [x for x in night_queue if x["titulo"] != deal["titulo"]]
                    save_night_queue(night_queue)
                    
                time.sleep(3) # Anti-spam delay
                
        # Night silent hours: Store locally to avoid messaging client
        else:
            if deal["origem"] == "scraped":
                print(f"💤 Night silent mode active. Queueing locally: {deal['titulo'][:50]}...")
                night_queue.append({
                    "titulo": deal["titulo"],
                    "preco": deal["preco"],
                    "link": deal['link'],
                    "imagem": deal.get("imagem")
                })
                save_night_queue(night_queue)
                register_published_in_supabase(deal['titulo'])
                history[deal_id] = datetime.now().isoformat()
                posted_count += 1
                
        if posted_count >= cycle_limit: 
            break
            
    # Clean history limits to prevent memory bloat
    if len(history) > 300:
        history = dict(sorted(history.items(), key=lambda x: x[1], reverse=True)[:300])
    save_local_history(history)
    print(f"🏁 Cycle finished. {posted_count} deals processed.")

# Schedule routine execution
schedule.every(2).hours.do(process_and_post_deals)

if __name__ == "__main__":
    print("-" * 50)
    print("AFFILIATE DEALS BOT SERVICE RUNNING")
    print(f"Publish Target: {GROUP_JID}")
    print("-" * 50)
    
    # Run once at startup
    process_and_post_deals()
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except KeyboardInterrupt:
            print("\nShutting down bot.")
            break
