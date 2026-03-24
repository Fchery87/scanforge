from dataclasses import dataclass


@dataclass
class ProjectScorecard:
    project_id: str
    overall_score: float
    security_score: float
    secrets_score: float
    dependency_score: float
    scan_count: int
    last_scan_at: str | None
    open_critical: int
    open_high: int
    open_medium: int
    open_low: int
    open_total: int
    fixed_30d: int
    new_this_week: int
    grade: str

    def compute_grade(self) -> str:
        score = self.overall_score
        if score >= 95:
            return "A+"
        elif score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"


def compute_security_score(
    open_critical: int,
    open_high: int,
    open_medium: int,
    open_low: int,
) -> float:
    penalty_critical = open_critical * 25
    penalty_high = open_high * 10
    penalty_medium = open_medium * 3
    penalty_low = open_low * 0.5

    total_penalty = penalty_critical + penalty_high + penalty_medium + penalty_low

    score = max(0.0, 100.0 - total_penalty)
    return round(score, 1)


def compute_secrets_score(
    open_secrets: int,
    total_scans: int,
) -> float:
    if total_scans == 0:
        return 100.0

    if open_secrets == 0:
        return 100.0

    penalty = min(open_secrets * 20, 100)
    return round(max(0.0, 100.0 - penalty), 1)


def compute_dependency_score(
    outdated_packages: int,
    vulnerable_packages: int,
    total_packages: int,
) -> float:
    if total_packages == 0:
        return 100.0

    vuln_rate = vulnerable_packages / total_packages
    outdated_rate = outdated_packages / total_packages

    score = 100.0 - (vuln_rate * 60) - (outdated_rate * 20)
    return round(max(0.0, score), 1)


def compute_overall_score(
    security_score: float,
    secrets_score: float,
    dependency_score: float,
) -> float:
    weights = {
        "security": 0.50,
        "secrets": 0.30,
        "dependency": 0.20,
    }

    weighted = (
        security_score * weights["security"] +
        secrets_score * weights["secrets"] +
        dependency_score * weights["dependency"]
    )

    return round(weighted, 1)
