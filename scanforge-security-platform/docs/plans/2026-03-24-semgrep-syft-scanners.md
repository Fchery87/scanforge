# Semgrep + Syft Scanner Integration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Semgrep (SAST) and Syft (SBOM/license) scanners to the worker, with normalizers that produce findings for the `code_quality`, `vulnerability`, `license_compliance`, and `dependency_outdated` categories.

**Architecture:** Each scanner follows the existing adapter pattern — a `ScannerAdapter` subclass that shells out to the binary, and a normalizer function that converts raw JSON output into the canonical finding format. The orchestrator's `_get_scanners_for_type` and `_get_scanner`/`_get_normalizer` maps are extended to include the new scanners.

**Tech Stack:** Semgrep OSS CLI, Syft CLI (already installed), Python subprocess, existing ScannerAdapter/ScannerResult pattern.

---

### Task 1: Semgrep Scanner Adapter

**Files:**
- Create: `apps/worker/app/scanners/semgrep.py`

**Step 1: Create the adapter**

```python
import json
import subprocess
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult


class SemgrepAdapter(ScannerAdapter):
    name = "semgrep"
    binary_name = "semgrep"

    def run(self, repo_path: Path) -> ScannerResult:
        import time
        start = time.time()

        try:
            result = subprocess.run(
                [
                    self.binary_name,
                    "scan",
                    "--json",
                    "--config", "auto",
                    "--json-output", "semgrep-results.json",
                    str(repo_path),
                ],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(repo_path),
            )

            duration_ms = int((time.time() - start) * 1000)

            output = {}
            artifacts = []
            output_file = repo_path / "semgrep-results.json"

            if output_file.exists():
                with open(output_file) as f:
                    try:
                        output = json.load(f)
                    except json.JSONDecodeError:
                        output = {"raw": f.read()}
                artifacts.append(output_file)

            # Semgrep returns exit code 1 when findings are found
            has_output = bool(output and output.get("results"))
            return ScannerResult(
                scanner_name=self.name,
                success=result.returncode == 0 or has_output,
                raw_output=output,
                artifact_paths=artifacts,
                version=self.get_version(),
                duration_ms=duration_ms,
                error=result.stderr.strip() if result.returncode != 0 and not has_output else "",
            )

        except subprocess.TimeoutExpired:
            return ScannerResult(
                scanner_name=self.name,
                success=False,
                raw_output={},
                artifact_paths=[],
                error="Scanner timed out",
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            return ScannerResult(
                scanner_name=self.name,
                success=False,
                raw_output={},
                artifact_paths=[],
                error=str(e),
            )
```

**Step 2: Commit**

```bash
git add apps/worker/app/scanners/semgrep.py
git commit -m "feat(worker): add Semgrep scanner adapter"
```

---

### Task 2: Semgrep Normalizer

**Files:**
- Create: `apps/worker/app/normalizers/semgrep.py`

Semgrep JSON output has `results[]` with `check_id`, `path`, `start.line`, `end.line`, `extra.severity` (ERROR/WARNING/INFO), `extra.message`, `extra.metadata.category`, `extra.metadata.cwe`, `extra.metadata.references`.

**Step 1: Create the normalizer**

