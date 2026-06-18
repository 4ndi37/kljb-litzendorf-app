from flask import Blueprint, render_template, redirect, request, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from models import db, Termin, Programmblock, Blockpunkt, Programmpunkt, Gruppenleiter, Konzept
from decorators import require_role
from push_notifications import send_push_to_all, send_push_to_user

bloecke_bp = Blueprint('bloecke', __name__)


def _ist_zugewiesen(block):
    return current_user in block.zugewiesene_leiter


def _darf_bearbeiten(block):
    if current_user.ist_admin:
        return block.status in ('entwurf', 'eingereicht')
    return _ist_zugewiesen(block) and block.status == 'entwurf'


def _konzept_aus_form_oder_neu(form):
    """Liefert (konzept_id, konzept_titel_wenn_neu).

    Abhängig vom Radio-Wert `konzept_modus`:
    - 'neu': legt neues Konzept an, current_user als Autor, liefert (id, titel).
    - 'bestehend' (default): liefert (int(konzept_id) oder None, None).
    Bei Validierungsfehler (neues Konzept ohne Titel) wird (None, None) geliefert.
    """
    modus = form.get('konzept_modus', 'bestehend')
    if modus == 'neu':
        titel = (form.get('neues_konzept_titel') or '').strip()
        if not titel:
            flash('Titel für neues Spiel fehlt – Punkt wurde ohne Konzept gespeichert.', 'warning')
            return None, None
        neues_konzept = Konzept(
            titel=titel,
            beschreibung=(form.get('neues_konzept_beschreibung') or '').strip() or None,
            material=(form.get('neues_konzept_material') or '').strip() or None,
        )
        neues_konzept.autoren.append(current_user)
        db.session.add(neues_konzept)
        db.session.flush()
        return neues_konzept.id, neues_konzept.titel
    konzept_id_raw = form.get('konzept_id')
    if konzept_id_raw:
        try:
            return int(konzept_id_raw), None
        except (ValueError, TypeError):
            return None, None
    return None, None


# ── Übersicht ────────────────────────────────────────────────────────────────

@bloecke_bp.route('/bloecke')
@login_required
def bloecke_uebersicht():
    if current_user.ist_admin:
        # Alle Blöcke des neuesten/aktuellen Events
        event = Termin.query.filter_by(typ='zeltlager').order_by(Termin.start.desc()).first()
        if not event:
            event = Termin.query.order_by(Termin.start.desc()).first()
        bloecke = Programmblock.query.filter_by(termin_id=event.id).order_by(Programmblock.tag, Programmblock.zeit_von).all() if event else []
    else:
        bloecke = current_user.bloecke
        event = None

    alle_termine = Termin.query.order_by(Termin.start.desc()).all() if current_user.ist_admin else []
    return render_template('bloecke_uebersicht.html', bloecke=bloecke, event=event, alle_termine=alle_termine)


@bloecke_bp.route('/bloecke/<int:termin_id>')
@login_required
@require_role('admin')
def bloecke_fuer_event(termin_id):
    event = db.session.get(Termin, termin_id)
    if not event:
        flash('Event nicht gefunden.', 'danger')
        return redirect(url_for('bloecke.bloecke_uebersicht'))
    bloecke = Programmblock.query.filter_by(termin_id=termin_id).order_by(Programmblock.tag, Programmblock.zeit_von).all()
    alle_termine = Termin.query.order_by(Termin.start.desc()).all()
    return render_template('bloecke_uebersicht.html', bloecke=bloecke, event=event, alle_termine=alle_termine)


# ── Block anlegen ────────────────────────────────────────────────────────────

@bloecke_bp.route('/block_neu/<int:termin_id>')
@login_required
@require_role('admin')
def block_neu(termin_id):
    event = db.session.get(Termin, termin_id)
    if not event:
        flash('Event nicht gefunden.', 'danger')
        return redirect(url_for('bloecke.bloecke_uebersicht'))
    alle_leiter = Gruppenleiter.query.order_by(Gruppenleiter.name).all()
    tage = []
    cur = event.start
    while cur <= event.ende:
        tage.append(cur.isoformat())
        cur += timedelta(days=1)
    return render_template('block_neu.html', event=event, alle_leiter=alle_leiter, wochentage=tage)


@bloecke_bp.route('/block_speichern', methods=['POST'])
@login_required
@require_role('admin')
def block_speichern():
    termin_id = request.form.get('termin_id', type=int)
    event = db.session.get(Termin, termin_id)
    if not event:
        flash('Event nicht gefunden.', 'danger')
        return redirect(url_for('bloecke.bloecke_uebersicht'))

    block = Programmblock(
        titel=request.form.get('titel'),
        beschreibung=request.form.get('beschreibung') or None,
        termin_id=termin_id,
        tag=request.form.get('tag'),
        zeit_von=request.form.get('zeit_von') or None,
        zeit_bis=request.form.get('zeit_bis') or None,
        status='entwurf',
        erstellt_am=datetime.now()
    )
    leiter_ids = request.form.getlist('leiter_ids')
    for lid in leiter_ids:
        try:
            l = db.session.get(Gruppenleiter, int(lid))
            if l:
                block.zugewiesene_leiter.append(l)
        except ValueError:
            continue

    db.session.add(block)
    db.session.commit()
    for leiter in block.zugewiesene_leiter:
        send_push_to_user(leiter.id, "Block zugewiesen", f"Du wurdest dem Block '{block.titel}' zugewiesen.", f"/block/{block.id}")
    flash('Programmblock angelegt.', 'success')
    return redirect(url_for('bloecke.block_detail', id=block.id))


