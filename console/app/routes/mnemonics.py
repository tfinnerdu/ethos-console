from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from app.database import db, ColleagueMnemonic

mnemonics_bp = Blueprint("mnemonics", __name__)


@mnemonics_bp.get("/")
def list_mnemonics():
    q = request.args.get("q", "").strip()
    query = ColleagueMnemonic.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                ColleagueMnemonic.mnemonic.ilike(like),
                ColleagueMnemonic.colleague_file.ilike(like),
                ColleagueMnemonic.eedm_resource.ilike(like),
                ColleagueMnemonic.gotchas.ilike(like),
                ColleagueMnemonic.cn_notes.ilike(like),
            )
        )
    items = query.order_by(ColleagueMnemonic.mnemonic).all()
    return jsonify([m.to_dict() for m in items])


@mnemonics_bp.get("/<int:item_id>")
def get_mnemonic(item_id: int):
    item = ColleagueMnemonic.query.get_or_404(item_id)
    return jsonify(item.to_dict())


@mnemonics_bp.post("/")
def create_mnemonic():
    data = request.get_json(force=True)
    if not data.get("mnemonic"):
        return jsonify({"error": "mnemonic is required"}), 400
    if ColleagueMnemonic.query.filter_by(mnemonic=data["mnemonic"].upper()).first():
        return jsonify({"error": "Mnemonic already exists"}), 409

    item = ColleagueMnemonic(
        mnemonic=data["mnemonic"].upper(),
        colleague_file=data.get("colleague_file"),
        eedm_resource=data.get("eedm_resource"),
        eedm_version=data.get("eedm_version"),
        cn_supported=bool(data.get("cn_supported", False)),
        cn_notes=data.get("cn_notes"),
        field_mappings=data.get("field_mappings"),
        gotchas=data.get("gotchas"),
        related_mnemonics=data.get("related_mnemonics"),
        updated_by=data.get("updated_by", "console"),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@mnemonics_bp.put("/<int:item_id>")
def update_mnemonic(item_id: int):
    item = ColleagueMnemonic.query.get_or_404(item_id)
    data = request.get_json(force=True)

    for field in ("colleague_file", "eedm_resource", "eedm_version", "cn_notes", "gotchas", "updated_by"):
        if field in data:
            setattr(item, field, data[field])
    if "cn_supported" in data:
        item.cn_supported = bool(data["cn_supported"])
    if "field_mappings" in data:
        item.field_mappings = data["field_mappings"]
    if "related_mnemonics" in data:
        item.related_mnemonics = data["related_mnemonics"]

    item.last_updated = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(item.to_dict())


@mnemonics_bp.delete("/<int:item_id>")
def delete_mnemonic(item_id: int):
    item = ColleagueMnemonic.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return "", 204
