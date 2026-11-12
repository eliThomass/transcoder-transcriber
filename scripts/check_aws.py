"""Read-only AWS connectivity check: uv run python scripts/check_aws.py

Uses the default boto3 credential chain (`aws login` / SSO profile); never put keys in code.
Optional env vars: S3_BUCKET, SQS_QUEUE_URL (AWS_PROFILE / AWS_REGION pick the profile and region).
Nothing is created or modified. Exits 1 if AWS can't be reached; security warnings don't fail it.
"""
import os
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError

BLOCK_PUBLIC_ACCESS = ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")


def check_identity(session: boto3.Session) -> list[str]:
    creds = session.get_credentials()
    if creds is None:
        raise RuntimeError("no AWS credentials found; run `aws login` (or `aws sso login`)")
    ident = session.client("sts").get_caller_identity()
    print(f"identity: {ident['Arn']} (account {ident['Account']})")
    print(f"credentials: {creds.method}, region: {session.region_name}")
    # IAM user access keys have no session token; temporary (login/SSO/role) credentials do.
    if creds.get_frozen_credentials().token is None:
        return ["long-lived access keys in use; prefer temporary credentials from `aws login` or SSO"]
    return []


def read_setting(call, missing_code: str, label: str) -> tuple[dict | None, list[str]]:
    """Run a Get* call; a missing config or AccessDenied becomes a warning instead of a failure."""
    try:
        return call(), []
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == missing_code:
            return None, [f"{label} not configured"]
        if code == "AccessDenied":
            return None, [f"can't read {label} (access denied)"]
        raise


def check_bucket(session: boto3.Session, bucket: str) -> list[str]:
    # Expected settings are in docs/aws-resources.md.
    s3 = session.client("s3")
    s3.head_bucket(Bucket=bucket)  # raises on 403/404
    print(f"s3: bucket {bucket} reachable")
    warnings = []

    pab, w = read_setting(lambda: s3.get_public_access_block(Bucket=bucket),
                          "NoSuchPublicAccessBlockConfiguration", "Block Public Access")
    warnings += w
    if pab and (off := [k for k in BLOCK_PUBLIC_ACCESS if not pab["PublicAccessBlockConfiguration"].get(k)]):
        warnings.append(f"Block Public Access not fully on: {', '.join(off)}")

    enc, w = read_setting(lambda: s3.get_bucket_encryption(Bucket=bucket),
                          "ServerSideEncryptionConfigurationNotFoundError", "default encryption")
    warnings += w
    if enc:
        rule = enc["ServerSideEncryptionConfiguration"]["Rules"][0]["ApplyServerSideEncryptionByDefault"]
        print(f"s3: default encryption {rule['SSEAlgorithm']}")

    lc, w = read_setting(lambda: s3.get_bucket_lifecycle_configuration(Bucket=bucket),
                         "NoSuchLifecycleConfiguration", "lifecycle rules")
    warnings += w
    if lc:
        expiring = {r.get("Filter", {}).get("Prefix", ""): r["Expiration"]["Days"]
                    for r in lc["Rules"] if r["Status"] == "Enabled" and "Days" in r.get("Expiration", {})}
        print(f"s3: expiry by prefix {expiring}")
        warnings += [f"no lifecycle expiry for {p}" for p in ("uploads/", "outputs/") if p not in expiring]
    return warnings


def check_queue(session: boto3.Session, url: str) -> list[str]:
    attrs = session.client("sqs").get_queue_attributes(QueueUrl=url, AttributeNames=["All"])["Attributes"]
    arn = attrs["QueueArn"]
    print(f"sqs: {arn} reachable, ~{attrs['ApproximateNumberOfMessages']} messages, "
          f"visibility timeout {attrs['VisibilityTimeout']}s, retention {int(attrs['MessageRetentionPeriod']) // 3600}h, "
          f"long polling {attrs['ReceiveMessageWaitTimeSeconds']}s")
    warnings = []
    if "RedrivePolicy" not in attrs:
        warnings.append(f"queue {arn} has no dead-letter queue")
    if attrs.get("SqsManagedSseEnabled") != "true" and "KmsMasterKeyId" not in attrs:
        warnings.append(f"queue {arn} is not encrypted at rest")
    if attrs["ReceiveMessageWaitTimeSeconds"] == "0":
        warnings.append(f"queue {arn} uses short polling; set receive wait time to 20s")
    return warnings


def main() -> int:
    session = boto3.Session()
    try:
        warnings = check_identity(session)
        if bucket := os.environ.get("S3_BUCKET"):
            warnings += check_bucket(session, bucket)
        else:
            print("s3: skipped (set S3_BUCKET)")
        if queue_url := os.environ.get("SQS_QUEUE_URL"):
            warnings += check_queue(session, queue_url)
        else:
            print("sqs: skipped (set SQS_QUEUE_URL)")
    except (ClientError, BotoCoreError, RuntimeError) as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 1
    for w in warnings:
        print(f"WARNING: {w}")
    print("AWS connectivity OK" + (f" ({len(warnings)} warning(s))" if warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
