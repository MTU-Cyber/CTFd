"""Admin control of global challenge containers."""

import re
import time

from flask import Blueprint, jsonify, render_template, request
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from CTFd.cache import clear_challenges
from CTFd.models import Challenges, Flags, db
from CTFd.plugins import register_admin_plugin_menu_bar, register_admin_plugin_script
from CTFd.utils import get_config, set_config
from CTFd.utils.decorators import admins_only

from . import manager


class TinyContainer(db.Model):
    __tablename__ = "tiny_containers"

    challenge_id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    compose_file = db.Column(db.String(512), nullable=False)
    service = db.Column(db.String(128), nullable=False)
    container_port = db.Column(db.Integer, nullable=False)
    host_port = db.Column(db.Integer, nullable=False)
    subdomain = db.Column(db.String(63), nullable=True, unique=True)
    protocol = db.Column(db.String(8), nullable=False, default="http")


class TinyContainerCandidate(db.Model):
    __tablename__ = "tiny_container_candidates"

    challenge_id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    enabled = db.Column(db.Boolean, nullable=False, default=True)


bp = Blueprint("tiny_containers", __name__, url_prefix="/admin/containers",
               static_folder="static")


def _error(message, status=400):
    return jsonify({"success": False, "error": str(message)}), status


def _record(challenge_id):
    challenge = Challenges.query.get_or_404(challenge_id)
    record = TinyContainer.query.get(challenge_id)
    return challenge, record


def _first_flag(challenge_id):
    flag = (
        Flags.query.filter_by(challenge_id=challenge_id)
        .order_by(Flags.id.asc())
        .first()
    )
    if flag is None:
        raise ValueError("Add a flag to the challenge before launching it")
    return flag.content


def _deadline():
    end = get_config("end")
    if not end:
        return None
    grace = int(get_config("tiny_containers_grace_minutes", 15))
    return int(end) + grace * 60


def _rows():
    records = {record.challenge_id: record for record in TinyContainer.query.all()}
    try:
        snapshot = manager.snapshot()
    except (RuntimeError, OSError):
        snapshot = None
    rows = []
    for challenge in Challenges.query.order_by(Challenges.name.asc()).all():
        record = records.get(challenge.id)
        if record is None:
            continue
        info = snapshot.get(challenge.id, {}) if snapshot is not None else {}
        status = info.get("status", "stopped") if snapshot is not None else "unavailable"
        metrics = {"cpu": info.get("cpu", "—"), "memory": info.get("memory", "—")}
        rows.append({"challenge": challenge, "record": record, "status": status,
                     "metrics": metrics, "services": info.get("services", []),
                     "running": info.get("running", False),
                     "endpoint": manager.endpoint(record)})
    return rows


@bp.get("")
@admins_only
def index():
    managed_ids = {record.challenge_id for record in TinyContainer.query.all()}
    candidate_ids = {candidate.challenge_id for candidate in TinyContainerCandidate.query.all()
                     if candidate.enabled}
    return render_template(
        "plugins/tiny_containers/templates/tiny_containers/index.html",
        rows=_rows(),
        available_challenges=(Challenges.query.filter(Challenges.id.in_(candidate_ids - managed_ids))
                              .order_by(Challenges.name.asc()).all()),
        files=manager.compose_files(),
        grace_minutes=int(get_config("tiny_containers_grace_minutes", 15)),
        deadline=_deadline(),
        domain=manager.DOMAIN,
        requested_challenge=request.args.get("challenge", type=int),
    )


@bp.get("/status")
@admins_only
def status():
    return jsonify({"success": True, "data": [
        {"id": row["challenge"].id, "status": row["status"],
         "visible": row["challenge"].state == "visible",
         "cpu": row["metrics"]["cpu"], "memory": row["metrics"]["memory"],
         "running": row["running"], "services": row["services"]}
        for row in _rows()
    ]})


@bp.get("/target")
@admins_only
def target():
    try:
        return jsonify({"success": True, "data": manager.public_target(request.args["file"])})
    except (KeyError, ValueError, RuntimeError, OSError) as exc:
        return _error(exc)


@bp.get("/<int:challenge_id>/logs")
@admins_only
def logs(challenge_id):
    _, record = _record(challenge_id)
    if record is None:
        return _error("Challenge is not managed", 404)
    try:
        return jsonify({"success": True, "data": manager.logs(challenge_id)})
    except (RuntimeError, OSError) as exc:
        return _error(exc, 500)


@bp.get("/<int:challenge_id>/metadata")
@admins_only
def metadata(challenge_id):
    _, record = _record(challenge_id)
    selected = TinyContainerCandidate.query.get(challenge_id)
    return jsonify({"success": True, "data": {"enabled": bool(selected and selected.enabled) or record is not None,
                                                 "managed": record is not None}})


@bp.post("/<int:challenge_id>/eligibility")
@admins_only
def eligibility(challenge_id):
    _, record = _record(challenge_id)
    enabled = (request.get_json() or {}).get("enabled")
    if not isinstance(enabled, bool):
        return _error("Enabled must be true or false")
    try:
        selected = TinyContainerCandidate.query.get(challenge_id)
        if selected is None:
            selected = TinyContainerCandidate(challenge_id=challenge_id)
            db.session.add(selected)
        selected.enabled = enabled
        if not enabled:
            if record is not None:
                if manager.containers(challenge_id):
                    db.session.rollback()
                    return _error("Stop the project before disabling tiny-containers")
                manager.discard(challenge_id)
                db.session.delete(record)
        db.session.commit()
        return jsonify({"success": True})
    except (RuntimeError, OSError, IntegrityError) as exc:
        db.session.rollback()
        return _error(exc)


