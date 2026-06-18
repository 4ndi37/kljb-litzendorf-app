from flask import Blueprint, render_template, redirect, request, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from models import db, Termin, Programmpunkt, Konzept, Gruppenleiter
from decorators import require_role

programm_bp = Blueprint('programm', __name__)


@programm_bp.route('/programm')
@login_required
def programm_ansicht():
    wochentage = []

    # Auto-detect: are we currently at an event?
    event = Termin.query.filter(
        Termin.typ.in_(['zeltlager', 'kindertage']),
        Termin.start <= date.today(),
        Termin.ende >= date.today()
    ).first()

    if event:
        # Live: show remaining days from today
        cur = date.today()
        while cur <= event.ende:
            wochentage.append(cur.isoformat())
            cur += timedelta(days=1)
    else:
        event = Termin.query.filter(
            Termin.typ.in_(['zeltlager', 'kindertage']),
            Termin.start >= date.today()
        ).order_by(Termin.start).first()
        if event:
            cur = event.start
            while cur <= event.ende:
                wochentage.append(cur.isoformat())
                cur += timedelta(days=1)

    alle_punkte = Programmpunkt.query.filter_by(termin_id=event.id).all() if event else []

    wochen_plan = {tag: [] for tag in wochentage}

    for punkt in alle_punkte:
        if punkt.tag in wochen_plan:
            wochen_plan[punkt.tag].append(punkt)

    for tag in wochen_plan:
        wochen_plan[tag].sort(key=lambda x: x.uhrzeit)

    return render_template('programm.html', wochen_plan=wochen_plan)


def _event_tage(event):
    tage = []
    cur = event.start
    while cur <= event.ende:
        tage.append(cur.isoformat())
        cur += timedelta(days=1)
    return tage


@programm_bp.route('/programm_neu')
@login_required
@require_role('admin')
def programm_erstellen():
    relevante_events = Termin.query.filter(
        Termin.typ.in_(['zeltlager', 'kindertage'])
    ).order_by(Termin.start).all()

    alle_konzepte = Konzept.query.order_by(Konzept.titel).all()
    alle_leiter = Gruppenleiter.query.order_by(Gruppenleiter.name).all()
    event_tage = {e.id: _event_tage(e) for e in relevante_events}

    return render_template('programm_erstellen.html',
                           konzept_liste=alle_konzepte,
                           leiter_liste=alle_leiter,
                           relevante_events=relevante_events,
                           event_tage=event_tage)

@programm_bp.route('/programm_punkt_loeschen/<int:id>', methods=['POST'])
@login_required
@require_role('admin')
def programm_punkt_loeschen(id):
    punkt = db.session.get(Programmpunkt, id)
    if punkt:
        db.session.delete(punkt)
        db.session.commit()

    return redirect(url_for('programm.programm_ansicht'))


@programm_bp.route('/programm_speichern', methods=['POST'])
@login_required
@require_role('admin')
def programm_speichern():
    event_id_raw = request.form.get('event_id_hidden', '').strip()
    if not event_id_raw or not event_id_raw.isdigit():
        flash("Kein gültiger Termin ausgewählt.", "danger")
        return redirect(url_for('programm.programm_erstellen'))
    event_id = int(event_id_raw)
    termin = db.session.get(Termin, event_id)
    if not termin or termin.typ not in ('zeltlager', 'kindertage'):
        flash("Ungültiger Termin.", "danger")
        return redirect(url_for('programm.programm_erstellen'))

    neuer_punkt = Programmpunkt(
        tag=request.form.get('tag'),
        uhrzeit=request.form.get('uhrzeit'),
        ende=request.form.get('ende') or '',
        kategorie=request.form.get('kategorie'),
        termin_id=event_id
    )
    leiter_ids = request.form.getlist('leiter_ids')
    namen_liste = []
    for lid in leiter_ids:
        try:
            l = db.session.get(Gruppenleiter, int(lid))
            if l:
                namen_liste.append(l.name)
        except ValueError:
            continue
    neuer_punkt.verantwortliche = ", ".join(namen_liste)

    if neuer_punkt.kategorie == 'spiel':
        neuer_punkt.konzept_id = request.form.get('konzept_id')
    else:
        titel_direkt = request.form.get('titel_direkt')
        titel_optional = request.form.get('titel_optional')


        eingabe_titel = titel_direkt if titel_direkt else titel_optional


        if eingabe_titel and eingabe_titel.strip() != "":
            neuer_punkt.custom_titel = eingabe_titel
        else:

            neuer_punkt.custom_titel = neuer_punkt.kategorie.capitalize()


    db.session.add(neuer_punkt)
    db.session.commit()

    return redirect(url_for('programm.programm_ansicht'))


def _wochen_plan_fuer_event(event):
    wochentage = []
    cur = event.start
    while cur <= event.ende:
        wochentage.append(cur.isoformat())
        cur += timedelta(days=1)
    alle_punkte = Programmpunkt.query.filter_by(termin_id=event.id).all()
    wochen_plan = {tag: [] for tag in wochentage}
    for punkt in alle_punkte:
        if punkt.tag in wochen_plan:
            wochen_plan[punkt.tag].append(punkt)
    for tag in wochen_plan:
        wochen_plan[tag].sort(key=lambda x: x.uhrzeit)
    return wochen_plan


@programm_bp.route('/programm_archiv')
@login_required
def programm_archiv():
    vergangene_events = Termin.query.filter(
        Termin.typ.in_(['zeltlager', 'kindertage']),
        Termin.ende < date.today()
    ).order_by(Termin.start.desc()).all()
    return render_template('programm_archiv.html', events=vergangene_events)


@programm_bp.route('/programm_archiv/<int:termin_id>')
@login_required
def programm_archiv_detail(termin_id):
    event = db.session.get(Termin, termin_id)
    if not event or event.typ not in ('zeltlager', 'kindertage'):
        flash('Event nicht gefunden.', 'warning')
        return redirect(url_for('programm.programm_archiv'))
    wochen_plan = _wochen_plan_fuer_event(event)
    return render_template('programm_archiv_detail.html', event=event, wochen_plan=wochen_plan)