```python
import hashlib

SEVERITY_MAP = {
    "ERROR": "high",
    "WARNING": "medium",
    "INFO": "low",
}

CATEGORY_MAP = {
    "security": "vulnerability",
    "correctness": "code_quality",
    "best-practice": "code_quality",
    "performance": "code_quality",
    "maintainability": "code_quality",
}


def compute_semgrep_fingerprint(
    check_id: str,
    path: str,
    repo_id: str,
) -> str:
    components = [check_id, path.lower(), repo_id]
    return hashlib.sha256("|".join(components).encode()).hexdigest()


def normalize_semgrep_output(raw_output: dict, repository_id: str) -> list[dict]:
    findings = []

    results = raw_output.get("results", [])

    for result in results:
        check_id = result.get("check_id", "")
        path = result.get("path", "")
        start = result.get("start", {})
        end = result.get("end", {})
        extra = result.get("extra", {})
        metadata = extra.get("metadata", {})

        raw_severity = extra.get("severity", "WARNING")
        severity = SEVERITY_MAP.get(raw_severity, "medium")

        # Use metadata.confidence to boost/lower severity
        confidence_str = metadata.get("confidence", "").upper()
        if confidence_str == "HIGH" and raw_severity == "ERROR":
            severity = "critical"

        raw_category = metadata.get("category", "security")
        category = CATEGORY_MAP.get(raw_category, "code_quality")

        message = extra.get("message", "")
        title = f"{check_id.split('.')[-1]}: {path}"
        if len(title) > 200:
            title = title[:197] + "..."

        fingerprint = compute_semgrep_fingerprint(
            check_id=check_id,
            path=path,
            repo_id=repository_id,
        )

        cwe_list = metadata.get("cwe", [])
        references = []
        for cwe in cwe_list:
            cwe_id = cwe.split(":")[0].strip() if ":" in cwe else cwe
            references.append({
                "type": "cwe",
                "value": cwe_id,
                "url": f"https://cwe.mitre.org/data/definitions/{cwe_id.replace('CWE-', '')}.html",
            })

        for ref_url in metadata.get("references", []):
            references.append({
                "type": "documentation",
                "value": ref_url,
                "url": ref_url,
            })

        confidence_map = {"HIGH": 0.95, "MEDIUM": 0.8, "LOW": 0.6}
        confidence_score = confidence_map.get(confidence_str, 0.75)

        finding = {
            "category": category,
            "severity": severity,
            "title": title,
            "description": message,
            "canonical_fingerprint": fingerprint,
            "primary_scanner": "semgrep",
            "confidence_score": confidence_score,
            "instance": {
                "path": path,
                "line_start": start.get("line"),
                "line_end": end.get("line"),
                "check_id": check_id,
                "lines": extra.get("lines", ""),
            },
            "references": references,
        }
        findings.append(finding)

    return findings
```

**Step 2: Commit**

```bash
git add apps/worker/app/normalizers/semgrep.py
git commit -m "feat(worker): add Semgrep normalizer"
```

---

### Task 3: Syft Scanner Adapter

**Files:**
- Create: `apps/worker/app/scanners/syft.py`

Syft produces an SBOM with `artifacts[]`. Each artifact has `name`, `version`, `type`, `licenses[]`, `purl`, `locations[]`. We scan the SBOM for license issues and outdated packages.

**Step 1: Create the adapter**

```python
import json
import subprocess
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult


class SyftAdapter(ScannerAdapter):
    name = "syft"
    binary_name = "syft"

    def run(self, repo_path: Path) -> ScannerResult:
        import time
        start = time.time()

        try:
            result = subprocess.run(
                [
                    self.binary_name,
                    "scan",
                    f"dir:{repo_path}",
                    "-o", "json",
                    "--file", str(repo_path / "syft-results.json"),
                ],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(repo_path),
            )

            duration_ms = int((time.time() - start) * 1000)

            output = {}
            artifacts = []
            output_file = repo_path / "syft-results.json"

            if output_file.exists():
                with open(output_file) as f:
                    try:
                        output = json.load(f)
                    except json.JSONDecodeError:
                        output = {"raw": f.read()}
                artifacts.append(output_file)

            has_output = bool(output and output.get("artifacts"))
            return ScannerResult(
                scanner_name=self.name,
                success=result.returncode == 0 or has_output,
                raw_output=output,
                artifact_paths=artifacts,
                version=self.get_version(),
                duration_ms=duration_ms,
                error=result.stderr.strip() if result.returncode != 0 and not has_output else "",
            )

        except subprocess.TimeoutExpired:
            return ScannerResult(
                scanner_name=self.name,
                success=False,
                raw_output={},
                artifact_paths=[],
                error="Scanner timed out",
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            return ScannerResult(
                scanner_name=self.name,
                success=False,
                raw_output={},
                artifact_paths=[],
                error=str(e),
            )

    def get_version(self) -> str:
        import subprocess
        try:
            result = subprocess.run(
                [self.binary_name, "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip()
        except Exception:
            return ""
```

