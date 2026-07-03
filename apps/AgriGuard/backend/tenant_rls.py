from __future__ import annotations

from dataclasses import dataclass

from auth import is_operator_user, user_owner_keys
from sqlalchemy import text
from sqlalchemy.orm import Session

RLS_OWNER_IDS_SETTING = "app.current_owner_ids"
RLS_GLOBAL_OPERATOR_SETTING = "app.is_global_operator"
RLS_OWNER_ID_DELIMITER = ","


@dataclass(frozen=True)
class TenantRLSContext:
    applied: bool
    dialect_name: str
    owner_ids: tuple[str, ...]
    is_global_operator: bool


def _safe_owner_ids(owner_ids: set[str]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                owner_id
                for owner_id in (str(value or "").strip() for value in owner_ids)
                if owner_id and RLS_OWNER_ID_DELIMITER not in owner_id
            }
        )
    )


def build_tenant_rls_context(current_user: dict, *, dialect_name: str = "unknown", applied: bool = False) -> TenantRLSContext:
    return TenantRLSContext(
        applied=applied,
        dialect_name=dialect_name,
        owner_ids=_safe_owner_ids(user_owner_keys(current_user)),
        is_global_operator=is_operator_user(current_user),
    )


def _dialect_name(db: Session) -> str:
    bind = db.get_bind()
    return str(getattr(getattr(bind, "dialect", None), "name", "unknown"))


def apply_tenant_rls_context(db: Session, current_user: dict) -> TenantRLSContext:
    dialect_name = _dialect_name(db)
    context = build_tenant_rls_context(current_user, dialect_name=dialect_name, applied=False)
    if dialect_name != "postgresql":
        return context

    db.execute(
        text("SELECT set_config(:setting_name, :setting_value, true)"),
        {
            "setting_name": RLS_OWNER_IDS_SETTING,
            "setting_value": ",".join(context.owner_ids),
        },
    )
    db.execute(
        text("SELECT set_config(:setting_name, :setting_value, true)"),
        {
            "setting_name": RLS_GLOBAL_OPERATOR_SETTING,
            "setting_value": "true" if context.is_global_operator else "false",
        },
    )
    return TenantRLSContext(
        applied=True,
        dialect_name=dialect_name,
        owner_ids=context.owner_ids,
        is_global_operator=context.is_global_operator,
    )
