## ADDED Requirements

### Requirement: ASP-040 — Versioned contract layout
A contract SHALL live in its provider repo, or in the product's platform repo when shared, as
`contracts/<name>/v<N>/` with exactly one of `schema.json` or `openapi.yaml`, at least one file in `examples/valid/`,
at least one in `examples/invalid/` for JSON Schema contracts, and a `README.md` naming the provider and consumers.
`ai-specs contract new <repo> <name> --kind jsonschema|openapi` SHALL create that layout for `v1`.

#### Scenario: New contract skeleton
- **GIVEN** an adopting repo without contracts
- **WHEN** `ai-specs contract new . greeting --kind jsonschema` runs
- **THEN** `contracts/greeting/v1/` contains `schema.json`, `examples/valid/example.json`, `examples/invalid/missing-required.json` and `README.md`
- **Proof:** `python3 -m unittest tests.test_contracts.NewTest` in ai-specs passes

### Requirement: ASP-041 — Conformance check
`ai-specs contract check <repo>` SHALL validate every JSON Schema contract's valid examples (all must pass) and invalid
examples (all must fail) with `ajv-cli@5.0.0`, and lint every OpenAPI contract with `@redocly/cli@1.34.5`, both run
through `npx`; it SHALL exit 1 on any mismatch, naming the file, and 2 when a validator cannot run.

#### Scenario: Invalid example that validates
- **GIVEN** a contract whose `examples/invalid/` contains a document that satisfies the schema
- **WHEN** `ai-specs contract check .` runs
- **THEN** it exits 1 naming that file as "invalid example accepted"
- **Proof:** `python3 -m unittest tests.test_contracts.CheckTest.test_invalid_example_that_passes_fails_the_check` in ai-specs passes

#### Scenario: Real validator on the skeleton
- **GIVEN** the skeleton created by `contract new`
- **WHEN** `ai-specs contract check .` runs with network access
- **THEN** it exits 0
- **Proof:** `bash scripts/e2e.sh` in ai-specs passes its "contract conformance" step

### Requirement: ASP-042 — Released versions are immutable
Once a contract version has been released (it exists on `production`), its folder SHALL NOT change; a breaking change
SHALL create the next version folder.

#### Scenario: Edit to a released contract
- **GIVEN** `contracts/greeting/v1/schema.json` present on `origin/production`
- **WHEN** a change branch edits that file and `ai-specs lint` runs
- **THEN** it exits 1 with "released contract greeting/v1 is immutable: create v2"
- **Proof:** `python3 -m unittest tests.test_contracts.ImmutableTest` in ai-specs passes
