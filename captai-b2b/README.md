# 🎯 Captai — Painel de Prospecção B2B com IA

O **Captai** é um painel inteligente de prospecção comercial B2B (Business-to-Business) voltado para agências, assessores de marketing e consultores. O sistema permite pesquisar empresas locais ativas por palavra-chave (nicho) e geolocalização, gerando automaticamente diagnósticos de fraquezas e abordagens comerciais personalizadas com inteligência artificial para otimizar os disparos comerciais via WhatsApp.

---

## ✨ Recursos de Destaque

* **Varredura Geográfica Integrada:** Busca empresas reais mapeadas localmente, agregando contatos de WhatsApp, nome da empresa e endereço de forma simplificada.
* **Diagnósticos com IA (Gemini):** Para cada lead capturado, o sistema executa uma análise heurística rápida via LLM para sugerir possíveis fragilidades (ex: falta de presença digital, avaliações ruins, site desatualizado) e redige uma copy de abordagem específica.
* **Régua de Disparo em Massa com Fila:** Os leads selecionados são enfileirados em lote em uma tabela de fila de disparos (`fila_envios`), aguardando o processamento controlado para evitar bloqueios de spam do WhatsApp.
* **Modelos Dinâmicos de Mensagem:** Suporte a templates com tags dinâmicas auto-injetadas (ex: `Olá {{primeiro_nome}}, analisei a {{nome_empresa}}...`).
