# 🤖 Lucas — Agente Standalone de IA Humanizado para WhatsApp

O **Lucas** (configurado na demonstração como a persona *Miriam*) é um agente conversacional autônomo e standalone desenvolvido em Python. Ele opera como um servidor de webhook multithread de alto desempenho para escutar notificações do WhatsApp (Evolution API), gravando conversas em um banco de dados relacional local **SQLite** para persistência de memória e utilizando o modelo multimodal **Gemini 2.5 Flash** para responder mensagens de texto, descrever imagens ou analisar áudios de voz nativamente.

---

## 🏗️ Fluxo de Funcionamento e Threads

O agente opera em duas threads paralelas principais em segundo plano:

```
                  ┌────────────────────────────────────────────────────────┐
                  │              Programa Principal (agent.py)             │
                  └───────────┬────────────────────────────────┬───────────┘
                              │ (Thread 1 - Principal)         │ (Thread 2 - Background)
                              ▼                                ▼
                  ┌──────────────────────┐          ┌──────────────────────┐
                  │ Webhook HTTP Server  │          │  Follow-up Engine    │
                  │     (Port 5005)      │          │  (Varredura SQLite)  │
                  └───────────┬──────────┘          └──────────┬───────────┘
                              │                                │
                              ▼ (Recebe WhatsApp)              ▼ (Silêncio por 2 min)
                  ┌──────────────────────┐          ┌──────────────────────┐
                  │  Salva no SQLite     │          │  Lê Histórico Chat   │
                  │  Simula Digitação    │          │  Gera Lembrete IA    │
                  │  Dispara Gemini API  │          │  Atualiza Fila       │
                  └──────────────────────┘          └──────────────────────┘
```

---

## ✨ Recursos de Engenharia Implementados

* **Compreensão Multimodal Nativa (Zero Transcrição Externa):** Aproveitando as capacidades multimodais do **Gemini 2.5 Flash**, o agente lê áudios gravados e imagens convertidos em base64 recebidos diretamente no payload do webhook da Evolution API. Isso elimina a latência e o custo de serviços de transcrição externos (como Whisper ou Google Speech-to-Text).
* **Mecanismo Ativo de Follow-up (Demonstração de Re-engajamento):** Um thread paralelo varre a tabela SQLite a cada 10 segundos. Se identificar que o cliente parou de responder há um período configurado (ex: 2 minutos para fins de teste) e a última mensagem enviada foi do agente, a IA analisa o histórico, monta uma abordagem comercial curta e informal relacionada ao tema do assunto, e envia espontaneamente o lembrete.
* **Simulação Realista de Tempo de Digitação (Humanização):** Antes de responder, o agente envia o estado `composing` (Digitando...) para a Evolution API e atrasa o disparo final dinamicamente com base no tamanho do texto gerado (calculando cerca de 40ms por caractere).
* **Memória Persistente Isolada:** Persiste o histórico de mensagens localmente sem depender de conexões de rede de bancos de dados externos pesados, tornando a solução leve e ideal para empacotamento standalone ou execução em contêineres Docker pequenos.
