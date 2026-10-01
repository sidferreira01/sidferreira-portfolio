# 🎙️ DitvvOS — ditado por voz de alta precisão, 100% local

Fale em vez de digitar, em **qualquer janela**: Claude Code, claude.ai, ChatGPT, VS Code, Gmail, WhatsApp
Web, Word… Segure uma tecla, fale e solte: o texto aparece onde está o cursor, já pontuado, sem "hã" e
"hum" e no tom certo para cada aplicativo. Sem mensalidade, sem limite de palavras, e o áudio nunca sai
do seu computador.

---

## 1. Pesquisa de mercado (out/2026)

| App | Preço | Onde roda | Destaques |
|---|---|---|---|
| **Wispr Flow** | ~US$ 15/mês | Nuvem | Remove hesitações, entende autocorreção ("2… na verdade 3"), dicionário, *snippets*, estilos por app, **Command Mode** (selecionar texto e pedir "deixe mais amigável") |
| **Superwhisper** | ~US$ 8–12/mês ou licença | Local (Whisper) + nuvem no Pro | Modelos locais, "modos" de IA personalizados, 100+ idiomas |
| **Aqua Voice** | ~US$ 8/mês | Nuvem | Maior precisão declarada, consciente de código, ~450 ms para inserir |
| **Willow Voice** | ~US$ 12/mês (grátis até 2.000 palavras/semana) | Nuvem | Formata conforme o app, comandos de voz ("nova linha", "tópico"), vocabulário |
| **OpenWhispr / Handy / VoiceInk** | Grátis (código aberto) | Local | Handy é minimalista (texto quase literal); OpenWhispr tem IA, mas via chaves de API pagas; VoiceInk é só para Mac |
| `/voice` do Claude Code | Grátis | Nuvem (Anthropic) | Só dentro do Claude Code; não funciona em sessões na nuvem/SSH |

**Conclusão:** os melhores (Wispr, Aqua, Willow) são pagos e enviam o áudio para a nuvem. Os gratuitos e
locais transcrevem bem, mas não têm a camada de "inteligência" (limpeza, estilos, comandos, Modo
Comando) que faz a diferença no uso diário. O DitvvOS junta as duas coisas.

## 2. O que o DitvvOS tem

| Recurso | Wispr Flow | Superwhisper | Willow | Handy | **DitvvOS** |
|---|:-:|:-:|:-:|:-:|:-:|
| Funciona em qualquer app | ✓ | ✓ | ✓ | ✓ | ✓ |
| Áudio 100% local | ✗ | ✓ | ✗ | ✓ | ✓ |
| Sem mensalidade / limite | ✗ | ✗ | ✗ | ✓ | ✓ |
| Segurar para falar + mãos-livres | ✓ | ✓ | ✓ | ✓ | ✓ |
| Remove hesitações e gaguejos | ✓ | IA | ✓ | ✗ | ✓ (regras + IA opcional) |
| Autocorreção falada ("2, quer dizer, 3") | ✓ | IA | — | ✗ | ✓ |
| "Apaga isso" / "cancela isso" | — | — | — | ✗ | ✓ |
| Comandos ("nova linha", "novo item", aspas) | — | — | ✓ | ✗ | ✓ |
| Dicionário pessoal | ✓ | ✓ | ✓ | — | ✓ (+ correções forçadas) |
| Atalhos de texto falados (*snippets*) | ✓ | — | — | ✗ | ✓ |
| Estilo por aplicativo | ✓ | modos | ✓ | ✗ | ✓ (casual, formal, código) |
| Modo Comando (editar a seleção por voz) | ✓ | — | — | ✗ | ✓ (IA local, Ollama) |
| Indicador visual com medidor de volume | ✓ | ✓ | ✓ | ✓ | ✓ |
| Histórico e estatísticas | ✓ | ✓ | — | — | ✓ |
| Iniciar com o sistema | ✓ | ✓ | ✓ | ✓ | ✓ |
| Celular | ✓ | ✓ | ✓ | ✗ | ✗ |

"—" = não encontrei a informação nas fontes pesquisadas.

## 3. Como usar

