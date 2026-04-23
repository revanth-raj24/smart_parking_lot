"""
Device registry service — all DB operations for IoT device tracking.

Responsibilities:
  - Upsert device records on registration (device boots with new DHCP IP)
  - Touch last_seen on heartbeat
  - Resolve current IP by device_type for master→slave communication
  - Mark stale devices offline (called by background watcher in main.py)
"""
import ipaddress
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.device import Device

logger = logging.getLogger(__name__)

OFFLINE_THRESHOLD_SECONDS = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_last_seen(ts: datetime | None) -> datetime | None:
    if ts is None:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def validate_ip(ip: str) -> str:
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        raise ValueError(f"Invalid IP address: {ip!r}")
    return ip


def upsert_device(
    db: Session,
    *,
    device_id: str,
    current_ip: str,
    device_type: str,
    port: int = 80,
    firmware_version: str | None = None,
) -> Device:
    """
    Insert or update a device record.
    Called on every ESP32 boot so the server always has the current DHCP IP.
    """
    validate_ip(current_ip)
    now = _now()
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if device:
        device.current_ip = current_ip
        device.port = port
        device.device_type = device_type
        device.last_seen = now
        device.status = "online"
        if firmware_version is not None:
            device.firmware_version = firmware_version
        logger.info(f"[DeviceSvc] Updated {device_id!r} → {current_ip}:{port}")
    else:
        device = Device(
            device_id=device_id,
            current_ip=current_ip,
            port=port,
            device_type=device_type,
            firmware_version=firmware_version,
            last_seen=now,
            status="online",
            registered_at=now,
        )
        db.add(device)
        logger.info(f"[DeviceSvc] New device {device_id!r} @ {current_ip}:{port} type={device_type}")
    db.commit()
    db.refresh(device)
    return device


def touch_heartbeat(db: Session, device_id: str) -> Device:
    """
    Update last_seen and status=online for a heartbeat ping.
    Raises LookupError if the device_id has never registered.
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise LookupError(
            f"Unknown device {device_id!r} — device must call POST /api/devices/register first"
        )
    device.last_seen = _now()
    device.status = "online"
    db.commit()
    return device


def get_device_ip(db: Session, device_type: str) -> tuple[str, int]:
    """
    Return (ip, port) for the most recently seen online device of the given type.

    If multiple devices share the same type, the one with the freshest last_seen wins.
    Raises LookupError if no device of that type has sent a heartbeat within the threshold.
    """
    cutoff = _now() - timedelta(seconds=OFFLINE_THRESHOLD_SECONDS)
    device = (
        db.query(Device)
        .filter(Device.device_type == device_type, Device.last_seen >= cutoff)
        .order_by(Device.last_seen.desc())
        .first()
    )
    if not device:
        raise LookupError(
            f"No online device of type '{device_type}' "
            f"(no heartbeat in the last {OFFLINE_THRESHOLD_SECONDS}s)"
        )
    return device.current_ip, device.port


def get_all_devices(db: Session) -> list[dict]:
    """Return all devices with live online/offline status derived from last_seen."""
    cutoff = _now() - timedelta(seconds=OFFLINE_THRESHOLD_SECONDS)
    devices = db.query(Device).order_by(Device.last_seen.desc()).all()
    result = []
    for d in devices:
        last = _normalize_last_seen(d.last_seen)
        is_online = last is not None and last >= cutoff
        seconds_ago = round((_now() - last).total_seconds()) if last else None
        result.append({
            "id": d.id,
            "device_id": d.device_id,
            "current_ip": d.current_ip,
            "port": d.port,
            "device_type": d.device_type,
            "firmware_version": d.firmware_version,
            "status": "online" if is_online else "offline",
            "last_seen": d.last_seen,
            "seconds_since_heartbeat": seconds_ago,
            "registered_at": d.registered_at,
        })
    return result


def mark_stale_devices_offline(db: Session) -> int:
    """
    Mark online devices offline if last_seen exceeded the threshold.
    Called periodically by the background watcher in main.py.
    Returns the number of devices marked offline.
    """
    cutoff = _now() - timedelta(seconds=OFFLINE_THRESHOLD_SECONDS)
    stale = (
        db.query(Device)
        .filter(Device.status == "online", Device.last_seen < cutoff)
        .all()
    )
    for d in stale:
        d.status = "offline"
        logger.info(f"[DeviceSvc] {d.device_id!r} marked offline (last seen: {d.last_seen})")
    if stale:
        db.commit()
    return len(stale)
