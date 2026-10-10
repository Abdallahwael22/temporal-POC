from datetime import timedelta
from dataclasses import dataclass

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activities — use the string-based import pattern to keep
# the workflow sandbox clean (required by Temporal Python SDK)
with workflow.unsafe.imports_passed_through():
    from activities import (
        download_pdf,
        extract_to_markdown,
        upload_markdown,
    )

    from helpers import (
        DownloadInput,
        ExtractInput,
        UploadInput,
    )

@dataclass
class PDFPipelineInput:
    s3_path: str   # e.g. "s3://my-pdfs-bucket/reports/annual-report.pdf"

@dataclass
class PDFPipelineOutput:
    output_s3_path: str  # e.g. "s3://my-markdown-bucket/reports/annual-report.md"




DEFAULT_RETRY = RetryPolicy(    
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0, # double the wait each retry: 2s, 4s, 8s
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=5
)



@workflow.defn
class PDFPipelineWorkflow:

    @workflow.run
    async def run(self, params: PDFPipelineInput) -> PDFPipelineOutput:

        workflow.logger.info(f"Starting PDF pipeline for: {params.s3_path}")
        
        # ── Step 1: Download PDF from S3 ─────────────────────────────────────
        download_result = await workflow.execute_activity(
            download_pdf,
            DownloadInput(s3_path=params.s3_path),
            retry_policy=DEFAULT_RETRY,
            start_to_close_timeout=timedelta(minutes=3),
        )

        # ── Step 2: Extract PDF to Markdown ──────────────────────────────────
        extract_result = await workflow.execute_activity(
            extract_to_markdown,
            ExtractInput(local_path=download_result.local_path),
            retry_policy=DEFAULT_RETRY,
            start_to_close_timeout=timedelta(minutes=10),
        )


        # ── Step 3: Upload Markdown to S3 ────────────────────────────────────
        upload_result = await workflow.execute_activity(
            upload_markdown,
            UploadInput(markdown_text=extract_result.markdown_text,
                        original_s3_path=params.s3_path),
            retry_policy=DEFAULT_RETRY,
            start_to_close_timeout=timedelta(minutes=3),
        )

        workflow.logger.info(f"Pipeline complete. Output: {upload_result.output_s3_path}")

        return PDFPipelineOutput(
            output_s3_path=upload_result.output_s3_path
        )
