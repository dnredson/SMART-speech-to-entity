# V0.5 — Firebase persistence

A V0.5 usa o projeto `smart-app-b807a` como persistência oficial do piloto.

## Recursos

- Firestore: `irrigation_events`
- Uso OpenAI: `openai_usage`
- Storage bucket: `smart-app-b807a.firebasestorage.app`
- Prefixo de áudio: `irrigation-audio/`

## Fluxo

```text
Browser / IndexedDB
  -> FastAPI
  -> salva áudio original no Firebase Storage
  -> cria registro PROCESSING no Firestore
  -> OpenAI STT
  -> OpenAI Structured Output
  -> SMART validator
  -> atualiza Firestore para REGISTERED / NEEDS_REVIEW
```

Se o processamento falhar depois do upload, o áudio original permanece armazenado e o documento é marcado como erro para auditoria.

## Organização dos áudios

```text
irrigation-audio/YYYY/MM/<event-id>/original.<ext>
```

Cada objeto guarda também SHA-256, `event_id`, `recorded_at` e o nome original quando disponível.

## Credencial local

O arquivo JSON privado não deve ser versionado. Guarde-o em `secrets/firebase-service-account.json` e configure `GOOGLE_APPLICATION_CREDENTIALS` no `.env` local. A pasta `secrets/` e arquivos de service account estão no `.gitignore`.

## Preview

Endpoints de preview continuam sem persistência. Somente endpoints `process` representam registros oficiais e armazenam o áudio.

## Fallback

Para desenvolvimento sem Firebase:

```env
PERSISTENCE_PROVIDER=sqlite
```

Nesse modo o histórico usa SQLite local.
