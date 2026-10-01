# 🎙️ Transcritor AI — áudio em texto de alta precisão, 100% local

Conversor de áudio e vídeo em texto que roda **na sua máquina ou VPS**, sem mensalidade e sem custo por minuto.
Reúne numa ferramenta só o que as soluções pagas oferecem separadamente: modelo de ponta, identificação de
falantes, vocabulário customizado, legendas prontas e revisão guiada das palavras incertas.

> **Objetivo:** substituir assinaturas de transcrição (TurboScribe, Otter, Fireflies, Rev…) e APIs cobradas
> por minuto, sem perder precisão em português.

---

## 1. Pesquisa de mercado (set/2026)

### 1.1 Ferramentas pagas para o usuário final

| Ferramenta | Preço | Motor | Pontos fortes | Limitações |
|---|---|---|---|---|
| **TurboScribe** | US$ 10/mês (anual) ou US$ 20/mês | **Whisper** (open-source) | Arquivos ilimitados, 98+ idiomas, exporta SRT/DOCX | Você paga por um modelo que é gratuito; áudio vai para a nuvem deles |
| **Otter.ai** | Planos pagos por usuário | Proprietário | Tempo real dentro de Zoom/Meet/Teams, resumos | Fraco fora do inglês; limite de minutos por plano |
| **Fireflies.ai** | Pro US$ 10, Business US$ 19 por usuário/mês | Proprietário | Bot que entra na reunião, busca no histórico, integrações CRM | Foco em reuniões; cobra por assento |
| **Rev** | US$ 25,49/assento/mês (Essentials) | Proprietário + humanos | Opção de revisão humana, usado em jurídico/médico | Caro; humano cobra à parte |

**Achado principal:** a líder de custo-benefício (TurboScribe) roda Whisper — o mesmo modelo aberto que usamos
aqui. O diferencial pago é conveniência (upload, editor, exportação), que este projeto reproduz.

### 1.2 APIs para desenvolvedores

| API | Preço aproximado | Observação |
|---|---|---|
| AssemblyAI Universal | a partir de US$ 0,0025/min | Diarização, vocabulário e recursos extras encarecem |
| Deepgram Nova-3 | ~US$ 0,0077/min | Baixa latência, WER real alto em áudio misto (~18% AA-WER) |
| OpenAI (Whisper/gpt-4o-transcribe) | até ~US$ 0,006–0,01/min | Simples, sem diarização nativa no Whisper |
| ElevenLabs Scribe v2 | — | Melhor WER entre APIs no ranking Artificial Analysis (2,2%, jul/2026) |

Com diarização + vocabulário + armazenamento, o custo real passa de **US$ 0,015/min** em várias delas.

### 1.3 Modelos abertos (o que dá para rodar de graça)

| Modelo | Português | Velocidade | Uso aqui |
|---|---|---|---|
| **Whisper large-v3** (OpenAI) | **WER 3,65% no FLEURS pt** — o melhor aberto em PT | Lento em CPU | Preset `maxima` |
| **Whisper large-v3-turbo** | Muito próximo do large-v3 | Várias vezes mais rápido (decoder de 4 camadas em vez de 32) | **Padrão** (`equilibrado`) |
| NVIDIA Parakeet-TDT 0.6B v3 | WER 4,76% no FLEURS pt | Muito rápido em CPU | Não adotado: pior em PT e exige NeMo |
| NVIDIA Canary-Qwen 2.5B | #1 do Open ASR Leaderboard, **só inglês** | — | Não se aplica ao PT |
| Voxtral (Mistral) | Bom multilíngue | Pesado (3B/24B) | Não compensa em CPU |
| **pyannote community-1** | Diarização (independe de idioma) | CPU/GPU | Identificação de falantes |

**Decisão técnica:** Whisper large-v3 / large-v3-turbo via **faster-whisper** (CTranslate2): mesma precisão do
original, até 4x mais rápido e com metade da memória, quantização int8 em CPU e float16 em GPU.

---

## 2. O que aplicamos de cada concorrente (e o que fizemos além)

