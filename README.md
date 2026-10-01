# 🚀 Sid Ferreira — Portfolio & AI-Powered Solutions

Bem-vindo ao meu portfólio de engenharia de software e integrações com Inteligência Artificial. Aqui você encontrará demonstrações limpas, seguras e bem documentadas de sistemas que desenvolvi, variando de plataformas SaaS multi-tenant a agentes conversacionais automatizados e ferramentas de controle de sistemas locais.

---

## 👨‍💻 Sobre Mim

Sou Desenvolvedor Full-Stack especializado na construção de **arquiteturas orientadas a eventos**, **SaaS multi-tenant**, **automações inteligentes de negócios (no-code e code)** e **integrações avançadas de IA (LLMs multimodais)**. 

* **Principais competências:** Desenvolvimento Web (React, TypeScript, Node.js), Banco de dados (PostgreSQL, Supabase), Automação de Infraestrutura & APIs (Docker, Deno Edge Functions, Linux VPS), Inteligência Artificial (Gemini API, OpenAI API, Anthropic) e bots integrados a mensageria (WhatsApp APIs).
* **Foco de atuação:** Criar ferramentas que automatizam processos operacionais repetitivos, geram insights comerciais inteligentes e escalam negócios através de tecnologia robusta e segura.

---

## 📂 Projetos em Destaque

Neste repositório de portfólio, cada pasta contém **documentações completas de arquitetura** e **trechos reais de código higienizado** (sem credenciais ou segredos comerciais) para fins de demonstração técnica:

### 1. [LeadTalkAI](./leadtalk-ai/)
Plataforma SaaS multi-tenant que analisa o sentimento e o perfil de conversas do WhatsApp em tempo real utilizando múltiplos LLMs (Gemini, OpenAI, Claude).
* **Tech Stack:** React 18, TypeScript, Tailwind CSS, Supabase (PostgreSQL + Edge Functions), Evolution API, Z-API.
* **Destaques:** Análise assíncrona baseada em eventos, painel Kanban interativo e disparos automáticos de alertas de churn/conversão para gestores.

### 2. [TikTok Performance Hub & Video Studio](./tiktok-performance-hub/)
Um painel analítico para criadores e marcas que se conecta ao modelo de IA **Gemini Veo 3.0** para roteirizar e renderizar criativos de vídeo de 8 segundos a partir de imagens de produtos.
* **Tech Stack:** React 19 (React Start), TanStack Router & Query, Supabase, Google AI Studio (Gemini Veo 3.0 API).
* **Destaques:** Otimização de roteiros usando IA, dashboard financeiro com GMV e velocidade de vendas, fila distribuída de renderização.

### 3. [Maison Aurea (Premium Scheduling)](./maison-aurea/)
Plataforma premium de agendamento online e CRM para negócios físicos de serviços (clínicas, salões e estúdios) com campanhas ativas de re-engajamento.
* **Tech Stack:** React, TypeScript, Supabase, Evolution API, PWA (Progressive Web App).
* **Destaques:** Sistema de agendamento anti-conflito, layout Dark & Gold de alto nível e automação de mensagens ativas pós-serviço (N dias).

### 4. [Captai B2B (Prospecting Panel)](./captai-b2b/)
Painel de prospecção inteligente que varre empresas locais por nicho, gera diagnósticos personalizados com IA e gerencia campanhas de atração no WhatsApp.
* **Tech Stack:** React, TypeScript, Supabase, Gemini API, Evolution API.
* **Destaques:** Scraping otimizado, análise automatizada de forças/fraquezas e gerador de abordagens (pitches) comerciais dinâmicas.

### 5. [Lucas (Humanized Standalone AI Agent)](./lucas-ai-agent/)
Agente conversacional standalone em Python com escuta de webhooks multithread, memória local persistente em SQLite e inteligência multimodal nativa.
* **Tech Stack:** Python, SQLite, Gemini 2.5 Flash, Evolution API (Base64 media processing).
* **Destaques:** Compreensão nativa de imagens e arquivos de voz (ogg), simulação realista de tempo de digitação e disparador em segundo plano de follow-up proativo para re-engajar clientes inativos.

### 6. [Bot de Afiliados (Afiliado Profissional)](./affiliate-deals-bot/)
Robô autônomo que monitora fóruns de promoções, converte links para monetização em programas de afiliados e redige copies profissionais automatizadas.
* **Tech Stack:** Python, BeautifulSoup, Google Gemini API, Supabase, Shopee API V2, Evolution API.
* **Destaques:** Raspagem programática, conversão automática via API oficial da Shopee, e gerenciador de "silêncio noturno" com fila de espera local.

### 7. [WhatsApp Remote Notebook Control](./whatsapp-remote-control/)
Ponte híbrida de comunicação que permite executar tarefas e monitorar sistemas Windows (bateria, prints, terminal CMD) remotamente via comandos do WhatsApp.
* **Tech Stack:** Python, n8n (Cloud & Local), Supabase (Realtime Queue), Evolution API, Gemini API (análise de mídia).
* **Destaques:** Modelo de funcionamento tolerante a falhas (nuvem assume se o notebook local estiver desligado) e segurança baseada em números de telefones restritos.

### 8. [Transcritor AI (Áudio → Texto de Alta Precisão)](./transcritor-ai/)
Conversor de áudio/vídeo em texto 100% local que substitui assinaturas de transcrição (TurboScribe, Otter, Fireflies) e APIs cobradas por minuto.
* **Tech Stack:** Python, faster-whisper (Whisper large-v3 / turbo), pyannote.audio (community-1), FastAPI, ffmpeg, Docker.
* **Destaques:** 2ª passada automática que re-decodifica trechos de baixa confiança, filtro de alucinações do Whisper em português, glossário com correções forçadas, identificação de falantes, legendas SRT/VTT profissionais e interface web com revisão guiada das palavras incertas. Precisão medida com WER no FLEURS pt-BR.

### 9. [DitvvOS (Ditado por Voz Local)](./transcritor-ai/DITVVOS.md)
Ditado por voz em qualquer janela (Claude Code, navegador, Gmail, WhatsApp Web), construído após análise de Wispr Flow, Superwhisper, Aqua Voice e Willow — sem mensalidade e com o áudio 100% local.
* **Tech Stack:** Python, faster-whisper, pynput, sounddevice, tkinter, Ollama (gemma3:4b), SQLite.
* **Destaques:** segurar para falar + mãos-livres, remoção de hesitações e autocorreção falada ("às duas, quer dizer, às três"), comandos de voz, dicionário pessoal, snippets, estilo automático por aplicativo, Modo Comando (editar a seleção por voz com IA local) com travas contra respostas indevidas, histórico com estatísticas e testes ponta a ponta com atalho global real.

---

## 🛠️ Contato e Links

* **E-mail:** [contato@sidferreira.com.br](mailto:contato@sidferreira.com.br)
* **LinkedIn:** [linkedin.com/in/sidferreira](https://linkedin.com/in/sidferreira) *(adicione seu link real)*
* **Portfólio Web:** [sidferreira.com.br](https://sidferreira.com.br) *(adicione seu site real)*
