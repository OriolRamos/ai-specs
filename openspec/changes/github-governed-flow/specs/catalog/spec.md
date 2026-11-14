## Purpose

Maps a multi-repo product (modules, capabilities, interfaces, data) so the impact of any change can be computed.

## ADDED Requirements

### Requirement: ASP-050 — Product platform repo and catalog
A product made of two or more repos that share a contract SHALL have a `<product>-platform` repo created with
`ai-specs init --platform`, holding `catalog/product.json` (modules, capabilities, interfaces, data), the shared
contracts, cross-repo ADRs in `docs/adr/`, and the product's epics as issues. `ai-specs catalog check <platform>` SHALL
exit 1 when an id is duplicated, a reference does not resolve, or a contract path does not exist.

#### Scenario: Dangling interface reference
- **GIVEN** a catalog with an interface whose provider is not a declared module
- **WHEN** `ai-specs catalog check .` runs
- **THEN** it exits 1 naming the interface and the unknown module
- **Proof:** `python3 -m unittest tests.test_catalog.CheckTest` in ai-specs passes

### Requirement: ASP-051 — Impact
`ai-specs impact <platform> <id>` SHALL print every capability, interface, data asset, module and spec path that
references the given id, grouped by kind; M and L proposals of a product with a catalog SHALL include that output in
their Change impact section.

#### Scenario: Impact of an interface
- **GIVEN** a catalog where interface `outfits-api-v1` is provided by `clothy-backend` and consumed by `clothy-frontend`
- **WHEN** `ai-specs impact . outfits-api-v1` runs
- **THEN** it prints the interface, its contract path, the provider and the consumer modules, and the capabilities that list either module
- **Proof:** `python3 -m unittest tests.test_catalog.ImpactTest` in ai-specs passes
