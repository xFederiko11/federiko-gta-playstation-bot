"""Public image hosting using an existing GitHub public repository.

No hosting plan is created or upgraded. Each PNG is uploaded once under its
SHA-256 filename. The built-in Actions GITHUB_TOKEN can write its own repository.
"""

import base64
import hashlib
import os
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests

PNG_HEADER = b"\x89PNG\r\n\x1a\n"
MAX_IMAGE_BYTES = 5 * 1024 * 1024


class AssetHostError(RuntimeError):
    pass


class GitHubAssetHost:
    def __init__(self, token=None, repository=None, branch=None, session=None):
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        self.repository = repository or os.getenv("GITHUB_REPOSITORY", "")
        self.branch = branch or os.getenv("GITHUB_BRANCH") or None
        if not self.token:
            raise AssetHostError("Configura GITHUB_TOKEN per pubblicare le immagini")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repository):
            raise AssetHostError("GITHUB_REPOSITORY deve avere formato proprietario/repository")
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": "Bearer " + self.token,
                                     "Accept": "application/vnd.github+json",
                                     "X-GitHub-Api-Version": "2022-11-28"})
        self._verified = False

    def _json(self, response, statuses=(200,)):
        if response.status_code not in statuses:
            raise AssetHostError(f"GitHub immagini: HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as error:
            raise AssetHostError("GitHub immagini: risposta JSON non valida") from error

    def _ensure_public(self):
        if self._verified:
            return
        response = self.session.get("https://api.github.com/repos/" + self.repository, timeout=30)
        data = self._json(response)
        if data.get("private") is not False or data.get("visibility", "public") != "public":
            raise AssetHostError("Le immagini richiedono un repository GitHub pubblico")
        if data.get("full_name", self.repository).casefold() != self.repository.casefold():
            raise AssetHostError("GitHub ha restituito un repository diverso da quello configurato")
        self.branch = self.branch or data.get("default_branch")
        if not self.branch:
            raise AssetHostError("Il repository non ha un branch predefinito")
        self._verified = True

    def _public_url(self, asset_path, response_data=None, commit_sha=None):
        if commit_sha and re.fullmatch(r"[a-fA-F0-9]{40}", commit_sha):
            return f"https://raw.githubusercontent.com/{self.repository}/{commit_sha}/{asset_path}"
        supplied = (response_data or {}).get("download_url")
        if supplied:
            parts = urlsplit(supplied)
            prefix = "/" + self.repository.casefold() + "/"
            if parts.scheme == "https" and parts.hostname == "raw.githubusercontent.com" and parts.path.casefold().startswith(prefix):
                return supplied
        return f"https://raw.githubusercontent.com/{self.repository}/{quote(self.branch, safe='')}/{asset_path}"

    def _existing(self, api_url, git_sha, asset_path):
        response = self.session.get(api_url, params={"ref": self.branch}, timeout=30)
        if response.status_code == 404:
            return None
        data = self._json(response)
        if data.get("type", "file") != "file" or data.get("sha") != git_sha:
            raise AssetHostError("Un'immagine con lo stesso nome ha contenuto diverso; nessuna sovrascrittura")
        return self._public_url(asset_path, data)

    def upload(self, path):
        content = Path(path).read_bytes()
        if not content.startswith(PNG_HEADER):
            raise AssetHostError("La scheda deve essere un'immagine PNG")
        if len(content) > MAX_IMAGE_BYTES:
            raise AssetHostError("L'immagine supera il limite locale di 5 MiB")
        self._ensure_public()
        digest = hashlib.sha256(content).hexdigest()
        git_sha = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content, usedforsecurity=False).hexdigest()
        asset_path = f"cards/{digest}.png"
        api_url = f"https://api.github.com/repos/{self.repository}/contents/{asset_path}"
        existing = self._existing(api_url, git_sha, asset_path)
        if existing:
            return existing
        response = self.session.put(api_url, json={
            "message": "Add generated GTA card " + digest[:12],
            "content": base64.b64encode(content).decode("ascii"),
            "branch": self.branch,
        }, timeout=30)
        if response.status_code in {409, 422}:
            # Another worker may have uploaded the same immutable asset.
            existing = self._existing(api_url, git_sha, asset_path)
            if existing:
                return existing
        data = self._json(response, statuses=(200, 201))
        return self._public_url(asset_path, data.get("content"), data.get("commit", {}).get("sha"))


# Keep both common spellings usable by the runner.
GithubAssetHost = GitHubAssetHost
