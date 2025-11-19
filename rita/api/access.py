from flask import Blueprint, jsonify, request
from database.db import access_db
from shared.auth.bot_api import api_key_required

api_bp = Blueprint("api", __name__)


@api_bp.route("/access-requests", methods=["GET"])
@api_key_required
def list_access_requests():
    status = request.args.get("status", "pending")
    requests_list = access_db.get_access_requests(status=status)
    return jsonify({"requests": requests_list})
