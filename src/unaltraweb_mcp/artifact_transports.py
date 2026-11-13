"""Public, optional binary transports for the adopted product-publication contract.

No ambient credentials, bucket/Release creation, ACL writes, cleanup or fallback.
GitHub uses the common flat content layout; S3/S4 uses named-v1 delivery.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import unicodedata
from urllib.parse import quote, urlsplit

from .artifact_publication import STORAGE_PROFILES, require
from .artifact_attempts import EvidenceError
from . import artifact_handoff_v1 as h

MULTIPART_THRESHOLD = 64 * 1024**2
PART_BYTES = 16 * 1024**2


def verify_stream(stream, row):
    hasher, count = hashlib.sha256(), 0
    while piece := stream.read(1024**2):
        count += len(piece)
        require(count <= row["bytes"], "Remote artifact exceeds its sealed size")
        hasher.update(piece)
    require((hasher.hexdigest(), count) == (row["sha256"], row["bytes"]), "Remote artifact SHA-256/size differs")


def http_session():
    import requests
    session = requests.Session()
    session.trust_env = False
    return session


def anonymous_check(session, url, row, public, *, redirects=0, named=False):
    # This session never has authentication headers or a host credential profile.
    response = session.get(url, stream=True, timeout=(10, 60), allow_redirects=False,
                           headers={"Accept-Encoding": "identity"})
    try:
        if response.status_code in {301, 302, 303, 307, 308}:
            redirected = urlsplit(response.headers.get("Location", ""))
            require(public and redirects < 2 and redirected.scheme == "https" and redirected.hostname
                    and redirected.hostname.endswith(".githubusercontent.com") and not redirected.username
                    and not redirected.password, "Unqualified anonymous redirect")
            access = anonymous_check(session, response.headers["Location"], row, public, redirects=redirects + 1, named=named)
            access["public_url"] = url
            return access
        if public:
            require(response.status_code == 200, "Public artifact is not anonymously readable")
            require(not named or response.headers.get("Content-Type") == row["media_type"]
                    and response.headers.get("Content-Disposition") == disposition(row), "Public named artifact download headers differ")
            verify_stream(response.raw, row)
        else:
            require(response.status_code in {401, 403, 404}, "Private artifact allows anonymous GET")
        return {"authentication_required": not public, "anonymous_read_verified": public,
                "anonymous_method": "GET", "anonymous_status": response.status_code,
                "public_url": url if public else None}
    finally:
        response.close()


def connect(publication, project_id, auth_file):
    from .editorial_sources import strict_json
    path = Path(auth_file)
    require(path.is_absolute(), "Select an absolute private authentication binding")
    with closing(h.Workspace(str(path.parent))) as workspace:
        _, _, raw = workspace.read(path.name, 65536, collect=True)
        with workspace.directory("") as directory:
            info = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600, "Authentication binding must be user-owned mode 0600")
        auth = strict_json(raw.decode())
        workspace.recheck()
    require(isinstance(auth, dict) and set(auth) == {"kind", "schema_version", "project_id", "bindings"}
            and auth["kind"] == "gacontext.publication-auth" and isinstance(auth["bindings"], dict)
            and type(auth["schema_version"]) is int and auth["schema_version"] == 1 and auth["project_id"] == project_id,
            "Authentication binding belongs to a different project/contract")
    target = publication["destination"]
    binding = auth["bindings"].get(target["auth_ref"], {})
    require(isinstance(binding, dict) and binding.get("driver") == target["driver"] and binding.get("destination_sha256") == publication["destination_sha256"],
            "Credentials are not bound to this exact destination")
    common = {"driver", "destination_sha256"}
    fields = {"token_env"} if target["driver"] == "github-release" else {"access_key_env", "secret_key_env"}
    optional = {"session_token_env"} if target["driver"] == "s3" else set()
    require(common | fields <= binding.keys() and binding.keys() <= common | fields | optional, "Unknown credential binding fields")
    credentials = {}
    for key in fields | (binding.keys() & optional):
        name = binding[key]
        require(isinstance(name, str) and re.fullmatch(r"[A-Z_][A-Z0-9_]{0,127}", name), "Invalid explicit credential environment binding")
        credentials[key] = os.environ.get(name, "")
        require(credentials[key], "Explicit project credentials are absent")
    if target["driver"] == "github-release":
        return GitHub(target, credentials["token_env"])
    try:
        import botocore.session
        from botocore.config import Config
    except ImportError as exc:
        raise RuntimeError("Install the optional artifact-publication extra (botocore==1.40.75)") from exc
    require(botocore.__version__ == "1.40.75", "Select the qualified public S3 SDK version")
    client = botocore.session.get_session().create_client("s3", endpoint_url=target["endpoint"], region_name=target["region"],
        aws_access_key_id=credentials["access_key_env"], aws_secret_access_key=credentials["secret_key_env"],
        aws_session_token=credentials.get("session_token_env"),
        config=Config(signature_version="s3v4", connect_timeout=10, read_timeout=60, retries={"total_max_attempts": 1},
                      request_checksum_calculation="when_required", response_checksum_validation="when_required", s3={"addressing_style": "path"}))
    return S3(target, client, profile=publication.get("storage_profile", "anonymous-delivery-v1"))


class GitHub:
    def __init__(self, target, token, *, session=None, anonymous=None):
        self.target = target
        self.session = session or http_session()
        self.anonymous = anonymous or http_session()
        self.headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28", "Accept-Encoding": "identity"}
        self.base = "https://api.github.com/repos/" + target["repository"]
        self.assets = {}

    def request(self, method, url, *, accept=None, **kwargs):
        headers = {**self.headers, **kwargs.pop("headers", {})}
        if accept:
            headers["Accept"] = accept
        response = self.session.request(method, url, headers=headers, allow_redirects=False, timeout=(10, 60), **kwargs)
        if response.status_code not in {200, 201, 302}:
            response.close()
            raise RuntimeError("GitHub artifact request failed; no fallback")
        return response

    def data(self, url):
        with self.request("GET", url) as response:
            require(response.status_code == 200 and len(response.content) <= 2 * 1024**2, "Unbounded GitHub metadata response")
            return response.json()

    def preflight(self):
        repository = self.data(self.base)
        require(type(repository.get("private")) is bool and repository["private"] == (self.target["visibility"] == "private"), "GitHub repository visibility differs from the selected policy")
        release = self.data(self.base + "/releases/tags/" + quote(self.target["release"], safe=""))
        require(release.get("draft") is False and type(release.get("id")) is int and release["id"] > 0, "Select an existing nondraft product Release")
        self.release_id = release["id"]
        for page in range(1, 12):
            rows = self.data(self.base + f"/releases/{self.release_id}/assets?per_page=100&page={page}")
            require(isinstance(rows, list), "Invalid GitHub Release inventory")
            for row in rows:
                require(row["name"] not in self.assets, "Ambiguous GitHub asset names")
                self.assets[row["name"]] = row
            require(len(self.assets) <= 1000, "GitHub Release asset limit exceeded")
            if len(rows) < 100:
                break
        else:
            raise RuntimeError("Unbounded GitHub Release inventory")

    def transfer(self, manifest, manifest_sha, row, source, *, write):
        name = "product-" + manifest_sha + ".json" if row["path"] == "product.json" else "sha256-" + row["sha256"] + ".blob"
        require(row["bytes"] < 2 * 1024**3, "GitHub assets must be smaller than 2 GiB")
        reused = name in self.assets
        if not reused:
            require(write and len(self.assets) < 1000, "GitHub artifact is absent or Release is full")
            url = "https://uploads.github.com/repos/" + self.target["repository"] + f"/releases/{self.release_id}/assets?name=" + quote(name)
            with self.request("POST", url, data=source, headers={"Content-Type": row["media_type"], "Content-Length": str(row["bytes"])}) as response:
                require(response.status_code == 201, "GitHub immutable asset was not created")
                self.assets[name] = response.json()
        asset = self.assets[name]
        require(type(asset.get("id")) is int and asset["id"] > 0 and asset.get("size") == row["bytes"], "GitHub asset identity/size differs")
        with self.request("GET", self.base + "/releases/assets/" + str(asset["id"]), accept="application/octet-stream", stream=True) as response:
            if response.status_code == 302:
                location = response.headers.get("Location", "")
                endpoint = urlsplit(location)
                require(endpoint.scheme == "https" and endpoint.hostname and endpoint.hostname.endswith(".githubusercontent.com")
                        and not endpoint.username and not endpoint.password, "Unqualified GitHub asset redirect")
                with self.anonymous.get(location, stream=True, timeout=(10, 60), allow_redirects=False) as download:
                    require(download.status_code == 200, "GitHub asset download failed")
                    verify_stream(download.raw, row)
            else:
                verify_stream(response.raw, row)
        url = "https://github.com/" + self.target["repository"] + "/releases/download/" + quote(self.target["release"], safe="") + "/" + name
        access = anonymous_check(self.anonymous, url, row, self.target["visibility"] == "public")
        return {"verified": True, "reused": reused, "locator": self.base + "/releases/assets/" + str(asset["id"]), "access": access}

    def close(self):
        self.session.close()
        self.anonymous.close()


class S3:
    def __init__(self, target, client, *, anonymous=None, profile="anonymous-delivery-v1"):
        require(profile in STORAGE_PROFILES and (profile != "authenticated-private-v1" or target["visibility"] == "private"),
                "Invalid private S3 capability selection")
        self.target, self.client = target, client
        self.profile = profile
        self.private_preflight = False
        self.attempt = None
        self.anonymous = anonymous or http_session()

    def bind_attempt(self, attempt):
        require(self.attempt is None, "An S3 store cannot change its local attempt binding")
        require(attempt.intent["destination"] == {key: self.target[key] for key in attempt.intent["destination"]}, "S3 attempt belongs to another destination")
        self.attempt = attempt

    def before_mutation(self, phase, **data):
        if self.attempt.intent["destination"] != {key: self.target[key] for key in self.attempt.intent["destination"]}:
            self.attempt.record("binding-changed", after_phase=self.attempt.phase)
            raise EvidenceError("S3 destination changed before mutation")
        self.attempt.before(phase, **data)

    @staticmethod
    def private_acl(acl):
        require(isinstance(acl, dict) and isinstance(acl.get("Grants"), list)
                and all(isinstance(grant, dict) and isinstance(grant.get("Grantee"), dict) for grant in acl["Grants"]),
                "Native S3 ACL could not be qualified")
        require(not any(grant["Grantee"].get("URI", "").endswith(("/AllUsers", "/AuthenticatedUsers")) for grant in acl["Grants"]),
                "Selected private S3 object has public grants")

    def access(self, key, row, *, named):
        if self.profile == "authenticated-private-v1":
            require(self.private_preflight, "Private S3 policy preflight is required")
            try:
                acl = self.client.get_object_acl(Bucket=self.target["bucket"], Key=key)
            except Exception:
                raise RuntimeError("Native private S3 object ACL could not be inspected") from None
            self.private_acl(acl)
            return {"profile": self.profile, "authenticated_read_verified": True, "native_object_acl_private": True,
                    "bucket_policy_private": True, "object_url_published": False, "anonymous_probe_performed": False,
                    "anonymous_object_url_qualified": False, "anonymous_read_verified": False, "public_url": None}
        url = self.target["endpoint"].rstrip("/") + "/" + self.target["bucket"] + "/" + quote(key, safe="/")
        return anonymous_check(self.anonymous, url, row, self.target["visibility"] == "public", named=named)

    @staticmethod
    def public_grant(statement):
        principal = statement.get("Principal")
        aws = principal.get("AWS") if isinstance(principal, dict) else None
        return statement.get("Effect") == "Allow" and (principal == "*" or aws == "*"
            or isinstance(aws, list) and "*" in aws or "NotPrincipal" in statement)

    def preflight(self):
        bucket = self.target["bucket"]
        acl = self.client.get_bucket_acl(Bucket=bucket)
        public_acl = any(grant.get("Grantee", {}).get("URI", "").endswith(("/AllUsers", "/AuthenticatedUsers")) for grant in acl.get("Grants", []))
        try:
            raw = self.client.get_bucket_policy(Bucket=bucket)["Policy"]
            require(len(raw) <= 65536, "Unbounded bucket policy")
            policy = json.loads(raw)
        except Exception as exc:
            require(getattr(exc, "response", {}).get("Error", {}).get("Code") == "NoSuchBucketPolicy", "S3 visibility preflight failed")
            policy = {"Statement": []}
        statements = policy.get("Statement", [])
        require(isinstance(statements, list) and all(isinstance(row, dict) for row in statements), "Unsupported bucket policy shape")
        public = [row for row in statements if self.public_grant(row)]
        if self.target["visibility"] == "private":
            self.private_acl(acl)
            require(not public_acl and not public, "Selected private bucket has public grants")
            self.private_preflight = True
        else:
            resource = "arn:aws:s3:::" + bucket + "/" + self.target["prefix"] + "/*"
            require(not public_acl and any(row.get("Action") in ("s3:GetObject", ["s3:GetObject"])
                    and row.get("Resource") in (resource, [resource]) and "Condition" not in row for row in public),
                    "Public S3 delivery needs an explicit readable selected-prefix policy")

    def key(self, manifest, manifest_sha, row):
        key = self.target["prefix"] + "/named/v1/" + manifest["project_id"] + "/" + manifest["product_id"] + "/" + manifest_sha + "/" + row["path"]
        require(len(key.encode()) <= 1024, "Named S3 artifact key exceeds its bound")
        return key

    def check(self, key, row, *, headers=True):
        try:
            response = self.client.get_object(Bucket=self.target["bucket"], Key=key)
        except Exception as exc:
            if getattr(exc, "response", {}).get("Error", {}).get("Code") == "NoSuchKey":
                return False
            raise RuntimeError("S3 artifact read failed; no fallback") from None
        with closing(response["Body"]) as body:
            require(response.get("ContentLength") == row["bytes"], "S3 artifact size differs")
            require(not headers or response.get("ContentType") == row["media_type"]
                    and response.get("ContentDisposition") == disposition(row), "Named S3 artifact download headers differ")
            verify_stream(body, row)
        return True

    def put(self, key, row, source):
        require(self.attempt is not None, "S3 mutation requires retained local attempt evidence")
        try:
            self._put(key, row, source)
        except Exception:
            raise self.attempt.failure() from None

    def _put(self, key, row, source):
        args = {"Bucket": self.target["bucket"], "Key": key, "ContentType": row["media_type"], "ContentDisposition": disposition(row)}
        if row["bytes"] < MULTIPART_THRESHOLD:
            self.before_mutation("put-requested", key=key)
            try:
                self.client.put_object(**args, Body=source, ContentLength=row["bytes"], IfNoneMatch="*")
            except Exception:
                self.attempt.record("put-uncertain", key=key)
                raise
            self.attempt.record("put-acknowledged", key=key)
            return
        self.before_mutation("create-requested", key=key)
        try:
            upload = self.client.create_multipart_upload(**args)["UploadId"]
            owned_record = {"bucket": args["Bucket"], "key": key, "upload_id": upload}
            self.attempt.record("upload-observed", key=key, owned_upload=owned_record)
        except EvidenceError:
            raise
        except Exception:
            self.attempt.record("create-uncertain", key=key)
            raise
        owned = {"Bucket": args["Bucket"], "Key": key, "UploadId": upload}
        parts, size, acknowledged = [], 0, 0
        try:
            while chunk := source.read(PART_BYTES):
                size += len(chunk)
                require(size <= row["bytes"], "Multipart artifact grew during upload")
                number = len(parts) + 1
                self.before_mutation("part-requested", key=key, owned_upload=owned_record, part_number=number,
                                    acknowledged_parts=len(parts), bytes_acknowledged=acknowledged)
                response = self.client.upload_part(**owned, PartNumber=number, Body=chunk, ContentLength=len(chunk))
                parts.append({"PartNumber": number, "ETag": response["ETag"]})
                acknowledged = size
                self.attempt.record("part-acknowledged", key=key, owned_upload=owned_record,
                                    acknowledged_parts=len(parts), bytes_acknowledged=acknowledged)
            require(size == row["bytes"], "Multipart artifact size changed")
        except EvidenceError:
            raise
        except Exception:
            self.attempt.record("part-uncertain", key=key, owned_upload=owned_record,
                                acknowledged_parts=len(parts), bytes_acknowledged=acknowledged)
            try:
                self.before_mutation("abort-requested", key=key, owned_upload=owned_record)
                self.client.abort_multipart_upload(**owned)
            except EvidenceError:
                raise
            except Exception:
                self.attempt.record("abort-uncertain", key=key, owned_upload=owned_record)
            else:
                self.attempt.record("abort-acknowledged", key=key, owned_upload=owned_record)
            raise
        self.before_mutation("complete-requested", key=key, owned_upload=owned_record,
                            acknowledged_parts=len(parts), bytes_acknowledged=acknowledged)
        try:
            self.client.complete_multipart_upload(**owned, MultipartUpload={"Parts": parts}, IfNoneMatch="*")
        except Exception:
            # Completion may have installed the final bytes: do not retry or abort.
            self.attempt.record("completion-uncertain", key=key, owned_upload=owned_record)
            raise
        self.attempt.record("complete-acknowledged", key=key, owned_upload=owned_record)

    def transfer(self, manifest, manifest_sha, row, source, *, write):
        key = self.key(manifest, manifest_sha, row)
        if self.attempt:
            self.attempt.record("object-check", key=key)
        reused = self.check(key, row)
        if not reused:
            if self.attempt:
                self.attempt.record("object-absent", key=key)
            require(write, "Selected S3 artifact is absent")
            self.put(key, row, source)
            self.attempt.record("readback-requested", key=key)
            try:
                require(self.check(key, row), "S3 artifact disappeared after upload")
            except Exception:
                self.attempt.record("readback-uncertain", key=key)
                raise
            self.attempt.record("readback-verified", key=key)
        try:
            access = self.access(key, row, named=True)
        except Exception:
            if self.attempt:
                self.attempt.record("access-uncertain", key=key)
            raise
        if row["path"] == "product.json":
            # The common authenticated fetch interface locates the original
            # manifest here, then verifies its named projection independently.
            canonical_key = self.target["prefix"] + "/manifests/" + manifest_sha + ".json"
            if not self.check(canonical_key, row, headers=False):
                require(write, "Canonical S3 product manifest is absent")
                source.seek(0)
                self.put(canonical_key, row, source)
                self.attempt.record("readback-requested", key=canonical_key)
                try:
                    require(self.check(canonical_key, row, headers=False), "Canonical S3 manifest readback failed")
                except Exception:
                    self.attempt.record("readback-uncertain", key=canonical_key)
                    raise
                self.attempt.record("readback-verified", key=canonical_key)
            self.access(canonical_key, row, named=False)
        if self.attempt:
            self.attempt.record("object-verified", key=key)
        return {"verified": True, "reused": reused, "locator": key, "access": access}

    def close(self):
        self.client.close()
        self.anonymous.close()


def disposition(row):
    name = Path(row["path"]).name
    fallback = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    fallback = "".join(char if 32 <= ord(char) < 127 and char not in '\\"' else "_" for char in fallback) or "download"
    mode = "inline" if row["media_type"] in {"application/pdf", "application/json"} else "attachment"
    return f'{mode}; filename="{fallback}"; filename*=UTF-8\'\'{quote(name, safe="")}'
