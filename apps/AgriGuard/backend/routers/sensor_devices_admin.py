# ruff: noqa: B008  # FastAPI's Depends() in defaults is the canonical injection pattern
import json
import os
from datetime import UTC, datetime, timedelta

import models
import schemas
from auth import get_current_user, user_owner_keys, user_roles
from dependencies import get_tenant_rls_db
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from services.mqtt_broker_provisioning import (
    build_acl_file,
    build_dynamic_security_commands,
    build_password_file_commands,
    is_broker_safe_sensor_id,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

get_db = get_tenant_rls_db

router = APIRouter(prefix="/sensor-devices")

_GLOBAL_SENSOR_OPERATOR_ROLES = {"admin", "operator", "quality_manager"}
_SENSOR_OPERATOR_ROLES = _GLOBAL_SENSOR_OPERATOR_ROLES | {"sensor_operator"}
_SENSOR_STATUSES = {"all", "active", "disabled"}
_SENSOR_ID_SAFE_PATTERN = "[A-Za-z0-9_.:-]+"
_SENSOR_ID_SAFE_DETAIL = "sensor_id may contain only letters, numbers, dot, underscore, colon, and hyphen."
_BROKER_PROVISIONING_EVIDENCE_EVENT = "mqtt_broker_provisioning_applied"
_BROKER_PROVISIONING_EVIDENCE_MODES = {"password_file", "dynamic_security", "combined"}


def _split_env_list(name: str) -> set[str]:
    return {value.strip().lower() for value in os.environ.get(name, "").split(",") if value.strip()}


def require_sensor_operator(current_user: dict = Depends(get_current_user)) -> dict:
    uid = str(current_user.get("uid") or "").strip().lower()
    email = str(current_user.get("email") or "").strip().lower()
    allowed_uids = _split_env_list("SENSOR_OPERATOR_UIDS")
    allowed_emails = _split_env_list("SENSOR_OPERATOR_EMAILS")

    if user_roles(current_user) & _SENSOR_OPERATOR_ROLES:
        return current_user
    if uid and uid in allowed_uids:
        return current_user
    if email and email in allowed_emails:
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Sensor device administration requires an operator role or explicit allow-list grant.",
    )


def _operator_session_id(current_user: dict) -> str:
    actor = str(current_user.get("uid") or current_user.get("email") or "unknown-operator").strip()
    return f"operator:{actor or 'unknown-operator'}"


def _operator_metadata(current_user: dict) -> dict:
    return {
        "actor_uid": current_user.get("uid"),
        "actor_email": current_user.get("email"),
        "actor_roles": sorted(user_roles(current_user)),
    }


def _is_global_sensor_operator(current_user: dict) -> bool:
    return bool(user_roles(current_user) & _GLOBAL_SENSOR_OPERATOR_ROLES)


def _primary_owner_key(current_user: dict) -> str | None:
    for key in ("owner_id", "tenant_id", "uid", "email", "organization"):
        value = str(current_user.get(key) or "").strip()
        if value:
            return value
    return None


def _can_manage_sensor(current_user: dict, sensor: models.SensorDevice) -> bool:
    if _is_global_sensor_operator(current_user):
        return True
    owner_id = str(sensor.owner_id or "").strip()
    return bool(owner_id and owner_id in user_owner_keys(current_user))


def _scoped_sensor_query(db: Session, current_user: dict):
    query = db.query(models.SensorDevice)
    if _is_global_sensor_operator(current_user):
        return query
    owner_keys = user_owner_keys(current_user)
    if not owner_keys:
        return query.filter(models.SensorDevice.owner_id == "__no_access__")
    return query.filter(models.SensorDevice.owner_id.in_(owner_keys))


def _get_manageable_sensor(db: Session, sensor_id: str, current_user: dict) -> models.SensorDevice:
    sensor = db.query(models.SensorDevice).filter(models.SensorDevice.sensor_id == sensor_id).first()
    if sensor is None or not _can_manage_sensor(current_user, sensor):
        raise HTTPException(status_code=404, detail="Sensor device not found")
    return sensor


