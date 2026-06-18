# KLJB Litzendorf – Projektdokumentation

Interne Web-App (PWA) für die ehrenamtlichen Gruppenleiter der KLJB Litzendorf.
Verwaltet Termine, Programmplanung (Zeltlager/Kindertage), Schichtpläne, Sitzungsprotokolle,
Aufgaben (Todos), Küchen-/Einkaufsplanung und versendet Push-Benachrichtigungen.

---

## Tech-Stack

- **Python / Flask** (Blueprints), Server: **gunicorn** hinter Reverse-Proxy
- **SQLAlchemy** + **SQLite** (Datei `kljb_zentrum.db`)
- **Flask-Login** (Auth), **Flask-WTF** (CSRF), **Flask-Limiter** (Rate-Limiting)
- **Flask-Migrate** (Alembic, Ordner `migrations/`)
- **pywebpush** + **Flask-APScheduler** (Push-Benachrichtigungen & tägliche Jobs)
- Frontend: serverseitige Jinja2-Templates, Vanilla JS, Lucide-Icons; **PWA** mit Service Worker
- Abhängigkeiten: siehe `requirements.txt`

---

## Projektstruktur

Einstiegspunkt ist `app.py` (App-Factory-artig, registriert alle Blueprints, Login-Manager,
CSRF, Security-Header, Scheduler, `db.create_all()` beim Start).

| Datei | Blueprint | Zuständig für |
|---|---|---|
| `app.py` | — | Startseite (`/`), Infos, `/sw.js`, Error-Handler, Setup aller Erweiterungen |
| `auth.py` | `auth` | Login, Logout, Passwort ändern |
| `admin.py` | `admin_bp` | Leiterverwaltung, Schichtplan generieren, Admin-Konsole, Erst-Setup |
| `termine.py` | `termine_bp` | Termine, Event-Planung, Abstimmungen, Anwesenheiten |
| `programm.py` | `programm_bp` | Programm-Anzeige & -Archiv |
| `bloecke.py` | `bloecke_bp` | Programmblöcke (Entwurf → Einreichen → Übernehmen-Workflow) |
| `protokoll.py` | `protokoll_bp` | Sitzungsprotokolle, TOPs, Archiv (erzeugt Todos beim Archivieren) |
| `schichtplan.py` | `schichtplan_bp` | Schichtplan ansehen, Schicht übernehmen/abgeben |
| `todos.py` | `todos_bp` | Aufgabenliste; Admin kann Todos erstellen/löschen |
| `kueche.py` | `kueche_bp` | Küche, Rezepte, Einkaufsliste, Packliste |
| `konzepte.py` | `konzepte_bp` | Spiele-/Konzept-Datenbank |
| `push_notifications.py` | `push_bp` | Push-Subscriptions, Versand-Helper, APScheduler-Jobs |
| `models.py` | — | Alle SQLAlchemy-Modelle |
| `decorators.py` | — | `require_role(*rollen)` – Rollen-Schutz für Routen |
| `extensions.py` | — | `limiter` (Flask-Limiter-Instanz) |

Templates in `templates/`, statische Dateien in `static/` (CSS, JS, Icons, `sw.js`, `manifest.json`).

---

## Datenmodell (`models.py`)

Wichtigste Modelle:
- **Gruppenleiter** (`UserMixin`): Nutzer. Flags `ist_admin`, `ist_kueche`; `name` ist **unique**.
  Passwort-Hashing via Werkzeug (`set_password`/`check_password`). Login-Sperre über
  `fehlversuche`/`gesperrt_bis`, Zwangs-Passwortwechsel über `muss_passwort_aendern`.
- **Termin**: Veranstaltungen. `typ` ∈ {zeltlager, kindertage, gruppenleiterrunde}.
  Soft-Delete über Flag `versteckt` (für Archiv-Typen, statt echtem Löschen).
- **Programmpunkt / Programmblock / Blockpunkt**: Programmplanung. Blöcke durchlaufen
  Status `entwurf → eingereicht → uebernommen`; beim Übernehmen werden Programmpunkte erzeugt.