| Ação | Como |
|---|---|
| **Ditar** | Segure **Ctrl direito**, fale, solte |
| **Mãos-livres** (textos longos) | **Toque rápido** no Ctrl direito, fale à vontade, toque de novo para enviar |
| **Modo Comando** | Selecione um texto, segure **Shift + Ctrl direito** e diga o que fazer: "traduza para o inglês", "deixe mais formal", "transforme em tópicos". Sem seleção, ele gera o texto pedido ("escreva um e-mail pedindo o orçamento") |
| Descartar o que acabou de falar | Termine com "**cancela isso**" |
| Recomeçar no meio da fala | Diga "**apaga isso**": só o que vier depois é inserido |
| Quebras e listas | "**nova linha**", "**novo parágrafo**", "**novo item**" |
| Aspas e parênteses | "**abre aspas** … **fecha aspas**", "**abre parênteses** … **fecha parênteses**" |

Exemplo real (testado):
> 🗣️ "Hum, a reunião vai ser às duas, quer dizer, às três da tarde. Nova linha. Abraço."
>
> ⌨️ A reunião vai ser às três da tarde.<br>Abraço.

### Estilos automáticos por aplicativo
| Estilo | Apps (padrão) | Efeito |
|---|---|---|
| `casual` | WhatsApp, Telegram, Slack, Discord, Teams | Sem ponto final em mensagem curta, como se digita no chat |
| `formal` | Gmail, Outlook, Word, Google Docs, Notion | Maiúsculas e pontuação final garantidas |
| `codigo` | Terminais, VS Code, Cursor, Claude, JetBrains | Preserva nomes de arquivos e comandos (sem ponto solto depois de `engine.py`) |
| `normal` | Demais | Texto como transcrito e limpo |

---

## 4. Instalação

Requisitos: Python 3.10+ e um microfone.

```bash
cd transcritor-ai
pip install -r requirements.txt -r requirements-ditvvos.txt
python -m ditvvos                  # ou dê dois cliques em iniciar-ditvvos.bat (Windows)
```

Na primeira vez o modelo (`large-v3-turbo`, ~1,6 GB) é baixado. Deixe a janela aberta (pode minimizar).

- **Windows:** funciona direto. Para colar em programas abertos como Administrador, rode o DitvvOS como Administrador também.
- **macOS:** permita *Acessibilidade* e *Microfone* para o Terminal (Ajustes → Privacidade e Segurança). Sem Ctrl direito no teclado? Use `--tecla alt_r` (Option direito).
- **Linux (X11):** `sudo apt install libportaudio2 xclip xdotool python3-tk`. No Wayland, atalhos globais podem ser bloqueados pelo sistema.

**Iniciar com o sistema:** `python -m ditvvos inicializacao ativar` (desfaz com `desativar`).

