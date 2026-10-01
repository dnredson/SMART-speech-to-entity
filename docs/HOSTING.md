# Hospedagem do SMART Irrigação

Atualizado em: 2026-10-01.

## Opção gratuita recomendada para testes

Para manter a arquitetura atual com o mínimo de mudanças:

```text
Frontend React/PWA  -> Cloudflare Pages (ou Render Static Site)
Backend FastAPI     -> Render Free Web Service
Banco PostgreSQL    -> Neon Free
OpenAI              -> API key somente no backend
```

### Por que não usar SQLite no Render Free?

O backend usa SQLite por padrão quando `DATABASE_URL` não é definido. Isso é adequado em desenvolvimento local ou em servidor com disco persistente.

Em serviços gratuitos com filesystem efêmero, como o Render Free, o arquivo SQLite pode desaparecer após restart, redeploy ou spin-down. Para hospedagem gratuita, configure um PostgreSQL externo.

A API já aceita `DATABASE_URL` via SQLAlchemy. Exemplo:

```env
DATABASE_URL=postgresql+psycopg://usuario:senha@host/database?sslmode=require
```

O driver `psycopg` já faz parte das dependências da V0.4.

## Variáveis mínimas do backend

```env
OPENAI_API_KEY=sk-proj-...
OPENAI_TEXT_MODEL=gpt-6-luna
OPENAI_TRANSCRIBE_MODEL=gpt-transcribe
ENTITY_EXTRACTOR=openai
STT_PROVIDER=openai
DATABASE_URL=postgresql+psycopg://...
CORS_ORIGINS=https://SEU-FRONTEND.example
```

Nunca coloque `OPENAI_API_KEY` no frontend ou em arquivo versionado.

## Observações para o piloto

- O microfone no navegador remoto precisa de HTTPS.
- Render Free pode entrar em spin-down quando fica sem tráfego; a primeira chamada depois disso pode levar mais tempo.
- O áudio gravado offline fica temporariamente no IndexedDB do navegador até a sincronização.
- Os eventos e o histórico ficam no banco configurado em `DATABASE_URL`.
- Sem `DATABASE_URL`, eventos e histórico ficam no SQLite local `./data/smart-irrigation.db`.

## Firebase

A V0.4 não usa Firebase/Firestore. O Firebase usado em experimentos anteriores do projeto não está conectado a este serviço web.

Persistência atual:

```text
Browser IndexedDB -> fila offline de áudio
Backend SQLite     -> eventos/histórico por padrão
PostgreSQL         -> recomendado para hospedagem externa
```

Se futuramente houver motivo para padronizar o projeto inteiro em Firebase, a camada de persistência pode ser substituída, mas não é necessário para o piloto atual.
