# Security and private data

Use the setup AP and local HTTP page only on trusted networks. Do not expose the clock's HTTP interface to the Internet. Per-session write protections are not a user-login system; stored device settings are not a promise of encrypted-at-rest secrets.

Never post Wi-Fi passwords, session tokens, complete flash backups, raw private captures or per-board factory data in issues. Crop/redact screenshots before sharing. For an ordinary bug, versions, selected modes, timing, LED code and a short symptom description are usually sufficient.

No cloud account, mDNS discovery or Internet-facing management service is required. Normal NTP/Wi-Fi operation still depends on a reachable network/time server.

Report a suspected security problem privately through the maintainer's GitHub contact route where available; do not disclose secrets publicly. No response-time guarantee or formal supported-release policy is claimed during pre-release development.
