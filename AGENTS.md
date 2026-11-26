# AutoData agent instructions

Work on the user-visible Workshop path directly. Routine changes do not need
agent plans, architecture records, Project updates, governance tests, or a
review chain. Use a short branch and pull request, and merge after relevant
product checks pass. Keep credentials and licensed source content out of Git.

For API changes, run focused Go checks and use remote CI. For UI changes, run
the client checks and verify the browser path on an available deployment. Do
not start local Docker test stacks for routine work. Test authentication,
grants, and payment behavior when a change touches them; use Stripe TEST for
payment checks. Report what the user can do and what remains unverified.

Use the running `autodata-api.service` release path for authorized Workshop
publishing. Verify readiness and the user path after each release, and retain
the previous binary and service configuration for rollback. The autonomous
runner and its records are opt-in tools, not routine development gates.
