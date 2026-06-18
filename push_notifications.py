from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from flask_apscheduler import APScheduler
from pywebpush import webpush, WebPushException
from models import db, PushSubscription, Schicht, Todo, Gruppenleiter
import json
import os
import logging

push_bp = Blueprint('push', __name__)
scheduler = APScheduler()
logger = logging.getLogger(__name__)


def _send(sub, title, body, url='/'):
    try:
        webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth}
            },
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=os.getenv('VAPID_PRIVATE_KEY', '').replace('\\n', '\n'),
            vapid_claims={"sub": os.getenv('VAPID_CLAIM_EMAIL', 'mailto:admin@example.com')}
        )
    except WebPushException as e:
        if e.response is not None and e.response.status_code in (404, 410):
            db.session.delete(sub)
            db.session.commit()
        else:
            logger.warning(f"Push fehlgeschlagen (endpoint={sub.endpoint[:40]}...): {e}")
    except Exception as e:
        logger.error(f"Unerwarteter Push-Fehler: {e}")


def send_push_to_all(title, body, url='/'):
    try:
        for sub in PushSubscription.query.all():
            _send(sub, title, body, url)
    except Exception as e:
        logger.error(f"send_push_to_all Fehler: {e}")


def send_push_to_user(leiter_id, title, body, url='/'):
    try:
        for sub in PushSubscription.query.filter_by(leiter_id=leiter_id).all():
            _send(sub, title, body, url)
    except Exception as e:
        logger.error(f"send_push_to_user Fehler: {e}")


@push_bp.route('/push/subscribe', methods=['POST'])
@login_required
def subscribe():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'kein JSON'}), 400
    endpoint = data.get('endpoint')
    if not endpoint:
        return jsonify({'error': 'endpoint fehlt'}), 400
    keys = data.get('keys', {})
    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if not existing:
        db.session.add(PushSubscription(
            leiter_id=current_user.id,
            endpoint=endpoint,
            p256dh=keys.get('p256dh', ''),
            auth=keys.get('auth', '')
        ))
        db.session.commit()
    return jsonify({'ok': True})


@push_bp.route('/push/unsubscribe', methods=['POST'])
@login_required
def unsubscribe():
    data = request.get_json(silent=True) or {}
    sub = PushSubscription.query.filter_by(endpoint=data.get('endpoint', '')).first()
    if sub and sub.leiter_id == current_user.id:
        db.session.delete(sub)
        db.session.commit()
    return jsonify({'ok': True})


@scheduler.task('cron', id='schichten_reminder', hour=8, minute=0, timezone='Europe/Berlin')
def schichten_reminder():
    with scheduler.app.app_context():
        try:
            anzahl = Schicht.query.filter_by(leiter_id=None).count()
            if anzahl > 0:
                send_push_to_all(
                    "Offene Schichten",
                    f"Es sind noch {anzahl} Schicht(en) im Schichtplan frei.",
                    "/schichtplan"
                )
        except Exception as e:
            logger.error(f"schichten_reminder Fehler: {e}")


@scheduler.task('cron', id='todo_reminder', hour=9, minute=0, timezone='Europe/Berlin')
def todo_reminder():
    with scheduler.app.app_context():
        try:
            for leiter in Gruppenleiter.query.all():
                anzahl = Todo.query.filter_by(leiter_id=leiter.id, erledigt=False).count()
                if anzahl > 0:
                    send_push_to_user(
                        leiter.id,
                        "Offene Aufgaben",
                        f"Du hast noch {anzahl} offene Aufgabe(n).",
                        "/todos"
                    )
        except Exception as e:
            logger.error(f"todo_reminder Fehler: {e}")
