# Cloud Deployment Templates

This folder includes deployment starter templates for:

- AWS (`infra/cloud/aws`)
- GCP (`infra/cloud/gcp`)
- Azure (`infra/cloud/azure`)

The CI/CD workflow calls `infra/cloud/deploy.sh` on manual dispatch.

## Recommended flow

1. Build and push container images (GitHub Actions `ci-cd.yml`).
2. Configure cloud credentials and environment secrets.
3. Use workflow dispatch with `cloud_provider` set to `aws`, `gcp`, or `azure`.
4. The workflow runs provider CLI deployment command from `deploy.sh`.

## Required secrets/environment

### AWS
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `AWS_ECS_CLUSTER`
- `AWS_ECS_SERVICE`

### GCP
- `GCP_SA_KEY` (service account JSON)
- `GCP_PROJECT_ID`
- `GCP_REGION`
- `GCP_SERVICE_NAME`

### Azure
- `AZURE_CREDENTIALS` (service principal JSON)
- `AZURE_RESOURCE_GROUP`
- `AZURE_CONTAINER_APP`