| Recurso de mercado | Quem tem | Como está no Transcritor AI |
|---|---|---|
| Upload arrastar-e-soltar, fila, histórico | TurboScribe, Rev | Interface web com fila, progresso e histórico salvo em disco |
| Qualquer formato (inclui vídeo) | Todos | ffmpeg: mp3, m4a, **ogg/opus do WhatsApp**, wav, mp4, mkv, mov… |
| Identificação de falantes | Otter, Fireflies, AssemblyAI | pyannote **community-1**, com nº de falantes opcional |
| Vocabulário customizado | AssemblyAI, Deepgram (pago à parte) | Glossário: termos (prompt do modelo) + correções `errado => certo` |
| Legendas SRT/VTT | TurboScribe, Rev | Quebra profissional: ≤42 caracteres/linha, 2 linhas, ≤6 s, cortes em pontuação |
| Player sincronizado com texto | Otter, Descript | Clique numa palavra → áudio pula para ela; palavra atual destacada |
| Busca no texto | Fireflies | Busca instantânea com destaque |
| Revisão de trechos duvidosos | Rev (revisão humana, paga) | **Palavras de baixa confiança destacadas + botão "Próxima incerta"** |
| Processamento em lote | TurboScribe | CLI transcreve pastas inteiras, com `--pular-existentes` |
| — (nenhum oferece) | — | **2ª passada automática:** trechos incertos são re-decodificados com busca mais ampla |
| — (nenhum oferece) | — | **Filtro de alucinações** do Whisper em PT ("Legendas pela comunidade Amara.org", loops de repetição) |
| Privacidade | Só planos enterprise | **O áudio nunca sai da sua máquina** |

---

## 3. Como a precisão é obtida

```
arquivo ─► ffmpeg ─► VAD ─► Whisper ─► 2ª passada ─► limpeza ─► diarização ─► exportação
           16kHz     corta   beam search  re-decodifica  alucinações  pyannote     txt srt vtt
           mono      silêncio timestamps   trechos com    repetições   quem falou   md json
           highpass           por palavra  baixa confiança glossário
           loudnorm           + glossário
```

1. **Pré-processamento (ffmpeg):** converte para 16 kHz mono (formato nativo do Whisper), filtro passa-alta de
   80 Hz (tira ronco de ar-condicionado/mesa), normalização de volume (falas baixas deixam de ser puladas) e
   redução de ruído opcional.
2. **VAD (Silero):** remove silêncios antes do modelo — é a principal defesa contra alucinações e ainda acelera.
3. **Decodificação:** beam search (5 a 8 feixes), idioma fixo em `pt` (evita erro de detecção), timestamps por
   palavra, `condition_on_previous_text=False` (evita loops em áudios longos) e descarte de texto "inventado"
   em silêncios longos (`hallucination_silence_threshold`).
4. **Contexto e glossário:** termos entram no prompt inicial — o Whisper copia a grafia de nomes, marcas e
   siglas. Correções `errado => certo` são aplicadas depois, inclusive nos timestamps por palavra.
5. **2ª passada de revisão:** trechos com log-probabilidade baixa, confiança média < 65% ou texto repetitivo
   são recortados e re-decodificados isoladamente com 10–12 feixes e temperaturas alternativas. A versão nova
   só substitui a original se o modelo estiver mais confiante nela.
6. **Limpeza:** remove frases que o Whisper alucina em PT por causa de legendas de treino, colapsa repetições
   ("eu acho eu acho eu acho…") e descarta cópias idênticas em sequência.
7. **Diarização (opcional):** cada palavra recebe o falante com maior sobreposição de tempo; segmentos são
   quebrados exatamente onde o falante muda.

### Resultados medidos (FLEURS pt-BR)

Medido neste projeto com `large-v3-turbo` em **CPU comum (4 núcleos, sem GPU)**, no conjunto de teste
FLEURS pt-BR — o mesmo usado nos rankings públicos. WER = % de palavras erradas (menor é melhor).

| Cenário | Whisper "puro" (como as ferramentas pagas usam) | **Transcritor AI** |
|---|---|---|
| 100 frases curtas (20,8 min) | WER 3,86% · 2,6x tempo real | **WER 3,78%** · 2,5x tempo real |
| Áudio longo com pausas (13,2 min) | WER 4,70% · 3,5x tempo real | **WER 4,10% · 4,4x tempo real** |

Leitura honesta dos números:
- Em frases curtas e limpas o Whisper já é muito bom; o ganho é pequeno.
- Em **áudio longo — o caso real de reuniões, aulas e podcasts — o erro caiu ~13% e ficou ~25% mais rápido**,
  graças ao VAD, ao corte de loops e ao filtro de alucinações.
