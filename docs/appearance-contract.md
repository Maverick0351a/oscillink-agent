# Governed Appearance Contract

## Purpose

The agent may express a visible presentation state without receiving authority to modify frontend code, execute assets, or write arbitrary host files.

The Phase 1 foundation avatar is a local, static SVG owned by the application. It is explicitly labeled as a preview and is not a durable agent-selected identity.

## State classes

### Runtime presence

Runtime presence is ephemeral and derived from externally observed runtime events:

- `idle`;
- `listening`;
- `retrieving`;
- `thinking`;
- `requesting_approval`;
- `acting`;
- `verifying`;
- `completed`;
- `blocked`;
- `error`.

These labels describe operational state, not emotion, consciousness, or subjective experience.

### Session appearance

A session may select approved expression, pose, glow intensity, animation preset, and palette variants. Session appearance is not durable memory and resets safely.

### Durable appearance

A durable change follows:

```text
propose -> validate -> preview -> human approve -> promote -> preserve lineage
```

Every promoted version retains its predecessor and supports rollback.

## Planned manifest fields

A future typed `AppearanceManifest` should include:

- manifest ID and schema version;
- logical appearance name and version;
- allowlisted local avatar artifact digest;
- bounded palette-token selections;
- runtime-state-to-expression mappings;
- allowlisted animation preset;
- bounded cosmetic accessory identifiers;
- proposing actor and rationale;
- review event reference;
- promoted and superseded lineage;
- creation and promotion timestamps.

## Prohibited fields and behavior

An appearance manifest must reject:

- JavaScript or executable code;
- CSS text or selectors;
- inline event handlers;
- arbitrary SVG, HTML, or shader source;
- remote URLs;
- unverified file paths;
- host commands;
- permission or policy changes;
- hidden data payloads in cosmetic metadata;
- modification of protected defaults or approval rules.

Approved assets are immutable content-addressed artifacts. MIME type, byte size, dimensions, animation duration, and decoder behavior must be validated outside the model boundary before promotion.

## Governance split

The agent may propose or select only within externally defined bounds. Human governance controls:

- asset and token allowlists;
- durable approval;
- protected defaults;
- emergency reset;
- rejection and rollback;
- the schema and promotion policy themselves.

Appearance citations and provenance establish origin, not safety or authority.

## Accessibility

Every appearance must preserve:

- sufficient text and control contrast;
- a text label for every operational state;
- visible keyboard focus;
- a nonanimated equivalent;
- `prefers-reduced-motion` behavior;
- no state conveyed by color alone;
- no rapid flashing or visually disruptive constant motion.
