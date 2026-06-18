from flask import Blueprint, render_template, redirect, request, url_for, flash
from flask_login import login_required, current_user
from datetime import date, timedelta
from models import db, Termin, Anwesenheit, Programmpunkt, Abstimmungsantwort, Programmblock
from push_notifications import send_push_to_all

ARCHIV_TYPEN = {'zeltlager', 'kindertage'}

termine_bp = Blueprint('termine', __name__)


@termine_bp.route('/termine')
@login_required
def termine():
    termin_liste = Termin.query.filter(
        db.or_(Termin.versteckt == False, Termin.versteckt == None)
    ).all()

    abstimmungen = {}
    meine_antworten = {}
    for t in termin_liste:
        if t.typ == 'gruppenleiterrunde':
            abstimmungen[t.id] = Abstimmungsantwort.query.filter_by(termin_id=t.id).all()
            meine = Abstimmungsantwort.query.filter_by(termin_id=t.id, leiter_id=current_user.id).first()
            meine_antworten[t.id] = meine.antwort if meine else None

    return render_template('termine.html', alle_termine=termin_liste, abstimmungen=abstimmungen, meine_antworten=meine_antworten)

@termine_bp.route('/termin_speichern', methods=['POST'])
@login_required
def termin_speichern():
    name = request.form.get('event_name')
    if not name or not name.strip():
        return redirect(url_for('termine.termine'))
    try:
        startzeit_raw = request.form.get('startzeit', '').strip()
        neuer_termin = Termin(
            name=name,
            start=date.fromisoformat(request.form.get('start_datum')),
            ende=date.fromisoformat(request.form.get('end_datum')),
            ort=request.form.get('event_ort'),
            startzeit=startzeit_raw if startzeit_raw else None,
            typ=request.form.get('event_typ'),
            leiter_id = current_user.id
        )
    except (ValueError, TypeError):
        flash("Ungültiges Datum. Bitte korrekt eingeben.", "danger")
        return redirect(url_for('termine.termine'))
    if neuer_termin.start > neuer_termin.ende:
        flash("Das Startdatum darf nicht nach dem Enddatum liegen.", "danger")
        return redirect(url_for('termine.termine'))
    db.session.add(neuer_termin)
    db.session.commit()
    send_push_to_all("Neuer Termin", f"'{neuer_termin.name}' wurde eingetragen.", "/termine")
    flash("Termin erfolgreich gespeichert.", "success")
    return redirect(url_for('termine.termine'))

@termine_bp.route('/termin_loeschen/<int:id>', methods=['POST'])
@login_required
def termin_loeschen(id):
    termin = db.session.get(Termin, id)
    if not termin:
        flash("Termin nicht gefunden.", "warning")
        return redirect(url_for('termine.termine'))
    if termin.leiter_id != current_user.id and not current_user.ist_admin:
        flash("Zugriff verweigert.", "danger")
        return redirect(url_for('termine.termine'))
    Abstimmungsantwort.query.filter_by(termin_id=id).delete()
    Anwesenheit.query.filter_by(termin_id=id).delete()
    if termin.typ in ARCHIV_TYPEN:
        termin.versteckt = True
        db.session.commit()
        flash("Termin wurde aus der Liste entfernt. Der Zeitplan ist im Programmarchiv weiterhin verfügbar.", "success")
    else:
        Programmpunkt.query.filter_by(termin_id=id).delete()
        for block in Programmblock.query.filter_by(termin_id=id).all():
            db.session.delete(block)
        db.session.delete(termin)
        db.session.commit()
    return redirect(url_for('termine.termine'))


GUELTIGE_EVENT_TYPEN = {'zeltlager', 'kindertage', 'gruppenleiterrunde'}

@termine_bp.route('/event_planen/<typ>')
@login_required
def event_planen(typ):
    if typ not in GUELTIGE_EVENT_TYPEN:
        flash("Ungültiger Veranstaltungstyp.", "danger")
        return redirect(url_for('termine.termine'))
    event = Termin.query.filter_by(typ=typ, versteckt=False).order_by(Termin.start).first()

    meine_anwesenheit = None
    alle_anwesenheiten = []

    # Vorbereitung für den Zeitplan
    wochen_plan = {}
    wochentage = []

    if event:
        cur = event.start
        while cur <= event.ende:
            wochentage.append(cur.isoformat())
            cur += timedelta(days=1)

        meine_anwesenheit = Anwesenheit.query.filter_by(
            leiter_id=current_user.id,
            termin_id=event.id
        ).first()
        alle_anwesenheiten = Anwesenheit.query.filter_by(termin_id=event.id).all()

        alle_punkte = Programmpunkt.query.filter_by(termin_id=event.id).all()

        wochen_plan = {tag: [] for tag in wochentage}

        for punkt in alle_punkte:
            if punkt.tag in wochen_plan:
                wochen_plan[punkt.tag].append(punkt)

        for tag in wochen_plan:
            wochen_plan[tag].sort(key=lambda x: x.uhrzeit)

    return render_template('event_planen.html',
                           event=event,
                           event_typ=typ,
                           meine_anwesenheit=meine_anwesenheit,
                           alle_anwesenheiten=alle_anwesenheiten,
                           wochen_plan=wochen_plan,
                            wochentage=wochentage)


@termine_bp.route('/abstimmung_speichern', methods=['POST'])
@login_required
def abstimmung_speichern():
    termin_id = request.form.get('termin_id')
    antwort = request.form.get('antwort')
    if antwort not in ('ja', 'nein'):
        flash("Ungültige Antwort.", "danger")
        return redirect(url_for('termine.termine'))
    existiert = Abstimmungsantwort.query.filter_by(
        leiter_id=current_user.id,
        termin_id=termin_id
    ).first()
    if existiert:
        existiert.antwort = antwort
    else:
        db.session.add(Abstimmungsantwort(
            leiter_id=current_user.id,
            termin_id=termin_id,
            antwort=antwort
        ))
    db.session.commit()
    return redirect(url_for('termine.termine'))

@termine_bp.route('/anwesenheit_speichern', methods=['POST'])
@login_required
def anwesenheit_speichern():
    termin_id=request.form.get('termin_id')
    status = request.form.get('status')
    typ_redirect = request.form.get('typ_redirect')
    GUELTIGE_STATUS = {'voll', 'teilweise', 'gar_nicht'}
    if status not in GUELTIGE_STATUS:
        flash("Ungültiger Status.", "danger")
        return redirect(url_for('termine.event_planen', typ=typ_redirect))
    bemerkung = request.form.get('bemerkung')

    existiert = Anwesenheit.query.filter_by(
        leiter_id=current_user.id,
        termin_id=termin_id
    ).first()

    if existiert:
        # kein db.add nötig, da Dirty Checking
        existiert.status = status
        existiert.bemerkung = bemerkung
    else:
        neu = Anwesenheit(
            leiter_id=current_user.id,
            termin_id=termin_id,
            status=status,
            bemerkung=bemerkung
        )
        db.session.add(neu)
    db.session.commit()

    return redirect(url_for('termine.event_planen', typ=typ_redirect))
