# AWS resources

The project's S3 bucket and SQS queues: what exists, how code should use them, and every setting with the reason for it. This is the single source of truth. If you change something in the console, update this file in the same PR.

## Quick info

| | |
|---|---|
| Account | `850870347029`. Sign in as your own IAM user (`aws login --profile cpsc454`), never root. |
| Region | **`us-east-1`**. Team IAM policies only allow SQS, EC2, RDS, Cognito and Logs there. |
| Bucket | `transcoding-titans-media-850870347029-us-east-1-an` |
| Job queue | `https://sqs.us-east-1.amazonaws.com/850870347029/transcoding-titans-jobs` |
| Dead-letter queue | `arn:aws:sqs:us-east-1:850870347029:transcoding-titans-jobs-dlq` |
| Naming | Every resource starts with `transcoding-titans-`. IAM only allows that prefix. |
| Tag | `Project = TranscodingTitans` on everything. The exact value is required to create EC2, RDS and Cognito resources. |

Created 2026-11-11 by Eli and verified. **Open item:** the bucket's `abort-incomplete-multipart` lifecycle rule hasn't been added yet.

Check access and settings (read-only; prints a `WARNING` for anything that doesn't match this file):

```bash
AWS_PROFILE=cpsc454 S3_BUCKET=transcoding-titans-media-850870347029-us-east-1-an \
  SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/850870347029/transcoding-titans-jobs \
  uv run python scripts/check_aws.py
```

In the console, switch to **US East (N. Virginia)**. Members don't have `s3:ListAllMyBuckets` or `sqs:ListQueues`, so lists may be empty or say "Access denied". Open resources by searching for their name.

## Rules for code

- **Credentials:** use the default boto3 chain. Locally that's your `aws login` profile; on AWS it's an IAM role. Never use access keys. The worker's EC2 role must be named `transcoding-titans-ec2-worker-role`, the only role members can pass to EC2.
- **Object keys:** `uploads/<uploadId>.mp4` for raw uploads, and `outputs/<jobId>/video_<res>.mp4`, `…_transcript.json`, `…_transcript.srt` for results. These match `local_data/storage/` today.
- **Uploads:** the browser POSTs straight to S3 with a presigned POST. Its conditions must enforce the exact key, `Content-Type: video/mp4`, and `content-length-range` up to `MAX_UPLOAD_BYTES`. The bucket can't enforce these itself.
- **Downloads:** presigned GET URLs only. Refuse to sign once a job is past `expiresAt`, because lifecycle deletion can lag by up to a day.
- **Workers:**
  - Long-poll with `WaitTimeSeconds=20`.
  - **Be idempotent**: a standard queue can deliver the same `jobId` twice.
  - Call `ChangeMessageVisibility` every few minutes on long jobs, since the 1-hour timeout can run out on a 2-hour video.
  - Delete the message only after the outputs are uploaded.
- **Retention** is handled by the lifecycle rules. Don't write cleanup code.

## S3 bucket

| Setting | Value | Why |
|---|---|---|
| Namespace | Account Regional (`-850870347029-us-east-1-an` suffix) | No other account can ever claim this name, even after the bucket is deleted. |
| Object Ownership | ACLs disabled | Access is decided only by IAM and the bucket policy, never by legacy ACLs. |
| Block Public Access | All four on | Nothing is public; users only get presigned URLs. |
| Versioning | Off | Deleted and expired files would otherwise linger as hidden versions. |
| Encryption | SSE-S3 | Encrypted at rest for free. SSE-KMS would add key-usage logs at about $1/month plus `kms:` permissions on every role. |
| Bucket policy | Deny non-TLS requests and TLS older than 1.2 | Encryption in transit. Only denies; grants nothing. |
| CORS | `POST` from `http://localhost:5173` | Lets the browser's upload `fetch` read S3's response. Add the deployed `https://` origin later, never `*`. |
| Lifecycle | `uploads/` 1 day, `outputs/` 7 days, incomplete multipart uploads 1 day | Uploads are only needed until the job runs. 7 days matches `RETENTION_DAYS` ("Expires in N days"). |
| Object Lock, website hosting | Off | Object Lock blocks expiry, and website hosting needs public access. |

<details>
<summary>Bucket policy and CORS JSON</summary>

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::transcoding-titans-media-850870347029-us-east-1-an",
        "arn:aws:s3:::transcoding-titans-media-850870347029-us-east-1-an/*"
      ],
      "Condition": { "Bool": { "aws:SecureTransport": "false" } }
    },
    {
      "Sid": "DenyOldTls",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::transcoding-titans-media-850870347029-us-east-1-an",
        "arn:aws:s3:::transcoding-titans-media-850870347029-us-east-1-an/*"
      ],
      "Condition": { "NumericLessThan": { "s3:TlsVersion": "1.2" } }
    }
  ]
}
```

```json
[{ "AllowedOrigins": ["http://localhost:5173"], "AllowedMethods": ["POST"], "MaxAgeSeconds": 3000 }]
```

</details>

## SQS queues

Both are **standard** queues with SSE-SQS encryption, 20 s long polling, no delivery delay and the default max message size.

| Setting | `transcoding-titans-jobs` | `transcoding-titans-jobs-dlq` | Why |
|---|---|---|---|
| Visibility timeout | 1 hour | 30 s | Hides a job while a worker runs it. The DLQ isn't consumed by workers. |
| Retention | 1 day | 14 days | Jobs are stale once their upload expires. The DLQ must outlast the source queue, because message age counts from the original send. |
| Dead-letter queue | DLQ after **3** receives | n/a | Stop retrying a job that keeps failing. |
| Redrive allow policy | n/a | Only `transcoding-titans-jobs` | Other queues can't use our DLQ. |
| Access policy | Owner account + deny non-TLS | Same | Each user or role still needs its own IAM permission; no other account gets access. |

Optional: a CloudWatch alarm on the DLQ when `ApproximateNumberOfMessagesVisible >= 1`.

<details>
<summary>Queue access policy JSON (replace <code>QUEUE_NAME</code>)</summary>

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "OwnerAccount",
      "Effect": "Allow",
      "Principal": { "AWS": "850870347029" },
      "Action": "sqs:*",
      "Resource": "arn:aws:sqs:us-east-1:850870347029:QUEUE_NAME"
    },
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "sqs:*",
      "Resource": "arn:aws:sqs:us-east-1:850870347029:QUEUE_NAME",
      "Condition": { "Bool": { "aws:SecureTransport": "false" } }
    }
  ]
}
```

