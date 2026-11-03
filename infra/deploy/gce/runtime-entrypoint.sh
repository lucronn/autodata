#!/bin/sh
# File-to-process-environment only. Secret values never enter Docker Config.Env.
# No tracing, eval, shell sourcing, caller-selected secret directory or fallback.
set +x
set -eu
PATH=/usr/local/bin:/usr/bin:/bin
LC_ALL=C
export PATH LC_ALL
umask 077
invalid() { printf '%s\n' 'runtime entrypoint: invalid configuration' >&2; exit 2; }
secret_failure() { printf '%s\n' 'runtime entrypoint: invalid secret files' >&2; exit 3; }
[ "$#" -gt 0 ] || invalid
# Preserve pre-existing development/CI image commands outside the hosted graph.
# Production and staging always require the explicit reviewed service identity.
if [ -z "${AUTODATA_RUNTIME_SERVICE+x}" ]; then
    case "${AUTODATA_ENV:-}" in production|staging) invalid ;; esac
    exec "$@"
fi
case "$AUTODATA_RUNTIME_SERVICE" in
    api) names='AUTODATA_POSTGRES_PASSWORD AUTODATA_S3_ACCESS_KEY AUTODATA_S3_SECRET_KEY AUTODATA_INGESTION_INTERNAL_TOKEN AUTODATA_IMAGE_URL_KEY' ;;
    ingestion-http) names='AUTODATA_POSTGRES_PASSWORD AUTODATA_S3_ACCESS_KEY AUTODATA_S3_SECRET_KEY AUTODATA_INGESTION_INTERNAL_TOKEN AUTODATA_STRIPE_SECRET_KEY AUTODATA_STRIPE_WEBHOOK_SECRET BANKONE_API_TOKEN BANKTWO_API_TOKEN' ;;
    article-worker) names='AUTODATA_POSTGRES_PASSWORD AUTODATA_S3_ACCESS_KEY AUTODATA_S3_SECRET_KEY BANKONE_API_TOKEN BANKTWO_API_TOKEN INCEPTION_API_KEY' ;;
    payment-reconciler) names='AUTODATA_POSTGRES_PASSWORD AUTODATA_INGESTION_INTERNAL_TOKEN AUTODATA_STRIPE_SECRET_KEY AUTODATA_STRIPE_WEBHOOK_SECRET' ;;
    migration) names='PGPASSWORD' ;;
    bootstrap) names='AUTODATA_S3_ACCESS_KEY AUTODATA_S3_SECRET_KEY' ;;
    metrics-probe) names='AUTODATA_POSTGRES_PASSWORD NATS_METRICS_USER NATS_METRICS_PASSWORD' ;;
    *) invalid ;;
esac
# Check names, never values. Reject even empty ambient credentials rather than
# silently retaining aliases or accidentally assigning another role's authority.
for ambient in $(/usr/bin/env | /usr/bin/sed -n 's/=.*//p'); do
    case "$ambient" in
        AUTODATA_POSTGRES_PASSWORD|AUTODATA_S3_ACCESS_KEY|AUTODATA_S3_SECRET_KEY|AUTODATA_INGESTION_INTERNAL_TOKEN|AUTODATA_IMAGE_URL_KEY|AUTODATA_STRIPE_SECRET_KEY|AUTODATA_STRIPE_WEBHOOK_SECRET|BANKONE_API_TOKEN|BANKTWO_API_TOKEN|INCEPTION_API_KEY|PGPASSWORD|POSTGRES_PASSWORD|NATS_METRICS_USER|NATS_METRICS_PASSWORD|S3_WORKER_ACCESS_KEY|S3_WORKER_SECRET_KEY|S3_API_ACCESS_KEY|S3_API_SECRET_KEY|AUTODATA_BANKONE_API_KEY|AUTODATA_BANKTWO_API_KEY|GOOGLE_*|GCLOUD_*|CLOUDSDK_*|GCE_METADATA_*|AWS_*|AZURE_*|FIREBASE_AUTH_EMULATOR_HOST|AUTODATA_READINESS_MODE|AUTODATA_AUTH_EMULATOR*|AUTODATA_FIXTURE*|LD_*|BASH_ENV|ENV) invalid ;;
    esac
done
secret_root=/run/autodata
secret_dir=$secret_root/$AUTODATA_RUNTIME_SERVICE
# All hosted wrapper users are UID/GID1000. Directory is readable/traversable
# only by that identity; delivered files are read-only and cannot be hardlinks.
[ "$(/usr/bin/id -u)" = 1000 ] && [ "$(/usr/bin/id -g)" = 1000 ] || secret_failure
[ ! -L "$secret_root" ] && [ -d "$secret_root" ] || secret_failure
[ ! -L "$secret_dir" ] && [ -d "$secret_dir" ] || secret_failure
[ "$(/usr/bin/stat -c '%u:%g:%a' -- "$secret_dir" 2>/dev/null)" = 1000:1000:500 ] || secret_failure
count=0
for path in "$secret_dir"/* "$secret_dir"/.[!.]* "$secret_dir"/..?*; do
    [ -e "$path" ] || [ -L "$path" ] || continue
    name=${path##*/}
    case " $names " in *" $name "*) ;; *) secret_failure ;; esac
    [ ! -L "$path" ] && [ -f "$path" ] || secret_failure
    [ "$(/usr/bin/stat -c '%u:%g:%a:%h' -- "$path" 2>/dev/null)" = 1000:1000:400:1 ] || secret_failure
    count=$((count + 1))
done
set -f
expected=0
for name in $names; do
    expected=$((expected + 1))
    path=$secret_dir/$name
    [ ! -L "$path" ] && [ -f "$path" ] || secret_failure
    identity=$(/usr/bin/stat -c '%d:%i:%u:%g:%a:%h:%s' -- "$path" 2>/dev/null) || secret_failure
    case "$identity" in *:1000:1000:400:1:*) ;; *) secret_failure ;; esac
    # Pin the opened inode and validate its metadata before reading its bytes.
    exec 3< "$path"
    [ "$(/usr/bin/stat -L -c '%d:%i:%u:%g:%a:%h:%s' -- "/proc/$$/fd/3" 2>/dev/null)" = "$identity" ] || secret_failure
    size=${identity##*:}
    [ "$size" -ge 1 ] && [ "$size" -le 16384 ] || secret_failure
    # A sentinel preserves trailing newlines. C-locale byte count rejects NUL
    # stripping by shells before any value can be exported.
    value=$(/usr/bin/cat <&3; printf '.')
    exec 3<&-
    value=${value%.}
    [ "${#value}" -eq "$size" ] || secret_failure
    cr=$(printf '\r')
    case "$value" in *'
'*|*"$cr"*) secret_failure ;; esac
    export "$name=$value"
done
[ "$count" -eq "$expected" ] || secret_failure
unset value cr names name path identity size ambient secret_dir secret_root count expected
exec "$@"