def _resolve_sensor_owner_id(
    current_user: dict,
    requested_owner_id: str | None,
    existing_owner_id: str | None = None,
    *,
    clear_owner: bool = False,
) -> str | None:
    normalized_requested = _normalize_optional_text(requested_owner_id)
    if clear_owner and normalized_requested is not None:
        raise HTTPException(status_code=400, detail="clear_owner cannot be combined with owner_id.")
    if _is_global_sensor_operator(current_user):
        if clear_owner:
            return None
        return normalized_requested if normalized_requested is not None else existing_owner_id

    if clear_owner:
        raise HTTPException(status_code=403, detail="Only global sensor operators can clear sensor ownership.")
    owner_keys = user_owner_keys(current_user)
    if normalized_requested is not None and normalized_requested not in owner_keys:
        raise HTTPException(status_code=403, detail="Cannot assign a sensor device to another owner.")
    return normalized_requested or existing_owner_id or _primary_owner_key(current_user)


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_registry_sensor_id(sensor_id: str) -> str:
    normalized = sensor_id.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="sensor_id must not be blank")
    if not is_broker_safe_sensor_id(normalized):
        raise HTTPException(status_code=400, detail=_SENSOR_ID_SAFE_DETAIL)
    return normalized


def _record_sensor_admin_event(
    db: Session,
    *,
    current_user: dict,
    event_type: str,
    sensor: models.SensorDevice,
    event_payload: dict,
) -> None:
    db.add(
        models.QRScanEvent(
            session_id=_operator_session_id(current_user),
            event_type=event_type,
            occurred_at=datetime.now(UTC),
            product_id=None,
            qr_value=sensor.sensor_id,
            source="sensor_device_admin",
            variant_id="sensor_device_admin_v1",
            metadata_json=json.dumps(
                {
                    **_operator_metadata(current_user),
                    **event_payload,
                    "sensor_id": sensor.sensor_id,
                    "owner_id": sensor.owner_id,
                    "zone": sensor.zone,
                    "is_active": sensor.is_active,
                },
                ensure_ascii=False,
            ),
        )
    )


def _sensor_summary(sensor: models.SensorDevice) -> schemas.SensorDeviceSummary:
    return schemas.SensorDeviceSummary.model_validate(sensor)


def _broker_unsupported_sensors(db: Session, current_user: dict) -> list[models.SensorDevice]:
    sensors = (
        _scoped_sensor_query(db, current_user)
        .order_by(
            models.SensorDevice.is_active.desc(),
            models.SensorDevice.zone.asc(),
            models.SensorDevice.sensor_id.asc(),
        )
        .all()
    )
    return [sensor for sensor in sensors if not is_broker_safe_sensor_id(sensor.sensor_id)]


def _normalized_cleanup_sensor_ids(sensor_ids: list[str] | None) -> list[str] | None:
    if sensor_ids is None:
        return None

    normalized: list[str] = []
    for raw_sensor_id in sensor_ids:
        sensor_id = str(raw_sensor_id or "").strip()
        if sensor_id and sensor_id not in normalized:
            normalized.append(sensor_id)
    return normalized


