from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SuppressionRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "suppression_rules"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    repository_id: Mapped[str | None] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    match_criteria_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class FindingSuppression(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "finding_suppressions"
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    suppression_rule_id: Mapped[str | None] = mapped_column(ForeignKey("suppression_rules.id", ondelete="SET NULL"))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
