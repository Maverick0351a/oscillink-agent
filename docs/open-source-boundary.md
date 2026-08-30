# Open-source and commercial boundary

Oscillink Agent is licensed under the [Apache License 2.0](../LICENSE). The license applies to the source code and documentation in this repository unless a file states otherwise. Third-party dependencies and imported datasets retain their own licenses.

## Why Apache-2.0

Oscillink is intended to become a shared continuity and evidence layer across model providers, coding agents, local runtimes, research tools, and—only after separate validation—physical-intelligence data workflows. A permissive license with an explicit patent grant reduces adoption and integration friction for individual developers, research groups, and companies.

The project does not depend on restricting local use or marking up model inference. Its intended commercial value is operating the shared system reliably for people and teams.

## Open local foundation

The planned open local product includes:

- product-owned memory identities and immutable revisions;
- correction, contradiction, supersession, and retraction history;
- provenance-bearing retrieval and deterministic context compilation;
- local provider and client adapters;
- typed capability and budget contracts;
- local run inspection, export, restore, and reproducible evaluation;
- public fixtures, manifests, schemas, and compatibility examples;
- local tools for inspecting physical-intelligence datasets if that experiment is validated.

Some listed surfaces are planned rather than implemented. The [README](../README.md) and capability ledger in the [build plan](build-plan.md) distinguish implemented, planned, and deferred behavior.

## Expected paid operational layers

A future hosted or enterprise offering may charge for services around the open local foundation, including:

- encrypted synchronization and managed backup;
- remote access and reliable hosted operation;
- multi-user workspaces, coordination, and policy administration;
- hosted evaluation, scheduled jobs, and operational observability;
- managed connectors and deployment integrations;
- organization audit, retention, residency, and access controls;
- on-premises packaging, service-level agreements, and support.

This is a product direction, not a promise that every listed service exists today. Any hosted service must preserve authorization, provenance, deletion, export, and rollback contracts rather than making the service the only usable source of customer state.

## Data, model, and connector ownership

The Apache-2.0 license does not grant rights to third-party data, model weights, external services, trademarks, or customer content.

- Customers retain responsibility for the data, credentials, models, and services they connect.
- Public fixtures must have documented provenance and license terms and be reproducible from pinned bytes.
- Secrets, private prompts, hidden benchmark labels, runtime databases, and private customer results must not enter the public repository.
- Provider credentials remain outside canonical memory, events, artifacts, citations, exports, and reports.

## Contribution boundary

Unless a contribution is explicitly designated otherwise, contributions intentionally submitted for inclusion in this repository are accepted under Apache-2.0 as described by Section 5 of the license. A future contribution guide will document development, verification, security, and provenance requirements before public promotion.

## Physical-intelligence boundary

Oscillink does not currently provide robot or equipment control. Any public physical-intelligence experiment begins with read-only episode, dataset, provenance, correction, and evaluation tooling.

Actuator-connected work requires a separate reviewed safety case, simulation-first testing, bounded deterministic low-level control, authentication, emergency-stop compatibility, operator responsibility, and explicit recognition that a physical action cannot be undone by restoring software state.
