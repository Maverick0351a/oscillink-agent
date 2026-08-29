# Product-Owned Memory and Source Taxonomy Contract

## Purpose

Oscillink owns stable memory identity, immutable record revisions and human review decisions. Native customer memory works without Obsidian. External Markdown remains portable source material that can be synchronized into the product repository with provenance.

Source presence does not make a record true, approved or authoritative. The repository separates source origin, authority state and derived retrieval projections.

## Canonical and derived state

Canonical product state is the product-owned memory repository:

- stable `mem_` record identities;
- immutable serialized record revisions;
- append-only review decisions;
- source bindings and synchronization outcomes.

Human-owned Markdown remains canonical for the customer's source document when Obsidian is used. Synchronization creates or revises an Oscillink record without transferring product identity back to a filename. The following remain rebuildable derived state:

- index snapshots;
- source content digests;
- adapter-local `doc_` IDs used by the legacy read-only source projection;
- automatic category and domain labels;
- FTS indexes;
- embeddings and nearest-neighbor edges;
- cluster memberships, labels and layout coordinates.

Explicit `category` and `domains` frontmatter are source metadata. Automatically inferred labels are projections and must not be written back to a source without review.

## Inclusion rules

The initial index includes UTF-8 Markdown records with supported typed frontmatter. It excludes:

- `00 Inbox/`, because captured material has not entered the curated memory surface;
- `99 Templates/`;
- `.obsidian/` and `.git/`;
- untyped Markdown;
- dashboards and folder-index records;
- symbolic links and paths resolving outside the vault;
- records exceeding the bounded note size.

Malformed UTF-8, malformed frontmatter and unsupported typed labels produce explicit index issues rather than silent omission or partial ingestion.

## Stable identity, revisions and provenance

Each product record carries:

- a stored opaque `mem_` identity independent of providers and source paths;
- source kind (`native` or `obsidian`) and a bounded source key;
- a relative source locator when applicable, never an absolute host path;
- SHA-256 source/content digest;
- content, title, topics and exact wikilinks;
- category and domain labels;
- explicit System Architecture container associations owned by the immutable revision;
- classification basis and source status;
- an authority state independent of source presence.

Native creation starts in `candidate`. Obsidian synchronization starts in `curated`. Human review can approve or reject either state. Every decision is bound to the reviewed content digest, so a later synchronized content revision returns to `curated` instead of inheriting approval. Rejected records are terminal for that revision. An approved record can be superseded only by another approved product record; the replacement identity is retained on the append-only decision. The latest valid decision for the current revision controls the projected authority state without rewriting prior review history.

Editing a synchronized source appends a record revision and preserves its product identity when the source locator is unchanged. A pure rename with unchanged bytes preserves identity when the repository can unambiguously match one prior locator absent from the current source snapshot. Ambiguous rename detection fails conservatively by creating a new record rather than silently merging records. Explicit connector-owned source IDs remain a future improvement.

## Primary categories

Every indexed node has one primary category. Category presentation is centralized so the API and UI share the same accessible legend.

| Value | Label | Color token | Symbol | Intended use |
| --- | --- | --- | --- | --- |
| `research` | Research | `#36f1cd` | R | Studies, literature and research synthesis |
| `tooling` | Tooling | `#8a7dff` | T | Procedures, reusable tools and operational methods |
| `project` | Projects | `#ff4fd8` | P | Active or preserved project records |
| `experiment` | Experiments | `#ffb84d` | X | Trials, hypotheses, measurements and results |
| `governance` | Governance | `#5ea8ff` | G | Policies, operating rules and reviewed controls |
| `reference` | Reference | `#93a4ad` | L | Archives and durable reference material |
| `note` | Notes | `#7ee787` | N | Curated notes not represented by a narrower category |

Color is never the only category signal. Every rendering must also expose the text label and symbol to support accessibility, printing and low-contrast environments.

## Subject domains

Domains are multi-label and independent of category. Initial controlled values are:

- `ai_ml`;
- `rf_em`;
- `science`;
- `mathematics`;
- `engineering`;
- `software`;
- `business`;
- `general`.

For example, an experiment can simultaneously belong to science, mathematics and RF/EM. A project can span AI/ML, software and business.

## Classification precedence

1. A supported explicit `category` frontmatter value controls the primary category.
2. Otherwise, the supported frontmatter `type` deterministically maps to a category.
3. Supported explicit `domains` values control the domain set.
4. Otherwise, bounded deterministic rules inspect title, area, topics and tags.
5. No domain match produces `general`.

Unknown explicit values fail closed as index issues. The classifier records its basis on every node so later UI and review flows can explain whether a label was human-specified or automatically derived.

Example reviewed frontmatter:

```yaml
---
type: research-note
status: active
category: experiment
domains: [science, mathematics, rf_em]
topics:
  - electromagnetic field inference
  - posterior calibration
---
```

## Lattice and architecture semantics

The Memory Lattice renders product-owned records for governance. The unified agent workspace also projects those records into seven explicit System Architecture memory containers:

- `identity-role` — Identity & Role;
- `goals-commitments` — Goals & Commitments;
- `projects-work` — Projects & Work;
- `knowledge-research` — Knowledge & Research;
- `people-relationships` — People & Relationships;
- `decisions-lessons` — Decisions & Lessons;
- `preferences-context` — Preferences & Context.

`architecture_node_ids` is validated at the typed API boundary, serialized with the immutable product record revision and preserved across restart. The UI never infers this association from category, domain, proximity or filename. Human review of the revision therefore covers its declared container associations. Architecture membership does not itself imply approval, truth, confidence or retrieval eligibility; the node sidebar must continue to show each associated record's authority and source state.

Across both projections:

- primary category controls the legend treatment;
- domains appear as textual badges and filters;
- individual records remain inspectable beneath any cluster;
- exact wikilinks and governed relationships remain distinct from inferred similarity;
- KNN edges and cluster membership remain versioned derived projections;
- authority state and source kind remain visible in the focused inspector;
- cluster size, depth, brightness and position must not imply truth, confidence or authority without an explicit legend.

User-adjustable focus weights are not implemented in this slice. When added, they must remain a separate bounded retrieval preference: authorization and authority eligibility run first, and focus cannot approve, validate or expose a record.

## Typed API

The current boundary exposes:

- `GET /api/v1/memory/index` for state, digest, category and domain legends, counts and sanitized issues;
- `GET /api/v1/memory/nodes` for category/domain-filtered summaries;
- `GET /api/v1/memory/nodes/{node_id}` for focused inspector metadata.
- `POST /api/v1/memory/nodes` for product-native candidate creation;
- `POST /api/v1/memory/nodes/{node_id}/reviews` for idempotent human approval, rejection or governed supersession;
- `POST /api/v1/memory/sources/obsidian/sync` for explicit idempotent synchronization of the configured source.

Responses use typed `ready`, `degraded` and `unavailable` states. Invalid category/domain labels and malformed `doc_`/`mem_` IDs are rejected before lookup. The browser receives only relative source locators and cannot access the filesystem directly. Artifact candidate associations can target either legacy `doc_` source projections or product-owned `mem_` records during migration.

The next milestones expose native creation and explicit source synchronization in the customer UI, then add approved-only retrieval, provenance-bearing evidence packets and deterministic context manifests. Browser review controls for candidate and curated records are implemented.
