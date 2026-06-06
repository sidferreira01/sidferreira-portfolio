# 🎬 TikTok Performance Hub & Video Studio IA

O **TikTok Performance Hub** é um dashboard analítico e estúdio de criação automatizado voltado para criadores de conteúdo e e-commerces. O sistema monitora a velocidade semanal de vendas, faturamento (GMV) e retenção de criativos de vídeo, e fornece uma interface integrada à Inteligência Artificial (Google Gemini Veo) para gerar anúncios de vídeo de alta conversão de 8 segundos a partir de imagens de produtos e prompts de roteiro.

---

## 🚀 Integração Google Gemini Veo (Video Studio)

A geração de vídeos é a funcionalidade mais avançada do projeto. Ela une design moderno de interface, carregamento assíncrono baseado em estados (Query/Polling) e consumo de APIs generativas de mídia:

1. **Otimização de Roteiro Assistida por IA:** O usuário digita uma ideia simples de vídeo (ex: "mostra o produto girando num fundo roxo"). O sistema executa a função de servidor `expandVideoPrompt` que traduz e enriquece o texto para inglês com terminologia técnica de filmagem cinematográfica (ex: *"Cinematic close-up of a rotating product with neon purple backlight, slow motion 4k, dramatic studio lighting"*), o que garante ótimos resultados nos modelos de imagem/vídeo.
2. **Dupla Categoria de Renderização:**
   * **Fast Mode:** Executado no modelo `veo-3.0-fast-generate-preview` (~US$ 0.40 por renderização), levando cerca de 1 a 3 minutos na fila para testes rápidos.
   * **Quality Mode:** Executado no modelo premium `veo-3.0` (~US$ 4.00 por renderização) para qualidade cinematográfica máxima de lançamento.
3. **Mídia Multimodal de Origem (Image-to-Video):** O usuário pode fazer o upload de uma imagem do próprio produto (limite de 18MB). A imagem é convertida em base64 e injetada no Gemini Veo junto com o prompt textual para que o vídeo gerado seja baseado exatamente na foto real do produto.
4. **Arquitetura Async / Polling:** Como a geração de vídeos por redes neurais generativas é demorada (~2 minutos), a interface React gerencia o estado por meio de consultas intervaladas de refetch dinâmicas (Polling). Uma rotina em background no cliente verifica se há processos `pending` ou `processing` e faz requisições até que o status mude para `completed` (exibindo o player de vídeo MP4 e botão de download) ou `failed` (exibindo o log de erro do modelo).
