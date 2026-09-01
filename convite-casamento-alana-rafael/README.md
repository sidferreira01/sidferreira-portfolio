# 💌 Convite Digital Interativo — Alana & Rafael

Versão web animada do convite de casamento (originalmente um PDF em formato
"story" 9:16), com as mesmas 3 telas, textos, alinhamentos e links do arquivo
original — nada foi alterado no conteúdo, apenas adicionada uma camada de
interação/animação.

**Tech Stack:** HTML5, CSS3 (3D transforms, transitions) e JavaScript puro
(Pointer Events), sem dependências externas.

## Interações

1. **Capa (página 1):** ao tocar/clicar no botão dourado, a capa se abre como
   uma porta dupla (rotação 3D nas duas metades) e revela a página 2 por
   baixo, com um leve efeito de "queda" (a página se assenta no lugar).
2. **Página 2 → Página 3:** navegação por arraste horizontal (swipe), com
   resistência nas bordas, snap suave e apoio por pontos indicadores, setas
   e teclado (← →) para quem não está em um dispositivo touch.
3. **Botões da página 3:** "Confirme sua presença", "Localização" e "Mimo
   Para os Noivos" continuam levando exatamente aos mesmos links do convite
   original (RSVP, Google Maps e página de Pix), abertos em nova aba.

## Como visualizar

Basta abrir `index.html` em um navegador, ou servir a pasta com qualquer
servidor estático:

```bash
python3 -m http.server 8080
# acesse http://localhost:8080
```

## Estrutura

```
convite-casamento-alana-rafael/
├── index.html      # marcação e hotspots (links) sobre as imagens originais
├── style.css        # layout responsivo 9:16, animação da porta e do swipe
├── script.js         # abertura da capa, arraste/swipe e navegação de apoio
└── assets/           # páginas do convite original exportadas em WebP
```
