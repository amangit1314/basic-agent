#!/bin/bash
# deploy.sh

PROJECT_ID="your-project-id"
REGION="us-central1"
SERVICE_NAME="notice-extractor"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Set project
gcloud config set project ${PROJECT_ID}

# Enable APIs
gcloud services enable cloudbuild.googleapis.com run.googleapis.com

# Optional: Create API key secret (only if using CrewAI)
read -p "Do you want to enable CrewAI mode? (y/n): " enable_crewai

if [ "$enable_crewai" = "y" ]; then
    read -sp "Enter OpenAI API Key: " api_key
    echo
    echo -n "$api_key" | gcloud secrets create openai-api-key --data-file=- || \
    echo -n "$api_key" | gcloud secrets versions add openai-api-key --data-file=-
    
    SECRET_FLAG="--set-secrets=OPENAI_API_KEY=openai-api-key:latest"
else
    echo "Deploying in Pydantic-only mode (no API keys needed)"
    SECRET_FLAG=""
fi

# Build
gcloud builds submit --tag ${IMAGE_NAME}

# Deploy
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --region ${REGION} \
    --platform managed \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 900 \
    --max-instances 10 \
    --min-instances 0 \
    ${SECRET_FLAG}

# Get URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')
echo "✅ Deployed successfully!"
echo "Service URL: ${SERVICE_URL}"
echo ""
echo "Test with:"
echo "curl ${SERVICE_URL}/health"