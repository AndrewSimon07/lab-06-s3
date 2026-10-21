#!/bin/bash
set -euo pipefail


# Check for 3 arguments
if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <book_url> <bucket> <expires_seconds>" >&2
    exit 1
fi

URL="$1"
BUCKET="$2"
EXPIRES="$3"
FILENAME="$(basename "$URL")"    

# Download the book into books/
mkdir -p books
curl -fsSL -o "books/$FILENAME" "$URL"

# Create the bucket unless it already exists
if ! aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    aws s3 mb "s3://$BUCKET"
fi

# Upload the book
aws s3 cp "books/$FILENAME" "s3://$BUCKET/$FILENAME" \
    --content-type "text/plain; charset=utf-8"

aws s3 presign "s3://$BUCKET/$FILENAME" --expires-in "$EXPIRES"