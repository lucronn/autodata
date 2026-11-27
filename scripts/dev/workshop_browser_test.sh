#!/bin/sh
# Run the real Workshop API and browser against local identity and payment fixtures.
set -eu

engine=${1:-all}
case "$engine" in
    all|chromium|firefox|webkit|simulation) ;;
    *) echo "Usage: $0 [all|chromium|firefox|webkit|simulation]" >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then
    echo "Usage: $0 [all|chromium|firefox|webkit|simulation]" >&2
    exit 2
fi

root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$root"

export AUTODATA_R3_CANDIDATE_SHA="$(git rev-parse HEAD)"
export AUTODATA_API21_SOURCE_TREE="$(git rev-parse HEAD^{tree})"

# A prebuilt browser-runtime image can be reused by CI or a local Docker host.
if [ -n "${AUTODATA_WORKSHOP_BROWSER_IMAGE:-}" ]; then
    export AUTODATA_R3_TEST_IMAGE="$AUTODATA_WORKSHOP_BROWSER_IMAGE"
else
    export AUTODATA_R3_TEST_IMAGE=autodata-workshop-browser:local
    docker build --target browser-runtime --tag "$AUTODATA_R3_TEST_IMAGE" \
        --file infra/compose/article-lifecycle-test.Dockerfile .
fi

umask 077
work=$(mktemp -d "${TMPDIR:-/tmp}/autodata-workshop-browser.XXXXXXXX")
export AUTODATA_LIFECYCLE_ARTIFACT_DIR="$(cd "$work" && pwd -P)"
suffix=$(printf '%s' "${work##*.}" | tr '[:upper:]' '[:lower:]')
project="autodata-workshop-browser-$suffix"

compose() {
    docker compose --env-file /dev/null --project-name "$project" \
        -f infra/compose/compose.article-lifecycle-test.yaml \
        -f infra/compose/compose.workshop-browser-test.yaml "$@"
}
cleanup() {
    status=$?
    trap - EXIT
    if ! compose down --volumes; then
        echo "Could not remove disposable Compose project $project." >&2
        if [ "$status" -eq 0 ]; then status=1; fi
    fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf 'Workshop browser results: %s\n' "$AUTODATA_LIFECYCLE_ARTIFACT_DIR"
compose up -d --wait --wait-timeout 60 postgres minio

if [ "$engine" = simulation ]; then
    compose run --rm -T --no-deps --pull never --user "$(id -u):$(id -g)" \
        go-test-runner xvfb-run -a sh -ec '
            mkdir -p "$GOCACHE" "$GOTMPDIR"
            go -C apps/api-go test -c -o /tmp/workshop-simulation.test .
            AUTODATA_REQUIRE_WORKSHOP_SIMULATION_BROWSER=1 \
            AUTODATA_WORKSHOP_SIMULATION_GO_BINARY=/tmp/workshop-simulation.test \
                python -m pytest -v -p no:cacheprovider \
                    --junitxml=/artifacts/workshop-simulation-browser.xml \
                    scripts/dev/test_workshop_simulation_browser.py'
    exit
fi

set -- python -m pytest -v -p no:cacheprovider \
    --junitxml=/artifacts/workshop-browser-api.xml \
    workers/ingestion-python/tests/test_workshop_browser_integration.py
if [ "$engine" != all ]; then
    set -- "$@" -k "$engine"
fi
# Warm the Go cache before pytest starts its per-case fixture deadlines.
compose run --rm -T --no-deps --pull never --user "$(id -u):$(id -g)" go-test-runner \
    xvfb-run -a sh -ec 'mkdir -p "$GOCACHE" "$GOTMPDIR"
        go -C apps/api-go test -run "^$" .
        AUTODATA_REQUIRE_PUBLISHED_MEDIA_HTTP=1 python -m pytest -v -p no:cacheprovider \
            --junitxml=/artifacts/workshop-published-media-http.xml \
            workers/ingestion-python/tests/test_published_media_http.py
        exec "$@"' workshop-browser "$@"
