# AWS resources

The project's S3 bucket, SQS queues and Cognito user pool: what exists, how code should use them, and every setting with the reason for it. This is the single source of truth. If you change something in the console, update this file in the same PR.

## Quick info

| | |
|---|---|
| Account | `850870347029`. Sign in as your own IAM user (`aws login --profile my-profile`), never root. |
| Region | **`us-east-1`**. Team IAM policies only allow SQS, EC2, RDS, Cognito and Logs there. |
| Bucket | `transcoding-titans-media-850870347029-us-east-1-an` |
| Job queue | `https://sqs.us-east-1.amazonaws.com/850870347029/transcoding-titans-jobs` |
| Dead-letter queue | `arn:aws:sqs:us-east-1:850870347029:transcoding-titans-jobs-dlq` |
| Results queue | `https://sqs.us-east-1.amazonaws.com/850870347029/transcoding-titans-results` (workers → API) |
| User pool | `us-east-1_ykiHRApQj` ("User pool - 5roma9"), app client `transcoding-titans-web` (`36eotca2knemj5q1sddj7suvhl`), login at `https://us-east-1ykihrapqj.auth.us-east-1.amazoncognito.com` |
| Naming | Every resource starts with `transcoding-titans-`. IAM only allows that prefix. |
| Tag | `Project = TranscodingTitans` on everything. The exact value is required to create EC2, RDS and Cognito resources. |

Created 2026-11-11 by Eli and verified. **Open item:** the bucket's `abort-incomplete-multipart` lifecycle rule hasn't been added yet.