- O FLEURS não tem jargão nem nomes de empresas, então **o ganho do glossário não aparece aqui**; em áudios
  de negócio (nomes de clientes, produtos, siglas) é justamente onde ele mais corrige.
- "2,5x tempo real" em CPU = 1 hora de áudio em ~25 min. Com GPU, 1 hora sai em 1–3 min.

Reproduza com `python bench/fleurs_wer.py` (instruções no topo do script).

---

## 4. Instalação

Requisitos: Python 3.10+. O ffmpeg vem pelo pip (`imageio-ffmpeg`), mas se já existir no sistema é usado.

```bash
cd transcritor-ai
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Na primeira execução o modelo é baixado automaticamente (turbo ≈ 1,6 GB; large-v3 ≈ 3 GB).

**GPU NVIDIA (opcional, ~10–30x mais rápido):** com CUDA 12 + cuDNN 9 instalados, é detectada automaticamente
e usa float16. Sem GPU, roda em CPU com int8.

**Diarização (opcional):**
```bash
pip install -r requirements-diarization.txt
# crie um token grátis em huggingface.co/settings/tokens e aceite os termos de
# huggingface.co/pyannote/speaker-diarization-community-1
export HF_TOKEN=hf_xxx
```

---

## 5. Uso

### Interface web
```bash
python -m transcritor servidor            # abre em http://127.0.0.1:8000
```
Arraste os arquivos, escolha a qualidade, (opcional) cole o glossário e clique em **Transcrever**.
Na visualização: clique em qualquer palavra para ouvir o trecho, use **Próxima incerta** para revisar
só o que o modelo não tinha certeza, e baixe em TXT, SRT, VTT, MD ou JSON.

### Linha de comando
```bash
# um arquivo, formatos padrão (txt + srt)
python -m transcritor transcrever reuniao.mp3

# pasta inteira, máxima precisão, com glossário e 2 falantes
python -m transcritor transcrever ./audios -p maxima -g glossario.exemplo.txt --falantes 2 -f txt srt md -o ./saida

# áudios de WhatsApp, rápido, só imprimir o texto
python -m transcritor transcrever *.ogg -p rapido --imprimir
```

| Opção | Descrição |
|---|---|
| `-p/--preset` | `equilibrado` (padrão), `maxima`, `rapido` |
| `-m/--modelo` | Força um modelo (`large-v3`, `large-v3-turbo`, `medium`, `small`…) |
| `-i/--idioma` | `pt` (padrão), `en`, `es`… ou `auto` |
| `-f/--formatos` | `txt srt vtt md json` |
| `-g/--glossario` | Arquivo de glossário (veja `glossario.exemplo.txt`) |
| `-t/--termo` | Termo avulso do vocabulário (repetível) |
| `-c/--contexto` | Frase de contexto do áudio |
| `--falantes N` / `--diarizar` | Identifica falantes (N fixo ou automático) |
| `--reduzir-ruido` | Filtro de ruído para gravações ruins |
| `--sem-revisao` | Desliga a 2ª passada (mais rápido) |
| `--pular-existentes` | Em lotes, não refaz o que já foi transcrito |

### Ditado por voz em qualquer janela → **DitvvOS**
O mesmo motor de transcrição alimenta o **DitvvOS**: segure Ctrl direito, fale e o texto é inserido em
qualquer janela (inclusive no Claude Code), com limpeza de hesitações, comandos de voz, estilos por app e
Modo Comando com IA local. Documentação completa em **[DITVVOS.md](./DITVVOS.md)**.

```bash
pip install -r requirements-ditvvos.txt
python -m ditvvos
```

### Docker / VPS
```bash
docker build -t transcritor-ai .
docker run -d -p 8000:8000 -e TRANSCRITOR_TOKEN=um-token-forte \
  -v transcritor-modelos:/modelos -v transcritor-dados:/dados transcritor-ai
