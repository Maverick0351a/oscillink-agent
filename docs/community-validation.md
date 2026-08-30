# Community validation protocol

This document defines the minimum evidence required before Oscillink Agent claims community usefulness or expands a product lane.

## Principles

- Technical efficacy, category demand, and Oscillink-specific product demand are separate questions.
- Stars, impressions, funding announcements, vendor claims, and demonstration videos are directional signals—not proof of retained use, safety, or willingness to pay.
- A person using the tool on their own data is stronger evidence than watching a prepared demo.
- Measure total human time: setup, active supervision, review, cleanup, correction, and recovery.
- Preserve failures and unavailable results; do not rewrite a protocol after seeing outcomes.
- Keep private user artifacts and identities outside the public repository unless explicitly sanitized and approved.

## Coding-agent alpha

### Target user

Developers using coding agents across multiple sessions, compaction events, restarts, or model/client changes.

### Core outcome

A user continues work without re-explaining approved project decisions, repeating a recorded failed approach, or relying on a superseded decision.

### Entry criteria

- Local installation requires no account.
- First useful recall is reachable in under five minutes on a clean supported environment.
- Two clients have been exercised directly against the same state.
- The deterministic acceptance scenario passes.
- Security and recovery boundaries are documented.

### Protocol

1. Record the user's current agent/client, project type, and manual continuity workaround.
2. Measure setup time without developer intervention.
3. Run at least three sessions separated by restart or compaction.
4. Record one project decision and one failed approach.
5. Introduce one correction that supersedes a prior decision.
6. Switch to the second exercised client without replaying the raw transcript.
7. Record useful recall, stale-memory reuse, repeated failed approaches, citation correctness, context size, and provider usage.
8. Record active supervision, review, cleanup, correction, and recovery time.
9. Ask what the user would replace, integrate, self-host, or pay to have operated.

### Promotion gate

Continue beyond the bounded alpha only if:

- at least five external users try it on their projects;
- at least three use it across three separated sessions;
- at least two independently report avoiding re-explanation, a repeated mistake, or stale context;
- at least one requests a concrete integration or hosted/team capability;
- measured review and cleanup do not erase the benefit.

A failed gate means narrow or improve the workflow; it does not justify adding unrelated features.

## Physical-intelligence discovery

### Current boundary

The first experiment may inspect recorded datasets and episode manifests. It must not command hardware, publish actuator topics, control emergency stops, train or promote a policy, or imply physical safety.

### Target users

- robotics hobbyists using LeRobot or comparable affordable systems;
- embodied-AI researchers and lab engineers;
- teleoperators, collection leads, and robot deployment engineers.

### Discovery questions

- How are episodes rejected, retried, corrected, and versioned?
- Which defects are discovered only after training?
- How are calibration, controller, sensor, task, environment, and operator revisions tracked?
- How are intervention and recovery trajectories represented?
- How much human time is spent per accepted trajectory or hour?
- What existing tool nearly solves the problem?
- Who owns the collection-quality and evaluation budget?

### Experiment gate

Do not expand the read-only Data Doctor experiment unless:

- at least ten firsthand workflow records identify repeated quality, correction, lineage, or evaluation burden;
- at least three users run it on their own datasets;
- at least two users receive an actionable finding;
- at least one requests a recurring integration, private pilot, or paid capability;
- the outcome is not already provided adequately by a trivial existing command.

If the gate fails, retain useful episode contracts and fixtures as components and stop product expansion.

## Evidence record

For each participant, store a private record containing:

- anonymous participant code;
- role and workflow;
- date and tested revision;
- setup and task duration;
- inputs and exact protocol version;
- observable outcomes and failures;
- supervision, review, cleanup, and recovery time;
- requested integrations or commercial capabilities;
- consent and publication status;
- follow-up decision: archive, component, iterate, or promote.

Only aggregate or explicitly approved sanitized findings belong in the public repository.
