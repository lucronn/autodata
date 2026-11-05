# Preserve the catalog image privacy assertion across gofmt

Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

Actual CI41691331286 atd0a8ace passed runtime, Go, contracts and Python worker
checks, then failed one of98 development tests. test_api_runtime.py requires
literal `StorageKey string` spacing. R3 added longer image field names and
gofmt aligned the struct; the field remains a string with the exact `json:"-"`
tag. Failure log: /tmp/autodata-ci-41691331286-failed.log.

Only implementation path: `scripts/dev/test_api_runtime.py`. Replace that one
literal assertion with a line-anchored regex permitting horizontal whitespace
between StorageKey, string and the exact JSON-exclusion tag. Keep the existing
test name, media-test checks, all other tests and application code unchanged.
Do not accept a public JSON tag, a different type/name, a missing field or a
commented-out declaration. No dependency, workflow or formatter change.

Concrete todo:

1. Synchronize Issue186/Project8 and canonical verification record, commit this
   checkpoint and pass exact-base preflight before editing the test.
2. Retain the existing failing command, implement the one assertion change,
   verify single/tab/multiple-space cases and reject public/missing/type/comment
   mutations. Run all development tests plus existing Go image-privacy tests.
3. Obtain independent exact-commit review, push and inspect actual full CI.
   Retain prior failed runs separately and do not claim overall CI until passed.

R5 also owns this runtime test file for later authentication assertions. The
identity builder has been told to leave this exact assertion alone; coordinator
integration preserves both changes. Sol6.1/medium/Fast remains required.
