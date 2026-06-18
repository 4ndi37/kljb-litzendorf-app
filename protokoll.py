from flask import Blueprint, render_template, redirect, request, url_for, flash
from flask_login import login_required
from json import loads, dumps, JSONDecodeError
from models import db, Gruppenleiter, Protokoll, ProtokollPunkt, Todo, ProtokollEntwurfTop
from datetime import date
from decorators import require_role
from push_notifications import send_push_to_all, send_push_to_user
import logging

logger = logging.getLogger(__name__)

protokoll_bp = Blueprint('protokoll', __name__)


@protokoll_bp.route('/protokoll_neu')
@login_required
def protokoll_ansicht_route():
    tops = ProtokollEntwurfTop.query.all()
    alle_leiter = Gruppenleiter.query.order_by(Gruppenleiter.name).all()
    return render_template('protokoll_erstellen.html', tops=tops, leiter_liste=alle_leiter)


@protokoll_bp.route('/top_hinzufuegen', methods=['POST'])
@login_required
def top_hinzufuegen():
    aufgaben_roh = request.form.get('aufgaben_json')
    try:
        aufgaben_liste = loads(aufgaben_roh) if aufgaben_roh else []
    except JSONDecodeError:
        aufgaben_liste = []

    neuer_top = ProtokollEntwurfTop(
        titel=request.form.get('top_titel'),
        inhalt=request.form.get('top_inhalt'),
        aufgaben_json=dumps(aufgaben_liste)
    )
    db.session.add(neuer_top)
    db.session.commit()
    return redirect(url_for('protokoll.protokoll_ansicht_route'))


@protokoll_bp.route('/protokoll_archivieren', methods=['POST'])
@login_required
def protokoll_archivieren():
    aktuelle_themen = ProtokollEntwurfTop.query.all()
    try:
        neues_archiv_protokoll = Protokoll(
            datum=date.fromisoformat(request.form.get('datum')),
            schreiber=request.form.get('leitung')
        )
        db.session.add(neues_archiv_protokoll)
        db.session.commit()

        todo_empfaenger = set()
        for thema in aktuelle_themen:
            aufgaben = loads(thema.aufgaben_json or '[]')
            voller_inhalt = thema.inhalt or ''
            if aufgaben:
                voller_inhalt += "\n\n--- Aufgaben ---"
                for aufg in aufgaben:
                    namen_liste = []
                    for l_id in aufg['leiter_ids']:
                        leiter = db.session.get(Gruppenleiter, l_id)
                        if leiter:
                            namen_liste.append(leiter.name)
                    voller_inhalt += f"\n- {aufg['text']} ({', '.join(namen_liste)})"

            punkt = ProtokollPunkt(
                titel=thema.titel,
                inhalt=voller_inhalt,
                protokoll_id=neues_archiv_protokoll.id
            )
            db.session.add(punkt)

            for aufgabe_daten in aufgaben:
                for l_id in aufgabe_daten['leiter_ids']:
                    neues_todo = Todo(
                        aufgabe=aufgabe_daten['text'],
                        leiter_id=l_id,
                        quelle=f"TOP: {thema.titel} ({neues_archiv_protokoll.datum})",
                        erledigt=False
                    )
                    db.session.add(neues_todo)
                    todo_empfaenger.add(l_id)

        ProtokollEntwurfTop.query.delete()
        db.session.commit()
        send_push_to_all("Neues Protokoll", "Ein neues Protokoll wurde archiviert.", "/archiv")
        for l_id in todo_empfaenger:
            send_push_to_user(l_id, "Neue Aufgabe(n)", "Dir wurden neue Aufgaben zugewiesen.", "/todos")

    except Exception as e:
        logger.error(f"Fehler beim Archivieren: {e}")
        db.session.rollback()
        flash("Fehler beim Archivieren. Bitte erneut versuchen.", "danger")
        return redirect(url_for('protokoll.protokoll_ansicht_route'))

    flash("Protokoll erfolgreich archiviert.", "success")
    return redirect('/')