# ── Detailansicht ────────────────────────────────────────────────────────────

@bloecke_bp.route('/block/<int:id>')
@login_required
def block_detail(id):
    block = db.session.get(Programmblock, id)
    if not block:
        flash('Block nicht gefunden.', 'danger')
        return redirect(url_for('bloecke.bloecke_uebersicht'))

    if not current_user.ist_admin and not _ist_zugewiesen(block):
        flash('Zugriff verweigert.', 'danger')
        return redirect(url_for('bloecke.bloecke_uebersicht'))

    alle_konzepte = Konzept.query.order_by(Konzept.titel).all()
    kategorien = ['spiel', 'mahlzeit', 'pause', 'lagerfeuer', 'gottesdienst', 'transport', 'sonstiges']
    return render_template('block_detail.html', block=block,
                           alle_konzepte=alle_konzepte, kategorien=kategorien,
                           darf_bearbeiten=_darf_bearbeiten(block))


# ── Blockpunkte verwalten ─────────────────────────────────────────────────────

@bloecke_bp.route('/blockpunkt_speichern/<int:block_id>', methods=['POST'])
@login_required
def blockpunkt_speichern(block_id):
    block = db.session.get(Programmblock, block_id)
    if not block:
        flash('Block nicht gefunden.', 'danger')
        return redirect(url_for('bloecke.bloecke_uebersicht'))

    if not _darf_bearbeiten(block):
        flash('Bearbeitung nicht erlaubt.', 'danger')
        return redirect(url_for('bloecke.block_detail', id=block_id))

    max_reihenfolge = db.session.query(db.func.max(Blockpunkt.reihenfolge)).filter_by(block_id=block_id).scalar() or 0

    kategorie = request.form.get('kategorie', 'sonstiges')
    titel = request.form.get('custom_titel', '').strip()
    konzept_id = None

    if kategorie == 'spiel':
        konzept_id, neuer_konzept_titel = _konzept_aus_form_oder_neu(request.form)
        if neuer_konzept_titel and not titel:
            titel = neuer_konzept_titel

    if not titel:
        titel = kategorie.capitalize()

    punkt = Blockpunkt(
        block_id=block_id,
        uhrzeit=request.form.get('uhrzeit'),
        ende=request.form.get('ende'),
        custom_titel=titel,
        kategorie=kategorie,
        konzept_id=konzept_id,
        notiz=request.form.get('notiz') or None,
        reihenfolge=max_reihenfolge + 1
    )
    db.session.add(punkt)
    db.session.commit()
    flash('Programmpunkt hinzugefügt.', 'success')
    return redirect(url_for('bloecke.block_detail', id=block_id))


@bloecke_bp.route('/blockpunkt_bearbeiten/<int:id>', methods=['POST'])
@login_required
def blockpunkt_bearbeiten(id):
    punkt = db.session.get(Blockpunkt, id)
    if not punkt:
        flash('Punkt nicht gefunden.', 'danger')
        return redirect(url_for('bloecke.bloecke_uebersicht'))

    if not _darf_bearbeiten(punkt.block):
        flash('Bearbeitung nicht erlaubt.', 'danger')
        return redirect(url_for('bloecke.block_detail', id=punkt.block_id))

    kategorie = request.form.get('kategorie', punkt.kategorie)
    titel = request.form.get('custom_titel', '').strip()
    konzept_id = None

    if kategorie == 'spiel':
        konzept_id, neuer_konzept_titel = _konzept_aus_form_oder_neu(request.form)
        if neuer_konzept_titel and not titel:
            titel = neuer_konzept_titel

    punkt.uhrzeit = request.form.get('uhrzeit', punkt.uhrzeit)
    punkt.ende = request.form.get('ende', punkt.ende)
    punkt.custom_titel = titel if titel else kategorie.capitalize()
    punkt.kategorie = kategorie
    punkt.konzept_id = konzept_id
    punkt.notiz = request.form.get('notiz') or None
    db.session.commit()
    flash('Punkt aktualisiert.', 'success')
    return redirect(url_for('bloecke.block_detail', id=punkt.block_id))


