from flask import Blueprint, jsonify, send_from_directory, request, Response
from ragapp.models import ChatHistory, ChatFeedback, ChatConversation, UnauthenticatedSession
from extensions import db
from sqlalchemy import text
import os

metrics_bp = Blueprint('metrics', __name__)

# ── Password protection ───────────────────────────────────────────
METRICS_PASSWORD = os.getenv("METRICS_PASSWORD", "bucbuddy-admin-2026")

def is_authorised():
    pw_param  = request.args.get("password", "")
    pw_header = request.headers.get("X-Metrics-Password", "")
    return pw_param == METRICS_PASSWORD or pw_header == METRICS_PASSWORD

def auth_error():
    return Response(
        "Access denied. Add ?password=YOUR_PASSWORD to the URL.\n"
        "Example: /metrics?password=bucbuddy-admin-2026",
        status=401,
        mimetype="text/plain"
    )
# ─────────────────────────────────────────────────────────────────


@metrics_bp.route('/metrics')
def metrics_dashboard():
    if not is_authorised():
        return auth_error()
    src_dir = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(src_dir, 'metrics_dashboard.html')


@metrics_bp.route('/metrics/data')
def metrics_data():
    if not is_authorised():
        return auth_error()
    result = db.session.execute(text("""
        SELECT historyid, conversationid, useremail, userquery, llmresponse,
               top_n_document, citation_data, timestamp,
               top_5_retrieved, prompt_received_at, response_generated_at, response_time_ms
        FROM chat_history ORDER BY timestamp DESC
    """))
    rows = result.fetchall()
    keys = result.keys()
    records = []
    for row in rows:
        r = dict(zip(keys, row))
        records.append({
            'historyid':             r['historyid'],
            'conversationid':        r['conversationid'],
            'useremail':             r['useremail'],
            'userquery':             r['userquery'],
            'llmresponse':           r['llmresponse'],
            'top_n_document':        r['top_n_document'],
            'citation_data':         r['citation_data'],
            'timestamp':             r['timestamp'].isoformat() if r['timestamp'] else None,
            'top_5_retrieved':       r['top_5_retrieved'],
            'prompt_received_at':    r['prompt_received_at'].isoformat() if r['prompt_received_at'] else None,
            'response_generated_at': r['response_generated_at'].isoformat() if r['response_generated_at'] else None,
            'response_time_ms':      r['response_time_ms'],
        })
    return jsonify({'records': records, 'total': len(records)})


@metrics_bp.route('/metrics/feedback')
def metrics_feedback():
    if not is_authorised():
        return auth_error()
    rows = ChatFeedback.query.order_by(ChatFeedback.timestamp.desc()).all()
    up   = sum(1 for r in rows if r.vote == 'up')
    down = sum(1 for r in rows if r.vote == 'down')
    records = [{
        'id': r.id, 'conversation_id': r.conversation_id,
        'vote': r.vote, 'comment': r.comment,
        'userquery': r.userquery, 'llmresponse': r.llmresponse,
        'timestamp': r.timestamp.isoformat() if r.timestamp else None,
    } for r in rows]
    return jsonify({'up': up, 'down': down, 'total': len(rows), 'records': records})


@metrics_bp.route('/metrics/conversations')
def metrics_conversations():
    if not is_authorised():
        return auth_error()
    result = db.session.execute(text("""
        SELECT c.conversationid, c.useremail, c.title, c.created_at, c.last_updated,
               COUNT(h.historyid) AS message_count,
               AVG(h.response_time_ms) AS avg_response_ms
        FROM chat_conversations c
        LEFT JOIN chat_history h ON h.conversationid = c.conversationid
        GROUP BY c.conversationid, c.useremail, c.title, c.created_at, c.last_updated
        ORDER BY c.created_at DESC
    """))
    rows = result.fetchall()
    keys = result.keys()
    records = []
    for row in rows:
        r = dict(zip(keys, row))
        if r.get('created_at'):      r['created_at']      = r['created_at'].isoformat()
        if r.get('last_updated'):    r['last_updated']     = r['last_updated'].isoformat()
        if r.get('avg_response_ms'): r['avg_response_ms']  = float(r['avg_response_ms'])
        records.append(r)
    return jsonify({'records': records, 'total': len(records)})


@metrics_bp.route('/metrics/summary')
def metrics_summary():
    if not is_authorised():
        return auth_error()
    total_q       = db.session.execute(text("SELECT COUNT(*) FROM chat_history")).scalar() or 0
    avg_ms        = db.session.execute(text("SELECT AVG(response_time_ms) FROM chat_history WHERE response_time_ms IS NOT NULL")).scalar()
    timing_count  = db.session.execute(text("SELECT COUNT(*) FROM chat_history WHERE response_time_ms IS NOT NULL")).scalar() or 0
    no_answer     = db.session.execute(text("""
        SELECT COUNT(*) FROM chat_history
        WHERE llmresponse ILIKE '%I cannot%' OR llmresponse ILIKE '%I don%t have%'
           OR llmresponse ILIKE '%not have enough%' OR llmresponse ILIKE '%cannot provide%'
           OR llmresponse ILIKE '%No suitable context%'
    """)).scalar() or 0
    up            = db.session.execute(text("SELECT COUNT(*) FROM chat_feedback WHERE vote='up'")).scalar() or 0
    down          = db.session.execute(text("SELECT COUNT(*) FROM chat_feedback WHERE vote='down'")).scalar() or 0
    total_convos  = db.session.execute(text("SELECT COUNT(*) FROM chat_conversations")).scalar() or 0
    unique_users  = db.session.execute(text("SELECT COUNT(DISTINCT useremail) FROM chat_history WHERE useremail IS NOT NULL")).scalar() or 0
    avg_depth     = db.session.execute(text("SELECT AVG(cnt) FROM (SELECT COUNT(*) as cnt FROM chat_history GROUP BY conversationid) sub")).scalar()
    daily         = db.session.execute(text("""
        SELECT DATE(timestamp) as day, COUNT(*) as count
        FROM chat_history WHERE timestamp >= NOW() - INTERVAL '30 days'
        GROUP BY DATE(timestamp) ORDER BY day ASC
    """)).fetchall()

    return jsonify({
        'total_queries':       total_q,
        'avg_response_ms':     float(avg_ms) if avg_ms else None,
        'timing_coverage':     timing_count,
        'no_answer_count':     no_answer,
        'no_answer_rate':      round((no_answer/total_q*100), 2) if total_q else 0,
        'feedback_up':         up,
        'feedback_down':       down,
        'feedback_total':      up + down,
        'feedback_score_pct':  round((up/(up+down))*100, 1) if (up+down) > 0 else None,
        'total_conversations': total_convos,
        'unique_users':        unique_users,
        'avg_session_depth':   round(float(avg_depth), 1) if avg_depth else 0,
        'daily_query_counts':  [{'day': str(r[0]), 'count': r[1]} for r in daily],
    })


@metrics_bp.route('/metrics/unauthenticated')
def metrics_unauthenticated():
    if not is_authorised():
        return auth_error()
    rows = UnauthenticatedSession.query.order_by(UnauthenticatedSession.timestamp.desc()).all()
    return jsonify({'total': len(rows), 'records': [r.to_dict() for r in rows]})