**Step 2: Commit**

```bash
git add apps/worker/app/scanners/syft.py
git commit -m "feat(worker): add Syft scanner adapter"
```

---

### Task 4: Syft Normalizer

**Files:**
- Create: `apps/worker/app/normalizers/syft.py`

Syft doesn't produce "findings" — it produces an SBOM. We analyze the SBOM for:
- Packages with no license (license_compliance)
- Packages with copyleft/restrictive licenses (license_compliance)

**Step 1: Create the normalizer**

```python
import hashlib

# Copyleft / restrictive licenses that should be flagged
RESTRICTIVE_LICENSES = {
    "GPL-2.0", "GPL-2.0-only", "GPL-2.0-or-later",
    "GPL-3.0", "GPL-3.0-only", "GPL-3.0-or-later",
    "AGPL-1.0", "AGPL-3.0", "AGPL-3.0-only", "AGPL-3.0-or-later",
    "SSPL-1.0", "EUPL-1.1", "EUPL-1.2",
    "LGPL-2.0", "LGPL-2.1", "LGPL-3.0",
    "CC-BY-SA-4.0", "CC-BY-NC-4.0",
}

# Permissive licenses that are fine
PERMISSIVE_LICENSES = {
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause",
    "ISC", "0BSD", "Unlicense", "CC0-1.0", "Zlib",
    "PSF-2.0", "Python-2.0", "BSL-1.0",
}


def compute_license_fingerprint(
    package_name: str,
    license_id: str,
    repo_id: str,
) -> str:
    components = [package_name.lower(), license_id.lower(), repo_id]
    return hashlib.sha256("|".join(components).encode()).hexdigest()


def normalize_syft_output(raw_output: dict, repository_id: str) -> list[dict]:
    findings = []

    artifacts = raw_output.get("artifacts", [])

    for artifact in artifacts:
        name = artifact.get("name", "")
        version = artifact.get("version", "")
        pkg_type = artifact.get("type", "")
        purl = artifact.get("purl", "")
        licenses_raw = artifact.get("licenses", [])
        locations = artifact.get("locations", [])

        location_path = ""
        if locations:
            location_path = locations[0].get("path", "")

        # Extract license IDs
        license_ids = []
        for lic in licenses_raw:
            if isinstance(lic, str):
                license_ids.append(lic)
            elif isinstance(lic, dict):
                lic_val = lic.get("value") or lic.get("spdxExpression") or lic.get("type", "")
                if lic_val:
                    license_ids.append(lic_val)

        # Flag packages with restrictive licenses
        for lic_id in license_ids:
            lic_upper = lic_id.upper().replace("_", "-")
            is_restrictive = any(r.upper() in lic_upper for r in RESTRICTIVE_LICENSES)
            if not is_restrictive:
                continue

            fingerprint = compute_license_fingerprint(name, lic_id, repository_id)

            finding = {
                "category": "license_compliance",
                "severity": "medium",
                "title": f"Restrictive license: {name}@{version} ({lic_id})",
                "description": (
                    f"Package {name}@{version} uses license {lic_id} which may have "
                    f"copyleft or restrictive terms that could affect your project."
                ),
                "canonical_fingerprint": fingerprint,
                "primary_scanner": "syft",
                "confidence_score": 0.9,
                "instance": {
                    "package_name": name,
                    "installed_version": version,
                    "package_type": pkg_type,
                    "license": lic_id,
                    "purl": purl,
                    "path": location_path,
                },
                "references": [
                    {
                        "type": "license",
                        "value": lic_id,
                        "url": f"https://spdx.org/licenses/{lic_id}.html",
                    }
                ],
            }
            findings.append(finding)

        # Flag packages with no license
        if not license_ids:
            fingerprint = compute_license_fingerprint(name, "NO_LICENSE", repository_id)
            finding = {
                "category": "license_compliance",
                "severity": "low",
                "title": f"No license declared: {name}@{version}",
                "description": (
                    f"Package {name}@{version} does not declare a license. "
                    f"This may pose legal risk for use in your project."
                ),
                "canonical_fingerprint": fingerprint,
                "primary_scanner": "syft",
                "confidence_score": 0.7,
                "instance": {
                    "package_name": name,
                    "installed_version": version,
                    "package_type": pkg_type,
                    "purl": purl,
                    "path": location_path,
                },
            }
            findings.append(finding)

    return findings
```

