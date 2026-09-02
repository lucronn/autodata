# AutoData Domain Model

## Modeling principles

The model separates four kinds of data:

| Kind | Purpose | Mutation rule |
| --- | --- | --- |
| Canonical domain data | Normalized vehicle and repair knowledge used by all projections | Updated only through validated publication and revision history |
| Provenance data | Source snapshots, documents, extraction runs, evidence, model versions, and licenses | Append-only except for lifecycle/takedown state |
| Review data | Human feedback, review decisions, corrections, and quality findings | Mutable workflow records with audit trail |
| Purchaser projections | Entitlement-scoped, vehicle-specific materialized views | Immutable revisions; new enrichment creates a new revision |

All records use UUID identifiers, UTC timestamps, content hashes where applicable, and explicit source/revision references. Foreign keys must not be replaced with untraceable polymorphic strings where a typed relationship is possible.

## Vehicle identity and taxonomy

Canonical vehicle identity begins with `vehicles`, keyed by region/specification market, make, model, model year, trim, body style, drivetrain layout, and production dates. `vin_patterns` links WMI/VDS/VIS rules and assembly-plant metadata to a vehicle identity.

`canonical_taxonomy` contains standardized modules, sensors, fluids, systems, and other terms. `taxonomy_aliases` maps OEM and technician terminology such as ECU, PCM, or DME to a canonical term. Taxonomy changes are versioned because terminology affects extraction, search, and review.

## Powertrain and energy systems

Powertrain tables remain separate by architecture:

- `powertrain_ice`: engine code, displacement, cylinders, configuration, valvetrain, fuel delivery, and forced induction.
- `powertrain_hybrid`: the hybrid-specific relationship between combustion engine, battery, motor, inverter, operating mode, and charging behavior.
- `powertrain_ev`: battery chemistry/capacity, system voltage, motor layout, charging standard, and high-voltage metadata.

Vehicle-to-powertrain relationships must support more than one configuration when production variants or region-specific options require it. Safety-sensitive high-voltage and SRS information is tagged for restricted review and presentation.

## Diagnostics and repair knowledge

The diagnostics context contains:

- `dtcs`: code, vehicle applicability, module, description, set conditions, MIL behavior, and optional embedding.
- `freeze_frame_requirements`: required PIDs and expected ranges for a DTC.
- `symptoms`: normalized customer/technician symptoms and optional embeddings.
- `diagnostic_decision_nodes`: ordered test instructions with yes/no paths and resolution references.
- `tsbs`: source-backed bulletins with issue/correction summaries and optional embeddings.

The repair context contains:

- `repair_procedures`: vehicle-specific procedure identity, labor estimates, difficulty, and semantic representation.
- `procedure_prerequisites`: directed prerequisite relationships.
- `safety_warnings`: severity and text, including high-voltage and SRS/explosive warnings.
- `procedure_steps`: ordered instructions, torque/spec references, and media links.

Diagnostic recommendations must distinguish observed evidence, extracted guidance, and human-approved resolution. The platform must not represent a low-confidence extraction as a confirmed repair instruction.

## Specifications, fluids, and spatial information

- `specifications` stores nominal values, tolerances, units, categories, and optional sequence diagrams.
- `fluid_specifications` stores fluid system, standard, viscosity, dry-fill capacity, service-fill capacity, and units.
- `components` maps canonical components to a vehicle and optional coordinates, meshes, and location descriptions.

Units are stored in normalized form with the source unit retained in provenance. Conversion is explicit and reversible; displayed units are a presentation concern.

## Electrical and network topology

The electrical context keeps visual documents and logical topology separate:

- `wire_diagrams`: vehicle/subsystem diagrams, image URLs, and SVG overlays.
- `harnesses`: named harnesses and routing artifacts.
- `connectors`: connector identity, harness/component relationships, pin count, gender, and face-view media.
- `wire_pins`: pin number, colors, gauge, wire type, circuit description, and default voltage.
- `splices_and_grounds`: splice/ground identity, location, and coordinates.
- `network_topology`: protocol, baud rate, master module, and termination metadata.

Electrical facts must retain evidence to the original diagram or page and must be marked as image-derived, text-derived, or human-verified where relevant.

## Inventory, software, and maintenance

- `parts`, `part_supersessions`: OEM numbers, names, dimensions/weight, replacement lineage, reason, and effective date.
- `special_tools`: tool number, calibration requirement, image, and usage relationship.
- `software_flashes`: calibration transitions, component/TSB relationships, J2534 requirement, and procedure requirements.
- `procedure_requirements`: typed links to parts, tools, software, or fluids with quantity and mandatory state.
- `maintenance_schedules`, `maintenance_tasks`: interval, operating condition, action, and target system.

Typed junction tables or explicit link tables are preferred over an unconstrained polymorphic `item_id`. If a generalized link is unavoidable, it must include a type discriminator enforced by application validation and an audit record.

## Human review and feedback

`technician_feedback` or its normalized successor `feedback_items` stores user, target record, issue type, notes, status, timestamps, reviewer, and applied revision. Feedback never silently mutates a published revision. An approved correction produces a new canonical/projection revision and links the feedback item to that change.

## Platform spine

The platform tables in [contracts.md](contracts.md) connect these contexts to fulfillment:

```text
dataset_products
      |
entitlements ---- payment_events
      |
dataset_requests ---- source_snapshots ---- source_documents
      |                         |
dataset_projections       ingestion_jobs/extraction_runs
      |
dataset_revisions ---- dataset_section_status
      |
publication_events ---- feedback_items / audit records
```

`dataset_products` declares the vehicle selector and minimum viewable sections. `dataset_requests` records the requested selector, source snapshot, lane state, and correlation IDs. `dataset_projections` scopes canonical content to one request/product. `dataset_revisions` is immutable and records the source watermark, schema version, readiness summary, and changelog. `dataset_section_status` tracks independent readiness. `entitlements` controls access to the projection and permitted revisions.

## Data retention and deletion

Raw source and derived artifacts follow source-specific retention and takedown policy. Deleting or revoking user access does not delete audit records, hashes, or the fact that a revision existed. A takedown marks affected content revoked and prevents new projection publication while preserving an auditable tombstone.
