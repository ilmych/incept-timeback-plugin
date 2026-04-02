# S3 Upload Patterns

## Bucket

All uploads go to: `ai-first-incept-media`

## Images

```python
import boto3

s3 = boto3.client("s3")
s3.upload_file(
    str(local_path),
    "ai-first-incept-media",
    s3_key,
    ExtraArgs={"ContentType": content_type}
)
```

Content types: `image/png`, `image/jpeg`, `image/svg+xml`, `image/gif`

### Size Limits

Inceptstore upload API has ~750KB base64 limit. For larger images:

```python
from PIL import Image

def compress_for_upload(path, max_px=2000, qualities=[85, 70, 50, 30]):
    img = Image.open(path)
    if max(img.size) > max_px:
        img.thumbnail((max_px, max_px), Image.LANCZOS)
    for q in qualities:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=q)
        if buf.tell() < 700_000:  # under 700KB with margin
            return buf.getvalue()
    raise ValueError(f"Cannot compress {path} under 750KB")
```

### The "original.png" Problem

Multiple images share the same filename (`original.png`) with different hash paths. Hash the full URL path for unique S3 keys:

```python
import hashlib
unique_name = hashlib.md5(source_url.encode()).hexdigest()[:12] + "_" + filename
```

## Videos

```python
from concurrent.futures import ThreadPoolExecutor

def upload_video(s3, filepath, s3_key):
    s3.upload_file(
        str(filepath),
        "ai-first-incept-media",
        s3_key,
        ExtraArgs={"ContentType": "video/mp4"}
    )

# Parallel upload with 10 workers
with ThreadPoolExecutor(max_workers=10) as pool:
    for fp in video_files:
        pool.submit(upload_video, s3, fp, f"{PREFIX}{fp.name}")
```

## PCI JS Modules

```python
s3.put_object(
    Bucket="ai-first-incept-media",
    Key=f"pci-modules/{module_name}.js",
    Body=js_content.encode('utf-8'),
    ContentType="application/javascript",  # NOT text/javascript
    CacheControl="no-cache, no-store, must-revalidate",  # During dev
)
```

### Mandatory Post-Upload Verification

S3 has eventual consistency. Always verify after upload:

```python
import time
import requests

time.sleep(0.2)  # wait for S3 propagation
url = f"https://ai-first-incept-media.s3.amazonaws.com/pci-modules/{module_name}.js"
resp = requests.head(url, timeout=10)
assert resp.status_code == 200, f"Upload verification failed: {resp.status_code}"
```

For production (not dev), set proper cache headers:

```python
CacheControl="public, max-age=31536000, immutable"  # 1 year for versioned assets
```

## S3 Key Conventions

```
images/{course_prefix}/{unit}/{filename}          # Course images
videos/{course_prefix}/{unit}-{topic}.mp4          # Topic videos
pci-modules/{module_name}.js                       # PCI interactive modules
static-visuals/{course_prefix}/{visual_id}.svg     # SVG diagrams
```

## Batch Upload with Progress

```python
from tqdm import tqdm

failed = []
for path in tqdm(files, desc="Uploading"):
    try:
        s3.upload_file(str(path), BUCKET, key_for(path), ExtraArgs={"ContentType": mime_for(path)})
    except Exception as e:
        failed.append((path, str(e)))

if failed:
    print(f"\n{len(failed)} uploads failed:")
    for path, err in failed:
        print(f"  {path}: {err}")
```

## Cleanup

To remove uploaded assets (e.g., during course deletion):

```python
# List and delete all objects with prefix
paginator = s3.get_paginator("list_objects_v2")
for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
    for obj in page.get("Contents", []):
        s3.delete_object(Bucket=BUCKET, Key=obj["Key"])
```
