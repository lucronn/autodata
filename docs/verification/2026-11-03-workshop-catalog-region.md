# Exact configuration region: verified discovery correction

Implementation `2d1b6a89a1c1282c0462c97556b983726df08c39`, integrated at
`924fdc447cb2b91b85d4633b077cb8b5b3da76db`.
Issue: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8

The bank selector now uses the selected configuration's identity-base region,
matching commerce and paid authorization. Vehicle-only discovery and approved
provider mappings retain their behavior. Normal identity ingestion already
aligns these regions; this corrects the database-valid differing-region case
without alleging existing production corruption.

The [two-file plan](../superpowers/plans/2026-11-03-workshop-catalog-region.md)
and Issue/Project update were saved and read back before implementation. The
machine preflight at `8649659f87dc6a6ed2a682a1e84e07b70df80a2f` returned
`status: synchronized`, `errors: []`.

Actual isolated PostgreSQL and loopback connector evidence:

- Before the correction, US passed and CA failed because the observed bank
  selector sent US. Retained run `/tmp/autodata-region-red-61006165a0`, result
  SHA256 `a147d897fe294f2c0d74f376f15dd56eb65d6d2bbab1ad3e7edc4150ac86b742`,
  JUnit SHA256 `0540c291c31e3161f1366fb6b280c55e09d7f58babddb9e4a1df1be339a633a2`.
- After the correction, all13 coverage cases passed, with no skips, including
  US/CA selectors observed independently by both banks, ambiguity, partial and
  unconfigured coverage, exact configuration membership and approved mappings.
  Retained run `/tmp/autodata-region-green-eb7d1cd907`, result SHA256
  `d5ca185654c2a796302875dcbd9de4930a394a158af36cb06a1c09595edfbd5a`, JUnit
  SHA256 `bc1ed6056b76bdb878863784d83c8bd50dc6b4aa8db32c539dc377067e7bf742`.
- Both runs removed all owned containers, network and volume. Their two input
  hashes bind the red production file to the gated base and the green files to
  the exact implementation commit. An earlier artifact-permission harness
  failure remains preserved at `/tmp/autodata-region-red-59ef64a21b` and is not
  counted as the regression proof.

Independent review found no blocker and checked raw JUnit and input hashes:
`/tmp/autodata-region-2d1b6a8-independent-review.md`, SHA256
`c6ccdf76c831b6b7da8e021c2cb9c23e1de159f698a1fe050d2f071f69540456`.
The runtime used immutable PG and test image IDs, an internal owned network,
fixture-only credentials and a read-only source mount. No live bank, model,
customer database or cloud deployment was involved.

This verifies the bounded region correction. The paid12 and browser141
inventories, final integrated CI, configured staging and production release
remain separately required.
