from flask import Flask, request, jsonify, render_template, send_file, redirect, url_for, session
import sqlite3, qrcode, io, base64, json, uuid, datetime, os, zipfile
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage

app = Flask(__name__)
app.secret_key = "super_secret_key_for_session"

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    # Base table (for fresh DB)
    conn.execute('''CREATE TABLE IF NOT EXISTS teams (
                        team_id TEXT PRIMARY KEY,
                        team_name TEXT NOT NULL,
                        members TEXT NOT NULL,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS members (
                        member_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        team_id TEXT,
                        member_name TEXT,
                        check_in INTEGER DEFAULT 0,
                        check_out INTEGER DEFAULT 0,
                        snacks INTEGER DEFAULT 0,
                        dinner INTEGER DEFAULT 0,
                        round1 INTEGER DEFAULT 0,
                        refresh2 INTEGER DEFAULT 0,
                        round2 INTEGER DEFAULT 0,
                        refresh3 INTEGER DEFAULT 0,
                        round3 INTEGER DEFAULT 0
                    )''')

    # If DB already existed earlier, add new columns safely
    try:
        conn.execute("ALTER TABLE members ADD COLUMN round1 INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE members ADD COLUMN refresh2 INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE members ADD COLUMN round2 INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE members ADD COLUMN refresh3 INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE members ADD COLUMN round3 INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


init_db()

# ---------------- FONT + LOGO HELPERS ----------------

def load_bold_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except:
            continue
    return ImageFont.load_default()

def fit_text(draw, text, max_width, start_size):
    size = start_size
    while size >= 14:
        font = load_bold_font(size)
        width = draw.textlength(text, font=font)
        if width <= max_width:
            return font
        size -= 2
    return load_bold_font(14)

def add_logo_to_qr(qr_img):
    logo_path = os.path.join("static", "logo.png")
    if not os.path.exists(logo_path):
        return qr_img

    logo = Image.open(logo_path).convert("RGBA")
    qr_w, qr_h = qr_img.size
    logo_size = qr_w // 5
    logo = logo.resize((logo_size, logo_size))
    pos = ((qr_w - logo_size) // 2, (qr_h - logo_size) // 2)
    qr_img.paste(logo, pos, logo)
    return qr_img

def generate_qr_with_text(team_name, qr_payload):
    qr = qrcode.QRCode(version=4, box_size=16, border=6)
    qr.add_data(qr_payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_img = add_logo_to_qr(qr_img)

    qr_w, qr_h = qr_img.size
    side_pad = int(qr_w * 0.12)
    bottom_area = int(qr_h * 0.40)

    new_w = qr_w + side_pad * 2
    new_h = qr_h + bottom_area

    canvas = Image.new("RGB", (new_w, new_h), "white")
    qr_x = (new_w - qr_w) // 2
    canvas.paste(qr_img, (qr_x, 0))

    draw = ImageDraw.Draw(canvas)
    text = team_name.upper()

    max_text_width = new_w - int(new_w * 0.12)
    start_font_size = max(72, qr_w // 5)
    font = fit_text(draw, text, max_text_width, start_font_size)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    text_x = (new_w - text_w) // 2
    text_y = qr_h + (bottom_area - text_h) // 2

    draw.text((text_x, text_y), text, font=font, fill="black", stroke_width=3, stroke_fill="gray")
    return canvas


# ---------------- ROUTES ----------------

# ----------- LOGIN -----------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form.get('role')
        password = request.form.get('password')

        if role == 'admin' and password == 'admin123':
            session['role'] = 'admin'
            return redirect(url_for('admin'))
        elif role == 'coordinator' and password == 'coord123':
            session['role'] = 'coordinator'
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid credentials!")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ----------- REGISTER TEAM -----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        data = request.json
        team_name = data.get("team_name", "").strip()
        members = [m.strip() for m in data.get("members", []) if m.strip()]

        if not team_name or not members:
            return jsonify({"error": "Missing team name or members"}), 400

        team_id = str(uuid.uuid4())
        conn = get_db()

        conn.execute(
            "INSERT INTO teams (team_id, team_name, members) VALUES (?, ?, ?)",
            (team_id, team_name, json.dumps(members))
        )

        for m in members:
            conn.execute("INSERT INTO members (team_id, member_name) VALUES (?, ?)", (team_id, m))

        conn.commit()

        qr_payload = json.dumps({
            "team_id": team_id,
            "team_name": team_name,
            "members": members
        })

        qr_img = generate_qr_with_text(team_name, qr_payload)
        buf = io.BytesIO()
        qr_img.save(buf, format="PNG")
        qr_b64 = base64.b64encode(buf.getvalue()).decode()

        return jsonify({"team_id": team_id, "qr": qr_b64})

    return render_template("register.html")


# ----------- COORDINATOR DASHBOARD -----------
@app.route('/dashboard')
def dashboard():
    if session.get('role') != 'coordinator':
        return redirect(url_for('login'))
    return render_template('dashboard.html')


# ----------- ADMIN VIEW -----------
@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = get_db()
    teams = conn.execute(
        "SELECT * FROM teams ORDER BY datetime(last_updated) DESC"
    ).fetchall()

    teams_data = []
    for t in teams:
        members = conn.execute(
            "SELECT * FROM members WHERE team_id = ?", (t["team_id"],)
        ).fetchall()

        teams_data.append({
            "team": dict(t),
            "members": [dict(m) for m in members]
        })

    return render_template("admin.html", teams_data=teams_data)


# ----------- GET TEAM DETAILS -----------
@app.route("/get_team_details", methods=["POST"])
def get_team_details():
    data = request.json
    team_id = data.get("team_id")

    if not team_id:
        return jsonify({"error": "Team ID required"}), 400

    conn = get_db()
    team = conn.execute("SELECT * FROM teams WHERE team_id = ?", (team_id,)).fetchone()
    if not team:
        return jsonify({"error": "Team not found"}), 404

    members = conn.execute(
        "SELECT * FROM members WHERE team_id = ?", (team_id,)
    ).fetchall()

    return jsonify({
        "team": {
            "team_id": team["team_id"],
            "team_name": team["team_name"],
            "last_updated": team["last_updated"],
        },
        "members": [
            {
                "member_id": m["member_id"],
                "member_name": m["member_name"],
                "check_in": m["check_in"],
                "snacks": m["snacks"],       # Refreshment-1 (4 PM)
                "round1": m["round1"],       # Round 1 eval
                "dinner": m["dinner"],       # Dinner (10 PM)
                "refresh2": m["refresh2"],   # Refreshment-2 (3 AM)
                "round2": m["round2"],       # Round 2 eval
                "refresh3": m["refresh3"],   # Refreshment-3 (10 AM)
                "round3": m["round3"],       # Round 3 eval
                "check_out": m["check_out"]
            }
            for m in members
        ]
    })


# ----------- UPDATE MEMBER STATUS -----------
@app.route("/update_members", methods=["POST"])
def update_members():
    data = request.json
    updates = data.get("members", [])
    team_id = data.get("team_id")

    if not team_id or not updates:
        return jsonify({"error": "Invalid data"}), 400

    conn = get_db()

    for m in updates:
        conn.execute('''
            UPDATE members SET 
                check_in = ?, 
                snacks = ?,      -- Refreshment-1
                round1 = ?,      -- Round 1 eval
                dinner = ?,      -- Dinner
                refresh2 = ?,    -- Refreshment-2
                round2 = ?,      -- Round 2 eval
                refresh3 = ?,    -- Refreshment-3
                round3 = ?,      -- Round 3 eval
                check_out = ?
            WHERE member_id = ?
        ''', (
            m.get("check_in", 0),
            m.get("snacks", 0),
            m.get("round1", 0),
            m.get("dinner", 0),
            m.get("refresh2", 0),
            m.get("round2", 0),
            m.get("refresh3", 0),
            m.get("round3", 0),
            m.get("check_out", 0),
            m["member_id"]
        ))

    conn.execute(
        "UPDATE teams SET last_updated = CURRENT_TIMESTAMP WHERE team_id = ?",
        (team_id,)
    )

    conn.commit()
    return jsonify({"status": "updated"})


# ----------- DELETE TEAM -----------
@app.route("/delete_team/<team_id>", methods=["POST"])
def delete_team(team_id):
    conn = get_db()
    conn.execute("DELETE FROM members WHERE team_id = ?", (team_id,))
    conn.execute("DELETE FROM teams WHERE team_id = ?", (team_id,))
    conn.commit()
    return redirect(url_for("admin"))


# ----------- DELETE ALL DATA -----------
@app.route("/delete_all", methods=["POST"])
def delete_all():
    conn = get_db()
    conn.execute("DELETE FROM members")
    conn.execute("DELETE FROM teams")
    conn.commit()
    return redirect(url_for("admin"))


# ----------- SHOW & DOWNLOAD SINGLE TEAM QR -----------
@app.route("/team_qr/<team_id>")
def team_qr(team_id):
    team_id = str(team_id).strip()

    conn = get_db()
    team = conn.execute("SELECT * FROM teams WHERE team_id = ?", (team_id,)).fetchone()
    if not team:
        return f"Team not found: {team_id}", 404

    qr_payload = json.dumps({
        "team_id": team["team_id"],
        "team_name": team["team_name"],
        "members": json.loads(team["members"])
    })

    qr_img = generate_qr_with_text(team["team_name"], qr_payload)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG", dpi=(300, 300))
    buf.seek(0)

    return send_file(buf, mimetype="image/png")


@app.route("/download_qr/<team_id>")
def download_qr(team_id):
    team_id = str(team_id).strip()

    conn = get_db()
    team = conn.execute("SELECT * FROM teams WHERE team_id = ?", (team_id,)).fetchone()
    if not team:
        return f"Team not found: {team_id}", 404

    qr_payload = json.dumps({
        "team_id": team["team_id"],
        "team_name": team["team_name"],
        "members": json.loads(team["members"])
    })

    qr_img = generate_qr_with_text(team["team_name"], qr_payload)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG", dpi=(300, 300))
    buf.seek(0)

    return send_file(
        buf,
        mimetype="image/png",
        as_attachment=True,
        download_name=f"{team['team_name']}.png"
    )


# ----------- EXPORT ALL QRs -----------
@app.route("/export_qrs")
def export_qrs():
    conn = get_db()
    teams = conn.execute("SELECT * FROM teams").fetchall()

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for t in teams:
            qr_payload = json.dumps({
                "team_id": t["team_id"],
                "team_name": t["team_name"],
                "members": json.loads(t["members"])
            })

            qr_img = generate_qr_with_text(t["team_name"], qr_payload)

            img_buffer = io.BytesIO()
            qr_img.save(img_buffer, format="PNG")
            img_buffer.seek(0)

            zipf.writestr(f"{t['team_name']}.png", img_buffer.read())

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name="All_QRs.zip"
    )


# ----------- EVENT REPORT (PDF) -----------
@app.route("/event_report")
def event_report():
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()
    story = []

    logo_path = os.path.join("static", "logo.png")
    if os.path.exists(logo_path):
        story.append(RLImage(logo_path, width=80, height=80))
        story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Ignitron 2k25 - Code Rush Event Report</b>", styles["Title"]))
    story.append(Paragraph(f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
    story.append(Spacer(1, 12))

    conn = get_db()
    row = conn.execute("SELECT SUM(check_in), SUM(snacks), SUM(dinner), SUM(check_out) FROM members").fetchone()

    story.append(Paragraph("<b>Stats Summary</b>", styles["Heading2"]))
    story.append(Paragraph(
        f"✅ Check-Ins: {row[0] or 0} &nbsp;&nbsp; 🍪 Snacks: {row[1] or 0} "
        f"&nbsp;&nbsp; 🍽️ Dinners: {row[2] or 0} &nbsp;&nbsp; 🚪 Check-Outs: {row[3] or 0}",
        styles["Normal"]
    ))
    story.append(Spacer(1, 10))

    teams = conn.execute("SELECT * FROM teams ORDER BY team_name").fetchall()
    data = [["Team Name", "Members", "Last Updated"]]
    for t in teams:
        members_str = ", ".join(json.loads(t["members"]))
        data.append([t["team_name"], members_str, t["last_updated"]])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#00b894")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(table)
    story.append(Spacer(1, 18))
    story.append(Paragraph("<para align='center'><b>Built with 💙 by Samarth S G | Ignitron 2k25</b></para>", styles["Normal"]))

    doc.build(story)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="Ignitron_Report.pdf")


# ----------- STATS -----------
@app.route("/stats")
def stats():
    conn = get_db()
    row = conn.execute('''
        SELECT 
            SUM(check_in) AS in_t,
            SUM(snacks) AS sn_t,
            SUM(dinner) AS dn_t,
            SUM(check_out) AS out_t
        FROM members
    ''').fetchone()

    return jsonify({
        "check_in": row["in_t"] or 0,
        "snacks": row["sn_t"] or 0,
        "dinner": row["dn_t"] or 0,
        "check_out": row["out_t"] or 0,
    })


# ----------- RUN APP -----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
