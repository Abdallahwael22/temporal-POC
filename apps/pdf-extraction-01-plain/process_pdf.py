"""
Phase 1 — Plain Python PDF-to-Markdown pipeline.
Usage: 
      $ python process_pdf.py s3://temporalpoc/files/ragcheatsheet.pdf
"""

import os
import sys
import tempfile
import logging
from pathlib import Path

import boto3
import pymupdf4llm
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

load_dotenv()

AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_REGION = os.environ["AWS_REGION"]
AWS_S3_ENDPOINT_URL = os.environ["AWS_S3_ENDPOINT_URL"]
S3_BUCKET = os.environ["S3_BUCKET"]
TEMP_DIR = os.environ["TEMP_DIR"]

os.makedirs(TEMP_DIR, exist_ok=True)

# ── S3 helper ────────────────────────────────────────────────────────────────

def get_s3_client():
    return boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        endpoint_url=AWS_S3_ENDPOINT_URL,
    )

def parse_s3_path(s3_path: str):
    s3_path_no_scheme = s3_path.replace("s3://", "")
    bucket, _, key =  s3_path_no_scheme.partition("/")
    return bucket, key

# ── Step 1: Download ─────────────────────────────────────────────────────────
def download_pdf(s3_path: str) -> str:
    """Download a PDF from S3. Returns local file path."""
    bucket, key = parse_s3_path(s3_path)
    filename = Path(key).name

    local_path = str(Path(TEMP_DIR) / filename)

    log.info(f"Downloading: s3://{bucket}/{key} => {local_path}")

    s3_client = get_s3_client()
    s3_client.download_file(
        bucket,
        key,
        local_path
    )

    log.info(f"COMPLETED Downloading : {local_path} ")
    return local_path

# ── Step 2: Extract to Markdown ───────────────────────────────────────────────
def extract_to_markdown(local_pdf_path: str) -> str:
    """Extract text from PDF and convert to Markdown. Returns markdown string."""
    log.info(f"Extracting text from {local_pdf_path}")
    markdown_text = pymupdf4llm.to_markdown(local_pdf_path)

    log.info(f"Extraction complete — {len(markdown_text)} characters")
    return markdown_text

# ── Step 3: Upload Markdown ──────────────────────────────────────────────────
def upload_markdown(markdown_text: str, original_s3_path: str) -> str:
    """Upload markdown content to S3. Returns the output S3 path."""
    bucket, key = parse_s3_path(original_s3_path)
    md_key = key.replace(".pdf", ".md")

    log.info(f"Uploading markdown → s3://{bucket}/{md_key}")
    s3_client = get_s3_client()

    s3_client.put_object(
        Bucket=bucket,
        Key=md_key,

        Body=markdown_text.encode("utf-8"),
        ContentType="text/markdown",
    )

    output_path = f"s3://{bucket}/{md_key}"
    log.info(f"Upload complete: {output_path}")
    return output_path

# ── Main pipeline ─────────────────────────────────────────────────────────────
def process_pdf(s3_input_path: str) -> str:
    """Run the full pipeline. Returns the output S3 path."""

    log.info(f"Starting pipeline for: {s3_input_path}")

    local_pdf  = download_pdf(s3_input_path)
    markdown   = extract_to_markdown(local_pdf)
    output_s3  = upload_markdown(markdown, s3_input_path)

    # Clean up temp file
    os.remove(local_pdf)

    log.info(f"Pipeline complete. Output: {output_s3}")
    return output_s3

if __name__ == "__main__":


    output_s3 = process_pdf(
        sys.argv[1]
    )

    print(f"\nDone! Markdown saved to: {output_s3}")
