# Reviewed Memory Index and Taxonomy Contract

## Purpose

The reviewed Obsidian index is a deterministic, read-only projection of curated Markdown records. It is the source boundary for the later typed memory API, lattice projection, lexical retrieval, embeddings, K-nearest-neighbor neighborhoods and derived clusters.

The index does not make a note true, approved or authoritative merely because the note exists. It preserves source provenance and reports how every organizational label was assigned.

## Canonical and derived state

Canonical human-owned state remains Markdown in the reviewed Obsidian vault. The following are rebuildable derived state:

- index snapshots;
- source content digests;
- path-derived document IDs;
- automatic category and domain labels;
- FTS indexes;
- embeddings and nearest-neighbor edges;
- cluster memberships, labels and layout coordinates.

Explicit `category` and `domains` frontmatter are human-reviewed metadata. Automatically inferred labels are projections and must not be written back to the vault without review.

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

## Stable identity and provenance

Each indexed node carries:

- a stable opaque `doc_` ID derived from its normalized vault-relative path;
- its vault-relative POSIX source path, never an absolute host path;
- SHA-256 of the exact source bytes;
- frontmatter type and source status;
- title, topics and Obsidian wikilinks;
- category and domain labels;
- classification basis.

Editing content preserves the node ID and changes both its source digest and the complete index digest. A rename currently changes the path-derived ID. A future explicit frontmatter ID can provide rename-stable identity after its promotion and collision rules are specified.

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

## Lattice semantics

The current neural renderer remains a foundation architecture map until the typed memory projection API is connected. When real nodes arrive:

- primary category controls the legend treatment;
- domains appear as textual badges and filters;
- individual records remain inspectable beneath any cluster;
- exact wikilinks and governed relationships remain distinct from inferred similarity;
- KNN edges and cluster membership remain versioned derived projections;
- cluster size, depth, brightness and position must not imply truth, confidence or authority without an explicit legend.

## Typed projection API

The read-only projection boundary exposes:

- `GET /api/v1/memory/index` for state, digest, category and domain legends, counts and sanitized issues;
- `GET /api/v1/memory/nodes` for category/domain-filtered summaries;
- `GET /api/v1/memory/nodes/{node_id}` for focused inspector metadata.

Responses use typed `ready`, `degraded` and `unavailable` states. Invalid category/domain labels and malformed document IDs are rejected before vault lookup. The browser receives only vault-relative paths and cannot access the filesystem directly.

The next milestone is to replace the foundation-only lattice data with real projected nodes and a focused inspector while retaining the truthful architecture-map disclosure as a separate system view.
