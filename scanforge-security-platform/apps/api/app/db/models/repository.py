from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import RepoProvider
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Repository(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("provider", "full_name", name="uq_repo_provider_full_name"),)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[RepoProvider] = mapped_column(
        Enum(RepoProvider, name="repo_provider", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    external_repo_id: Mapped[str | None] = mapped_column(String(255))
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String(255))
    clone_url: Mapped[str | None] = mapped_column(String(1024))
    html_url: Mapped[str | None] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

class RepositoryIntegration(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "repository_integrations"
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, unique=True)
    installation_id: Mapped[str | None] = mapped_column(String(255))
    provider_account_id: Mapped[str | None] = mapped_column(String(255))
    webhook_secret_ref: Mapped[str | None] = mapped_column(String(255))
    access_metadata: Mapped[dict | None] = mapped_column(JSONB)
