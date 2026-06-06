# 🗣️ LeadTalkAI — CRM Conversacional SaaS com IA

O **LeadTalkAI** é um software como serviço (SaaS) multi-tenant construído para monitorar, analisar e otimizar interações comerciais no WhatsApp. Ele escuta mensagens via webhooks, transcreve gravações de voz automaticamente e utiliza modelos de Inteligência Artificial para gerar diagnósticos ricos de conversas, incluindo sentimento do cliente, probabilidade de fechamento, score de vendas e alerta precoce de churn (risco de cancelamento).

---

## 🏗️ Design do Banco de Dados & Relações

A arquitetura do banco de dados relacional (Supabase PostgreSQL) está organizada da seguinte forma:

```
┌─────────────────┐        ┌─────────────────┐        ┌───────────────────┐
│    companies    │ ───<   │    profiles     │ ───<   │    ai_provider    │
│ (Tenant Master) │        │ (Comercial/User)│        │   (Config Chaves) │
└────────┬────────┘        └─────────────────┘        └─────────┬─────────┘
         │                                                      │
         ├───────────────────────┬──────────────────────────────┤ (company_id)
         ▼                       ▼                              ▼
┌─────────────────┐        ┌─────────────────┐        ┌───────────────────┐
│    customers    │ ───<   │  conversations  │ ───<   │    ai_analyses    │
│ (Leads/Contatos)│        │ (active/won/etc)│        │ (Sentimento/Score)│
└────────┬────────┘        └────────┬────────┘        └───────────────────┘
         │                          │
         ▼ (customer_id)            ▼ (conversation_id)
         └──────────┬───────────────┘
                    ▼
           ┌─────────────────┐
           │    messages     │
           │ (Histórico Chat)│
           └─────────────────┘
```

---

## ✨ Recursos Técnicos Relevantes no Repositório

### 1. Webhook assíncrono com Transcrição Whisper (`whatsapp-webhook.ts`)
* Função Edge Function rodando em Deno.
* Realiza o handshake seguro do webhook do WhatsApp Cloud API.
* Efetua o download seguro de arquivos de áudio ogg da API da Meta e realiza a transcrição usando o modelo Whisper-1 da OpenAI.
* Utiliza um fluxo assíncrono (fire-and-forget) para disparar a análise de sentimento por IA em segundo plano após a 3ª mensagem, garantindo que o webhook responda à API da Meta em menos de 1 segundo (evitando retentativas por timeout).

### 2. Kanban Drag-and-Drop de Vendas (`KanbanPipeline.tsx`)
* Painel construído com React, TypeScript e a biblioteca `@dnd-kit/core`.
* Permite que operadores arrastem leads entre colunas (`Novos`, `Em Andamento`, `Ganhos`, `Perdidos`), disparando patches otimistas de atualização no Supabase.
* Renderiza dinamicamente badges visuais especiais baseados em análises prévias de IA (ex: badge vermelho piscante `🚨 Churn` para riscos críticos de cancelamento ou `🔥 Lead Quente` para alta pontuação de vendas).
