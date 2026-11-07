# Shared gcloud flags for the backend service and its jobs, sourced by the
# steps in backend/cloudbuild.yaml. Reads REGION, IMAGE, CLOUDSQL_INSTANCE,
# REDIS_URL, REDIS_URL_SECRET, VPC_CONNECTOR, EXTRA_ENV and EXTRA_SECRETS from
# the build environment. REDIS_URL_SECRET names a Secret Manager secret holding
# the whole URL, for a Memorystore AUTH string that mustn't sit in a plain env
# var; set it or REDIS_URL, not both.
# --set-env-vars/--set-secrets replace what the service had, so every setting
# belongs in these values, not in ad-hoc `services update` calls.

if [ -n "${REDIS_URL}" ] && [ -n "${REDIS_URL_SECRET}" ]; then
  echo "Set _REDIS_URL or _REDIS_URL_SECRET, not both." >&2
  false  # the sourcing step runs with set -e, so this stops the build
fi

env_vars="DB_ENGINE=postgres,DB_HOST=/cloudsql/${CLOUDSQL_INSTANCE}"
if [ -n "${REDIS_URL}" ]; then
  env_vars="${env_vars},REDIS_URL=${REDIS_URL}"
fi
if [ -n "${EXTRA_ENV}" ]; then
  env_vars="${env_vars},${EXTRA_ENV}"
fi

secrets="SECRET_KEY=django-secret:latest,DB_PASSWORD=db-password:latest"
if [ -n "${REDIS_URL_SECRET}" ]; then
  secrets="${secrets},REDIS_URL=${REDIS_URL_SECRET}:latest"
fi
if [ -n "${EXTRA_SECRETS}" ]; then
  secrets="${secrets},${EXTRA_SECRETS}"
fi

# Service and jobs run the same image with the same config.
COMMON_FLAGS=(
  --image="${IMAGE}"
  --region="${REGION}"
  --set-env-vars="${env_vars}"
  --set-secrets="${secrets}"
)
if [ -n "${VPC_CONNECTOR}" ]; then
  COMMON_FLAGS+=(--vpc-connector="${VPC_CONNECTOR}")
fi

SERVICE_FLAGS=(
  "${COMMON_FLAGS[@]}"
  --platform=managed
  --allow-unauthenticated
  --add-cloudsql-instances="${CLOUDSQL_INSTANCE}"
)
# Without Redis each instance keeps its own rate limits, phone codes and
# WebSocket groups, so stay on one instance until REDIS_URL is set.
if [ -z "${REDIS_URL}" ] && [ -z "${REDIS_URL_SECRET}" ]; then
  SERVICE_FLAGS+=(--max-instances=1)
fi

JOB_FLAGS=(
  "${COMMON_FLAGS[@]}"
  --set-cloudsql-instances="${CLOUDSQL_INSTANCE}"
  --max-retries=1
)
