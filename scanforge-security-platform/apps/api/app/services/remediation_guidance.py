def build_remediation_guidance(finding) -> dict:
    instances = list(getattr(finding, "instances", None) or [])
    references = [ref.url for ref in (getattr(finding, "references", None) or []) if getattr(ref, "url", None)]
    first_instance = instances[0] if instances else None

    package_name = getattr(first_instance, "package_name", None) if first_instance else None
    installed_version = getattr(first_instance, "installed_version", None) if first_instance else None
    fixed_version = getattr(finding, "fixed_version", None)
    path = getattr(first_instance, "path", None) if first_instance else None

    if package_name and fixed_version:
        summary = f"Update {package_name}"
        if installed_version:
            summary += f" from {installed_version}"
        summary += f" to {fixed_version}."
        return {
            "summary": summary,
            "steps": [
                f"Review the affected dependency in {path or 'the affected manifest'}.",
                f"Upgrade {package_name} to {fixed_version}.",
                "Run the relevant dependency and regression tests.",
            ],
            "references": references,
        }

    title = getattr(finding, "title", "the finding")
    return {
        "summary": f"Review and remediate {title}.",
        "steps": [
            f"Inspect the affected evidence in {path or 'the reported location'}.",
            "Apply the remediation recommended by the scanner evidence.",
            "Run the relevant scanner again to confirm the finding is no longer observed.",
        ],
        "references": references,
    }
