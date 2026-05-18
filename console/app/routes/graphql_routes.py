from flask import Blueprint, jsonify, request, current_app
from app import get_ethos
from app.database import db, EthosErrorLog, SavedQuery

graphql_bp = Blueprint("graphql", __name__)

INTROSPECTION_QUERY = """
{
  __schema {
    queryType { name }
    types {
      name kind
      fields(includeDeprecated: false) {
        name
        type { name kind ofType { name kind ofType { name kind ofType { name kind } } } }
      }
    }
  }
}
"""

_schema_cache = None


@graphql_bp.get("/schema")
def get_schema():
    global _schema_cache
    if _schema_cache is not None:
        return jsonify(_schema_cache)

    ethos = get_ethos(current_app._get_current_object())
    if not ethos.is_configured():
        return jsonify({"error": "Ethos API key not configured"}), 503

    try:
        result = ethos.graphql(INTROSPECTION_QUERY)
        _schema_cache = result
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@graphql_bp.post("/execute")
def execute_query():
    ethos = get_ethos(current_app._get_current_object())
    if not ethos.is_configured():
        return jsonify({"error": "Ethos API key not configured"}), 503

    data = request.get_json(force=True) or {}
    query = data.get("query", "")
    variables = data.get("variables")

    try:
        result = ethos.graphql(query, variables)
        return jsonify(result)
    except Exception as exc:
        try:
            entry = EthosErrorLog(
                source="graphql_console",
                endpoint="/graphql",
                error_message=str(exc),
            )
            db.session.add(entry)
            db.session.commit()
        except Exception:
            pass
        return jsonify({"error": str(exc)}), 502


@graphql_bp.get("/saved")
def list_saved_queries():
    queries = SavedQuery.query.order_by(SavedQuery.id).all()
    return jsonify({"items": [q.to_dict() for q in queries]})


@graphql_bp.post("/saved")
def create_saved_query():
    data = request.get_json(force=True) or {}
    name = data.get("name", "").strip()
    query_text = data.get("query_text", "").strip()

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not query_text:
        return jsonify({"error": "query_text is required"}), 400

    entry = SavedQuery(
        name=name,
        description=data.get("description"),
        query_text=query_text,
        variables=data.get("variables"),
        is_preloaded=False,
        updated_by=data.get("updated_by"),
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify(entry.to_dict()), 201


@graphql_bp.delete("/saved/<int:qid>")
def delete_saved_query(qid: int):
    entry = SavedQuery.query.get_or_404(qid)
    if entry.is_preloaded:
        return jsonify({"error": "Cannot delete a preloaded query"}), 403
    db.session.delete(entry)
    db.session.commit()
    return jsonify({"deleted": True, "id": qid})