### IA local opcional (Modo Comando e polimento)
1. Instale o [Ollama](https://ollama.com) (gratuito) e baixe o modelo: `ollama pull gemma3:4b`
2. Ative: `python -m ditvvos ia` (testa e liga)
3. Opcional, polimento de todo ditado (mais natural, +3–5 s por fala em CPU):
   `python -m ditvvos config definir llm.polish true`

Com 16 GB de RAM ou GPU, modelos maiores (`gemma3:12b`, `qwen2.5:7b`) dão resultados ainda melhores:
`python -m ditvvos config definir llm.model gemma3:12b`

## 5. Personalização

```bash
# dicionário pessoal: nomes, marcas, jargões (o modelo passa a acertar a grafia)
python -m ditvvos dicionario adicionar "LeadTalkAI"
python -m ditvvos dicionario corrigir "super base" "Supabase"
python -m ditvvos dicionario importar glossario.exemplo.txt

# atalhos falados: diga só o gatilho e o texto completo é inserido
python -m ditvvos atalhos adicionar "minha assinatura" "Atenciosamente,\nSid Ferreira\ncontato@sidferreira.com.br"

# estilos
python -m ditvvos estilos definir slack formal
python -m ditvvos estilos padrao casual

# configurações gerais (arquivo: ~/.ditvvos/config.json)
python -m ditvvos config                                # mostra tudo
python -m ditvvos config definir hotkey '"f9"'          # outra tecla
python -m ditvvos config definir submit true            # Enter automático após inserir
python -m ditvvos config definir model '"small"'        # mais rápido em PCs fracos

# histórico
python -m ditvvos historico                    # últimos ditados
python -m ditvvos historico --buscar orçamento
python -m ditvvos historico --estatisticas     # palavras, tempo economizado, espera média
python -m ditvvos historico --copiar-ultimo
```

---

## 6. Como foi validado

Tudo foi testado num ambiente Linux com tela virtual (Xvfb + gerenciador de janelas), usando o
**atalho global real** (teclas pressionadas pelo sistema com `xdotool`), uma janela de editor como alvo e
o **Ollama real** com `gemma3:4b`. O único elemento simulado foi o microfone: o áudio veio de
gravações reais de voz (FLEURS pt-BR) e de voz sintetizada.

| Cenário | Resultado |
|---|---|
| Segurar Ctrl direito → colar | ✓ texto correto, foco preservado na janela-alvo |
| Toque rápido → mãos-livres → toque → colar | ✓ |
| Modo "digitar" com acentos (í, ó, á, ç) | ✓ |
| Estilo por app (título "WhatsApp Web" → casual; "Claude Code" → código) | ✓ |
| "Hum… às duas, quer dizer, às três… Nova linha. Abraço." | ✓ "A reunião vai ser às três da tarde.⏎Abraço." |
| Modo Comando: seleção + "Traduza para o inglês" | ✓ seleção substituída pela tradução em 7,6 s |
| Indicador visual some quando ocioso e não rouba o foco | ✓ |
| 71 testes automatizados (regras de texto, atalho, IA com servidor falso, CLI, histórico, autostart) | ✓ |

**Tempos medidos (CPU de 4 núcleos, sem GPU):** frases de 7–20 s ficam prontas em **~4,5–5,5 s**
(`large-v3-turbo`) ou **~2,5–3 s** (`small`). Modo Comando: ~4–8 s com `gemma3:4b`. Com GPU NVIDIA a
transcrição cai para menos de 1 s.

### Travas de segurança da IA
Modelos pequenos às vezes *respondem* o que foi ditado ("qual é a capital da França?" → "Paris…") ou
misturam outros alfabetos. O DitvvOS bloqueia os dois casos: se a revisão perder mais de 40% das
palavras ditadas ou trouxer caracteres de outro alfabeto, ele descarta a saída da IA e usa o texto das
regras locais.

## 7. Limitações (honestas)

- **Latência:** serviços na nuvem inserem o texto em ~0,5 s; aqui, em CPU, são ~5 s por frase. Uma GPU
  resolve; sem GPU, o modelo `small` é um meio-termo.
- **Sem texto ao vivo enquanto fala** (o Aqua Voice mostra; aqui o texto aparece ao soltar a tecla).
- **Sem app de celular** e sem ícone na bandeja: a configuração é por linha de comando/arquivo JSON.
- **Não testado fisicamente em Windows e macOS.** O código trata as duas plataformas (colar com
  Cmd+V, detecção do app ativo, autostart, indicador que não rouba foco), mas a validação completa foi
  feita em Linux.
- A qualidade da IA local depende do modelo: `gemma3:4b` é bom para tradução, tom e listas, mas não
  chega ao nível dos modelos de nuvem.
- O cancelamento é por voz ("cancela isso"). `Esc` não é usado porque um atalho global não consegue
  "engolir" a tecla: ela chegaria também ao app em foco (no Claude Code, interromperia a resposta).

## Fontes
- [Wispr Flow alternatives — Saner.ai](https://www.saner.ai/blogs/best-wispr-flow-alternatives)
- [Wispr Flow review — recursos (snippets, dicionário, estilos, Command Mode)](https://kripeshadwani.com/wispr-flow-review/) · [eesel.ai](https://eesel.ai/blog/wispr-flow-overview)
- [Aqua Voice — alternativas](https://aquavoice.com/blog/wispr-flow-alternatives) · [Willow alternatives](https://usevoicy.com/blog/willow-voice-alternatives)
- [OpenWhispr vs Handy](https://www.getvoibe.com/resources/openwhispr-vs-handy/) · [VoiceInk](https://openalternative.co/alternatives/voiceink)
- [Ditado por voz do Claude Code](https://code.claude.com/docs/en/voice-dictation)
