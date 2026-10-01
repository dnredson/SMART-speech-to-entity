# SMART Irrigação — V0.5

Piloto web/PWA para registrar irrigação e fertirrigação por voz. O fluxo principal foi desenhado para reduzir ao mínimo o trabalho em campo: o agrônomo pode falar setor, operação, horário, duração e insumos em uma única gravação.

Stack principal:

- React + TypeScript + Vite/PWA;
- Python 3.12 + FastAPI;
- OpenAI para speech-to-text e extração estruturada;
- Cloud Firestore para eventos/histórico;
- Firebase Storage para preservar os áudios originais;
- IndexedDB para fila offline no navegador.

## Fluxo

```text
Agrônomo fala
   ↓
IndexedDB local
   ↓ quando online
FastAPI
   ↓
Firebase Storage       <- áudio original + SHA-256
   ↓
Firestore PROCESSING   <- vínculo criado antes da IA
   ↓
OpenAI transcription
   ↓
OpenAI Structured Output
   ↓
SMART validator
   ↓
Firestore REGISTERED / NEEDS_REVIEW
```

Exemplo:

> Hoje irriguei o setor 7 às 21 horas durante duas horas.

Resultado esperado:

```json
{
  "sector_id": 7,
  "operation_type": "IRRIGATION",
  "start_time": "21:00",
  "duration_minutes": 120
}
```

Também existe um fluxo guiado de fallback para selecionar manualmente setor e operação.

## V0.5

A V0.5 muda a persistência oficial do piloto:

- Firestore substitui SQLite como banco principal;
- Firebase Storage guarda o áudio original de cada registro por voz;
- cada áudio recebe SHA-256 e metadados de auditoria;
- áudio é salvo antes da transcrição;
- se STT/extração falharem, o áudio permanece preservado e o documento fica marcado como erro;
- `irrigation_events` guarda o histórico operacional;
- `openai_usage` guarda o contador/telemetria de chamadas OpenAI;
- SQLite continua disponível apenas com `PERSISTENCE_PROVIDER=sqlite`.

Projeto Firebase configurado:

```text
Project ID: smart-app-b807a
Storage bucket: smart-app-b807a.firebasestorage.app
Firestore events: irrigation_events
Storage prefix: irrigation-audio/
```

## Segurança das credenciais

Nunca versione:

- chave OpenAI real;
- JSON real da Firebase service account;
- `.env` local.

O repositório já ignora `secrets/`, arquivos de service account e `.env`.

Estrutura local recomendada:

```text
SMART-speech-to-entity/
├── secrets/
│   └── firebase-service-account.json
├── apps/
└── ...
```

## 1. Configurar o backend

```powershell
cd apps\irrigation-api
Copy-Item .env.example .env
notepad .env
```

O `.env.example` já traz os IDs públicos do Firebase. Preencha somente as credenciais locais:

```env
OPENAI_API_KEY=sk-proj-SUA_CHAVE
GOOGLE_APPLICATION_CREDENTIALS=../../secrets/firebase-service-account.json
```

Configuração Firebase esperada:

```env
PERSISTENCE_PROVIDER=firebase
FIREBASE_PROJECT_ID=smart-app-b807a
FIREBASE_STORAGE_BUCKET=smart-app-b807a.firebasestorage.app
FIRESTORE_EVENTS_COLLECTION=irrigation_events
FIRESTORE_USAGE_COLLECTION=openai_usage
FIREBASE_AUDIO_PREFIX=irrigation-audio
```

## 2. Instalar a API

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

A resposta deve indicar:

```json
{
  "version": "0.5.0",
  "openai_configured": true,
  "persistence": {
    "provider": "firebase",
    "configured": true,
    "project_id": "smart-app-b807a",
    "storage_bucket": "smart-app-b807a.firebasestorage.app",
    "events_collection": "irrigation_events"
  }
}
```

Swagger:

```text
http://localhost:8030/api/docs
```

## 4. Frontend

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

Fluxo principal:

1. toque em **Toque para falar**;
2. diga setor, operação, horário e duração;
3. em fertirrigação, inclua produto, kg/ha e litros de solução;
4. finalize a gravação;
5. o app salva localmente antes de tentar sincronizar.

## 5. Histórico

A aba **Histórico** consulta o Firestore através do FastAPI e permite:

- visualizar os registros dos sete setores;
- filtrar por setor;
- filtrar por irrigação/fertirrigação;
- ver horário e duração;
- ver produtos e quantidades;
- consultar a transcrição original;
- identificar registros que precisam de revisão.

## 6. Áudio original

Somente endpoints `process` persistem áudio. `preview` permanece descartável.

Caminho padrão:

```text
irrigation-audio/YYYY/MM/<event-id>/original.<ext>
```

No Firestore, o evento guarda:

```json
{
  "audio": {
    "storage_path": "irrigation-audio/2026/10/<event-id>/original.webm",
    "bucket": "smart-app-b807a.firebasestorage.app",
    "mime_type": "audio/webm",
    "size_bytes": 123456,
    "sha256": "..."
  }
}
```

O áudio não é tornado público.

## 7. Firestore

Não é necessário criar `irrigation_events` ou `openai_usage` manualmente. O backend cria documentos na primeira utilização.

O frontend não grava diretamente no Firestore. A autoridade permanece no FastAPI/SMART validator.

## 8. Offline-first

```text
sem internet
   ↓
IndexedDB guarda a gravação
   ↓
internet volta
   ↓
FastAPI recebe
   ↓
Storage + Firestore
```

## 9. Docker Compose

Coloque o JSON real em:

```text
secrets/firebase-service-account.json
```

Depois copie a configuração:

```powershell
Copy-Item .env.example .env
```

E suba:

```powershell
docker compose up --build
```

O Compose monta a credencial somente para leitura em `/run/secrets/firebase-service-account.json`.

## 10. Fallback SQLite

Para desenvolvimento sem Firebase:

```env
PERSISTENCE_PROVIDER=sqlite
```

Nesse modo os eventos ficam no SQLite local e o áudio não é enviado ao Firebase Storage.

## 11. Testes

```powershell
pytest
```

Casos relevantes incluem:

- irrigação sem exigir produto;
- fertirrigação exigindo as quantidades;
- múltiplos produtos;
- setor e tipo de operação extraídos da fala;
- validação determinística do SMART após a interpretação da IA.

## Documentação

- `ARCHITECTURE.md` — arquitetura geral;
- `docs/V0.4.md` — registro totalmente por voz e histórico;
- `docs/firebase-migration-plan.md` — desenho da persistência Firebase V0.5;
- `docs/HOSTING.md` — implantação.

## Screenshots

Capturas reais da V0.5 serão adicionadas em `docs/screenshots/` após a validação no navegador/servidor. A ideia é manter no README apenas screenshots reais da interface, não mockups.
