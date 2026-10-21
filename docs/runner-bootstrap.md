# EcoSmart: GitHub Actions runner (first bootstrap)

This is **phase 1 only**: verify that GitHub Actions can execute a read-only job on the Raspberry Pi. Do not grant the runner sudo, add SSH keys to Actions, or automate deployments yet.

## Safety first

This repository is **public**. A self-hosted runner on a public repository can be exposed to untrusted workflow code, notably through pull requests and potentially other workflows. This is a real security risk, especially on a personal LAN. **Prefer making the repository private before registering the device** (or use a separate private deployment repository). Do not configure pull_request jobs to use this runner. Keeping this smoke test manual-only is not a complete security boundary.

The runner must use a dedicated unprivileged Linux account. Do not add it to `sudo` or `docker` groups. Never reuse the `sef` account, SSH private keys, or Tailscale auth keys for the runner.

## Bootstrap checklist (do not execute all at once)

1. Make the repository private before installing the runner, or stop and reevaluate the risk.
2. In GitHub open **Settings → Actions → Runners → New self-hosted runner**, select **Linux → ARM64**.
3. Follow GitHub's **current, time-limited** installation commands on the Pi under a dedicated unprivileged account, using a dedicated directory. **Never paste the registration token into issues, PRs, chat, or repository files**.
4. Add the custom runner label `ecosmart-pi` via the GitHub runner settings. Confirm the runner is **Online**.
5. After merging this PR, from the **Actions** tab trigger **EcoSmart Raspberry runner connectivity** via **Run workflow**. It should show `aarch64` and an unprivileged username.

## Deliberately not in this PR

- No unattended sudo or root access.
- No Ansible deployment automation yet.
- No public-PR trigger and no automatic push trigger.
- No OAuth/Tailscale integration required for a runner on the Pi itself.
- No changes to NetworkManager, Ethernet, or the existing Wi-Fi fallback service.

In phase 2 we can add an audited local Ansible invocation and a narrowly-scoped privilege elevation mechanism, with manual approval before enabling any automatic deployment.
