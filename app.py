from flask import Flask, render_template, request, redirect, flash, url_for
from flask_login import LoginManager, login_required, current_user
from werkzeug.middleware.proxy_fix import ProxyFix
import os
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from extensions import limiter
from flask_migrate import Migrate
from models import db, Termin, Programmpunkt, Info, Gruppenleiter, Schicht
from zoneinfo import ZoneInfo
from decorators import require_role

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv('key.env')

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
if not app.config['SECRET_KEY']:
    raise RuntimeError("SECRET_KEY nicht gesetzt!")
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'
app.config['VAPID_PUBLIC_KEY'] = os.getenv('VAPID_PUBLIC_KEY', '')
app.config['SCHEDULER_API_ENABLED'] = False

csrf = CSRFProtect(app)
@app.after_request
def security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

limiter.init_app(app)

# Login Manager einrichten
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# --- DATENBANK KONFIGURATION ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'kljb_zentrum.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)


with app.app_context():
    db.create_all()


@app.before_request
def passwort_pflicht():
    if current_user.is_authenticated and getattr(current_user, 'muss_passwort_aendern', False):
        erlaubt = {'auth.passwort_aendern', 'auth.logout', 'static'}
        if request.endpoint not in erlaubt:
            flash("Bitte ändere zuerst dein Passwort.", "warning")
            return redirect(url_for('auth.passwort_aendern'))


@app.template_filter('wochentag')
def wochentag_filter(iso_str):
    namen = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    try:
        d = date.fromisoformat(str(iso_str))
        return f"{namen[d.weekday()]}, {d.strftime('%d.%m.')}"
    except (ValueError, TypeError):
        return str(iso_str)



# Login Manager
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Gruppenleiter, int(user_id))

# --- ROUTEN ---



@app.route('/')
@login_required
def index():
    aktuelle_infos = Info.query.order_by(Info.zeitstempel.desc()).limit(5).all()
    freie_schichten_anzahl = Schicht.query.filter_by(leiter_id=None).count()

    now = datetime.now(ZoneInfo('Europe/Berlin'))
    heute_datum = date.today()
    jetzt_zeit = now.strftime('%H:%M')
    heute_tag = heute_datum.isoformat()

    aktuelles_lager = Termin.query.filter(
        Termin.start <= heute_datum,
        Termin.ende >= heute_datum,
        Termin.typ.in_(['zeltlager', 'kindertage']),
        Termin.versteckt == False
    ).first()
    status_objekt = None
    modus = "leer"

    if aktuelles_lager:
        modus = "lager"
        lauffender_punkt = Programmpunkt.query.filter(
            Programmpunkt.termin_id == aktuelles_lager.id,
            Programmpunkt.tag == heute_tag,
            Programmpunkt.uhrzeit <= jetzt_zeit,
            Programmpunkt.ende >= jetzt_zeit
        ).first()
        status_objekt = lauffender_punkt
    else:
        heutiger_termin = Termin.query.filter(
            Termin.start <= heute_datum,
            Termin.ende >= heute_datum,
            Termin.versteckt == False
        ).first()
        if heutiger_termin:
            modus = "heute"
            status_objekt = heutiger_termin
        else:
            status_objekt = Termin.query.filter(
                Termin.start > heute_datum,
                Termin.versteckt == False
            ).order_by(Termin.start).first()
            if status_objekt:
                modus = "termin"
            else:
                modus = "leer"

    meine_bloecke = current_user.bloecke if current_user.is_authenticated else []

    return render_template('index.html', infos=aktuelle_infos, freie_schichten=freie_schichten_anzahl,
                           modus=modus, status=status_objekt, heute_tag=heute_tag,
                           aktuelles_lager=aktuelles_lager, meine_bloecke=meine_bloecke)

@app.route('/info_speichern', methods=['POST'])
@login_required
def info_speichern():
    nachricht = request.form.get('nachricht')
    if nachricht and nachricht.strip():
        neue_info = Info(nachricht=nachricht, zeitstempel=datetime.now(ZoneInfo('Europe/Berlin')))
        db.session.add(neue_info)
        db.session.commit()

    return redirect('/')

@app.route('/info_loeschen/<int:id>', methods=['POST'])
@login_required
@require_role('admin')
def info_loeschen(id):
    info_punkt = db.session.get(Info, id)
    if info_punkt:
        db.session.delete(info_punkt)
        db.session.commit()

    return redirect('/')

@app.route('/sw.js')
def service_worker():
    return app.send_static_file('sw.js')

@app.errorhandler(404)
def nicht_gefunden(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_fehler(e):
    return render_template('500.html'), 500

from kueche import kueche_bp
app.register_blueprint(kueche_bp)

from konzepte import konzepte_bp
app.register_blueprint(konzepte_bp)

from termine import termine_bp
app.register_blueprint(termine_bp)

from programm import programm_bp
app.register_blueprint(programm_bp)

from protokoll import protokoll_bp
app.register_blueprint(protokoll_bp)

from schichtplan import schichtplan_bp
app.register_blueprint(schichtplan_bp)

from todos import todos_bp
app.register_blueprint(todos_bp)

from auth import auth
app.register_blueprint(auth)

from admin import admin_bp
app.register_blueprint(admin_bp)

from bloecke import bloecke_bp
app.register_blueprint(bloecke_bp)

from push_notifications import push_bp, scheduler
app.register_blueprint(push_bp)
scheduler.init_app(app)
scheduler.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)


