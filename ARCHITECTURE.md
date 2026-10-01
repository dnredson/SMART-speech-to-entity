# SMART Irrigação V0.5 — arquitetura

## Objetivo

Entregar ao agrônomo um registrador web/PWA de irrigação e fertirrigação com o menor atrito possível, preservando rastreabilidade do dado original.

## Fluxo principal

```text
React / TypeScript / Vite PWA
           │
           ├── registro rápido por voz
           │     └── setor + operação também podem vir da fala
           ├── fluxo guiado opcional
           └── MediaRecorder
                    │
                    ▼
              IndexedDB local
                    │
              quando online
                    ▼
                  FastAPI
                    │
          gera/recebe event_id
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
Firebase Storage          Firestore PROCESSING
áudio original + SHA-256       │
        │                       │
        └───────────┬───────────┘
                    ▼
             gpt-transcribe
                    │
                    ▼
                transcript
                    │
                    ▼
      gpt-6-luna / Structured Output
                    │
                    ▼
             Pydantic + SMART
                 Validator
                    │
       ┌────────────┴────────────┐
       │                         │
   REGISTERED               NEEDS_REVIEW
       │                         │
       └────────────┬────────────┘
                    ▼
                Firestore
```

Se STT ou extração falharem depois do upload, o áudio original permanece no Storage e o documento de processamento pode ser auditado.

## Separação de autoridade

### Usuário/interface

No fluxo guiado, setor e operação vêm da seleção explícita.

No fluxo rápido, a fala pode conter `sector_id` e `operation_type`. A IA só propõe esses valores quando estiverem claros; caso contrário retorna `null`.

### OpenAI

É usada para:

- transcrever áudio;
- interpretar setor/operação no modo rápido;
- interpretar data, hora, duração e produtos;
- produzir saída compatível com schema estruturado.

Não decide se o registro está completo.

### SMART Validator

É autoridade para:

- validar setor 1–7;
- validar data/hora/duração;
- exigir campos conforme o tipo da operação;
- exigir nome/kg-ha/litros para cada produto de fertirrigação;
- construir `missing_fields`;
- definir `complete` e status final.

## Persistência

### Firestore

Coleções oficiais:

```text
irrigation_events
openai_usage
```

`irrigation_events` contém evento estruturado, transcrição, referência ao áudio, status e metadados de processamento.

### Firebase Storage

Bucket:

```text
smart-app-b807a.firebasestorage.app
```

Estrutura:

```text
irrigation-audio/YYYY/MM/<event-id>/original.<ext>
```

O áudio é preservado em formato original e recebe SHA-256.

### IndexedDB

É somente fila offline do navegador. Depois de sincronizado e confirmado pelo backend, o item local é removido.

### SQLite

Continua disponível apenas como fallback explícito:

```env
PERSISTENCE_PROVIDER=sqlite
```

## Preview e persistência

```text
/transcript/preview       sem persistência
/voice/preview            sem persistência
/voice/quick/preview      sem persistência

/transcript/process       persiste entidade
/voice/process            persiste áudio + entidade
/voice/quick/process      persiste áudio + entidade
```

## Datas relativas e fuso horário

O frontend envia `recorded_at` com offset local, por exemplo:

```text
2026-10-01T07:30:00-03:00
```

Isso ancora expressões como "hoje", "ontem" e "anteontem" no horário real do usuário.

## Auditoria

Para cada registro por voz são preservados, quando disponíveis:

- áudio original;
- SHA-256 do áudio;
- transcrição;
- entidade extraída;
- modelo de transcrição;
- modelo de extração;
- timestamps de criação/processamento;
- status e campos faltantes.

## Limites

- máximo de 2 minutos por gravação no frontend;
- limite local de tamanho no backend;
- `OPENAI_MAX_CALLS_PER_MONTH`;
- hard spend limit configurado no projeto OpenAI;
- nenhuma repetição infinita de chamadas.

## Evolução prevista

- tela de revisão dos campos faltantes;
- catálogo real de nutrientes/produtos;
- metadados dos 7 setores;
- autenticação/roles do portal SMART;
- vazão nominal e medida;
- cálculo de volume e lâmina no backend determinístico;
- correlação temporal com sensores de solo e fluxo.
