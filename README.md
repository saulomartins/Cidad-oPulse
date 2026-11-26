# CidadãoPulse

Sistema completo de **Monitoramento de Sentimento na Internet e Redes Sociais** + **Radar Semanal Mundial de Premiações e Concursos** para softwares e iniciativas de atendimento ao cidadão (com ou sem IA).

## Funcionalidades Principais

1. **Cadastro de Sistemas e Iniciativas**
   - URLs oficiais, palavras-chave, hashtags e arrobas para monitoramento de reputação.
   - Ficha completa do que o sistema é: estágio (**iniciativa/em desenvolvimento** ou **já desenvolvido/em produção**), uso de IA (**com IA**, **sem IA** ou **híbrido**), área de atendimento ao cidadão, público-alvo e impacto.
2. **Monitoramento de Sentimento Híbrido e Modular**
   - **Prontos sem chave:** Google News RSS e Reddit Busca Pública + analisador de sentimento local PT-BR/EN.
   - **Com `GEMINI_API_KEY`:** Gemini (`gemini-4-hydrogen`) com **Google Search Grounding** varrendo toda a internet e referências públicas em redes sociais (notícias, Reclame Aqui, X, Instagram, Facebook, LinkedIn, YouTube, App Stores) + análise semântica de sentimento, tópicos e detecção de sinais de crise.
   - **Plugáveis (basta inserir a chave nas Configurações):** YouTube Data API v3, Apify (Instagram/TikTok/Facebook), X API v2 e Meta Graph API.
3. **Radar Semanal Mundial de Premiações e Concursos**
   - Pesquisa mundial (ONU/UNPSA, WSIS, GovTech Prize, Bloomberg Mayors Challenge, Smart City Expo, OECD OPSI, MIT Solve, DPGA, ENAP, Conexão Inova, ABEP-TIC, CLP e novas descobertas ao vivo via Gemini Google Search Grounding).
   - Calcula **% de aderência (Match Score)** com justificativa personalizada considerando se o sistema usa IA ou não e se é uma iniciativa ou sistema já em produção.
   - Pipeline de acompanhamento (`Novo` → `Em Análise` → `Inscrito` → `Premiado`) e exportação em **Markdown** e **CSV**.
4. **Agendamento Automático + Alertas**
   - Agendador `APScheduler` integrado (radar semanal configurável + varredura recorrente de sentimento) e botões de disparo manual.
   - Alertas automáticos via **Webhook (Slack / Microsoft Teams / Genérico)** e **E-mail (SMTP)**.

## Como Rodar Localmente (Windows / PowerShell)

### Opção rápida
```powershell
.\start.ps1
```

### Opção manual

1. **Backend (FastAPI + SQLite)**
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

2. **Frontend (React + Vite)**
```powershell
cd frontend
npm install
npm run dev
```

3. Acesse `http://localhost:5173` e (opcionalmente) configure sua `GEMINI_API_KEY` na aba **Conectores & Alertas** ou em um arquivo `.env` na raiz (copie `.env.example` para `.env`).
