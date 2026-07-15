# Infra (Terraform)

Manages the VPC, subnet, security group, and EC2 instance running the app in
`ap-southeast-2`. State lives in S3 (`academic-paper-assistant-tfstate-718203020368`),
locked via DynamoDB (`academic-paper-assistant-tflock`).

## One-time setup (already done)

- S3 state bucket + DynamoDB lock table (created via AWS CLI, not Terraform —
  a backend can't bootstrap itself).
- Scoped IAM user `academic-paper-assistant-ci` for GitHub Actions (not the
  account's admin user), with a policy limited to EC2 in this region + the
  state bucket/lock table.
- The EC2 key pair `academic-paper-assistant` (AWS-generated; referenced here
  via a data source, not managed, since AWS never returns the public key
  material for a `create-key-pair`-generated pair).

## Required GitHub secrets

- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — for the `academic-paper-assistant-ci` IAM user.
- `SSH_PRIVATE_KEY` — contents of the `.pem` file, for `deploy.yml` to SSH into the instance.

## Workflows

- **terraform-import.yml** — manual (`workflow_dispatch`) only. Adopts the
  resources that were created by hand before this existed. Safe to re-run.
- **infra.yml** — `terraform plan` on PRs touching `infra/**`, `apply` on push
  to `main`.
- **deploy.yml** (repo root `.github/workflows/`) — on push to `main` for
  anything *except* `infra/**`: SSHes in, `git pull`, rebuilds/restarts the
  `api` container and the `gradio-app` systemd service.

## Local changes

Airflow is intentionally not part of this stack (it needs far more disk/RAM
than this instance has to spare — see the CUDA/torch deps in its image). If
you add it back, bump `root_volume_size` and probably `instance_type` too.
