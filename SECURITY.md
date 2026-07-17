# Security policy

## Supported scope

This is an educational prototype, not a production hotel access-control system. Security fixes are accepted for the current default branch; there are no long-term supported releases.

Report a suspected vulnerability privately through GitHub's **Report a vulnerability** form when available. Do not include real card UIDs, passwords, tokens, database dumps, addresses, or network topology in a public issue.

## Deployment boundary

- Keep the Raspberry Pi, client, and database on an isolated, trusted LAN.
- The custom TCP protocol has no TLS. The client-side SHA-256 value is replayable to an observer; it is not a password-authenticated key exchange.
- Bind to `127.0.0.1` by default. Set `ROOMCARD_BIND_HOST=0.0.0.0` only behind a trusted network boundary, or place the protocol inside an authenticated encrypted tunnel.
- Create unique accounts interactively. The repository contains no default user or default password.
- Database credentials belong in environment variables or a protected service configuration, never in Git.
- RC522 UID is not a secure credential: common cards can be cloned and the UID travels through the prototype as an identifier.
- Session tokens live in memory, expire by time, and are lost on restart. They are still exposed on plaintext TCP.
- SG90 actuation has no lock-position feedback. A successful response means the PWM task was queued, not that a physical door opened or closed.

Before any real deployment, add TLS or a secured tunnel, rate limiting, lockout policy, encrypted secret storage, hardware-backed credentials, tamper monitoring, actuator feedback, fail-safe design, audit retention rules, and an independent security review.
