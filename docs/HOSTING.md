# Hospedagem do SMART Irrigação

Atualizado em: 2026-10-01.

## Arquitetura recomendada para o piloto

```text
Frontend React/PWA  -> Firebase Hosting ou Cloudflare Pages
Backend FastAPI     -> servidor próprio, Render ou Cloud Run
Eventos/histórico   -> Cloud Firestore
Áudios originais    -> Cloud Storage for Firebase
OpenAI              -> chave somente no backend
```

Projeto Firebase usado pela V0.5:

```text
Project ID: smart-app-b807a
Storage: smart-app-b807a.firebasestorage.app
Firestore events: irrigation_events
```

## Credenciais no backend

O Firebase Admin SDK usa Application Default Credentials. Fora do Google Cloud, configure:

```env
GOOGLE_APPLICATION_CREDENTIALS=/caminho/seguro/firebase-service-account.json
```

Nunca coloque o JSON real da service account no Git. O repositório ignora `secrets/`, `firebase-service-account.json` e variantes de nome de service account.

## Variáveis mínimas

```env
OPENAI_API_KEY=sk-proj-...
OPENAI_TEXT_MODEL=gpt-6-luna
OPENAI_TRANSCRIBE_MODEL=gpt-transcribe
ENTITY_EXTRACTOR=openai
STT_PROVIDER=openai

PERSISTENCE_PROVIDER=firebase
FIREBASE_PROJECT_ID=smart-app-b807a
FIREBASE_STORAGE_BUCKET=smart-app-b807a.firebasestorage.app
FIRESTORE_EVENTS_COLLECTION=irrigation_events
FIRESTORE_USAGE_COLLECTION=openai_usage
FIREBASE_AUDIO_PREFIX=irrigation-audio
GOOGLE_APPLICATION_CREDENTIALS=/caminho/seguro/firebase-service-account.json

CORS_ORIGINS=https://SEU-FRONTEND.example
```

## Persistência

O fluxo oficial da V0.5 é:

```text
Browser IndexedDB -> fila offline temporária
Firebase Storage  -> áudio original permanente
Cloud Firestore   -> evento estruturado + transcrição + metadados do áudio
```

SQLite continua disponível somente como fallback de desenvolvimento:

```env
PERSISTENCE_PROVIDER=sqlite
```

## Áudio original

Em endpoints `process`, o backend salva o áudio antes de chamar a OpenAI. O caminho padrão é:

```text
irrigation-audio/YYYY/MM/<event-id>/original.<ext>
```

O objeto recebe SHA-256 e metadados de auditoria. O arquivo não é tornado público.

Os endpoints `preview` continuam sem persistência e não deixam áudio no Storage.

## Docker Compose

Coloque a credencial em:

```text
secrets/firebase-service-account.json
```

O `docker-compose.yml` monta o arquivo somente para leitura em `/run/secrets/firebase-service-account.json`.

## HTTPS

O microfone em implantação remota exige contexto seguro; publique o frontend em HTTPS. Firebase Hosting e Cloudflare Pages já fornecem HTTPS automaticamente.

## Firestore e Storage Rules

O frontend não precisa acessar Firestore nem Storage diretamente nesta versão. O FastAPI é a autoridade de escrita e usa Firebase Admin SDK. Isso permite manter as regras de cliente fechadas e centralizar validação no backend.
