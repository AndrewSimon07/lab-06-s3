#!/usr/bin/env python3
import logging
import os
import boto3
import sys
import time
import requests
import json
from botocore.exceptions import ClientError



logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name="us-east-1")


def parse_args():
    if len(sys.argv) < 4:
        log.error("Usage: %s <list_file> <index_path> <bucket>", sys.argv[0])
        sys.exit(1)
    return sys.argv[1], sys.argv[2], sys.argv[3]


def download_books(list_file, dest_dir):
    """Download each URL in list_file into dest_dir"""
    os.makedirs(dest_dir, exist_ok=True)

    with open(list_file) as f:
        urls = []
        for line in f:
            if line.strip():            
                urls.append(line.strip())

    paths = []
    for url in urls:
        filename = url.rstrip("/").split("/")[-1] 
        path = os.path.join(dest_dir, filename)

        if os.path.exists(path):
            log.info("Already downloaded, skipping: %s", path)
            paths.append(path)
            continue

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(path, "wb") as out:
                out.write(response.content)
            log.info("Downloaded %s -> %s", url, path)
            paths.append(path)
        except requests.RequestException as e:
            log.error("Error downloading %s: %s", url, e)

        time.sleep(1) 

    return paths


def create_bucket(bucket):
    """bucket is bucket name"""

    try:
        # us-east-1: omit LocationConstraint or create_bucket fails
        s3.create_bucket(Bucket=bucket)
        log.info(f"Created bucket: {bucket}")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "BucketAlreadyOwnedByYou":
                log.info("Bucket already exists: %s", bucket)
                return True
        log.error("Error creating bucket %s: %s", bucket, e)
        return False

def make_public(bucket):
    """Turn off Block Public Access and allow anyone to read buckets"""
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket}/*",
            }
        ],
    }
    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        log.info("Bucket is now public: %s", bucket)
        return True
    except ClientError as e:
        log.error("Error making bucket %s public: %s", bucket, e)
        return False


def upload_files(bucket, file_paths):
    """Upload each file to the top level of the bucket"""
    count = 0
    for path in file_paths:
        key = os.path.basename(path)   # books/pg1342.txt -> pg1342.txt
        try:
            s3.upload_file(
                path, bucket, key,
                ExtraArgs={"ContentType": "text/plain; charset=utf-8"},
            )
            log.info("Uploaded %s -> s3://%s/%s", path, bucket, key)
            count += 1
        except (ClientError, FileNotFoundError) as e:
            log.error("Error uploading %s: %s", path, e)
    return count


def upload_index(bucket, index_path):
    """Upload the index page as index.html"""
    if not os.path.exists(index_path):
        log.error("Index file not found: %s", index_path)
        return False
    try:
        s3.upload_file(
            index_path, bucket, "index.html",
            ExtraArgs={"ContentType": "text/html"},
        )
        log.info("Uploaded index page: %s", index_path)
        return True
    except ClientError as e:
        log.error("Error uploading index %s: %s", index_path, e)
        return False


def main():
    list_file, index_path, bucket = parse_args()

    file_paths = download_books(list_file, "books")
    if not file_paths:
        log.error("No books were downloaded.")
        sys.exit(1)

    if not create_bucket(bucket):
        sys.exit(1)

    if not make_public(bucket):
        sys.exit(1)

    uploaded = upload_files(bucket, file_paths)
    index_ok = upload_index(bucket, index_path)

    url = f"https://{bucket}.s3.amazonaws.com/index.html"
    if index_ok and uploaded == len(file_paths):
        log.info("Success: uploaded %d books. Site: %s", uploaded, url)
    else:
        log.error("Finished with errors: %d of %d books uploaded, index %s. Site: %s",
                  uploaded, len(file_paths), "ok" if index_ok else "FAILED", url)


if __name__ == "__main__":
    main()