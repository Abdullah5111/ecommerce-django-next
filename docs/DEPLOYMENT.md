# Deployment — Google Cloud Run

This deploys the backend and frontend as two Cloud Run services backed by a single Cloud SQL Postgres instance.

## Prerequisites

- `gcloud` CLI authenticated (`gcloud auth login`)
- A GCP project with billing enabled
- Roles required: `roles/run.admin`, `roles/cloudbuild.builds.editor`, `roles/cloudsql.admin`, `roles/artifactregistry.admin`, `roles/secretmanager.admin`

## 1. Set variables

```bash
export PROJECT_ID=your-project
export REGION=us-central1
export REPO=ecommerce
export SQL_INSTANCE=ecommerce-db
gcloud config set project $PROJECT_ID
```

## 2. Enable APIs

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com
```

## 3. Create Artifact Registry

```bash
gcloud artifacts repositories create $REPO \
  --repository-format=docker \
  --location=$REGION
```

## 4. Provision Cloud SQL (Postgres 16)

```bash
gcloud sql instances create $SQL_INSTANCE \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=$REGION

gcloud sql databases create ecommerce --instance=$SQL_INSTANCE
gcloud sql users create ecommerce --instance=$SQL_INSTANCE --password=$(openssl rand -base64 24 | tr -d '/+=')
```

Note the connection name: `PROJECT_ID:REGION:SQL_INSTANCE`.

## 5. Store secrets

```bash
echo -n "$(openssl rand -base64 48)" | gcloud secrets create django-secret --data-file=-
echo -n "your-db-password"            | gcloud secrets create db-password    --data-file=-
```

## 6. Deploy backend

The pipeline in [`backend/cloudbuild.yaml`](../backend/cloudbuild.yaml) builds the image and deploys to Cloud Run.

```bash
gcloud builds submit \
  --config backend/cloudbuild.yaml \
  --substitutions=_REGION=$REGION,_REPO=$REPO,_CLOUDSQL_INSTANCE=$PROJECT_ID:$REGION:$SQL_INSTANCE
```

After the first deploy, run migrations:

```bash
gcloud run services proxy ecommerce-backend --region $REGION &
# in another shell, run a one-off job — or simpler, exec into a Cloud Shell container with cloud-sql-proxy + psql
```

Or use a Cloud Run Job for one-off migrations (recommended for production).

## 7. Deploy frontend

```bash
gcloud builds submit frontend \
  --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/ecommerce-frontend

gcloud run deploy ecommerce-frontend \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/ecommerce-frontend \
  --region=$REGION \
  --allow-unauthenticated \
  --set-env-vars=NEXT_PUBLIC_API_URL=https://ecommerce-backend-XXXX.$REGION.run.app/api
```

Replace `XXXX` with the hash from the backend service URL.

## 8. Wire CORS

Update the backend env vars to allow the frontend origin:

```bash
gcloud run services update ecommerce-backend \
  --region=$REGION \
  --update-env-vars="CORS_ALLOWED_ORIGINS=https://ecommerce-frontend-XXXX.$REGION.run.app,ALLOWED_HOSTS=ecommerce-backend-XXXX.$REGION.run.app"
```

## Costs (rough)

- Cloud Run: free tier covers small demos
- Cloud SQL db-f1-micro: ~$8/mo
- Artifact Registry storage: pennies
