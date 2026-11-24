# Security policy

## Reporting a vulnerability

Please report security problems privately, not in a public issue: open the
[Security tab](https://github.com/alexcpn/tabmail/security) of this repository
and click **Report a vulnerability**. Include what you found, how to reproduce
it, and what an attacker could do with it.

You should get a first reply within a week.

## What counts

tabmail handles Gmail credentials (a Google sign-in token or an app password)
and passes email text to an AI model, so these are especially interesting:

- ways for credentials to leak from `~/.config/tabmail/` or the system keyring
- email content that makes tabmail run commands, change or delete mail, or send
  data anywhere other than Gmail and the configured AI backend
- anything that makes tabmail change mail while `allow_changes = false`

## Supported versions

Only the latest version on the `main` branch gets fixes.

## Automated checks

Every push and pull request runs the test suite, [Bandit](https://bandit.readthedocs.io/),
[pip-audit](https://pypi.org/project/pip-audit/) and [Gitleaks](https://github.com/gitleaks/gitleaks).
GitHub's secret scanning (with push protection), Dependabot alerts and CodeQL
code scanning are also enabled for this repository.