- **Protokoll / ProtokollPunkt / ProtokollEntwurfTop**: laufendes Protokoll (Entwurf-TOPs) →
  beim Archivieren entstehen Protokoll + Punkte + **Todos** für zugewiesene Leiter.
- **Todo**: `aufgabe`, `leiter_id`, `quelle`, `erledigt`.
- **Schicht**: `event_name`, `datum`, `uhrzeit`, `leiter_id` (NULL = frei).
- **PushSubscription**: `leiter_id`, `endpoint` (unique), `p256dh`, `auth`.
- Weitere: Anwesenheit, Abstimmungsantwort, Konzept, Info, Einstellung, Rezept, Zutat,
  EinkaufslisteGespeichert/-Eintrag.

---

## Rollen & Zugriffsschutz

Drei Rollen, abgeleitet aus Flags am Gruppenleiter: **admin**, **kueche**, **leiter** (Standard).
- Routen schützen mit `@require_role('admin')` (aus `decorators.py`) – prüft `ist_<rolle>`,
  bei Fehlen Redirect auf `/` mit Flash.
- Im Template analog: `{% if current_user.ist_admin %} … {% endif %}`.
- **Wichtig:** UI-Sichtbarkeit reicht nie als Schutz – die Route **immer zusätzlich**
  serverseitig mit dem Decorator absichern.

---

## Push-Benachrichtigungen

Implementiert in `push_notifications.py`. Helper:
- `send_push_to_all(title, body, url='/')`
- `send_push_to_user(leiter_id, title, body, url='/')`

Abgelaufene Subscriptions (HTTP 404/410) werden automatisch aus der DB gelöscht.
Frontend: `static/js/push.js` (Banner + Subscribe), Service-Worker-Handler in `static/sw.js`.
Im `<head>` von `layout.html` liefern Meta-Tags `csrf-token` und `vapid-public-key` an das JS.

**Auslöser (9):** neuer Termin, archiviertes Protokoll, neuer Schichtplan, Schicht frei
geworden (je an alle); Block zugewiesen + neue Todo-Aufgabe (an betroffene Leiter);
neuer Programmzeitplan (an alle). Dazu zwei tägliche **APScheduler**-Jobs (Zeitzone
Europe/Berlin): **08:00** Erinnerung an freie Schichten (an alle, falls vorhanden),
**09:00** Erinnerung an offene Todos (pro Nutzer, falls vorhanden).

> ⚠️ **VAPID-Falle:** Der `VAPID_PRIVATE_KEY` in `key.env` **muss in einer einzigen Zeile**
> stehen (raw base64url, P-256). Steht er umgebrochen über mehrere Zeilen, liest dotenv nur
> die erste Zeile → der Key ist abgeschnitten → `Could not deserialize key data … ASN.1
> parsing error: short data`, und alle Pushes scheitern still. `VAPID_PUBLIC_KEY` muss zum
> privaten Schlüssel passen, sonst werden bestehende Subscriptions ungültig.

---

## Konfiguration (`key.env`)

Wird via `load_dotenv('key.env')` geladen. Enthält **Secrets – nicht committen** (steht in `.gitignore`):
- `SECRET_KEY` – Flask-Session-Schlüssel (Pflicht, sonst Startabbruch)
- `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIM_EMAIL` – Web Push
- `ADMIN_NAME`, `ADMIN_PASSWORT` – für Erst-Setup (`/erster_admin_setup`, nur wenn `SETUP_ERLAUBT=ja`)
- `STANDARD_PASSWORT` – Passwort-Reset-Vorgabe
- `FLASK_ENV` – bei `production` werden Secure-Cookies aktiviert

---

## Lokale Entwicklung

```bash
# Linux/Mac:
python -m venv venv && source venv/bin/activate
# Windows (PowerShell):  python -m venv venv ; .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
# key.env mit den nötigen Werten anlegen (siehe oben)
python app.py            # startet auf http://0.0.0.0:5000 (debug=False)
```

