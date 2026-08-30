# src/lifecycle/version_manager.py
import json
import logging
import asyncio
from pathlib import Path
from typing import Optional

from ..core.constants import BASE_API, CACHE_DIR, DOCS_TO_CACHE
from ..core.exceptions import VersionMismatchError

logger = logging.getLogger(__name__)

class VersionManager:
    def __init__(self, key: str):
        self.key = key
        self.version: Optional[str] = None
        self.cache = Path(CACHE_DIR)
        self.cache.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        
        try:
            self.meta = json.loads((self.cache / "etag_meta.json").read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            self.meta = {}
    
    async def ensure_current(self, session):
        async with self._lock:
            # 1. GET VERSION - TANPA X-Version header
            async with session.get(
                f"{BASE_API}/version",
                headers={"X-API-Key": self.key},
                timeout=15
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                self.version = data.get("version") or data.get("data", {}).get("version")
                logger.info(f"✅ Server version: {self.version}")
            
            # 2. Cek apakah cache valid
            if (self.meta.get("_version") == self.version and 
                all(doc in self.meta for doc in DOCS_TO_CACHE)):
                logger.info(f"📚 Docs cached for version {self.version}")
                return
            
            # 3. Download docs dengan version
            logger.info(f"📥 Downloading docs for version {self.version}...")
            headers = {
                "X-API-Key": self.key,
                "X-Version": self.version  # <-- KIRIM VERSION
            }
            
            for path in DOCS_TO_CACHE:
                try:
                    async with session.get(
                        f"{BASE_API}{path}",
                        headers=headers,
                        timeout=30
                    ) as resp:
                        if resp.status == 404:
                            logger.warning(f"Doc {path} not found (404)")
                            continue
                        if resp.status == 426:
                            raise VersionMismatchError(f"Version mismatch for {path}")
                        if resp.status != 200:
                            logger.warning(f"Doc {path} HTTP {resp.status}")
                            continue
                        
                        body = await resp.text()
                        cache_path = path.lstrip("/").replace("/", "__")
                        (self.cache / cache_path).write_text(body)
                        self.meta[path] = {
                            "etag": resp.headers.get("ETag"),
                            "version": self.version
                        }
                        logger.info(f"✅ Downloaded: {path}")
                        
                except Exception as e:
                    logger.warning(f"Doc {path} failed: {e}")
            
            self.meta["_version"] = self.version
            (self.cache / "etag_meta.json").write_text(json.dumps(self.meta, indent=2))
            logger.info(f"✅ Version {self.version} cache updated")
