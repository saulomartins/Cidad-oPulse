# Guia de Publicação 100% Gratuita — CidadãoPulse

Este projeto já está empacotado em **1 único container Docker** (o próprio FastAPI serve a API e o site React compilado na mesma URL), com **proteção por senha** (`APP_PASSWORD`) e suporte nativo a **PostgreSQL gratuito** (`DATABASE_URL`).

---

## Opção Recomendada: Render (App Grátis) + Neon (PostgreSQL Grátis)
*Não exige cartão de crédito em nenhuma das duas plataformas.*

### Passo 1 — Criar o banco de dados gratuito (Neon)
1. Acesse [https://neon.tech](https://neon.tech) e crie uma conta gratuita (pode entrar com GitHub ou Google).
2. Clique em **New Project** → dê o nome `cidadao-pulse` → escolha a região mais próxima (ex.: São Paulo ou US East) → **Create project**.
3. Na tela inicial do projeto, clique em **Connect** e copie a **Connection String** (começa com `postgresql://...`).
   - Guarde essa string — ela será usada na variável `DATABASE_URL`.

### Passo 2 — Subir o código para o GitHub (Repositório Privado)
No PowerShell, dentro da pasta `C:\Users\saulo\.gemini\antigravity\scratch\cidadao-pulse`:
```powershell
git init
git add .
git commit -m "Deploy inicial CidadaoPulse"
```
> **Segurança garantida:** o arquivo `.gitignore` já bloqueia `.env`, `.venv`, `node_modules` e o banco local `backend/data/cidadao_pulse.db`, então nenhuma chave privada vai para o GitHub.

Crie um repositório **Privado** em [https://github.com/new](https://github.com/new) (ex.: `cidadao-pulse`) e envie:
```powershell
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/cidadao-pulse.git
git push -u origin main
```

### Passo 3 — Publicar de graça no Render
1. Acesse [https://dashboard.render.com](https://dashboard.render.com) e entre com sua conta do GitHub.
2. Clique em **New +** → **Blueprint** (ou **Web Service** escolhendo **Docker**).
3. Selecione o repositório `cidadao-pulse` que você acabou de criar.
4. Configure as **Environment Variables** (Variáveis de Ambiente):
   - `DATABASE_URL` = *(cole a Connection String do Neon do Passo 1)*
   - `APP_PASSWORD` = *(crie uma senha forte para proteger o painel)*
   - `GEMINI_API_KEY` = *(sua chave da Gemini API)*
   - `GEMINI_MODEL` = `gemini-3.5-flash-lite`
   - `APIFY_TOKEN` = *(seu token da Apify para Instagram/Facebook)*
5. Confirme o plano **Free** e clique em **Apply / Deploy**.
6. Aguarde ~3 a 5 minutos pelo build do Docker. Quando ficar **Live**, abra sua URL `https://cidadao-pulse-xxxx.onrender.com` e entre com a senha definida em `APP_PASSWORD`!

---

## Compartilhando Acesso com Outros Usuários (Tokens de Convidado)
Depois de entrar como **Admin**, vá em **Conectores & Alertas → Tokens de Acesso para Convidados**:
1. Informe o nome do destinatário (ex.: `Diretoria SEE-MG`), escolha a permissão (**Somente Leitura** ou **Colaborador**) e a validade.
2. Clique em **Gerar Token** e use:
   - **Copiar Link Direto** (`https://sua-url/?token=cp_...`): a pessoa abre o painel já autenticada sem precisar digitar nada; ou
   - **Copiar Token** (`cp_...`): a pessoa cola diretamente na tela de login.
3. Convidados **nunca** veem a aba de Configurações nem suas chaves de API, e você pode clicar em **Revogar** a qualquer momento para cortar o acesso imediatamente.

---

## Passo 4 (Opcional) — Manter varreduras automáticas funcionando no plano Free
No plano gratuito do Render, o servidor hiberna após 15 minutos sem acesso (acordando automaticamente em ~30–50s quando alguém abre a URL).

Para garantir que a **varredura diária de sentimento** e o **radar semanal de premiações** continuem rodando sozinhos mesmo com o app hibernado, você pode usar o serviço gratuito [https://cron-job.org](https://cron-job.org):
1. Crie uma conta grátis em `cron-job.org`.
2. Crie um agendamento **POST** para:
   - Sentimento (diário): `https://SUA-URL.onrender.com/api/sentiment/scan`
   - Premiações (semanal, ex.: segunda 08h): `https://SUA-URL.onrender.com/api/awards/scan`
3. Em **Headers** (Cabeçalhos), adicione:
   - `Content-Type`: `application/json`
   - `X-App-Password`: *(a mesma senha que você colocou em `APP_PASSWORD`)*
4. Em **Body**, coloque `{}`.

---

## Alternativa Gratuita com 16 GB de RAM: Hugging Face Spaces (Docker)
Se quiser menos hibernação (só dorme após **48 horas** sem uso) e **16 GB de RAM grátis** sem cartão:
1. Crie uma conta grátis em [https://huggingface.co](https://huggingface.co).
2. Clique em **New Space** → SDK: **Docker (Blank)** → Visibilidade: **Private** (ou Public, já que o app tem `APP_PASSWORD`).
3. Em **Settings → Variables and secrets**, adicione:
   - `PORT` = `7860`
   - `DATABASE_URL` = *(sua URL do Neon)*
   - `APP_PASSWORD` = *(sua senha)*
   - `GEMINI_API_KEY`, `GEMINI_MODEL=gemini-3.5-flash-lite`, `APIFY_TOKEN`
4. Envie os arquivos do repositório via Git para o Space — o `Dockerfile` na raiz já faz o build completo automaticamente!