**Step 2: Commit**

```bash
git add apps/worker/app/normalizers/syft.py
git commit -m "feat(worker): add Syft SBOM/license normalizer"
```

---

### Task 5: Wire Scanners Into Orchestrator

**Files:**
- Modify: `apps/worker/app/services/scan_orchestrator.py` (lines 309-389)
- Modify: `apps/worker/app/normalizers/__init__.py`

**Step 1: Update `__init__.py`**

Add the new normalizer imports to `apps/worker/app/normalizers/__init__.py`:

```python
from app.normalizers.gitleaks import normalize_gitleaks_output
from app.normalizers.osv import normalize_osv_output
from app.normalizers.semgrep import normalize_semgrep_output
from app.normalizers.syft import normalize_syft_output
from app.normalizers.trivy import normalize_trivy_output
```

**Step 2: Update `_get_scanners_for_type` in orchestrator**

```python
def _get_scanners_for_type(self, scan_type: str) -> list[str]:
    mapping = {
        "scan.repo.full": ["trivy", "gitleaks", "osv", "semgrep", "syft"],
        "scan.repo.diff": ["gitleaks", "semgrep"],
        "scan.dependencies": ["trivy", "osv", "syft"],
        "scan.secrets": ["gitleaks"],
    }
    return mapping.get(scan_type, ["trivy", "gitleaks", "osv", "semgrep", "syft"])
```

**Step 3: Update `_get_scanner` in orchestrator**

Add to the if/elif chain:

```python
elif name == "semgrep":
    from app.scanners.semgrep import SemgrepAdapter
    return SemgrepAdapter()
elif name == "syft":
    from app.scanners.syft import SyftAdapter
    return SyftAdapter()
```

**Step 4: Update `_get_normalizer` in orchestrator**

Add to the if/elif chain:

```python
elif name == "semgrep":
    from app.normalizers.semgrep import normalize_semgrep_output
    return normalize_semgrep_output
elif name == "syft":
    from app.normalizers.syft import normalize_syft_output
    return normalize_syft_output
```

**Step 5: Commit**

```bash
git add apps/worker/app/services/scan_orchestrator.py apps/worker/app/normalizers/__init__.py
git commit -m "feat(worker): wire Semgrep and Syft into scan orchestrator"
```

---

### Task 6: Update Frontend Scan Type Mapping

**Files:**
- Modify: `apps/api/app/api/v1/routes/scans.py` (scan_type_map around line 50)

The `scan_type_map` in the create_scan route should remain as-is — the scan types (`full`, `diff`, `dependencies`, `secrets`) are job types, not scanner names. The orchestrator's `_get_scanners_for_type` already handles which scanners run for each type. No API changes needed.

**Step 1: Verify no changes needed**

The scan creation flow at `apps/api/app/api/v1/routes/scans.py:50-56` maps scan types to job queue types. The orchestrator handles scanner selection. No change required.

---

### Task 7: Install Semgrep in Worker Environment

**Step 1: Install semgrep**

```bash
pip install semgrep
# or
pipx install semgrep
```

Verify:
```bash
semgrep --version
```

**Step 2: Add to worker requirements if applicable**

If the worker has a `requirements.txt` or `pyproject.toml`, add `semgrep` to it.

---
