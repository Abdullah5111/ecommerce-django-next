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

**Stripe (optional).** Leave these unset and checkout runs in mock mode — fine for
a demo. To take real (test-mode) card payments, store the keys and expose them to
the backend service as `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, and
`STRIPE_WEBHOOK_SECRET`:

```bash
echo -n "sk_test_..."   | gcloud secrets create stripe-secret-key     --data-file=-
echo -n "whsec_..."     | gcloud secrets create stripe-webhook-secret --data-file=-
# publishable key is not sensitive; pass it as a plain env var
```

Then point a Stripe webhook endpoint at `https://<backend-url>/api/payments/webhook/`
and use its signing secret for `STRIPE_WEBHOOK_SECRET`.

**Web Push (optional).** Leave unset and in-app notifications + emails still work;
the browser-push subscribe UI just hides. To enable it, generate a VAPID keypair
(`python -m py_vapid --gen`) and expose `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`,
and `VAPID_ADMIN_EMAIL` to the backend (store the private key as a secret):

```bash
echo -n "<vapid-private-key>" | gcloud secrets create vapid-private-key --data-file=-
# public key + admin email are not sensitive; pass them as plain env vars
```

**Google sign-in (optional).** Leave unset and the Google button hides. To enable
it, create an OAuth 2.0 Client ID (Web application) in the Google Cloud console,
add the deployed frontend origin to *Authorized JavaScript origins*, and pass the
client ID to the backend as `GOOGLE_OAUTH_CLIENT_ID` (not sensitive — a plain env
var). The frontend reads it from `/api/auth/google/config/`, so no frontend env
is needed.

**Media bucket (required for uploads).** Unlike the options above, this one is not
safe to skip: user uploads (profile avatars, review photos) go to local disk
without it, and **Cloud Run's filesystem is ephemeral and per-instance** — so
uploads disappear on the next redeploy and are invisible to other instances while
they last. Create a bucket and grant the runtime service account write access:

```bash
gcloud storage buckets create gs://$PROJECT_ID-media --location=$REGION
gcloud storage buckets add-iam-policy-binding gs://$PROJECT_ID-media \
  --member="serviceAccount:$(gcloud projects describe $PROJECT_ID \
      --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
  --role=roles/storage.objectAdmin
```

Then pass `GS_BUCKET_NAME=$PROJECT_ID-media` to the backend (a plain env var —
credentials come from the runtime service account, so there is no key to store).
Objects are written with a public-read ACL and stable, unguessable URLs.

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
