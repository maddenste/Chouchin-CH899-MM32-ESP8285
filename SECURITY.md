# Use your clock safely

Use the settings page only on a trusted local network. **Do not forward it to the Internet or expose it through your router.** It is a local setup page, not a password-protected online account.

The Wi-Fi setup network is open while the clock is awake. Configure it somewhere you trust, and do not assume stored settings are encrypted.

Before sharing a screenshot, check that it does not reveal your password or other private information. Never upload complete device backups, session tokens or private network captures to an issue.

For an ordinary clock problem, use [troubleshooting](docs/TROUBLESHOOTING.md) and the issue form. Report a suspected security problem privately through the maintainer's GitHub contact route where available, rather than publishing secrets.

For developers, the webpage's request checks help prevent accidental/unwanted writes but are not user authentication. Network settings, HTTP/session protections and storage limitations should be considered when proposing changes.
