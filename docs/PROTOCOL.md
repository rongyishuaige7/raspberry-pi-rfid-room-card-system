# TCP protocol

The Qt client and Python server use UTF-8, newline-delimited commands and newline-delimited JSON responses on TCP. The default port is `8888`.

## Authentication

```text
LOGIN:<username>:<sha256(password)>
```

A successful response contains a random in-memory session token. Subsequent commands insert that token as the first argument:

```text
GET_CARDS:<token>
CHECK_CARD:<token>:<uid>
```

The server stores only a salted PBKDF2 derivative of the client's SHA-256 value. This improves database-at-rest handling but **does not** make the plaintext transport safe: an observer can replay the transmitted digest. Use an isolated trusted LAN or an authenticated encrypted tunnel.

## Commands

| Command | Arguments after token | Roles |
|:--|:--|:--|
| `READ_CARD` | none | Admin, FrontDesk |
| `ADD_CARD` | `uid:room_id:YYYY-MM-DD` | Admin, FrontDesk |
| `OPEN_DOOR` | `uid` | All roles for normal cards; Admin only for lost-card emergency exception |
| `CHECK_CARD` | `uid` | All roles |
| `LOST_CARD` | `uid` | Admin, FrontDesk |
| `CANCEL_CARD` | `uid` | Admin, FrontDesk |
| `DELETE_CARD` | `uid` | Admin only |
| `GET_CARDS` | none | All roles |
| `GET_ROOMS` | none | All roles |
| `GET_LOGS` | optional limit, clamped to 1–500 | Admin only |
| `GET_STATS` | none | All roles |

The client historically included an operator string in several write commands. The public server ignores that value and takes the operator from the authenticated session.

## Response semantics

```json
{"code": 200, "data": {}}
```

`OPEN_DOOR` returns HTTP-like code `202` in JSON when an actuator task is queued:

```json
{
  "code": 202,
  "msg": "开门任务已下发；未确认舵机完成动作",
  "actuation_confirmed": false
}
```

The SG90 path has no position sensor or lock feedback. A queued PWM sequence is not proof that a physical door opened.

## Boundaries

- This is a custom educational protocol, not HTTP.
- There is no TLS, certificate validation, packet signature, or replay protection.
- RC522 UID is an identifier, not a cryptographically secure access credential.
- Session tokens are in-memory, bounded, expire by time, and are cleared by server restart.
- Responses are newline-delimited. A request line is capped at 8192 bytes by default.
