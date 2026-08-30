# Security Policy

Oscillink Agent is alpha software. It handles durable memory, imported evidence, provider configuration, capability grants, run history, and workspace recovery. Treat it as security-sensitive and do not expose it directly to an untrusted network.

## Supported versions

Security fixes currently target the latest commit on the default branch. No released version has a guaranteed security-support period yet.

| Version | Supported |
|---|---|
| Latest default-branch revision | Best effort |
| Older alpha revisions | No |

This table will be replaced with an explicit release support policy before a stable release.

## Reporting a vulnerability

Do not file a public issue containing an exploit, credential, private prompt, customer data, host path, or sensitive runtime artifact.

Preferred reporting path:

1. Use GitHub private vulnerability reporting for `Maverick0351a/oscillink-agent` when that feature is enabled.
2. If it is unavailable, open a minimal issue at <https://github.com/Maverick0351a/oscillink-agent/issues> requesting private maintainer contact. Do not include vulnerability details.
3. If the repository is private and you have authorized access, contact the repository owner through the existing private collaboration channel.

Include, when safe:

- affected revision and environment;
- prerequisite access and configuration;
- minimal reproduction steps;
- observed and expected behavior;
- impact and scope;
- sanitized logs or artifacts;
- whether the issue is already being exploited or publicly known.

No response or remediation SLA is promised during alpha. Maintainers will avoid public disclosure until a fix or mitigation is available when practical and will credit reporters who request attribution, subject to privacy and safety constraints.

## High-priority security boundaries

Reports are especially valuable when they show:

- authentication or workspace-scope bypass;
- grant forgery, replay, scope expansion, actor mismatch, or expiry bypass;
- retrieved content or model output changing policy or permissions;
- secret, credential, private prompt, host-path, or hidden-label leakage;
- arbitrary file, shell, network, process, deployment, or actuator access;
- unsafe symlink, reparse-point, archive, or path traversal behavior;
- workspace export, restore, migration, or deletion integrity failure;
- event-ledger tampering or revision/provenance confusion;
- cross-workspace or future cross-tenant data exposure;
- denial of service that bypasses declared size, time, call, output, or concurrency limits;
- dependency or build-chain compromise.

## Deployment guidance

- Bind the alpha server to loopback unless a reviewed private-network deployment is required.
- Use explicit origin and trusted-host allowlists.
- Keep the workspace credential outside the data root, logs, memory, events, artifacts, citations, and exports.
- Keep provider credentials server-side and out of canonical state.
- Use a dedicated data directory with least-privilege filesystem access.
- Do not expose an unrestricted host shell or mount sensitive directories.
- Back up through the governed export path and test restore using verified manifests.
- Review generated reports and fixtures before publishing.

See [`docs/private-pilot-runbook.md`](docs/private-pilot-runbook.md) for the current bounded deployment procedure.

## Physical systems

Oscillink Agent does not currently provide robot or equipment control. Do not connect the alpha to actuators, safety PLCs, emergency-stop systems, industrial controllers, or other safety-critical equipment.

Future actuator-connected work requires a separate safety analysis, simulation-first testing, bounded deterministic low-level control, authentication, network isolation, emergency-stop compatibility, incident logging, operator responsibility, and legal/insurance review. Restoring software state cannot undo a completed physical action.

## Secrets and private data

Never submit real secrets or private customer data as a reproduction. Use synthetic placeholders such as `[REDACTED]`. If a real credential was exposed, revoke or rotate it through the issuing service before reporting; deleting it from Git history or a message does not make it safe again.

## Scope limitations

This policy is not a security certification, penetration-test report, warranty, bug bounty, or promise that the software is fit for safety-critical, regulated, or production use. The Apache-2.0 warranty and liability terms apply.
