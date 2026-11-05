# Security model

Report a vulnerability privately through GitHub's repository security reporting
feature when it is enabled. Until then, do not include secrets or working exploit
details in public issues. This is a new distribution with no independent security
audit or established support window.

## Trust boundaries

Model output and system observations are untrusted text. They cannot execute
commands. The root console broker has a fixed API and validates every supported
plan. The HTTP service cannot apply plans; applying requires the local root CLI.
The browser uses text nodes for model output, bearer authentication, a restrictive
CSP and no persistent token storage. HTTP does not provide transport encryption;
the default listener is loopback and remote use should be tunneled.

The local `chromax` account may invoke `chromaxctl` through sudo. This authorizes
the reviewed management interface, including trust-key and endpoint provisioning.
It does not authorize arbitrary app execution as root. The wrapper uses Python
isolated mode and an absolute module path. Package run rejects root invocations.
The console is an administrator's console: possession of local console or SSH
access as this user is a privileged trust decision. This is not a multi-tenant
privilege-separation design.

Root and user passwords are initially locked; the serial console deliberately
auto-enters `chromax` for first-run provisioning. SSH disables root and password
login. Protect physical and hypervisor console access. `chromaxctl ssh-key`
provisions one public key; adding a password does not enable SSH passwords.

The inference service is a dedicated non-login user and listens only on loopback.
Models are explicitly supplied and checksummed. GGUF header/hash validation is
not a proof that a model is safe; llama.cpp parses it and must be kept patched.
No inference sandbox escape resistance is claimed. Local prompts are not audited
or written to disk by Chromax; upstream inference behavior must be assessed when
changing runtime versions.

Packages require Ed25519 signatures from a separately trusted root-managed key.
An archive is frozen before verification, and extraction accepts only regular
files matching its signed manifest. Paths, modes, size and architecture are
checked. Activation and rollback change a symlink atomically. A signing key
authorizes executable apps for the user; it is not a trust guarantee about app
behavior. Applications have no automatic sandbox and must be trusted accordingly.

## Limitations and operation

- The initial system does not provide measured/verified boot, disk encryption,
  app confinement, hardened production multi-user policy or automatic OS updates.
- The root filesystem is writable. Store backups before replacing disk images.
- Remote AI explicitly sends the user's question and the documented system
  snapshot to the configured endpoint. Configure only a provider you trust.
- A console token permits observation, AI requests and pending plan creation.
  Protect it. Restarting the console rotates the token.
- Plan failure is visible and non-replayable. Hostname rollback information is
  recorded, but no broad transactional filesystem rollback is claimed.
- Source checksums pin content; they do not replace upstream review or CVE
  maintenance. Rebuild qualified images after security updates.
