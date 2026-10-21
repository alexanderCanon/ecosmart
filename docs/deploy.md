# EcoSmart deployment gateway

## Intended operation

After **one** local bootstrap, `Deploy EcoSmart service` in GitHub Actions runs on `ecosmart-pi`, and a root-owned wrapper checks out the requested, already-merged commit from `main`. It executes the selected Ansible playbook locally (`homepage` or `docker`) with no interactive sudo prompts, no SSH, and no Tailscale OAuth.

The workflow is **manual-only initially**. A future PR can enable deploy-on-merge once we confirm a successful run.

## One-time bootstrap (performed by the Pi administrator)

Keep Ethernet connected. On the **Raspberry Pi**, with a copy of the updated repo checked out, run:

```bash
sudo bash scripts/install-deployer.sh
```

This installs Ansible from APT, copies the deploy gateway under a root-owned path and adds one `sudoers` rule for `ghrunner`.

Verify the script contents **before running**. This step is a privilege-boundary change and cannot safely be performed by the unprivileged runner itself. Do not add `ghrunner` to `sudo` or `docker` groups.

## Trigger

After merging this PR, GitHub → Actions → **Deploy EcoSmart service** → **Run workflow**, branch **main**, select `homepage`. If it succeeds, the Pi should still serve Homepage over Tailscale.

## Trust boundary

The gateway only accepts `homepage` or `docker`, validates the 40-hex commit hash and checks it is an ancestor of `origin/main`. However, **Ansible playbooks from main run as root**, so write access and merge policies on this public repository are highly sensitive. This model is only suitable when contributors and merges are controlled. A self-hosted runner in a public repository still carries separate risks. Prefer moving deployment automation to a private repository when possible.

**Not included:** Wi-Fi changes, Wi-Fi fallback PR #3 deployment, automatic on-push deployment. We must review and validate these separately.