@bloecke_bp.route('/blockpunkt_loeschen/<int:id>', methods=['POST'])
@login_required
def blockpunkt_loeschen(id):
    punkt = db.session.get(Blockpunkt, id)
    if not punkt:
        flash('Punkt nicht gefunden.', 'danger')
        return redirect(url_for('bloecke.bloecke_uebersicht'))

    block_id = punkt.block_id
    if not _darf_bearbeiten(punkt.block):
        flash('Löschen nicht erlaubt.', 'danger')
        return redirect(url_for('bloecke.block_detail', id=block_id))

    db.session.delete(punkt)
    db.session.commit()
    flash('Punkt gelöscht.', 'success')
    return redirect(url_for('bloecke.block_detail', id=block_id))


# ── Workflow-Aktionen ─────────────────────────────────────────────────────────

@bloecke_bp.route('/block_einreichen/<int:id>', methods=['POST'])
@login_required
def block_einreichen(id):
    block = db.session.get(Programmblock, id)
    if not block:
        flash('Block nicht gefunden.', 'danger')
        return redirect(url_for('bloecke.bloecke_uebersicht'))

    if not _ist_zugewiesen(block) and not current_user.ist_admin:
        flash('Zugriff verweigert.', 'danger')
        return redirect(url_for('bloecke.bloecke_uebersicht'))

    if block.status != 'entwurf':
        flash('Block kann nur im Status "Entwurf" eingereicht werden.', 'warning')
        return redirect(url_for('bloecke.block_detail', id=id))

    block.status = 'eingereicht'
    db.session.commit()
    flash('Block eingereicht. Admin wird benachrichtigt.', 'success')
    return redirect(url_for('bloecke.block_detail', id=id))


@bloecke_bp.route('/block_zurueckweisen/<int:id>', methods=['POST'])
@login_required
@require_role('admin')
def block_zurueckweisen(id):
    block = db.session.get(Programmblock, id)
    if not block:
        flash('Block nicht gefunden.', 'danger')
        return redirect(url_for('bloecke.bloecke_uebersicht'))

    bemerkung = request.form.get('bemerkung', '').strip()
    block.status = 'entwurf'
    if bemerkung:
        block.beschreibung = (block.beschreibung or '') + f'\n\n⚠️ Zurückgewiesen: {bemerkung}'
    db.session.commit()
    flash('Block zurückgewiesen – Gruppe kann nachbessern.', 'success')
    return redirect(url_for('bloecke.block_detail', id=id))


@bloecke_bp.route('/block_uebernehmen/<int:id>', methods=['POST'])
@login_required
@require_role('admin')
def block_uebernehmen(id):
    block = db.session.get(Programmblock, id)
    if not block:
        flash('Block nicht gefunden.', 'danger')
        return redirect(url_for('bloecke.bloecke_uebersicht'))

    if block.status != 'eingereicht':
        flash('Block muss im Status "Eingereicht" sein.', 'warning')
        return redirect(url_for('bloecke.block_detail', id=id))

    verantwortliche = ', '.join(l.name for l in block.zugewiesene_leiter)
    warnungen = []

    for punkt in block.punkte:
        # Kollisions-Prüfung
        konflikt = Programmpunkt.query.filter_by(
            termin_id=block.termin_id,
            tag=block.tag,
            uhrzeit=punkt.uhrzeit
        ).first()
        if konflikt:
            titel_konflikt = konflikt.konzept_info.titel if (konflikt.kategorie == 'spiel' and konflikt.konzept_info) else (konflikt.custom_titel or konflikt.kategorie)
            warnungen.append(f'{punkt.uhrzeit} Uhr: Kollision mit "{titel_konflikt}"')

        neuer_pp = Programmpunkt(
            tag=block.tag,
            uhrzeit=punkt.uhrzeit,
            ende=punkt.ende,
            termin_id=block.termin_id,
            kategorie=punkt.kategorie,
            custom_titel=punkt.custom_titel,
            konzept_id=punkt.konzept_id,
            verantwortliche=verantwortliche
        )
        db.session.add(neuer_pp)

    block.status = 'uebernommen'
    db.session.commit()
    termin = db.session.get(Termin, block.termin_id)
    termin_name = termin.name if termin else "das Event"
    send_push_to_all("Neuer Programmzeitplan", f"Der Zeitplan für '{termin_name}' wurde aktualisiert.", "/programm")

    if warnungen:
        flash('Block übernommen – aber Achtung, folgende Zeiten kollidieren mit bestehenden Punkten: ' + '; '.join(warnungen), 'warning')
    else:
        flash(f'Block "{block.titel}" erfolgreich in den Gesamtzeitplan übernommen.', 'success')
    return redirect(url_for('bloecke.block_detail', id=id))


@bloecke_bp.route('/block_loeschen/<int:id>', methods=['POST'])
@login_required
@require_role('admin')
def block_loeschen(id):
    block = db.session.get(Programmblock, id)
    if not block:
        flash('Block nicht gefunden.', 'danger')
        return redirect(url_for('bloecke.bloecke_uebersicht'))

    termin_id = block.termin_id
    db.session.delete(block)
    db.session.commit()
    flash('Block gelöscht.', 'success')
    return redirect(url_for('bloecke.bloecke_fuer_event', termin_id=termin_id))
