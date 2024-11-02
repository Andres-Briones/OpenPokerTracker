from flask import Blueprint, request, jsonify, session, render_template
from models import get_db_connection, load_hands_from_db
import json

statistics_bp = Blueprint('statistics', __name__)

@statistics_bp.route('/')
def statistics():
    return render_template('statistics.html')
