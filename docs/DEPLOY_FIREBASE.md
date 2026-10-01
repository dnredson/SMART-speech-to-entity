# Deploy do SMART Irrigação

Arquitetura pública do piloto:

```text
https://smart-app-b807a.web.app
        |
        +-- frontend: Firebase Hosting
        |
        +-- /api/** -> Cloud Run (smart-irrigation-api, southamerica-east1)
                         |
                         +-- Firestore
                         +-- Firebase Storage
                         +-- Secret Manager (OPENAI_API_KEY)
```

## Pré-requisitos

- Firebase CLI instalada (`npm install -g firebase-tools`)
- Google Cloud CLI (`gcloud`) instalada
- projeto Google/Firebase: `smart-app-b807a`
- billing ativo (Blaze)

## 1. Login

```powershell
firebase login
gcloud auth login
gcloud config set project smart-app-b807a
```

## 2. Habilitar APIs

```powershell
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
```

## 3. Criar identidade do backend

```powershell
gcloud iam service-accounts create smart-irrigation-api --display-name="SMART Irrigation API"
$SA="smart-irrigation-api@smart-app-b807a.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding smart-app-b807a --member="serviceAccount:$SA" --role="roles/datastore.user"
gcloud projects add-iam-policy-binding smart-app-b807a --member="serviceAccount:$SA" --role="roles/storage.objectUser"
gcloud projects add-iam-policy-binding smart-app-b807a --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
```

## 4. Criar o Secret da OpenAI

Crie `openai-api-key` no Google Cloud Secret Manager e coloque como valor a chave real da OpenAI.

Não envie a chave para o Git e não coloque o JSON da service account no Cloud Run.

## 5. Deploy do backend

Na raiz do repositório:

```powershell
$SA="smart-irrigation-api@smart-app-b807a.iam.gserviceaccount.com"

gcloud run deploy smart-irrigation-api `
  --source apps/irrigation-api `
  --region southamerica-east1 `
  --allow-unauthenticated `
  --service-account $SA `
  --env-vars-file deploy/cloudrun-env.yaml `
  --set-secrets OPENAI_API_KEY=openai-api-key:latest
```

Ao terminar, o Cloud Run exibirá a URL do serviço. Teste `/api/health` nessa URL.

## 6. Build do frontend

```powershell
npm --prefix apps/web-ui install
npm --prefix apps/web-ui run build
```

## 7. Deploy do Firebase Hosting

```powershell
firebase use smart-app-b807a
firebase deploy --only hosting
```

O endereço final será:

```text
https://smart-app-b807a.web.app
```

O `firebase.json` envia `/api/**` para o serviço `smart-irrigation-api` no Cloud Run e todo o resto para a SPA React.

## 8. Testes pós-deploy

Abra:

```text
https://smart-app-b807a.web.app/api/health
```

Depois teste pelo site:

1. abrir `https://smart-app-b807a.web.app`;
2. permitir microfone;
3. gravar uma irrigação;
4. verificar o evento no Firestore;
5. verificar o áudio no Storage;
6. instalar a PWA no Android pela opção `Instalar app` / `Adicionar à tela inicial`.