@protokoll_bp.route('/archiv')
@login_required
def archiv_aufklappen():
    archiv = Protokoll.query.order_by(Protokoll.datum.desc()).all()
    return render_template('archiv.html', protokolle=archiv)


@protokoll_bp.route('/top_loeschen/<int:id>', methods=['POST'])
@login_required
def top_loeschen(id):
    top = db.session.get(ProtokollEntwurfTop, id)
    if not top:
        flash("TOP nicht gefunden.", "warning")
        return redirect(url_for('protokoll.protokoll_ansicht_route'))
    db.session.delete(top)
    db.session.commit()
    return redirect(url_for('protokoll.protokoll_ansicht_route'))


@protokoll_bp.route('/top_bearbeiten/<int:id>', methods=['GET', 'POST'])
@login_required
def top_bearbeiten(id):
    top = db.session.get(ProtokollEntwurfTop, id)
    if not top:
        flash("TOP nicht gefunden.", "warning")
        return redirect(url_for('protokoll.protokoll_ansicht_route'))
    if request.method == 'POST':
        titel = request.form.get('top_titel', '').strip()
        if not titel:
            flash("Titel darf nicht leer sein.", "warning")
            return redirect(url_for('protokoll.top_bearbeiten', id=id))
        aufgaben_roh = request.form.get('aufgaben_json')
        try:
            aufgaben_liste = loads(aufgaben_roh) if aufgaben_roh else []
        except JSONDecodeError:
            aufgaben_liste = []
        top.titel = titel
        top.inhalt = request.form.get('top_inhalt', '')
        top.aufgaben_json = dumps(aufgaben_liste)
        db.session.commit()
        flash("TOP aktualisiert.", "success")
        return redirect(url_for('protokoll.protokoll_ansicht_route'))
    alle_leiter = Gruppenleiter.query.order_by(Gruppenleiter.name).all()
    return render_template('top_bearbeiten.html', top=top, leiter_liste=alle_leiter)


@protokoll_bp.route('/protokoll_loeschen/<int:id>', methods=['POST'])
@login_required
@require_role('admin')
def protokoll_loeschen(id):
    protokoll = db.session.get(Protokoll, id)
    if not protokoll:
        flash("Protokoll nicht gefunden.", "warning")
        return redirect(url_for('protokoll.archiv_aufklappen'))
    ProtokollPunkt.query.filter_by(protokoll_id=id).delete()
    db.session.delete(protokoll)
    db.session.commit()
    flash("Protokoll gelöscht.", "success")
    return redirect(url_for('protokoll.archiv_aufklappen'))


@protokoll_bp.route('/protokoll_bearbeiten/<int:id>', methods=['GET', 'POST'])
@login_required
@require_role('admin')
def protokoll_bearbeiten(id):
    protokoll = db.session.get(Protokoll, id)
    if not protokoll:
        flash("Protokoll nicht gefunden.", "warning")
        return redirect(url_for('protokoll.archiv_aufklappen'))
    if request.method == 'POST':
        try:
            protokoll.datum = date.fromisoformat(request.form.get('datum'))
        except (ValueError, TypeError):
            flash("Ungültiges Datum.", "danger")
            return redirect(url_for('protokoll.protokoll_bearbeiten', id=id))
        protokoll.schreiber = request.form.get('schreiber', '').strip()
        for punkt in protokoll.themen:
            punkt.titel  = request.form.get(f'titel_{punkt.id}',  punkt.titel ).strip() or punkt.titel
            punkt.inhalt = request.form.get(f'inhalt_{punkt.id}', punkt.inhalt)
        db.session.commit()
        flash("Protokoll aktualisiert.", "success")
        return redirect(url_for('protokoll.archiv_aufklappen'))
    return render_template('protokoll_bearbeiten.html', protokoll=protokoll)