```
Com `TRANSCRITOR_TOKEN` definido, a API exige `Authorization: Bearer <token>` (a interface pede o token uma vez).

### API REST (para integrar com n8n, Evolution API, etc.)
| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/api/jobs` | Envia arquivo (`multipart`: `file`, `preset`, `language`, `diarize`, `num_speakers`, `denoise`, `glossary`, `context`) |
| `GET` | `/api/jobs/{id}` | Status, progresso e, quando concluído, a transcrição completa em JSON |
| `GET` | `/api/jobs/{id}/download/{fmt}` | Baixa `txt`, `srt`, `vtt`, `md` ou `json` |
| `GET` | `/api/jobs` | Histórico |
| `DELETE` | `/api/jobs/{id}` | Apaga transcrição e áudio |

---

## 6. Configuração por variáveis de ambiente

| Variável | Padrão | Uso |
|---|---|---|
| `TRANSCRITOR_TOKEN` | — | Protege a API/interface |
| `TRANSCRITOR_DEVICE` | auto | `cpu` ou `cuda` |
| `TRANSCRITOR_COMPUTE_TYPE` | auto | `int8`, `int8_float16`, `float16`… |
| `TRANSCRITOR_CPU_THREADS` | todos | Limita threads em CPU |
| `TRANSCRITOR_MODELS_DIR` | cache do HF | Onde os modelos ficam salvos |
| `TRANSCRITOR_MAX_UPLOAD_MB` | 2048 | Tamanho máximo de upload |
| `HF_TOKEN` | — | Necessário só para a diarização |

---

## 7. Estrutura

```
transcritor-ai/
├── transcritor/
│   ├── audio.py         # ffmpeg: conversão + filtros
│   ├── engine.py        # faster-whisper, 2ª passada de revisão, orquestração
│   ├── postprocess.py   # anti-alucinação, repetições, glossário
│   ├── diarization.py   # pyannote + alinhamento palavra→falante
│   ├── exporters.py     # txt, srt, vtt, md, json
│   ├── config.py        # presets e glossário
│   ├── server.py        # API FastAPI + fila
│   ├── cli.py           # linha de comando
│   └── static/index.html
├── ditvvos/             # DitvvOS: ditado por voz em qualquer janela (veja DITVVOS.md)
├── bench/fleurs_wer.py  # benchmark de precisão (WER)
└── tests/               # pytest (não precisa baixar modelo)
```

Testes: `pip install -r requirements-dev.txt && pytest`

---

## 8. Economia

Exemplo com 20 h de áudio por mês:

| Opção | Custo mensal |
|---|---|
| TurboScribe (mensal) | US$ 20 |
| Fireflies Business, 1 usuário | US$ 19 |
| API com diarização (~US$ 0,015/min × 1.200 min) | ~US$ 18 |
| **Transcritor AI no seu computador** | **US$ 0** |
| Transcritor AI numa VPS CPU de 4 vCPU/8 GB | o que você já paga pela VPS |

Limitações honestas: em CPU o processamento é mais lento que nos serviços pagos (veja a velocidade medida
acima) — para grandes volumes vale uma GPU (mesmo uma de entrada) ou deixar lotes rodando à noite.
Transcrição ao vivo durante reuniões (estilo Otter) não faz parte desta versão.

---

## Fontes da pesquisa
- [Open ASR Leaderboard — Hugging Face](https://huggingface.co/blog/open-asr-leaderboard) e [artigo](https://arxiv.org/html/2510.06961v4)
- [Canary-1B-v2 & Parakeet-TDT-0.6B-v3 (NVIDIA) — WER por idioma, incluindo PT](https://arxiv.org/pdf/2509.14128)
- [Best STT Providers 2026 — Coval](https://www.coval.ai/blog/best-speech-to-text-providers-in-2026-independent-benchmarks-and-how-to-choose/)
- [Best open source STT 2026 — Northflank](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks)
- [pyannote community-1](https://pyannote.ai/blog/community-1)
- [TurboScribe vs Otter](https://turboscribe.ai/learn/turboscribe-vs-otter-ai) · [5 Best AI Transcribers 2026](https://site.joinleland.com/library/a/ai-transcribers) · [Fireflies vs Rev (G2)](https://www.g2.com/compare/fireflies-ai-vs-rev)
- [Preços de APIs STT 2026 — Smallest.ai](https://smallest.ai/blog/speech-to-text-api-pricing-models-explained-(2026)) · [AssemblyAI vs Deepgram — CostBench](https://costbench.com/compare/assemblyai-vs-deepgram)
