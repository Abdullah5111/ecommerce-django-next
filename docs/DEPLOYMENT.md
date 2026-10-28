# Deployment — Google Cloud Run

This deploys the backend and frontend as two Cloud Run services backed by a single Cloud SQL Postgres instance. The backend serves via daphne (ASGI), which the realtime WebSocket channel requires — Cloud Run supports WebSocket sessions natively.

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
  secretmanager.googleapis.com \
  cloudscheduler.googleapis.com
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
and use its signing secret for `STRIPE_WEBHOOK_SECRET`. Subscribe it to
`payment_intent.succeeded`, `charge.refunded`, `charge.dispute.created` and
`charge.dispute.closed`.

**Web Push (optional).** Leave unset and in-app notifications + emails still work;
the browser-push subscribe UI just hides. To enable it, generate a VAPID keypair
(`python -m py_vapid --gen`) and expose `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`,
and `VAPID_ADMIN_EMAIL` to the backend (store the private key as a secret):

```bash
echo -n "<vapid-private-key>" | gcloud secrets create vapid-private-key --data-file=-
# public key + admin email are not sensitive; pass them as plain env vars
```

**SMS for phone verification (optional).** Without a provider, the profile
page's "verify phone" step returns 503; nothing else depends on it. To send real
codes with Twilio, set `SMS_BACKEND=twilio` and expose `TWILIO_ACCOUNT_SID`,
`TWILIO_AUTH_TOKEN` (store it as a secret) and either `TWILIO_FROM_NUMBER` or
`TWILIO_MESSAGING_SERVICE_SID`:

```bash
echo -n "<twilio-auth-token>" | gcloud secrets create twilio-auth-token --data-file=-
```

Never set `SMS_BACKEND=console` in production — it writes codes to the logs.

**Google sign-in (optional).** Leave unset and the Google button hides. To enable
it, create an OAuth 2.0 Client ID (Web application) in the Google Cloud console,
add the deployed frontend origin to *Authorized JavaScript origins*, and pass the
client ID to the backend as `GOOGLE_OAUTH_CLIENT_ID` (not sensitive — a plain env
var). The frontend reads it from `/api/auth/google/config/`, so no frontend env
is needed.

**Redis (required for more than one instance).** Set `REDIS_URL` (e.g. a
Memorystore instance reached over a VPC connector) and the backend uses it for the
cache — rate limits and phone sign-in codes — and the WebSocket channel layer.
Without it each instance keeps its own: limits are per instance, a code sent from
one instance fails verification on another, and live updates don't cross
instances. A single instance works without it, and the deploy pipeline caps the
service at one (`--max-instances=1`) until `_REDIS_URL` is set (step 6).

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

[`backend/cloudbuild.yaml`](../backend/cloudbuild.yaml) builds the image, **runs
migrations** as a Cloud Run Job (`ecommerce-migrate`, before the new code takes
traffic; a failed migration stops the deploy), deploys the API service, and
deploys the scheduled-task jobs below. Run it from the repo root:

```bash
# ^##^ switches the substitution separator to ##, so the comma-separated lists
# inside _EXTRA_ENV / _EXTRA_SECRETS survive.
gcloud builds submit \
  --config backend/cloudbuild.yaml \
  --substitutions="^##^_REGION=$REGION##_REPO=$REPO##_CLOUDSQL_INSTANCE=$PROJECT_ID:$REGION:$SQL_INSTANCE\
##_EXTRA_ENV=ALLOWED_HOSTS=<backend-host>,STRIPE_PUBLISHABLE_KEY=pk_test_...\
##_EXTRA_SECRETS=STRIPE_SECRET_KEY=stripe-secret-key:latest,STRIPE_WEBHOOK_SECRET=stripe-webhook-secret:latest"
```

Every deploy **replaces** the service's env vars and secrets with what the build
passes, so all configuration goes in `_EXTRA_ENV` (comma-separated `KEY=VALUE`)
and `_EXTRA_SECRETS` (`ENV=secret:version`). Settings added later with
`gcloud run services update` are dropped by the next deploy. A single value that
contains commas (e.g. two CORS origins) needs gcloud's
[alternate delimiter](https://cloud.google.com/sdk/gcloud/reference/topic/escaping)
inside `--set-env-vars` too.

**Redis.** Without `_REDIS_URL` the service is capped at one instance (rate
limits, phone codes and WebSocket groups are per instance). To scale out, create
a Memorystore instance and a Serverless VPC Access connector, then add
`_REDIS_URL=redis://<memorystore-ip>:6379/0,_VPC_CONNECTOR=<connector-name>`.

### Scheduled tasks

Locally, Celery Beat runs the periodic tasks. Cloud Run has no Beat (and no
RabbitMQ — without a broker, tasks such as email run inline in the request), so
the build deploys each periodic task as a Cloud Run Job running its management
command. Trigger them with Cloud Scheduler once:

```bash
SA=$(gcloud iam service-accounts list --filter="displayName:Compute Engine default" --format='value(email)')
for job in "release-expired-orders */5 * * * *" \
           "retry-pending-refunds */5 * * * *" \
           "prune-stripe-events 0 3 * * *"; do
  set -- $job; name=$1; shift
  gcloud scheduler jobs create http "ecommerce-$name" \
    --location=$REGION --schedule="$*" --http-method=POST \
    --uri="https://run.googleapis.com/v2/projects/$PROJECT_ID/locations/$REGION/jobs/ecommerce-$name:run" \
    --oauth-service-account-email="$SA"
done
```

| Job | Schedule | Why |
|-----|----------|-----|
| `ecommerce-release-expired-orders` | every 5 min | returns stock held by unpaid orders |
| `ecommerce-retry-pending-refunds` | every 5 min | finishes refunds whose Stripe call failed |
| `ecommerce-prune-stripe-events` | daily | trims the webhook de-duplication table |

## 7. Deploy frontend

`NEXT_PUBLIC_API_URL` is compiled into the browser bundle, so it is a **build
argument** — setting it on the running service has no effect.
[`frontend/cloudbuild.yaml`](../frontend/cloudbuild.yaml) passes it to the
Docker build and also sets `INTERNAL_API_URL` for server-side rendering:

```bash
gcloud builds submit \
  --config frontend/cloudbuild.yaml \
  --substitutions=_REGION=$REGION,_REPO=$REPO,_API_URL=https://<backend-host>/api
```

## 8. Wire CORS

Once both URLs exist, redeploy the backend (step 6) with the frontend origin in
`_EXTRA_ENV`: `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` and `FRONTEND_URL`
set to `https://<frontend-host>`, and `ALLOWED_HOSTS` to the backend host.

**Sign-in cookie.** The refresh token is an httpOnly cookie the API sets for
the storefront, so the two must be able to share it:

- **Recommended:** map custom domains on one site (`shop.example.com` and
  `api.example.com`, via Cloud Run domain mappings or a load balancer). The
  default `AUTH_COOKIE_SAMESITE=Lax` then just works.
- **Two `*.run.app` URLs:** each is its own site (`run.app` is a public
  suffix), so the cookie is third-party. Add `AUTH_COOKIE_SAMESITE=None` to
  `_EXTRA_ENV`; browsers that block third-party cookies (Safari by default)
  will still drop it, and those users are signed out on every page load.

## Costs (rough)

- Cloud Run: free tier covers small demos
- Cloud SQL db-f1-micro: ~$8/mo
- Artifact Registry storage: pennies
