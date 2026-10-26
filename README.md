# Temporal POC: PDF Extraction

This repository contains proof-of-concept implementations for processing PDF files from S3, converting them to Markdown using [PyMuPDF4LLM](https://github.com/pymupdf/RAG), and uploading the results back to S3. It demonstrates both a simple synchronous pipeline and a durable, orchestrated workflow using [Temporal](https://temporal.io/).

## Architecture Overview

The project is organized into three applications under `apps/`:

| App | Purpose | Description |
|---|---|---|
| [`pdf-extraction-01-plain`](apps/pdf-extraction-01-plain/) | Baseline (non-Temporal) | A straightforward Python script that downloads, extracts, and uploads PDFs in a single synchronous flow. |
| [`pdf-extraction-01-temporal`](apps/pdf-extraction-01-temporal/) | Temporal Orchestration | A Temporal workflow implementation split into Activities (download, extract, upload) with retry policies, timeouts, and durable execution. |
| [`client-app`](apps/client-app/) | API Client | A FastAPI service that acts as a client to the Temporal server, allowing you to start or execute PDF processing workflows via HTTP endpoints. |

## How It Works

### Plain Implementation
1. **Download** - Fetches a PDF from S3 using boto3
2. **Extract** - Converts the PDF to Markdown using `pymupdf4llm.to_markdown()`
3. **Upload** - Writes the Markdown back to S3 with `.md` extension
4. **Cleanup** - Removes the local temporary file

### Temporal Implementation
The Temporal version follows Temporal best practices:

- **Workflow** ([`workflow_process_pdf.py`](apps/pdf-extraction-01-temporal/workflow_process_pdf.py)) - Orchestrates the pipeline with defined timeouts and retry policies. Uses `workflow.unsafe.imports_passed_through()` to safely import activities.
- **Activities** ([`activities.py`](apps/pdf-extraction-01-temporal/activities.py)) - Each step (download, extract, upload) is a separate activity with its own execution context and can be retried independently on failure.
- **Worker** ([`worker.py`](apps/pdf-extraction-01-temporal/worker.py)) - Polls the Temporal task queue and executes workflows and activities.
- **Helpers** ([`helpers.py`](apps/pdf-extraction-01-temporal/helpers.py)) - Shared S3 utilities and dataclasses for serializing inputs/outputs between workflow and activities.

### Client App
The FastAPI client decouples API requests from worker code. It connects to Temporal, references workflows by name, and can either:
- **Execute synchronously** (`POST /process-pdf/execute`) - Start workflow and wait for completion, returning the result
- **Start asynchronously** (`POST /process-pdf/start`) - Start workflow and return immediately with the workflow ID
- **Query status** (`GET /workflow/status/{workflow_id}`) - Check execution status and retrieve results if completed

The client also includes endpoints for contract review workflows (see API documentation in [main.py](apps/client-app/main.py)).

## Prerequisites

- Python 3.9+
- Access to an S3-compatible object store (or AWS S3)
- A running [Temporal Server](https://docs.temporal.io/self-hosted-guide/setup) (local dev server via `temporal server start-dev` is sufficient)
- `uv` or `pip` for dependency management

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/your-org/temporal-POC.git
cd temporal-POC
```

### 2. Configure environment variables

Each app has its own `.env.example`. Copy and fill in your values:

#### For plain implementation
```bash
cp apps/pdf-extraction-01-plain/.env.example apps/pdf-extraction-01-plain/.env
```
Edit `apps/pdf-extraction-01-plain/.env`:
```env
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-west-2
AWS_S3_ENDPOINT_URL=https://your-s3-endpoint
S3_BUCKET=your-bucket-name
TEMP_DIR=/tmp/pdf-pipeline
```

#### For Temporal implementation
```bash
cp apps/pdf-extraction-01-temporal/.env.example apps/pdf-extraction-01-temporal/.env
```
You'll need S3 credentials plus Temporal configuration (same keys as plain plus Temporal settings). Check the actual `.env` files for required fields.

#### For client app
```bash
cp apps/client-app/.env.example apps/client-app/.env
```
```env
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_PDF_PROCESS_TASK_QUEUE=pdf-pipeline-queue
TEMPORAL_CONTRACT_REVIEW_TASK_QUEUE=contract-review-queue
```

### 3. Install dependencies

```bash
# Plain version
pip install -r apps/pdf-extraction-01-plain/requirements.txt

# Temporal worker
pip install -r apps/pdf-extraction-01-temporal/requirements.txt

# Client API
pip install -r apps/client-app/requirements.txt
```

## Usage

### Option 1: Run the plain script
```bash
cd apps/pdf-extraction-01-plain
python process_pdf.py s3://your-bucket/path/to/document.pdf
```

### Option 2: Run with Temporal

You'll need three components running:

1. **Start Temporal server** (in a separate terminal):
```bash
temporal server start-dev
```

2. **Start the worker** (in a separate terminal):
```bash
cd apps/pdf-extraction-01-temporal
python worker.py
```
The worker will poll the task queue `pdf-pipeline-queue` for work.

3. **Start the client API** (in a separate terminal):
```bash
cd apps/client-app
uvicorn main:app --reload --port 5000
```

4. **Trigger processing**:
```bash
# Execute and wait for result
curl -X POST http://localhost:5000/process-pdf/execute \
  -H "Content-Type: application/json" \
  -d '{"s3_path": "s3://your-bucket/path/to/document.pdf"}'

# Or start async and poll status
curl -X POST http://localhost:5000/process-pdf/start \
  -H "Content-Type: application/json" \
  -d '{"s3_path": "s3://your-bucket/path/to/document.pdf"}'

curl http://localhost:5000/workflow/status/<workflow-id>
```

## Key Differences: Plain vs Temporal

| Aspect | Plain | Temporal |
|---|---|---|
| **Execution** | Synchronous, all-or-nothing | Durable, resumable on failure |
| **Retries** | Manual/error-prone | Automatic with configurable retry policies (exponential backoff) |
| **Visibility** | Logs only | Full execution history in Temporal UI (`http://localhost:8233`) |
| **Scalability** | Single process | Distributed workers can scale independently |
| **Timeouts** | None built-in | Activity timeouts prevent hanging tasks |
| **Observability** | Limited | Query workflow state, inspect history, replay executions |

## Dependencies

- **[boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)** - AWS S3 SDK
- **[PyMuPDF4LLM](https://github.com/pymupdf/RAG)** - PDF to Markdown conversion optimized for LLMs
- **[Temporal Python SDK](https://docs.temporal.io/develop/python)** - Workflow orchestration
- **[FastAPI](https://fastapi.tiangolo.com/)** - API framework for the client app
- **[python-dotenv](https://pypi.org/project/python-dotenv/)** - Environment variable management

## License

See [LICENSE](LICENSE) for details.
