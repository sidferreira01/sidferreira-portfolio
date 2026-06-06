# ⚜️ Maison Aurea — Sistema Premium de Agendamentos e Retenção

A **Maison Aurea** é uma solução completa de agendamento digital voltada para clínicas de estética, salões de beleza de alto padrão, estúdios de tatuagem e barbearias. O sistema engloba um portal do cliente com interface refinada (Black & Gold), fluxo de agendamento livre de conflitos, painel administrativo para controle de serviços e profissionais, e automação ativa de notificações e marketing de retenção.

---

## 🎨 Design System Premium & Tokens HSL
Para impressionar o usuário final à primeira vista e comunicar alta qualidade do negócio, a Maison Aurea utiliza um design system baseado em HSL e tons nobres:

* **Dark Background:** `hsl(240, 5%, 4%)` (Preto profundo)
* **Gold Highlights:** `hsl(37, 75%, 50%)` (Dourado refinado de destaque para seleções, botões e badges)
* **Card Surface:** `hsl(240, 6%, 10%)` (Cinza escuro para contraste suave)
* **Typography:** Outfit (Modern & Sleek sans-serif)

---

## 🚀 Motor de Retenção de Clientes (Marketing Activo)

Uma das maiores dores de negócios de estética e beleza é o esquecimento do retorno do cliente após alguns dias. O sistema aborda essa dor programaticamente:

1. **Retenção Customizada por Serviço:** Cada serviço cadastrado no sistema (ex: Limpeza de Pele, Design de Sobrancelhas, Corte de Cabelo) possui uma configuração própria de `retention_days` (ex: 30 dias).
2. **pg_cron / Servidor de Tarefas:** Uma rotina agendada diária dispara a Edge Function `reengagement-scheduler.ts` no Supabase.
3. **Análise de Datas:** O sistema puxa agendamentos passados concluídos, calcula `data_agendamento + retention_days` e, se for igual a hoje, gera um texto de marketing e dispara o agendamento de volta via Evolution API com o link personalizado do negócio.
4. **Proteção contra Envio Duplo:** A tabela grava o timestamp `retention_sent_at` para garantir que o cliente seja re-engajado no tempo certo apenas uma vez por atendimento.
