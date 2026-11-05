# Task55 Autonomous Verification timeout — draft verification contract

Goal: Restore complete Autonomous Verification for the expanded developer suite by raising only the autonomy-policy job timeout from 20 to 30 minutes, preserving every check, smoke and release block.

Issue https://github.com/lucronn/autodata/issues/186; Project https://github.com/users/lucronn/projects/8. The synchronized gate and exact dispatch must precede any workflow edit.

Required red/green: before change assert exact single `autonomy-policy` timeout20 in the pinned 15003-byte workflow; after change assert timeout30 and exact reconstructed expected bytes from a one-time replacement. Verify only `.github/workflows/autonomous-verification.yml` changes, exactly one line, no job/step/trigger/permission/DTO/R3/script/content mutation, `git diff --check`, repository-governance checks, and YAML parse/workflow structure if tooling is available without installation. Preserve all evidence outside repo.

Fresh CI must include source-push and actual PR checkout identity/tree, all three jobs terminal SUCCESS, every required policy and live Compose step terminal SUCCESS, relevant test counts and DTO synthetic artifact identity. A cancellation or Vercel failure remains explicit. This CI result alone grants no real API/browser/provider/merchant/payment/host/staging/DNS/deploy/release authority or acceptance case credit.

Tracking synchronized at 2026-11-05T04:07:10Z: https://github.com/lucronn/autodata/issues/186#issuecomment-6649400966; Project8 current index points there. Checkpoint/dual preflight/review/dispatch still pending.
