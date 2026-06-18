from extensions import limiter
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, Gruppenleiter
from datetime import datetime, timedelta

auth = Blueprint('auth', __name__)

MAX_FEHLVERSUCHE = 10
SPERR_MINUTEN    = 30


@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if request.method == 'POST':
        name     = request.form.get('name')
        passwort = request.form.get('passwort')
        user = Gruppenleiter.query.filter_by(name=name).first()

        if user and user.ist_gesperrt:
            verbleibend = max(1, int((user.gesperrt_bis - datetime.utcnow()).total_seconds() / 60))
            return render_template('login.html',
                error=f"Account gesperrt. Bitte {verbleibend} Minute(n) warten.")

        if user and user.check_password(passwort):
            user.fehlversuche = 0
            user.gesperrt_bis = None
            db.session.commit()
            login_user(user)
            if user.muss_passwort_aendern:
                flash("Bitte ändere dein Passwort.", "warning")
                return redirect(url_for('auth.passwort_aendern'))
            flash(f"Willkommen, {user.name}!", "success")
            return redirect('/')
        else:
            if user:
                user.fehlversuche = (user.fehlversuche or 0) + 1
                if user.fehlversuche >= MAX_FEHLVERSUCHE:
                    user.gesperrt_bis = datetime.utcnow() + timedelta(minutes=SPERR_MINUTEN)
                    user.fehlversuche = 0
                    db.session.commit()
                    return render_template('login.html',
                        error=f"Zu viele Fehlversuche. Account für {SPERR_MINUTEN} Min. gesperrt.")
                db.session.commit()
            return render_template('login.html', error="Falscher Name oder Passwort!")
    return render_template('login.html')


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Du wurdest abgemeldet.", "info")
    return redirect(url_for('auth.login'))


@auth.route('/passwort_aendern', methods=['GET', 'POST'])
@login_required
@limiter.limit("10 per minute")
def passwort_aendern():
    if request.method == 'POST':
        altes_pw     = request.form.get('altes_passwort')
        neues_pw     = request.form.get('neues_passwort')
        bestaetigung = request.form.get('bestaetigung')

        if not current_user.check_password(altes_pw):
            return render_template('passwort_aendern.html', error="Das alte Passwort ist nicht korrekt.")
        if neues_pw != bestaetigung:
            return render_template('passwort_aendern.html', error="Passwörter stimmen nicht überein.")
        if len(neues_pw) < 12:
            return render_template('passwort_aendern.html', error="Passwort muss mindestens 12 Zeichen haben.")
        if not any(c.isdigit() for c in neues_pw):
            return render_template('passwort_aendern.html', error="Passwort muss mindestens eine Zahl enthalten.")

        current_user.muss_passwort_aendern = False
        current_user.set_password(neues_pw)
        db.session.commit()
        flash("Passwort erfolgreich geändert!", "success")
        return redirect('/')

    return render_template('passwort_aendern.html')
