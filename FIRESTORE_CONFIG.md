# Firestore Configuration

This document explains how to configure the Firestore database settings for the AI News Agent.

## Environment Variables

The Firestore implementation supports the following environment variables:

### Required
- `GOOGLE_CLOUD_PROJECT`: Your Google Cloud project ID

### Optional
- `FIRESTORE_DATABASE_ID`: Firestore database ID (defaults to `"(default)"`)
- `FIRESTORE_COLLECTION_NAME`: Collection name for storing news (defaults to `"news"`)
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to your service account key file (for local development)

## Configuration Examples

### 1. Using Environment Variables (Recommended)

Create a `.env` file in your project root:

```bash
# Required
GOOGLE_CLOUD_PROJECT=your-project-id

# Optional - customize these if needed
FIRESTORE_DATABASE_ID=(default)
FIRESTORE_COLLECTION_NAME=news

# For local development
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
```

### 2. Using System Environment Variables

```bash
export GOOGLE_CLOUD_PROJECT="your-project-id"
export FIRESTORE_DATABASE_ID="(default)"
export FIRESTORE_COLLECTION_NAME="news"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
```

### 3. Programmatic Configuration

You can also create a Firestore manager with custom settings:

```python
from app.tools.firestore_tools import create_firestore_manager

# Create manager with custom settings
manager = create_firestore_manager(
    project_id="my-custom-project",
    database_id="my-news-database",
    collection_name="ai_news"
)
```

## Database Structure

The news items are stored in Firestore with the following structure:

```
Collection: {FIRESTORE_COLLECTION_NAME} (default: "news")
├── Document ID: news_{url_hash} (Firestore-safe hash of URL)
└── Fields:
    ├── title: string
    ├── url: string (unique identifier)
    ├── date: string
    ├── domain: string
    └── created_at: timestamp
```

**Note**: Document IDs are generated using a SHA-256 hash of the URL to ensure Firestore compatibility. URLs containing special characters (like `/`, `?`, `#`) are safely handled by using the hash as the document ID while storing the original URL in the `url` field.

## Setting Up Google Cloud

1. **Create a Google Cloud Project** (if you don't have one)
2. **Enable Firestore API** in your project
3. **Create a Firestore Database** (Native mode recommended)
4. **Set up authentication**:
   - For local development: Download a service account key
   - For production: Use Application Default Credentials

## Example Service Account Permissions

Your service account needs the following IAM roles:
- `Cloud Datastore User` (for Firestore operations)
- `Firebase Admin` (if using Firebase features)

## Multiple Environments

You can use different configurations for different environments:

### Development
```bash
GOOGLE_CLOUD_PROJECT=my-project-dev
FIRESTORE_DATABASE_ID=(default)
FIRESTORE_COLLECTION_NAME=news_dev
```

### Production
```bash
GOOGLE_CLOUD_PROJECT=my-project-prod
FIRESTORE_DATABASE_ID=(default)
FIRESTORE_COLLECTION_NAME=news_prod
```

## Troubleshooting

### Common Issues

1. **Authentication Error**: Make sure `GOOGLE_APPLICATION_CREDENTIALS` points to a valid service account key
2. **Project Not Found**: Verify `GOOGLE_CLOUD_PROJECT` is correct
3. **Database Not Found**: Check if the Firestore database exists in your project
4. **Permission Denied**: Ensure your service account has the required IAM roles

### Testing Configuration

You can test your configuration by running:

```python
from app.tools.firestore_tools import create_firestore_manager

try:
    manager = create_firestore_manager()
    print(f"Connected to project: {manager.project_id}")
    print(f"Using database: {manager.database_id}")
    print(f"Collection: {manager.collection_name}")
except Exception as e:
    print(f"Configuration error: {e}")
```
