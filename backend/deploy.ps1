param(
    [Parameter(Mandatory = $true)][string]$ProjectId,
    [string]$Region = "us-central1",
    [string]$Bucket = "",
    [string]$Service = "post-cronos-api",
    [string]$AllowedOrigins = "*"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "gcloud no está instalado. Instalá Google Cloud SDK y volvé a ejecutar."
}

if (-not $Bucket) {
    $Bucket = "$ProjectId-post-cronos-dibujos"
}

$ServiceAccount = "post-cronos-api"
$ServiceAccountEmail = "$ServiceAccount@$ProjectId.iam.gserviceaccount.com"

gcloud config set project $ProjectId

gcloud services enable `
    run.googleapis.com `
    cloudbuild.googleapis.com `
    artifactregistry.googleapis.com `
    storage.googleapis.com `
    bigquery.googleapis.com `
    aiplatform.googleapis.com

$existing = gcloud iam service-accounts describe $ServiceAccountEmail 2>$null
if (-not $existing) {
    gcloud iam service-accounts create $ServiceAccount --display-name="Post-Cronos API"
}

foreach ($role in @("roles/storage.objectAdmin", "roles/bigquery.dataEditor", "roles/bigquery.jobUser", "roles/aiplatform.user")) {
    gcloud projects add-iam-policy-binding $ProjectId `
        --member="serviceAccount:$ServiceAccountEmail" `
        --role=$role --quiet | Out-Null
}

$bucketExists = gcloud storage buckets describe "gs://$Bucket" 2>$null
if (-not $bucketExists) {
    gcloud storage buckets create "gs://$Bucket" --location=$Region --uniform-bucket-level-access
}

gcloud storage buckets add-iam-policy-binding "gs://$Bucket" `
    --member=allUsers --role=roles/storage.objectViewer --quiet | Out-Null

$envVars = @(
    "GOOGLE_CLOUD_PROJECT=$ProjectId",
    "BUCKET=$Bucket",
    "DATASET=post_cronos",
    "TABLE=encuestas",
    "LOCATION=$Region",
    "MODEL=gemini-2.5-flash-lite",
    "MAX_UPLOAD_MB=10",
    "UPLOAD_PREFIX=uploads",
    "ALLOWED_ORIGINS=$AllowedOrigins"
) -join ","

gcloud run deploy $Service `
    --source $PSScriptRoot `
    --region $Region `
    --allow-unauthenticated `
    --service-account $ServiceAccountEmail `
    --set-env-vars $envVars `
    --memory 1Gi `
    --cpu 1 `
    --timeout 300 `
    --max-instances 3 `
    --quiet

$url = gcloud run services describe $Service --region $Region --format="value(status.url)"
Write-Output "API desplegada en: $url"
Write-Output "Configurá la web con: window.POST_CRONOS_API = '$url';"