def _event_metadata(event: models.QRScanEvent) -> dict:
    try:
        decoded = json.loads(event.metadata_json or "{}")
    except json.JSONDecodeError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _parse_metadata_datetime(value: object, fallback: datetime | None = None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return fallback
    return fallback


def _mqtt_rejection_summary(event: models.QRScanEvent) -> schemas.MQTTRejectionEventSummary:
    metadata = _event_metadata(event)
    return schemas.MQTTRejectionEventSummary(
        id=event.id,
        sensor_id=metadata.get("sensor_id") or event.qr_value,
        reason=metadata.get("reason") or event.error_code,
        occurred_at=event.occurred_at,
        error_message=event.error_message,
        registry_required=metadata.get("registry_required") if isinstance(metadata.get("registry_required"), bool) else None,
    )


def _broker_provisioning_evidence_summary(
    event: models.QRScanEvent | None,
) -> schemas.MQTTBrokerProvisioningEvidenceSummary | None:
    if event is None:
        return None

    metadata = _event_metadata(event)
    recorded_at = event.occurred_at
    applied_at = _parse_metadata_datetime(metadata.get("applied_at"), recorded_at) or recorded_at
    artifact_generated_at = _parse_metadata_datetime(metadata.get("artifact_generated_at"))
    return schemas.MQTTBrokerProvisioningEvidenceSummary(
        id=event.id,
        recorded_at=recorded_at,
        applied_at=applied_at,
        mode=str(metadata.get("mode") or "combined"),
        artifact_hash=str(metadata.get("artifact_hash") or event.qr_value or ""),
        artifact_generated_at=artifact_generated_at,
        broker_host=metadata.get("broker_host"),
        runbook_reference=metadata.get("runbook_reference"),
        active_sensor_count=int(metadata.get("active_sensor_count") or 0),
        disabled_sensor_count=int(metadata.get("disabled_sensor_count") or 0),
        unsupported_sensor_count=int(metadata.get("unsupported_sensor_count") or 0),
        credential_rotation_required=bool(metadata.get("credential_rotation_required")),
        actor_uid=metadata.get("actor_uid"),
        actor_email=metadata.get("actor_email"),
        rotation_note=metadata.get("rotation_note"),
    )


def _broker_evidence_visible(event: models.QRScanEvent, current_user: dict) -> bool:
    if _is_global_sensor_operator(current_user):
        return True
    owner_id = str(_event_metadata(event).get("owner_id") or "").strip()
    return bool(owner_id and owner_id in user_owner_keys(current_user))


def _latest_broker_provisioning_evidence(db: Session, current_user: dict) -> models.QRScanEvent | None:
    events = (
        db.query(models.QRScanEvent)
        .filter(
            models.QRScanEvent.source == "sensor_device_admin",
            models.QRScanEvent.event_type == _BROKER_PROVISIONING_EVIDENCE_EVENT,
        )
        .order_by(models.QRScanEvent.occurred_at.desc(), models.QRScanEvent.id.desc())
        .all()
    )
    return next((event for event in events if _broker_evidence_visible(event, current_user)), None)


def _broker_provisioning_evidence_query(db: Session):
    return db.query(models.QRScanEvent).filter(
        models.QRScanEvent.source == "sensor_device_admin",
        models.QRScanEvent.event_type == _BROKER_PROVISIONING_EVIDENCE_EVENT,
    )


def _broker_host_matches(event: models.QRScanEvent, broker_host: str) -> bool:
    metadata_host = str(_event_metadata(event).get("broker_host") or "").strip().lower()
    return metadata_host == broker_host.lower()


@router.get("", response_model=schemas.SensorDeviceListResponse)
def list_sensor_devices(
    sensor_status: str = Query(default="all", max_length=16),
    zone: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_tenant_rls_db),
    current_user: dict = Depends(require_sensor_operator),
) -> schemas.SensorDeviceListResponse:
    normalized_status = sensor_status.strip().lower()
    if normalized_status not in _SENSOR_STATUSES:
        raise HTTPException(status_code=400, detail="sensor_status must be one of all, active, disabled")

    base_query = _scoped_sensor_query(db, current_user)
    normalized_zone = _normalize_optional_text(zone)
    if normalized_zone:
        base_query = base_query.filter(models.SensorDevice.zone == normalized_zone)

    active_count = base_query.filter(models.SensorDevice.is_active.is_(True)).count()
    disabled_count = base_query.filter(models.SensorDevice.is_active.is_(False)).count()

    filtered_query = base_query
    if normalized_status == "active":
        filtered_query = filtered_query.filter(models.SensorDevice.is_active.is_(True))
    elif normalized_status == "disabled":
        filtered_query = filtered_query.filter(models.SensorDevice.is_active.is_(False))

    total = filtered_query.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    current_page = min(page, total_pages)
    offset = (current_page - 1) * page_size
    devices = (
        filtered_query.order_by(
            models.SensorDevice.is_active.desc(),
            models.SensorDevice.zone.asc(),
            models.SensorDevice.sensor_id.asc(),
        )
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return schemas.SensorDeviceListResponse(
        status="success",
        items=[_sensor_summary(sensor) for sensor in devices],
        total=total,
        active_count=active_count,
        disabled_count=disabled_count,
        page=current_page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/mqtt-broker-provisioning", response_model=schemas.MQTTBrokerProvisioningResponse)
def get_mqtt_broker_provisioning(
    password_file_path: str = Query(default="/etc/mosquitto/passwd", min_length=1, max_length=240),
    dynamic_security_role: str = Query(default="agriguard-sensor", min_length=1, max_length=80),
    db: Session = Depends(get_tenant_rls_db),
    current_user: dict = Depends(require_sensor_operator),
) -> schemas.MQTTBrokerProvisioningResponse:
    normalized_password_file_path = password_file_path.strip()
    normalized_role = dynamic_security_role.strip()
    if not normalized_password_file_path:
        raise HTTPException(status_code=400, detail="password_file_path must not be blank")
    if not is_broker_safe_sensor_id(normalized_role):
        raise HTTPException(
            status_code=400,
            detail="dynamic_security_role may contain only letters, numbers, dot, underscore, colon, and hyphen.",
        )

    sensors = _scoped_sensor_query(db, current_user).order_by(models.SensorDevice.sensor_id.asc()).all()
    active_sensor_ids: list[str] = []
    disabled_sensor_ids: list[str] = []
    unsupported_sensor_ids: list[str] = []
    for sensor in sensors:
        sensor_id = sensor.sensor_id.strip()
        if not is_broker_safe_sensor_id(sensor_id):
            unsupported_sensor_ids.append(sensor.sensor_id)
            continue
        if sensor.is_active:
            active_sensor_ids.append(sensor_id)
        else:
            disabled_sensor_ids.append(sensor_id)

    password_commands, password_delete_commands = build_password_file_commands(
        active_sensor_ids=active_sensor_ids,
        disabled_sensor_ids=disabled_sensor_ids,
        password_file_path=normalized_password_file_path,
    )

    return schemas.MQTTBrokerProvisioningResponse(
        status="success",
        generated_at=datetime.now(UTC),
        active_sensor_count=len(active_sensor_ids),
        disabled_sensor_count=len(disabled_sensor_ids),
        unsupported_sensor_ids=unsupported_sensor_ids,
        acl_file=build_acl_file(active_sensor_ids),
        password_file_commands=password_commands,
        password_file_delete_commands=password_delete_commands,
        dynamic_security_commands=build_dynamic_security_commands(
            active_sensor_ids=active_sensor_ids,
            disabled_sensor_ids=disabled_sensor_ids,
            role_name=normalized_role,
        ),
        notes=[
            "The generated ACL permits each active MQTT username to publish only to agriguard/sensors/{sensor_id}.",
            "mosquitto_passwd commands are interactive by design so sensor passwords are not exposed in shell history.",
            "Remove or disable broker credentials for disabled sensors before reloading production broker access control.",
            "Restart or signal Mosquitto as required by the selected authentication plugin after applying password-file ACL changes.",
        ],
    )


@router.get(
    "/mqtt-broker-provisioning/evidence",
    response_model=schemas.MQTTBrokerProvisioningEvidenceResponse,
)
def get_mqtt_broker_provisioning_evidence(
    db: Session = Depends(get_tenant_rls_db),
    current_user: dict = Depends(require_sensor_operator),
) -> schemas.MQTTBrokerProvisioningEvidenceResponse:
    latest = _latest_broker_provisioning_evidence(db, current_user)
    return schemas.MQTTBrokerProvisioningEvidenceResponse(
        status="success",
        latest=_broker_provisioning_evidence_summary(latest),
    )


@router.get(
    "/mqtt-broker-provisioning/evidence/history",
    response_model=schemas.MQTTBrokerProvisioningEvidenceHistoryResponse,
)
def list_mqtt_broker_provisioning_evidence_history(
    broker_host: str | None = Query(default=None, max_length=160),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_tenant_rls_db),
    current_user: dict = Depends(require_sensor_operator),
) -> schemas.MQTTBrokerProvisioningEvidenceHistoryResponse:
    normalized_broker_host = _normalize_optional_text(broker_host)
    ordered_events = _broker_provisioning_evidence_query(db).order_by(
        models.QRScanEvent.occurred_at.desc(),
        models.QRScanEvent.id.desc(),
    ).all()
    visible_events = [event for event in ordered_events if _broker_evidence_visible(event, current_user)]

    if normalized_broker_host:
        matching_events = [event for event in visible_events if _broker_host_matches(event, normalized_broker_host)]
        total = len(matching_events)
        total_pages = max(1, (total + page_size - 1) // page_size)
        current_page = min(page, total_pages)
        offset = (current_page - 1) * page_size
        page_events = matching_events[offset : offset + page_size]
    else:
        total = len(visible_events)
        total_pages = max(1, (total + page_size - 1) // page_size)
        current_page = min(page, total_pages)
        offset = (current_page - 1) * page_size
        page_events = visible_events[offset : offset + page_size]

    items: list[schemas.MQTTBrokerProvisioningEvidenceSummary] = []
    for event in page_events:
        summary = _broker_provisioning_evidence_summary(event)
        if summary is not None:
            items.append(summary)

    return schemas.MQTTBrokerProvisioningEvidenceHistoryResponse(
        status="success",
        items=items,
        total=total,
        broker_host=normalized_broker_host,
        page=current_page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "/mqtt-broker-provisioning/evidence",
    response_model=schemas.MQTTBrokerProvisioningEvidenceResponse,
)
def record_mqtt_broker_provisioning_evidence(
    request: schemas.MQTTBrokerProvisioningEvidenceRequest,
    db: Session = Depends(get_tenant_rls_db),
    current_user: dict = Depends(require_sensor_operator),
) -> schemas.MQTTBrokerProvisioningEvidenceResponse:
    mode = request.mode.strip().lower()
    if mode not in _BROKER_PROVISIONING_EVIDENCE_MODES:
        raise HTTPException(status_code=400, detail="mode must be one of password_file, dynamic_security, combined")

    artifact_hash = request.artifact_hash.strip().lower()
    if not all(character in "0123456789abcdef" for character in artifact_hash):
        raise HTTPException(status_code=400, detail="artifact_hash must be a lowercase SHA-256 hex digest")

    recorded_at = datetime.now(UTC)
    applied_at = request.applied_at or recorded_at
    event = models.QRScanEvent(
        session_id=_operator_session_id(current_user),
        event_type=_BROKER_PROVISIONING_EVIDENCE_EVENT,
        occurred_at=recorded_at,
        product_id=None,
        qr_value=artifact_hash,
        source="sensor_device_admin",
        variant_id="mqtt_broker_provisioning_v1",
        metadata_json=json.dumps(
            {
                **_operator_metadata(current_user),
                "mode": mode,
                "artifact_hash": artifact_hash,
                "artifact_generated_at": request.artifact_generated_at.isoformat()
                if request.artifact_generated_at
                else None,
                "applied_at": applied_at.isoformat(),
                "owner_id": _resolve_sensor_owner_id(current_user, None),
                "broker_host": _normalize_optional_text(request.broker_host),
                "runbook_reference": _normalize_optional_text(request.runbook_reference),
                "active_sensor_count": request.active_sensor_count,
                "disabled_sensor_count": request.disabled_sensor_count,
                "unsupported_sensor_count": request.unsupported_sensor_count,
                "credential_rotation_required": request.credential_rotation_required,
                "rotation_note": _normalize_optional_text(request.rotation_note),
            },
            ensure_ascii=False,
        ),
    )
    db.add(event)
    try:
        db.commit()
        db.refresh(event)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Broker provisioning evidence record failed: {str(exc)}") from exc

    return schemas.MQTTBrokerProvisioningEvidenceResponse(
        status="success",
        latest=_broker_provisioning_evidence_summary(event),
    )


@router.get("/unsupported-identities", response_model=schemas.UnsupportedSensorIdentityListResponse)
def list_unsupported_sensor_identities(
    db: Session = Depends(get_tenant_rls_db),
    current_user: dict = Depends(require_sensor_operator),
) -> schemas.UnsupportedSensorIdentityListResponse:
    sensors = _broker_unsupported_sensors(db, current_user)
    active_count = sum(1 for sensor in sensors if sensor.is_active)
    disabled_count = len(sensors) - active_count

    return schemas.UnsupportedSensorIdentityListResponse(
        status="success",
        items=[_sensor_summary(sensor) for sensor in sensors],
        total=len(sensors),
        active_count=active_count,
        disabled_count=disabled_count,
        safe_pattern=_SENSOR_ID_SAFE_PATTERN,
        notes=[
            "Unsupported sensor IDs are omitted from broker provisioning output.",
            "Disable active unsupported sensors, reissue a broker-safe sensor ID, then rotate broker credentials.",
        ],
    )


@router.post("/unsupported-identities/disable", response_model=schemas.UnsupportedSensorIdentityCleanupResponse)
def disable_unsupported_sensor_identities(
    request: schemas.UnsupportedSensorIdentityCleanupRequest,
    db: Session = Depends(get_tenant_rls_db),
    current_user: dict = Depends(require_sensor_operator),
) -> schemas.UnsupportedSensorIdentityCleanupResponse:
    requested_sensor_ids = _normalized_cleanup_sensor_ids(request.sensor_ids)
    unsupported_sensors = _broker_unsupported_sensors(db, current_user)
    unsupported_by_id = {sensor.sensor_id: sensor for sensor in unsupported_sensors}
    skipped_sensor_ids: list[str] = []
    candidates: list[models.SensorDevice] = []

    if requested_sensor_ids is None:
        candidates = [sensor for sensor in unsupported_sensors if sensor.is_active]
    else:
        for sensor_id in requested_sensor_ids:
            sensor = unsupported_by_id.get(sensor_id)
            if sensor is None or not sensor.is_active:
                skipped_sensor_ids.append(sensor_id)
                continue
            candidates.append(sensor)

    for sensor in candidates:
        sensor.is_active = False
        sensor.updated_at = datetime.now(UTC)
        _record_sensor_admin_event(
            db,
            current_user=current_user,
            event_type="sensor_device_unsupported_identity_disabled",
            sensor=sensor,
            event_payload={
                "was_active": True,
                "cleanup_action": "disable_unsupported_identity",
                "safe_pattern": _SENSOR_ID_SAFE_PATTERN,
            },
        )

    try:
        db.commit()
        for sensor in candidates:
            db.refresh(sensor)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unsupported sensor cleanup failed: {str(exc)}") from exc

    return schemas.UnsupportedSensorIdentityCleanupResponse(
        status="success",
        disabled_count=len(candidates),
        disabled_sensor_ids=[sensor.sensor_id for sensor in candidates],
        skipped_sensor_ids=skipped_sensor_ids,
        items=[_sensor_summary(sensor) for sensor in candidates],
    )


@router.post("/unsupported-identities/reissue", response_model=schemas.UnsupportedSensorIdentityReissueResponse)
def reissue_unsupported_sensor_identity(
    request: schemas.UnsupportedSensorIdentityReissueRequest,
    db: Session = Depends(get_tenant_rls_db),
    current_user: dict = Depends(require_sensor_operator),
) -> schemas.UnsupportedSensorIdentityReissueResponse:
    old_sensor_id = request.old_sensor_id.strip()
    if not old_sensor_id:
        raise HTTPException(status_code=400, detail="old_sensor_id must not be blank")
    if is_broker_safe_sensor_id(old_sensor_id):
        raise HTTPException(status_code=400, detail="old_sensor_id must reference an unsupported broker identity")

    new_sensor_id = _normalize_registry_sensor_id(request.new_sensor_id)
    existing_replacement = db.query(models.SensorDevice).filter(models.SensorDevice.sensor_id == new_sensor_id).first()
    if existing_replacement is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="new_sensor_id already exists")

    source_sensor = _get_manageable_sensor(db, old_sensor_id, current_user)
    if is_broker_safe_sensor_id(source_sensor.sensor_id):
        raise HTTPException(status_code=400, detail="source sensor is already broker-safe")

    now = datetime.now(UTC)
    source_was_active = source_sensor.is_active
    source_sensor.is_active = False
    source_sensor.updated_at = now
    replacement_sensor = models.SensorDevice(
        sensor_id=new_sensor_id,
        owner_id=source_sensor.owner_id,
        label=source_sensor.label,
        zone=source_sensor.zone,
        expected_interval_minutes=source_sensor.expected_interval_minutes,
        is_active=True,
        registered_at=now,
        first_seen_at=None,
        last_seen_at=None,
        last_battery=None,
        last_status=None,
        updated_at=now,
    )
    db.add(replacement_sensor)

    _record_sensor_admin_event(
        db,
        current_user=current_user,
        event_type="sensor_device_unsupported_identity_reissued",
        sensor=source_sensor,
        event_payload={
            "cleanup_action": "reissue_unsupported_identity_source",
            "new_sensor_id": replacement_sensor.sensor_id,
            "source_was_active": source_was_active,
            "source_disabled": True,
            "safe_pattern": _SENSOR_ID_SAFE_PATTERN,
        },
    )
    _record_sensor_admin_event(
        db,
        current_user=current_user,
        event_type="sensor_device_broker_safe_identity_created",
        sensor=replacement_sensor,
        event_payload={
            "cleanup_action": "reissue_unsupported_identity_replacement",
            "old_sensor_id": source_sensor.sensor_id,
            "broker_rotation_required": True,
            "copied_fields": ["label", "zone", "expected_interval_minutes"],
        },
    )

    try:
        db.commit()
        db.refresh(source_sensor)
        db.refresh(replacement_sensor)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unsupported sensor reissue failed: {str(exc)}") from exc

    return schemas.UnsupportedSensorIdentityReissueResponse(
        status="success",
        source_sensor=_sensor_summary(source_sensor),
        replacement_sensor=_sensor_summary(replacement_sensor),
        broker_rotation_required=True,
        notes=[
            "Historical readings remain linked to the old unsupported sensor ID for audit continuity.",
            "Rotate broker credentials for the replacement sensor ID before returning the physical device to service.",
        ],
    )


@router.get("/mqtt-rejections", response_model=schemas.MQTTRejectionListResponse)
def list_mqtt_rejections(
    window_hours: int = Query(default=24, ge=1, le=168),
    sensor_id: str | None = Query(default=None, max_length=120),
    reason: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_tenant_rls_db),
    current_user: dict = Depends(require_sensor_operator),
) -> schemas.MQTTRejectionListResponse:
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=window_hours)
    normalized_sensor_id = _normalize_optional_text(sensor_id)
    normalized_reason = _normalize_optional_text(reason)

    base_query = db.query(models.QRScanEvent).filter(
        models.QRScanEvent.source == "mqtt_ingest",
        models.QRScanEvent.event_type == "mqtt_sensor_rejected",
        models.QRScanEvent.occurred_at >= cutoff,
    )
    if not _is_global_sensor_operator(current_user):
        sensor_ids = [sensor.sensor_id for sensor in _scoped_sensor_query(db, current_user).all()]
        base_query = (
            base_query.filter(models.QRScanEvent.qr_value.in_(sensor_ids))
            if sensor_ids
            else base_query.filter(models.QRScanEvent.qr_value == "__no_access__")
        )
    if normalized_sensor_id:
        base_query = base_query.filter(models.QRScanEvent.qr_value == normalized_sensor_id)

    reason_counts = {
        key or "unknown": int(count)
        for key, count in (
            base_query.with_entities(models.QRScanEvent.error_code, func.count(models.QRScanEvent.id))
            .group_by(models.QRScanEvent.error_code)
            .all()
        )
    }

    filtered_query = base_query
    if normalized_reason:
        filtered_query = filtered_query.filter(models.QRScanEvent.error_code == normalized_reason)

    total = filtered_query.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    current_page = min(page, total_pages)
    offset = (current_page - 1) * page_size
    events = (
        filtered_query.order_by(models.QRScanEvent.occurred_at.desc(), models.QRScanEvent.id.asc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return schemas.MQTTRejectionListResponse(
        status="success",
        items=[_mqtt_rejection_summary(event) for event in events],
        total=total,
        reason_counts=reason_counts,
        window_hours=window_hours,
        page=current_page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.put("/{sensor_id}", response_model=schemas.SensorDeviceActionResponse)
def upsert_sensor_device(
    request: schemas.SensorDeviceUpsertRequest,
    sensor_id: str = Path(min_length=1, max_length=120),
    db: Session = Depends(get_tenant_rls_db),
    current_user: dict = Depends(require_sensor_operator),
) -> schemas.SensorDeviceActionResponse:
    normalized_sensor_id = _normalize_registry_sensor_id(sensor_id)

    now = datetime.now(UTC)
    sensor = db.query(models.SensorDevice).filter(models.SensorDevice.sensor_id == normalized_sensor_id).first()
    is_new = sensor is None
    previous_owner_id = None if sensor is None else sensor.owner_id
    resolved_owner_id = _resolve_sensor_owner_id(
        current_user,
        request.owner_id,
        None if sensor is None else sensor.owner_id,
        clear_owner=request.clear_owner,
    )
    if sensor is None:
        sensor = models.SensorDevice(sensor_id=normalized_sensor_id, owner_id=resolved_owner_id, registered_at=now)
        db.add(sensor)
    elif not _can_manage_sensor(current_user, sensor):
        raise HTTPException(status_code=404, detail="Sensor device not found")

    sensor.owner_id = resolved_owner_id
    sensor.label = _normalize_optional_text(request.label)
    sensor.zone = _normalize_optional_text(request.zone)
    sensor.expected_interval_minutes = request.expected_interval_minutes
    sensor.is_active = request.is_active
    sensor.updated_at = now

    try:
        _record_sensor_admin_event(
            db,
            current_user=current_user,
            event_type="sensor_device_registered" if is_new else "sensor_device_updated",
            sensor=sensor,
            event_payload={
                "label": sensor.label,
                "expected_interval_minutes": sensor.expected_interval_minutes,
                "created": is_new,
                "previous_owner_id": previous_owner_id,
                "owner_cleared": request.clear_owner,
            },
        )
        db.commit()
        db.refresh(sensor)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Sensor device upsert failed: {str(exc)}") from exc

    return schemas.SensorDeviceActionResponse(status="success", sensor=_sensor_summary(sensor))


def _set_sensor_active_state(
    *,
    sensor_id: str,
    is_active: bool,
    event_type: str,
    db: Session,
    current_user: dict,
) -> schemas.SensorDeviceActionResponse:
    sensor = _get_manageable_sensor(db, sensor_id, current_user)

    was_active = sensor.is_active
    sensor.is_active = is_active
    sensor.updated_at = datetime.now(UTC)
    try:
        _record_sensor_admin_event(
            db,
            current_user=current_user,
            event_type=event_type,
            sensor=sensor,
            event_payload={"was_active": was_active},
        )
        db.commit()
        db.refresh(sensor)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Sensor device state update failed: {str(exc)}") from exc

    return schemas.SensorDeviceActionResponse(status="success", sensor=_sensor_summary(sensor))


@router.post("/{sensor_id}/disable", response_model=schemas.SensorDeviceActionResponse)
def disable_sensor_device(
    sensor_id: str = Path(min_length=1, max_length=120),
    db: Session = Depends(get_tenant_rls_db),
    current_user: dict = Depends(require_sensor_operator),
) -> schemas.SensorDeviceActionResponse:
    return _set_sensor_active_state(
        sensor_id=sensor_id.strip(),
        is_active=False,
        event_type="sensor_device_disabled",
        db=db,
        current_user=current_user,
    )


@router.post("/{sensor_id}/reactivate", response_model=schemas.SensorDeviceActionResponse)
def reactivate_sensor_device(
    sensor_id: str = Path(min_length=1, max_length=120),
    db: Session = Depends(get_tenant_rls_db),
    current_user: dict = Depends(require_sensor_operator),
) -> schemas.SensorDeviceActionResponse:
    return _set_sensor_active_state(
        sensor_id=sensor_id.strip(),
        is_active=True,
        event_type="sensor_device_reactivated",
        db=db,
        current_user=current_user,
    )
