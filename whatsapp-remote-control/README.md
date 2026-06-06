# 💻 WhatsApp Remote Notebook Control

Este projeto consiste em uma ponte de integração inteligente que permite controlar um notebook com sistema operacional Windows remotamente a partir de conversas seguras no WhatsApp. O sistema opera de forma híbrida e tolerante a falhas (offline/online) integrando **n8n**, **Supabase**, **Evolution API** e o modelo de IA **Google Gemini**.

---

## 🏗️ Desenho de Arquitetura

O fluxo de dados segue a seguinte estrutura:

```
[Cliente (WhatsApp)] ──> [Evolution API] ──> [n8n Cloud (Webhook)]
                                                   │
     ┌─────────────────────────────────────────────┴─────────────────────────────────────────────┐
     ▼ [Notebook LIGADO / Online]                                                                ▼ [Notebook DESLIGADO / Offline]
[Supabase (Fila de Comandos)]                                                              [n8n Cloud]
     │                                                                                           │
     ▼ (Pesquisa Ativa a cada 5s)                                                                │ (IA Responde com contexto de
[Ponte Local (Python - agent)] ──> [Executa Ação no OS]                                            última hora salva no Supabase)
     │                                                                                           │
     └─────────────────────────────────────────────┬─────────────────────────────────────────────┘
                                                   ▼
                                        [Resposta no WhatsApp]
```

---

## ✨ Funcionalidades Principais

* **Modo Híbrido Resiliente:** Se o notebook estiver desligado, o fluxo na nuvem (n8n Cloud) assume a conversa automaticamente e informa ao usuário as últimas informações conhecidas da máquina (como nível de bateria e horário de desligamento) salvas no Supabase.
* **Comandos Locais do Windows:**
  * `/note print`: Tira captura de tela instantânea da área de trabalho e envia a imagem de volta.
  * `/note bateria`: Retorna a carga e o estado da fonte de energia.
  * `/note lock`: Bloqueia o Windows (`LockWorkStation`).
  * `/note calculadora`: Executa aplicações locais.
* **Terminal Seguro (CMD/PowerShell Whitelist):** Executa comandos do sistema com proteção nativa contra injeção de shell (bloqueio de caracteres especiais `;`, `&`, `|`, `>`, etc.) e limite de uso a uma lista estrita de utilitários de leitura (`dir`, `ipconfig`, `systeminfo`, `whoami`, etc.).
* **Integração Multimodal Gemini:** Ao receber imagens ou áudios gravados, a ponte local utiliza inteligência artificial para descrever imagens ou transcrever e contextualizar áudios instantaneamente.

---

## 🔒 Melhores Práticas de Segurança Implementadas

1. **Autorização por Número:** Apenas números de telefone autorizados listados nas variáveis de ambiente podem disparar comandos do sistema operacional ou ler dados confidenciais.
2. **Proteção Shell Injection (A05:Injection):** Utilização da biblioteca `shlex` para divisão segura de argumentos e execução com `subprocess.check_output(..., shell=False)` para mitigar ataques de injeção de parâmetros em comandos locais do console.
3. **Persistência do Serviço (Windows Anti-Sono):** Chamada de baixo nível de APIs da kernel do Windows (`ctypes.windll.kernel32.SetThreadExecutionState`) para manter a thread do sistema operacional acordada e ativa enquanto o script ponte estiver rodando.
