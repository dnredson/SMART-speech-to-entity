# SMART Irrigação V0.3 — arquitetura

## Objetivo

Entregar rapidamente ao agrônomo um registrador web/PWA de irrigação e fertirrigação compatível com a identidade e a stack do portal SMART.

## Fluxo

```text
React / TypeScript / Vite PWA
           │
           ├── operação selecionada explicitamente
           ├── setor 1–7 selecionado explicitamente
           ├── formulário manual
           └── MediaRecorder
                    │
                    ▼
              IndexedDB local
                    │
              quando online
                    ▼
                  FastAPI
                    │
       ┌────────────┴────────────┐
       │                         │
 gpt-transcribe             gpt-6-luna
 áudio → texto          Structured Outputs
       │                         │
       └──────── transcrição ────┘
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
                  SQLite
```

## Separação de autoridade

### Interface/usuário

É autoridade para:

- `sector_id`;
- `operation_type`.

Esses campos não são inferidos da fala.

### OpenAI

É usada para:

- transcrever áudio;
- interpretar data, hora, duração e produtos presentes na transcrição;
- produzir uma saída compatível com o schema estruturado.

Não decide se o registro está completo.

### SMART Validator

É autoridade para:

- validar setor 1–7;
- validar data/hora/duração;
- exigir campos conforme o tipo da operação;
- exigir nome/kg-ha/litros para cada produto em fertirrigação;
- construir `missing_fields`;
- definir `complete` e `REGISTERED/NEEDS_REVIEW`.

## Preview e persistência

```text
/transcript/preview   texto → entidade        sem persistir
/voice/preview        áudio → texto → entidade sem persistir
/transcript/process   texto → entidade        persiste
/voice/process        áudio → texto → entidade persiste
```

Os endpoints de preview são próprios para desenvolvimento e validação.

## Datas relativas e fuso horário

O frontend envia `recorded_at` com offset local, por exemplo:

```text
2026-09-30T20:30:00-03:00
```

Isso evita transformar "hoje" em amanhã quando a gravação ocorre à noite no Brasil e o JavaScript converte a data para UTC.

## Offline-first

O áudio é gravado e persistido no IndexedDB antes do envio. A falta de internet não impede o registro em campo; a sincronização acontece posteriormente.

## Limites

- máximo de 2 minutos por gravação no frontend;
- limite local de tamanho no backend;
- `OPENAI_MAX_CALLS_PER_MONTH`;
- hard spend limit configurado no projeto OpenAI;
- nenhuma repetição infinita de chamadas.

## Evolução prevista

- revisão assistida somente dos campos faltantes;
- catálogo real de nutrientes/produtos;
- metadados dos 7 setores;
- PostgreSQL na integração ao portal;
- autenticação e roles do portal;
- vazão nominal e medida;
- correlação temporal com sensores de solo e fluxo.