@bp.post("/settings")
@admins_only
def settings():
    try:
        minutes = int(request.get_json()["grace_minutes"])
        if not 0 <= minutes <= 1440:
            raise ValueError("Grace period must be between 0 and 1440 minutes")
        set_config("tiny_containers_grace_minutes", str(minutes))
        return jsonify({"success": True})
    except (KeyError, TypeError, ValueError) as exc:
        return _error(exc)


@bp.post("/<int:challenge_id>/configure")
@admins_only
def configure(challenge_id):
    challenge, record = _record(challenge_id)
    data = request.get_json() or {}
    if not data.get("enabled"):
        if record is not None:
            if manager.containers(challenge_id):
                return _error("Stop the container before disabling management")
            manager.discard(challenge_id)
            db.session.delete(record)
            db.session.commit()
        return jsonify({"success": True})

    try:
        selected = TinyContainerCandidate.query.get(challenge_id)
        if record is None and (selected is None or not selected.enabled):
            raise ValueError("Enable tiny-containers on the challenge first")
        compose_file = str(data["compose_file"])
        if compose_file not in manager.compose_files():
            raise ValueError("Select a Compose file from the challenge repository")
        public_target = manager.public_target(compose_file)
        service = public_target["service"]
        container_port = public_target["container_port"]
        host_port = int(data["port"])
        protocol = str(data.get("protocol", "http"))
        if protocol not in ("http", "tcp"):
            raise ValueError("Protocol must be HTTP or TCP")
        if not 1 <= container_port <= 65535 or not 1 <= host_port <= 65535:
            raise ValueError("Ports must be between 1 and 65535")
        subdomain = None
        if protocol == "http":
            subdomain = str(data["subdomain"]).lower()
            manager.hostname(subdomain)
            if not re.fullmatch(r"[a-z0-9-]+", subdomain):
                raise ValueError("Invalid subdomain")
        if record is not None and manager.containers(challenge_id):
            return _error("Stop the container before changing its deployment")
        other = TinyContainer.query.filter_by(host_port=host_port).first()
        if other is not None and other.challenge_id != challenge_id:
            raise ValueError("That port is already assigned")
        if record is None:
            record = TinyContainer(challenge_id=challenge.id)
            db.session.add(record)
        record.compose_file = compose_file
        record.service = service
        record.container_port = container_port
        record.host_port = host_port
        record.subdomain = subdomain
        record.protocol = protocol
        db.session.commit()
        return jsonify({"success": True})
    except (KeyError, TypeError, ValueError, RuntimeError, OSError, IntegrityError) as exc:
        db.session.rollback()
        return _error(exc)


@bp.post("/<int:challenge_id>/action")
@admins_only
def action(challenge_id):
    challenge, record = _record(challenge_id)
    if record is None:
        return _error("Challenge is not managed", 404)
    operation = (request.get_json() or {}).get("action")
    try:
        existing = manager.containers(challenge_id) if operation in ("build", "launch", "restart", "stop") else []
        running = any(item.get("State") == "running" for item in existing)
        if operation in ("build", "launch", "restart"):
            deadline = _deadline()
            if deadline is not None and time.time() >= deadline:
                raise ValueError("The CTF container deadline has passed")
            if operation == "build":
                if running:
                    raise ValueError("Stop the project before building it")
                manager.build(record, _first_flag(challenge_id))
            else:
                if operation == "launch" and running:
                    raise ValueError("The project is already running")
                if operation == "restart" and not running:
                    raise ValueError("Launch the project before restarting it")
                manager.up(record, _first_flag(challenge_id), recreate=operation == "restart")
                challenge.connection_info = manager.endpoint(record)
                db.session.commit()
                clear_challenges()
        elif operation == "stop":
            if not existing:
                raise ValueError("The project is already stopped")
            manager.down(challenge_id)
            if challenge.connection_info == manager.endpoint(record):
                challenge.connection_info = None
                db.session.commit()
                clear_challenges()
        elif operation == "visibility":
            challenge.state = "visible" if challenge.state != "visible" else "hidden"
            db.session.commit()
            clear_challenges()
        else:
            raise ValueError("Unknown action")
        return jsonify({"success": True})
    except (ValueError, RuntimeError, OSError) as exc:
        db.session.rollback()
        return _error(exc)


def load(app):
    with app.app_context():
        TinyContainer.__table__.create(bind=db.engine, checkfirst=True)
        TinyContainerCandidate.__table__.create(bind=db.engine, checkfirst=True)
        candidate_columns = {column["name"] for column in inspect(db.engine).get_columns("tiny_container_candidates")}
        if "enabled" not in candidate_columns:
            db.engine.execute(text(
                "ALTER TABLE tiny_container_candidates ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT 1"
            ))
        columns = {column["name"] for column in inspect(db.engine).get_columns("tiny_containers")}
        if "protocol" not in columns:
            db.engine.execute(text(
                "ALTER TABLE tiny_containers ADD COLUMN protocol VARCHAR(8) NOT NULL DEFAULT 'http'"
            ))
        subdomain_column = next(column for column in inspect(db.engine).get_columns("tiny_containers")
                                if column["name"] == "subdomain")
        if not subdomain_column["nullable"]:
            with db.engine.begin() as connection:
                migration = MigrationContext.configure(connection)
                with Operations(migration).batch_alter_table("tiny_containers") as batch:
                    batch.alter_column("subdomain", existing_type=db.String(63), nullable=True)
    app.register_blueprint(bp)
    register_admin_plugin_menu_bar("tiny-containers", "/admin/containers")
    register_admin_plugin_script("/admin/containers/static/challenge-toggle.js")
