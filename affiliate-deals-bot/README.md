# 🛍️ Bot de Curadoria e Automação de Ofertas de Afiliados com IA

Este projeto é um robô de automação comercial autônomo escrito em Python. Ele atua na raspagem de promoções de fóruns web, na resolução de links com redirecionamentos múltiplos, na conversão automática dessas URLs para links de afiliado monetizados (integração direta com **API Oficial da Shopee V2** e links personalizados de afiliados da Amazon e Mercado Livre) e na geração de cópias comerciais persuasivas utilizando a IA **Google Gemini**.

---

## 🏗️ Fluxo e Processamento de Ofertas

O robô executa a rotina de processamento de forma sequencial seguindo as etapas abaixo:

```
[Inicia Ciclo (2 horas)] ──> [Esvazia Fila Noturna (Se horário comercial)]
                                  │
                                  ▼
                     [Scraping de Ofertas (Gatry)]
                                  │
                                  ▼
                [Resolve Redirecionamentos de Links (HTTP)]
                                  │
                                  ▼
                [Verifica Duplicadas (Supabase + Cache MD5)]
                                  │
      ┌───────────────────────────┴───────────────────────────┐
      ▼ [Horário Comercial: 08h às 20h]                       ▼ [Horário Noturno: Silêncio]
[Converte Links (Shopee API / regex)]                   [Enfileira Fila Noturna Local]
      │                                                       │
      ▼                                                       ▼
[Gera Cópia Persuasiva (Gemini)]                        [Salva no Supabase como Histórico]
      │
      ▼
[Dispara Mensagem (Evolution API)]
```

---

## ✨ Recursos de Destaque

* **Web Scraping com Tratamento de Redirecionamento:** O bot varre o portal de promoções e analisa a rede HTTP para encontrar o link final de destino do produto, resolvendo redirects complexos de encurtadores comuns de forma autônoma.
* **Conversão Programática (Shopee API V2):** O sistema detecta links originados do domínio da Shopee e utiliza chamadas assinadas à API oficial de desenvolvedores para convertê-los em links parametrizados de afiliados (`short_link` e `app_link`) em tempo real.
* **Redator Comercial IA (Gemini Copywriting):** Reescreve os anúncios brutos em mensagens de alta conversão para o WhatsApp, seguindo regras rígidas de tom de voz (sem markdown robótico duplo `**`, usando emojis, benefícios rápidos e mantendo o link limpo na última linha).
* **Fila Noturna / Restrição Horária:** Para evitar incomodar os clientes, o bot possui um motor de controle de fuso horário. Promoções encontradas fora da janela de postagem (das 08h às 20h) são persistidas localmente em uma fila e postadas em lote imediatamente na manhã seguinte.
* **Prevenção de Duplicatas Centralizada:** Para evitar postar duas vezes a mesma promoção caso o fórum seja atualizado, o bot faz uma dupla validação (cache de MD5 do título e verificação assíncrona contra a tabela `historico_afiliado` do Supabase).