Check access and settings (read-only; prints a `WARNING` for anything that doesn't match this file). Replace `my-profile` with your AWS CLI profile name; the README has Windows versions:

```bash
AWS_PROFILE=my-profile S3_BUCKET=transcoding-titans-media-850870347029-us-east-1-an \
  SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/850870347029/transcoding-titans-jobs \
  uv run python scripts/check_aws.py
```

In the console, switch to **US East (N. Virginia)**. Members don't have `s3:ListAllMyBuckets` or `sqs:ListQueues`, so lists may be empty or say "Access denied". Open resources by searching for their name.

## Rules for code

- **Credentials:** use the default boto3 chain. Locally that's your `aws login` profile; on AWS it's an IAM role. Never use access keys. The worker's EC2 role must be named `transcoding-titans-ec2-worker-role`, the only role members can pass to EC2.
- **Object keys:** `uploads/<userId>/<uploadId>.mp4` for raw uploads, and `outputs/<userId>/<jobId>/video_<res>.mp4`, `…_transcript.json`, `…_transcript.srt` for results. `userId` is the Cognito `sub`. All S3 calls are in `api/storage.py`.
- **Uploads:** the browser POSTs straight to S3 with a presigned POST. Its conditions must enforce the exact key, `Content-Type: video/mp4`, and `content-length-range` up to `MAX_UPLOAD_BYTES`. The bucket can't enforce these itself.
- **Downloads:** presigned GET URLs only. Refuse to sign once a job is past `expiresAt`, because lifecycle deletion can lag by up to a day.
- **Workers** (`worker/main.py`):
  - Long-poll with `WaitTimeSeconds=20`, one job at a time.
  - **Idempotent**: a standard queue can deliver the same `jobId` twice. A repeat run writes the same keys, and the API ignores results for finished jobs.
  - Extend the message's visibility every 10 minutes while a job runs, since the 1-hour timeout can run out on a 2-hour video.
  - Report `started` and the result on the results queue, then delete the job message. Malformed job messages are left alone so they land in the DLQ.
  - **No database access.** Workers handle untrusted video, so they only get S3 and SQS. The API applies their reports, only moves jobs forward, and rejects result keys outside the job's `outputs/<userId>/<jobId>/` folder.
- **Retention** is handled by the lifecycle rules. Don't write cleanup code.
- **Auth:** users sign in on Cognito's managed login page; our login form never sees a password. The API owns the whole OAuth flow (see [Cognito user pool](#cognito-user-pool)). Every endpoint gets the user from the session, and a job's owner is the user's Cognito `sub`.

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

**`transcoding-titans-results`** (workers → API) is also standard, SSE-SQS, 20 s long polling and the same access policy. Visibility timeout **60 s** (the API applies a report in milliseconds), retention **4 days** (reports wait out an API outage over a weekend), **no DLQ** (the API drops malformed reports itself; a failed database write is retried).

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

## Cognito user pool

Created 2026-11-14 in the console and verified (every setting read back; the login page loads). Sign-up, sign-in, password reset and MFA all happen on Cognito's **managed login** pages, so passwords never reach our code. The API is a confidential OAuth client: it runs the authorization code flow with PKCE, `state` and `nonce`, then keeps its own session.

**Login flow:**
1. The browser opens `GET /auth/login` (or `/auth/signup`) on the API.
2. The API redirects to managed login. It stores `state`, `nonce` and the PKCE verifier in a short-lived httpOnly cookie.
3. Cognito redirects back to `GET /auth/callback`. The API checks `state`, exchanges the code using the client secret and PKCE verifier, and validates the ID token (signature via JWKS, `iss`, `aud`, `token_use`, `exp`, `nonce`).
4. The API creates a server-side session (random ID, `sub` and email, 8-hour expiry) and sets an httpOnly, Secure, `SameSite=Lax` cookie. It then redirects to the frontend.
5. **Logout:** the API deletes the session, clears the cookie and redirects to Cognito's `/logout`, which ends the managed login session too.

The API discards Cognito's tokens after login; its own session is what counts. The flow cookies must be `SameSite=Lax`, not `Strict`, because the callback is a cross-site redirect from Cognito's domain.

### Settings

| Setting | Value | Why |
|---|---|---|
| Feature plan | Essentials (the default) | Required for managed login. Plus adds threat protection (compromised-password checks, adaptive MFA) at a per-user cost; optional upgrade. |
| Sign-in identifier | Email, case-insensitive | Simple for users. **Can't be changed after creation.** |
| Self-registration | On, email required and auto-verified | Anyone can sign up, but must prove they own the email. Email is the only attribute collected (minimal personal data). |
| Email changes | Keep the old email active until the new one is verified | Stops an account being moved to an unverified address. |
| Password policy | 12+ characters, upper, lower, number and symbol; the last 5 passwords can't be reused | Strong passwords. Cognito does the hashing and lockout. |
| MFA | **Required**, authenticator app (TOTP) only | Protects accounts even if a password leaks. No SMS: it costs money and is open to SIM-swap attacks. Managed login walks users through setup. |
| Account recovery | Verified email only | No SMS. |
| Email sending | Cognito default | Free, about 50 emails/day; enough for class. Production would use SES. |
| Deletion protection | Active | The pool can't be deleted by accident, which would delete every account. |
| Domain | Cognito prefix `us-east-1ykihrapqj` (picked by the console), managed login (v2) with the default style | The hosted login and sign-up pages. |
| App client | `transcoding-titans-web`, **with** a client secret | Confidential client: only the API ever holds the secret. It never goes in the frontend or git. |
| OAuth | Authorization code grant only; scopes `openid email`; Cognito as the only identity provider | No implicit grant (it puts tokens in URLs). No `profile` or `aws.cognito.signin.user.admin` scopes (least privilege). |
| Callback / sign-out URLs | `http://localhost:8000/auth/callback` / `http://localhost:5173/` | Must match exactly. Add the deployed `https://` URLs later. |
| Auth flows | SRP and refresh only | Never `USER_PASSWORD_AUTH`/`ADMIN_USER_PASSWORD_AUTH`, which send raw passwords to the API. |
| Prevent user existence errors | On | Login errors don't reveal whether an email is registered. |
| Token validity | Access and ID tokens 60 min, refresh token 60 min (the minimum); token revocation on | The API only uses the ID token once at login, so short lifetimes limit any leak. |

**How it was created:** with the console's "Set up resources for your application" wizard (Traditional web application, email sign-in, self-registration). The settings above were then applied in the console. Two things to know if you ever redo it:

- **Tags:** the wizard can't add tags, and members can only manage pools tagged `Project=TranscodingTitans`. Root added the tag after creation.
- **Managed login version:** the console couldn't switch the domain to managed login, because members lack `DescribeUserPoolDomain`. It was switched with `aws cognito-idp update-user-pool-domain --managed-login-version 2`.

**API configuration**, in the repo root's `.env` (gitignored; never prefix these with `VITE_`). The IDs aren't secret. **The client secret is:** get it from App clients → `transcoding-titans-web` → Show client secret, or from a teammate privately. Never put it in chat or git. On AWS, read it from a secret store.

```
COGNITO_USER_POOL_ID=us-east-1_ykiHRApQj
COGNITO_CLIENT_ID=36eotca2knemj5q1sddj7suvhl
COGNITO_DOMAIN=https://us-east-1ykihrapqj.auth.us-east-1.amazoncognito.com
COGNITO_CLIENT_SECRET=
```

## App IAM roles (not created yet)

Least-privilege policies for when the API and workers run on AWS.

<details>
<summary>API role: presign uploads/downloads, check objects exist, delete job files, enqueue jobs, read worker reports</summary>

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "PresignUploads", "Effect": "Allow", "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::transcoding-titans-media-850870347029-us-east-1-an/uploads/*" },
    { "Sid": "PresignDownloadsAndHead", "Effect": "Allow", "Action": "s3:GetObject",
      "Resource": [
        "arn:aws:s3:::transcoding-titans-media-850870347029-us-east-1-an/uploads/*",
        "arn:aws:s3:::transcoding-titans-media-850870347029-us-east-1-an/outputs/*"
      ] },
    { "Sid": "DeleteJobFiles", "Effect": "Allow", "Action": "s3:DeleteObject",
      "Resource": [
        "arn:aws:s3:::transcoding-titans-media-850870347029-us-east-1-an/uploads/*",
        "arn:aws:s3:::transcoding-titans-media-850870347029-us-east-1-an/outputs/*"
      ] },
    { "Sid": "EnqueueJobs", "Effect": "Allow", "Action": "sqs:SendMessage",
      "Resource": "arn:aws:sqs:us-east-1:850870347029:transcoding-titans-jobs" },
    { "Sid": "ReadReports", "Effect": "Allow", "Action": ["sqs:ReceiveMessage", "sqs:DeleteMessage"],
      "Resource": "arn:aws:sqs:us-east-1:850870347029:transcoding-titans-results" }
  ]
}
```

</details>

<details>
<summary>Worker role (<code>transcoding-titans-ec2-worker-role</code>): read uploads, write outputs, process the queue, send reports</summary>

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
      "Resource": "arn:aws:sqs:us-east-1:850870347029:transcoding-titans-jobs" },
    { "Sid": "SendReports", "Effect": "Allow", "Action": "sqs:SendMessage",
      "Resource": "arn:aws:sqs:us-east-1:850870347029:transcoding-titans-results" }
  ]
}
```

</details>
