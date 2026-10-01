# SMART Irrigação — V0.3

Módulo independente para registro de irrigação/fertirrigação do projeto SMART, mantendo a stack do portal de referência: **React + TypeScript + Vite** no frontend e **Python 3.12 + FastAPI** no backend.

A V0.3 fecha a primeira versão do fluxo **speech-to-entity** com OpenAI e reforça a regra principal de autoridade: a IA interpreta linguagem; o backend SMART decide se o registro está completo.

## Pipeline

```text
Agrônomo escolhe operação + setor
              ↓
           Microfone
              ↓
       MediaRecorder / PWA
              ↓
        IndexedDB local
              ↓ internet
            FastAPI
              ↓
        gpt-transcribe
              ↓
          transcrição
              ↓
 gpt-6-luna + Structured Outputs
              ↓
      Pydantic + SMART validator
              ↓
 REGISTERED / NEEDS_REVIEW
              ↓
            SQLite
```

## Novidades da V0.3

- `sector_id` e `operation_type` agora aparecem também no resultado de preview;
- o setor **não é inferido pela IA**: vem da seleção explícita do usuário e é validado como 1–7;
- `missing_fields` e `complete` são determinados pelo backend, não pelo modelo;
- IRRIGATION exige data, hora e duração, mas nunca exige produto;
- FERTIGATION exige data, hora, duração e ao menos um produto;
- para cada produto de fertirrigação, o SMART exige:
  - nome;
  - kg/ha;
  - litros de solução;
- múltiplos produtos continuam suportados no speech-to-entity;
- novo `POST /api/v1/voice/preview`: transcreve + extrai entidades **sem gravar no banco**;
- `POST /api/v1/voice/process` continua sendo o fluxo real e salva o evento;
- o frontend mostra produto/quantidades e campos faltantes no histórico;
- o timestamp enviado pelo navegador agora preserva o **fuso horário local**, evitando que “hoje/ontem” mude de dia por causa de UTC à noite;
- formulário manual de fertirrigação também exige kg/ha e litros de solução;
- limite local padrão de 100 chamadas OpenAI/mês, além do hard spend limit configurado na plataforma.

## 1. Configurar `.env`

Entre na API:

```powershell
cd apps\irrigation-api
```

Crie o arquivo:

```powershell
Copy-Item .env.example .env
notepad .env
```

Preencha somente sua chave:

```env
OPENAI_API_KEY=sk-proj-SUA_CHAVE
```

Configuração padrão:

```env
OPENAI_TEXT_MODEL=gpt-6-luna
OPENAI_TRANSCRIBE_MODEL=gpt-transcribe
ENTITY_EXTRACTOR=openai
STT_PROVIDER=openai
OPENAI_MAX_CALLS_PER_MONTH=100
MAX_AUDIO_BYTES=20971520
MAX_TRANSCRIPT_CHARS=5000
```

Nunca coloque a chave no frontend, GitHub, Dockerfile ou imagem Docker.

## 2. Instalar a API

A V0.3 usa Python 3.12.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## 3. Subir a API

```powershell
uvicorn smart_irrigation.main:app --host 0.0.0.0 --port 8030 --reload
```

Health:

```text
http://localhost:8030/api/health
```

Esperado:

```json
{
  "status": "ok",
  "service": "smart-irrigation-api",
  "version": "0.3.0",
  "openai_configured": true,
  "entity_extractor": "openai",
  "stt_provider": "openai",
  "text_model": "gpt-6-luna",
  "transcribe_model": "gpt-transcribe"
}
```

Swagger:

```text
http://localhost:8030/api/docs
```

## 4. Testar texto → entidade

Use:

```text
POST /api/v1/transcript/preview
```

Exemplo:

```json
{
  "sector_id": 5,
  "operation_type": "FERTIGATION",
  "transcript": "Hoje comecei às oito e meia da manhã, irriguei por duas horas, com nitrato de cálcio, três quilos por hectare e vinte litros de solução.",
  "recorded_at": "2026-09-30T20:30:00-03:00"
}
```

Esperado:

```json
{
  "sector_id": 5,
  "operation_type": "FERTIGATION",
  "start_date": "2026-09-30",
  "start_time": "08:30",
  "duration_minutes": 120,
  "products": [
    {
      "name": "nitrato de cálcio",
      "kg_per_ha": 3,
      "solution_liters": 20
    }
  ],
  "missing_fields": [],
  "complete": true
}
```