</details>

To recreate a queue in the console: create the DLQ first, then the job queue pointing at it, then edit the DLQ to set its redrive allow policy.

## App IAM roles (not created yet)

Least-privilege policies for when the API and workers run on AWS. How workers report results back is still undecided, so that isn't included.

<details>
<summary>API role: presign uploads/downloads, delete job files, enqueue jobs</summary>

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "PresignUploads", "Effect": "Allow", "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::transcoding-titans-media-850870347029-us-east-1-an/uploads/*" },
    { "Sid": "PresignDownloads", "Effect": "Allow", "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::transcoding-titans-media-850870347029-us-east-1-an/outputs/*" },
    { "Sid": "DeleteJobFiles", "Effect": "Allow", "Action": "s3:DeleteObject",
      "Resource": [
        "arn:aws:s3:::transcoding-titans-media-850870347029-us-east-1-an/uploads/*",
        "arn:aws:s3:::transcoding-titans-media-850870347029-us-east-1-an/outputs/*"
      ] },
    { "Sid": "EnqueueJobs", "Effect": "Allow", "Action": "sqs:SendMessage",
      "Resource": "arn:aws:sqs:us-east-1:850870347029:transcoding-titans-jobs" }
  ]
}
```

</details>

<details>
<summary>Worker role (<code>transcoding-titans-ec2-worker-role</code>): read uploads, write outputs, process the queue</summary>

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "ReadUploads", "Effect": "Allow", "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::transcoding-titans-media-850870347029-us-east-1-an/uploads/*" },
    { "Sid": "WriteOutputs", "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:AbortMultipartUpload"],
      "Resource": "arn:aws:s3:::transcoding-titans-media-850870347029-us-east-1-an/outputs/*" },
    { "Sid": "ProcessJobs", "Effect": "Allow",
      "Action": ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility"],
      "Resource": "arn:aws:sqs:us-east-1:850870347029:transcoding-titans-jobs" }
  ]
}
```

</details>