DB-Schemaänderungen: Modelle in `models.py` anpassen. Da `app.py` beim Start `db.create_all()`
aufruft, werden **neue Tabellen** automatisch angelegt. **Aber Achtung:** `create_all` fügt
**keine neuen Spalten** zu bereits bestehenden Tabellen hinzu – dafür Alembic nutzen
(`flask db migrate -m "…"` / `flask db upgrade`) oder notfalls per Hand `ALTER TABLE`. Die
Migrationen sind inkrementelle Patches auf das per `create_all` gebaute Schema (kein
„from scratch"-Aufbau).

---

## Repository / Versionskontrolle

Privates GitHub-Repo: **https://github.com/4ndi37/kljb-litzendorf-app** (Account `4ndi37`).
Repo-Wurzel ist dieser Ordner (`Programmierdateien/`), Branch `main`, Remote `origin`.

- **`.gitignore` schützt Secrets/Daten:** `key.env`, `*.db`, `*.bak`, `venv/`, `*.log`,
  `__pycache__/` u.a. landen **nie** im Repo. Im Zweifel vor dem Push mit `git status` bzw.
  `git check-ignore <datei>` prüfen.
- **Git ≠ Deployment:** `git push` lädt nur Code zu GitHub (Versionierung/Backup) und ändert
  **nichts** auf dem Server. Das Ausrollen läuft separat per rsync (siehe unten).
- Alltag: `git add -A` → `git commit -m "…"` → `git push`.

---

## Deployment

Produktivserver: **`kljb@178.104.253.215`**, App-Verzeichnis **`~/app/`** (= `/home/kljb/app/`).
systemd-Service **`kljb`** (gunicorn auf `127.0.0.1:5000`).

```bash
# 1) Dateien hochladen (vom Entwicklungsrechner)
rsync -avz --exclude '__pycache__' --exclude '*.pyc' --exclude '*.db' \
  <projektordner>/ kljb@178.104.253.215:~/app/

# 2) Auf dem Server: ggf. neue Abhängigkeiten
source ~/app/venv/bin/activate && pip install -r ~/app/requirements.txt

# 3) Neustart
sudo systemctl restart kljb

# Logs
sudo journalctl -u kljb -n 50 --no-pager
```

- **Neue DB-Migrationen?** Nach dem rsync auf dem Server einmal `flask db upgrade` ausführen
  (venv aktiv, `export FLASK_APP=app.py`). Der App-Start selbst spielt **keine** Migrationen ab
  (nur `create_all`), Spaltenänderungen also nicht vergessen.
- **DB-Datei ist `kljb_zentrum.db`** (nicht `kljb.db`!) – bei DB-Abfragen darauf achten:
  `sqlite3 ~/app/kljb_zentrum.db "…"`.
- `key.env` und die DB liegen auf dem Server und werden **nicht** per rsync überschrieben
  (durch `--exclude '*.db'` bzw. weil `key.env` separat gepflegt wird).
- Reiner Template-/Static-Änderung genügt der Neustart nicht zwingend (Browser lädt statische
  Dateien direkt); Route-/Python-Änderungen brauchen `systemctl restart kljb`.

---

## Fallstricke / Konventionen

- **POST-Formulare** brauchen das CSRF-Feld: `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`.
- **Mehrfachauswahl von Leitern**: wiederverwendbares Widget `static/js/multi_select.js` –
  `new MultiSelect('container-id', opts, 'feldname', 'Platzhalter')`; erzeugt pro Auswahl ein
  `<input name="feldname">`, im Backend mit `request.form.getlist('feldname')` lesen
  (Beispiele in `bloecke.py`, `todos.py`).
- Termine der Archiv-Typen werden **soft-deleted** (`versteckt=True`), nicht real gelöscht.
- Zeitzonenabhängige Logik nutzt `Europe/Berlin`.

---

## Offene Punkte / Ideen

- Gruppenleiter umbenennen: aktuell keine UI-Funktion – nur per direktem DB-`UPDATE`.