### Exemplo incompleto

```text
Hoje às nove da manhã irriguei por uma hora com nitrato de cálcio.
```

Para `FERTIGATION`, o backend deve retornar algo equivalente a:

```json
{
  "sector_id": 5,
  "operation_type": "FERTIGATION",
  "start_date": "2026-09-30",
  "start_time": "09:00",
  "duration_minutes": 60,
  "products": [
    {
      "name": "nitrato de cálcio",
      "kg_per_ha": null,
      "solution_liters": null
    }
  ],
  "missing_fields": [
    "products[0].kg_per_ha",
    "products[0].solution_liters"
  ],
  "complete": false
}
```

## 5. Testar voz sem salvar

No Swagger use:

```text
POST /api/v1/voice/preview
```

Preencha:

```text
sector_id      5
operation_type FERTIGATION
recorded_at    2026-09-30T20:30:00-03:00
audio          selecione um .webm/.m4a/.mp3/.wav
```

Esse endpoint usa duas chamadas:

1. `gpt-transcribe` → áudio para texto;
2. `gpt-6-luna` → texto para entidade estruturada.

Ele **não salva o evento**. A resposta inclui `transcript`, `sector_id`, `operation_type` e todos os campos extraídos.

Exemplo esperado:

```json
{
  "sector_id": 5,
  "operation_type": "FERTIGATION",
  "transcript": "Hoje comecei às oito e meia...",
  "start_date": "2026-09-30",
  "start_time": "08:30",
  "duration_minutes": 120,
  "products": [
    {
      "name": "nitrato de cálcio",
      "kg_per_ha": 3,
      "solution_liters": 20
    }
  ],
  "missing_fields": [],
  "complete": true
}
```

## 6. Testar pelo frontend com microfone

Em outro terminal:

```powershell
cd apps\web-ui
npm install
npm run dev
```

Abra:

```text
http://localhost:8503
```

Fluxo:

1. escolha **Irrigação** ou **Fertirrigação**;
2. escolha o **Setor 01–07**;
3. deixe **Por voz** selecionado;
4. toque em **Toque para falar**;
5. fale normalmente;
6. toque novamente para finalizar.

Exemplo de fala:

> Hoje comecei às oito e meia da manhã, irriguei por duas horas, com nitrato de cálcio, três quilos por hectare e vinte litros de solução.

O áudio é salvo primeiro no IndexedDB. Se houver internet, o app envia para `/api/v1/voice/process`; se estiver offline, mantém a gravação na fila e tenta depois.

`localhost` pode acessar microfone em HTTP. Em implantação remota, use HTTPS.

## 7. Autoridade de validação

```text
Interface
  ├── sector_id
  └── operation_type

OpenAI
  ├── transcrição
  └── proposta de data/hora/duração/produtos

SMART backend
  ├── valida setor 1–7
  ├── valida campos obrigatórios
  ├── calcula missing_fields
  └── decide complete/status
```

A IA nunca decide o setor e nunca é autoridade final sobre completude.

### IRRIGATION

Obrigatório:

- setor;
- data;
- hora de início;
- duração.

### FERTIGATION

Obrigatório:

- setor;
- data;
- hora de início;
- duração;
- ao menos um produto;
- nome de cada produto;
- kg/ha de cada produto;
- litros de solução de cada produto.

## 8. Uso e custo

```text
GET /api/v1/usage
```

Uma gravação por voz normalmente consome duas chamadas OpenAI. O contador local é proteção adicional; o hard spend limit da conta/projeto OpenAI continua sendo o teto financeiro principal.

## 9. Modo legado

Para comparar com o parser por regras:

```env
ENTITY_EXTRACTOR=rules
```

Para transcrição local com faster-whisper:

```powershell
pip install -e ".[local-stt]"
```

```env
STT_PROVIDER=local
```

## 10. Testes locais

```powershell
pytest
```

Há regressões para o parser legado e para a validação SMART de irrigação/fertirrigação.

## Próximas etapas

1. testar voz real no Chrome/Android;
2. colher frases reais do agrônomo;
3. criar tela de revisão assistida dos campos faltantes;
4. cadastrar metadados dos 7 setores;
5. cadastrar catálogo de produtos/nutrientes;
6. integrar vazão nominal e sensor de fluxo;
7. migrar SQLite → PostgreSQL na integração ao portal principal.
