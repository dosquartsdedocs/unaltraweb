---
title: Inspect And Close A Live MCP Session
description: Startup identity, exact prepared images and session-scoped resource release.
lang: en
ref: live_runtime_identity
profiles:
- unaltredocs
documentation_profiles:
- local-authors
- core-developers
section: Core Development
weight: 635
permalink: /live-runtime/
nav_title: Live Runtime
---

The [published 0.7.0 runtime](https://github.com/dosquartsdedocs/unaltraweb/releases/tag/v0.7.0)
distinguishes the process serving a connection from
the installed package, source checkout and rendering workers. Call
`runtime_identity` or read `web://runtime-identity` through that live MCP
connection. Both report the same backend instance and startup information.

The observation includes the loaded package version, startup code fingerprint,
current disk fingerprint, interpreter, PID/start information, workspace mapping
and selected versus observed image identities. A disk edit is reported as drift;
it does not upgrade an already-running process. Docker-host and container PID
namespaces are reported separately. Identity checks read engine/runtime metadata,
not website prose, private records or arbitrary environment variables.

## Prepare Explicitly, Then Launch

Use `unaltraweb-mcp-docker prepare --image REF` to acquire a selected release.
Launch, check, smoke and identity observations do not build or pull missing images.
For a managed launch, supply a full image ID or repository digest, or bind a local
reference to its independently verified configuration ID:

```bash
unaltraweb-mcp-docker serve --project /absolute/site \
  --image "$PREPARED_REFERENCE" --expected-image-id "$EXPECTED_IMAGE_ID" --managed
```

The expected value is Docker's full `sha256:` configuration ID, not the archive
checksum or OCI index digest. A missing or mismatched selection is an error.
Execution uses that inspected ID with `--pull never`; existing aliases are not
rewritten. Add `--offline` for a controller without networking. The declared
Docker socket remains available for local inspection and prepared workers.

The normal host launcher mounts the canonical site path and a `/workspace` alias.
A launcher itself running in a container must supply its explicit daemon-host
mapping using `--host-project`. Unsupported direct controller mappings require
inspection rather than guessing a host path from `/workspace`.

## Close One Connection Safely

1. Retain the identity's consumer binding, session ID and exact container ID.
2. Call `runtime_drain(confirm=true)`. The backend stops admitting new operations.
3. Close that stdio connection. Bounded active work finishes before its idle
   session resources are released.
4. Use the installed `session-status` command to confirm resource termination.

```bash
unaltraweb-mcp-docker session-status --project /absolute/site \
  --session-id "$SESSION_ID" --container-id "$CONTAINER_ID"
```

`connected`, `busy`, `orphaned` and `unknown` do not mean resources are free.
Only `stopped` with `resources_released=true` establishes observed absence.
After a crash, `reap-session` with the same retained tuple can recover eligible
idle leftovers. It preserves live backends, active jobs, other sessions, prepared
images, volumes and authored files. Disk cleanup remains explicit and separate.

The older `down` command is workspace-wide, and `mcp-down-all` is factory-wide.
Use them only for those intended scopes, not as a substitute for closing one
client. The managed stdio profile has one connection per backend; it does not
claim shared-HTTP backend reattachment semantics.

## Workers And Helpers

Worker references are fixed at startup. Managed rendering requires those exact
images to be prepared; it refuses a fallback pull/build or a conflicting authored
computation-image choice. The identity reports resource bounds and image
observations without running a renderer.

Visual helpers are separate MCP processes. Their versions and immutable package
selections describe the accepted rendering closure, not their current live
instances. The composing controller must obtain each helper's own live identity.
The selected Diavisuals 0.5.0 still requires its separately tracked D0 identity
correction before the entire coordinator closure can be marked managed-ready.
Existing 0.4.0 static provider receipts remain subject to full integrity checks
and do not force regeneration of authored figures during an upgrade.
