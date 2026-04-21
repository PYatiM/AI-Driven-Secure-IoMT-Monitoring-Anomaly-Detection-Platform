#!/usr/bin/env bash
set -euo pipefail

PROVIDER="${1:-}"
BACKEND_IMAGE="${2:-}"
FRONTEND_IMAGE="${3:-}"

if [[ -z "${PROVIDER}" ]]; then
  echo "Usage: ./infra/cloud/deploy.sh <aws|gcp|azure> <backend-image> <frontend-image>"
  exit 1
fi

case "${PROVIDER}" in
  aws)
    : "${AWS_REGION:?AWS_REGION is required}"
    : "${AWS_ECS_CLUSTER:?AWS_ECS_CLUSTER is required}"
    : "${AWS_ECS_SERVICE:?AWS_ECS_SERVICE is required}"
    echo "Updating AWS ECS service ${AWS_ECS_SERVICE} in cluster ${AWS_ECS_CLUSTER}..."
    aws ecs update-service \
      --region "${AWS_REGION}" \
      --cluster "${AWS_ECS_CLUSTER}" \
      --service "${AWS_ECS_SERVICE}" \
      --force-new-deployment
    ;;
  gcp)
    : "${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
    : "${GCP_REGION:?GCP_REGION is required}"
    : "${GCP_SERVICE_NAME:?GCP_SERVICE_NAME is required}"
    echo "Deploying to Google Cloud Run service ${GCP_SERVICE_NAME}..."
    gcloud run deploy "${GCP_SERVICE_NAME}" \
      --project "${GCP_PROJECT_ID}" \
      --region "${GCP_REGION}" \
      --image "${BACKEND_IMAGE}" \
      --platform managed \
      --allow-unauthenticated
    ;;
  azure)
    : "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP is required}"
    : "${AZURE_CONTAINER_APP:?AZURE_CONTAINER_APP is required}"
    echo "Updating Azure Container App ${AZURE_CONTAINER_APP}..."
    az containerapp update \
      --resource-group "${AZURE_RESOURCE_GROUP}" \
      --name "${AZURE_CONTAINER_APP}" \
      --image "${BACKEND_IMAGE}"
    ;;
  *)
    echo "Unsupported cloud provider: ${PROVIDER}"
    exit 1
    ;;
esac

echo "Deployment command completed for provider: ${PROVIDER}"

