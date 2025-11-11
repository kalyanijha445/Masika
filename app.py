import os
import random
import sqlite3
import time
import re # Added for better text parsing
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw
from fpdf import FPDF
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import platform

# ==============================================================================
# 1. GLOBAL CONFIGURATIONS
# ==============================================================================

# --- API Keys & Credentials ---
GEMINI_API_KEY = "AIzaSyD_OzWez__4EpgH-AKIhnzh0ljUfqIcu5U"
EMAIL_SENDER = "info.masika@gmail.com"  
EMAIL_PASSWORD = "tglf gszh exgn gnmz"       
EMAIL_RECEIVER = "vishmapasayat003@gmail.com"

# --- Gemini AI Safety Settings ---
SAFETY_SETTINGS = [
    {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_NONE},
    {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_NONE},
    {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
    {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_NONE}
]

# --- Application & Database Settings ---
DB_NAME = "cycle_users.db"
UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_EXT = {"jpg", "jpeg", "png", "bmp", "tiff"}

# --- Language Mapping ---
LANGUAGE_MAP = {
    "en": "English", "as": "Assamese", "bn": "Bengali", "brx": "Bodo", "doi": "Dogri",
    "gu": "Gujarati", "hi": "Hindi", "kn": "Kannada", "ks": "Kashmiri", "kok": "Konkani",
    "mai": "Maithili", "ml": "Malayalam", "mni": "Manipuri", "mr": "Marathi",
    "ne": "Nepali", "or": "Odia", "pa": "Punjabi", "sa": "Sanskrit", "sat": "Santali",
    "sd": "Sindhi", "ta": "Tamil", "te": "Telugu", "ur": "Urdu"
}

# ==============================================================================
# 2. FLASK APP INITIALIZATION
# ==============================================================================

app = Flask(__name__)
app.secret_key = "super_secret_key_replace_this"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Configure Google AI ---
genai.configure(api_key=GEMINI_API_KEY)


# ==============================================================================
# 3. HELPER FUNCTIONS
# ==============================================================================

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            email TEXT UNIQUE,
            age INTEGER,
            password TEXT
        )
    ''')
    conn.commit()
    conn.close()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

def _wrap_long_tokens(text, max_len=60):
    # This helper remains useful for PDF wrapping if needed
    out = []
    for token in (text or "").split():
        if len(token) <= max_len:
            out.append(token)
        else:
            chunks = [token[i:i+max_len] for i in range(0, len(token), max_len)]
            out.append(" ".join(chunks))
    return " ".join(out)

def sanitize_text_for_pdf(text):
    # Replace unsupported Unicode characters with safe alternatives
    # Latin-1 only supports 0–255
    return text.replace("•", "").encode("latin-1", "replace").decode("latin-1")

# ===== UPDATED & CORRECTED PDF GENERATION FUNCTION =====
def create_pdf_report(patient_name, summary_text, meta: dict):
    # --- Masika Brand & Info ---
    BRAND_NAME = "MASIKA"
    BRAND_TAGLINE = "Rewrite Your Period Story"
    BRAND_WEBSITE = "https://masika.onrender.com"
    BRAND_EMAIL = "info.masika@gmail.com"
    BRAND_PHONE = "+91 6371646251"
    BRAND_ADDRESS = "BPUT Campus, Biju Patnaik University Of Technology, Odisha, Rourkela - 769015"
    LOGO_PATH = os.path.join("static", "logo.png")
    
    # --- Professional & Modern Color Palette ---
    COLOR_PRIMARY_LIGHT = (245, 235, 238)  # Very light pink for subtle backgrounds
    COLOR_ACCENT = (235, 120, 140)         # A softer pink for subtle lines/accents
    COLOR_TEXT_DARK = (45, 45, 45)         # Dark charcoal for main text and new headers
    COLOR_TEXT_MEDIUM = (85, 85, 85)       # Grey for labels and secondary text
    COLOR_TEXT_LIGHT = (140, 140, 140)     # Light grey for meta info
    COLOR_WHITE = (255, 255, 255)
    GRADIENT_START = (255, 255, 255)       # Gradient: White
    GRADIENT_END = (252, 240, 243)         # Gradient: Very soft pink

    # Helper function to generate a gradient image for the header
    def create_gradient_header(width, height, start_color, end_color, filename):
        img = Image.new("RGB", (width, height), "#FFFFFF")
        draw = ImageDraw.Draw(img)
        r1, g1, b1 = start_color; r2, g2, b2 = end_color
        for i in range(height):
            r = int(r1 + (r2 - r1) * i / height); g = int(g1 + (g2 - g1) * i / height); b = int(b1 + (b2 - b1) * i / height)
            draw.line([(0, i), (width, i)], fill=(r, g, b))
        img.save(filename); return filename

    # Custom PDF class for automatic header/footer
    class PDF(FPDF):
        def footer(self):
            self.set_y(-18)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(*COLOR_TEXT_LIGHT)
            self.set_draw_color(*COLOR_PRIMARY_LIGHT)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(3)
            self.cell(0, 5, BRAND_ADDRESS, 0, 1, 'C')
            self.cell(0, 5, f'Page {self.page_no()}', 0, 0, 'C')

    # --- PDF Initialization ---
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)
    try:
        pdf.add_font('Arial', '', 'c:/windows/fonts/arial.ttf', uni=True)
        pdf.add_font('Arial', 'B', 'c:/windows/fonts/arialbd.ttf', uni=True)
        pdf.add_font('Arial', 'I', 'c:/windows/fonts/ariali.ttf', uni=True)
    except RuntimeError:
        print("Arial font not found, falling back to core FPDF fonts.")
    pdf.set_font("Arial", "", 10)

    # --- 1. Header Section ---
    gradient_img_path = create_gradient_header(210, 32, GRADIENT_START, GRADIENT_END, os.path.join(app.config["UPLOAD_FOLDER"], "header_gradient.png"))
    pdf.image(gradient_img_path, 0, 0, 210, 32)
    if os.path.exists(LOGO_PATH):
        pdf.image(LOGO_PATH, 15, 8, 16)

    pdf.set_xy(35, 9); pdf.set_font('Arial', 'B', 20); pdf.set_text_color(*COLOR_TEXT_DARK); pdf.cell(0, 8, BRAND_NAME)
    pdf.set_xy(35, 17); pdf.set_font('Arial', 'I', 9); pdf.set_text_color(*COLOR_TEXT_MEDIUM); pdf.cell(0, 8, BRAND_TAGLINE)
    
    pdf.set_xy(145, 9); pdf.set_font('Arial', '', 8); pdf.set_text_color(*COLOR_TEXT_DARK)
    pdf.cell(0, 5, f"Email: {BRAND_EMAIL}", ln=True, align='R'); pdf.set_x(145)
    pdf.cell(0, 5, f"Phone: {BRAND_PHONE}", ln=True, align='R'); pdf.set_x(145)
    pdf.cell(0, 5, f"Website: {BRAND_WEBSITE}", ln=True, align='R'); pdf.ln(18)

    # --- 2. Report Title ---
    pdf.set_font('Arial', 'B', 20)
    pdf.set_text_color(*COLOR_TEXT_DARK)
    pdf.cell(0, 10, "AI-Analysed Health Report", ln=True, align='C') 
    pdf.ln(12)

    # --- 3. Patient Information Block (Redesigned & Corrected Alignment) ---
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(*COLOR_ACCENT)
    pdf.cell(0, 8, "Patient & Report Details", ln=True)
    pdf.set_draw_color(220, 220, 220)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y()); pdf.ln(5)

    def info_row(label, value): 
        pdf.set_font('Arial', 'B', 10); pdf.set_text_color(*COLOR_TEXT_MEDIUM)
        pdf.cell(45, 7, label, align='L')
        pdf.set_font('Arial', '', 10); pdf.set_text_color(*COLOR_TEXT_DARK)
        pdf.cell(5, 7, ":")
        pdf.cell(0, 7, str(value), ln=True)
    
    report_id = f"MSK-{random.randint(100000, 999999)}"
    
    y_start = pdf.get_y()
    pdf.set_x(15); info_row("Patient Name", patient_name)
    pdf.set_x(15); info_row("Patient Age", meta.get("Age", "N/A"))
    pdf.set_x(15); info_row("Typical Cycle Length", f"{meta.get('Cycle Length (days)', 'N/A')} days")
    y_left_end = pdf.get_y()
    
    pdf.set_xy(110, y_start); info_row("Typical Period Duration", f"{meta.get('Period Days', 'N/A')} days")
    pdf.set_x(110); info_row("Report ID", report_id)
    pdf.set_x(110); info_row("Report Generated On", meta.get("Report Generated", "N/A"))
    y_right_end = pdf.get_y()
    
    pdf.set_y(max(y_left_end, y_right_end) + 5) 

    # --- 4. Report Body (Corrected Parsing) ---
    def parse_masika_sections(text):
        sections = {}
        parts = re.split(r'\n*\s*(?=(SUMMARY|WHAT_TO_DO|WHAT_TO_AVOID|DIET_SUGGESTIONS|FOLLOW_UP):)', text)
        for i in range(1, len(parts), 2):
            keyword = parts[i]
            # Strip colon from the start of the content
            content = parts[i+1].lstrip(':').strip()
            
            # ===== FIX #1: REMOVE DUPLICATE TITLE FROM CONTENT =====
            # This handles cases where the AI inconsistently includes the title again.
            if content.upper().startswith(keyword + ':'):
                content = content[len(keyword)+1:].strip()

            content = re.sub(r'[\*\-]', '•', content) 
            sections[keyword] = content
        return sections

    sections = parse_masika_sections(summary_text)
    section_order = ["SUMMARY", "WHAT_TO_DO", "WHAT_TO_AVOID", "DIET_SUGGESTIONS", "FOLLOW_UP"]

    for title_key in section_order:
        if title_key in sections and sections[title_key]:
            pdf.ln(5)
            # Section Header with new dark gray color
            pdf.set_font('Arial', 'B', 14)
            pdf.set_text_color(*COLOR_WHITE)
            # ===== FIX #2: CHANGE HEADER BACKGROUND COLOR =====
            pdf.set_fill_color(*COLOR_ACCENT) 
            section_title = f"  {title_key.replace('_', ' ').title()}  "
            pdf.cell(pdf.get_string_width(section_title) + 5, 9, section_title, ln=True, fill=True); pdf.ln(4)

            pdf.set_font('Arial', '', 10.5)
            pdf.set_text_color(*COLOR_TEXT_DARK)
            content_lines = [line.strip() for line in sections[title_key].split('\n') if line.strip()]
            
            # === CHANGE STARTS HERE ===
            for idx, line in enumerate(content_lines, start=1):
                line = sanitize_text_for_pdf(line)  # Remove unsupported characters
                if line.startswith('•'):
                    pdf.set_x(15)
                    pdf.cell(5, 6, f"{idx}.")  # Number instead of bullet
                    pdf.multi_cell(180, 6, line[1:].strip())
                else: 
                    pdf.set_x(10)
                    pdf.multi_cell(190, 6, line)
                pdf.ln(2)
            # === CHANGE ENDS HERE ===

    # --- 5. Disclaimer Section ---
    pdf.set_y(-45)
    pdf.set_fill_color(*COLOR_PRIMARY_LIGHT)
    pdf.rect(10, pdf.get_y() - 2, 190, 19, 'F')
    
    pdf.set_xy(12, pdf.get_y()); pdf.set_font('Arial', 'B', 9); pdf.set_text_color(*COLOR_TEXT_MEDIUM); pdf.cell(0, 6, "Disclaimer", ln=True)
    pdf.set_x(12); pdf.set_font('Arial', 'I', 8)
    pdf.multi_cell(186, 4, "This is an AI-assisted report generated by MASIKA for informational purposes only. It is not a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider for any medical concerns.")
    
    # --- 6. Generate the PDF file ---
    fname = f"{patient_name.replace(' ', '_')}_masika_report_{int(time.time())}.pdf"
    out_path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
    pdf.output(out_path)
    return out_path
# ===== END OF PDF FUNCTION =====


def image_to_text_via_gemini(image_path):
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        with open(image_path, "rb") as f:
            img_bytes = f.read()
            img_part = {"mime_type": "image/jpeg", "data": img_bytes}
            prompt_parts = [
                img_part,
                "Please extract any lab values (name:value pairs) from this lab report image. Return results as 'Marker: Value' lines. If none found, say 'NO_VALUES_FOUND'.",
            ]
            response = model.generate_content(prompt_parts, safety_settings=SAFETY_SETTINGS)
        return response.text
    except Exception as e:
        return f"ERROR_READING_IMAGE: {e}"

def parse_lab_values_text(extracted_text):
    values = {}
    if not extracted_text:
        return values
    for line in extracted_text.splitlines():
        line = line.strip()
        if not line: continue
        parts = re.split(r'[:=-]', line, 1)
        if len(parts) != 2:
            m = re.search(r"([A-Za-z\s\/]+)\s+([\d\.]+)", line)
            if m:
                parts = [m.group(1).strip(), m.group(2)]
            else:
                continue
        key = parts[0].strip()
        val = parts[1].strip()
        if key and val:
            values[key] = val
    return values

def generate_recommendations_from_inputs(age, cycle_days, period_days, description, lab_values, language="en"):
    model = genai.GenerativeModel("gemini-2.0-flash")
    language_name = LANGUAGE_MAP.get(language, "English")
    
    prompt_lines = [
        "You are an expert AI health assistant specializing in women's cyclical health. Your primary task is to perform an integrated analysis by deeply correlating the user's written symptoms with their lab results, all within the context of their age and cycle data. Your response must be highly personalized based on these connections. Crucially, you MUST NOT give a medical diagnosis. Instead, provide intelligent insights and safe, actionable suggestions.",
        f"IMPORTANT: All explanatory text and suggestions must be in the '{language_name}' language. However, the section keywords ('SUMMARY:', 'WHAT_TO_DO:', etc.) MUST remain in English.",
        "Structure your response with these exact keywords, each on a new line: SUMMARY:, WHAT_TO_DO:, WHAT_TO_AVOID:, DIET_SUGGESTIONS:, FOLLOW_UP:",
        "For the SUMMARY: section, provide a concise paragraph that explicitly connects the user's symptoms (e.g., fatigue, pain) with specific lab values (e.g., low hemoglobin). Acknowledge their age as a contributing factor.",
        "For the WHAT_TO_DO:, DIET_SUGGESTIONS:, etc., sections, ensure every bullet point (*) is a direct consequence of the analysis. For example, if symptoms suggest fatigue AND labs show low iron, a diet suggestion MUST specifically mention iron-rich foods and explain that it targets the suspected iron deficiency causing the fatigue. Do not give generic advice. All advice must be justified by the provided user data.",
        "\n--- Patient Data for Integrated Analysis ---",
        f"Age: {age}",
        f"Typical cycle length (days): {cycle_days}",
        f"Period duration (days): {period_days}",
        f"User-described Symptoms & Situation: {description or 'None provided'}",
        "Lab Values from Report (connect these to the symptoms):",
    ]
    
    if lab_values:
        for k, v in lab_values.items():
            prompt_lines.append(f"{k}: {v}")
    else:
        prompt_lines.append("No lab values were provided or could be extracted.")
    
    prompt = "\n".join(prompt_lines)
    
    try:
        response = model.generate_content([prompt], safety_settings=SAFETY_SETTINGS)
        return response.text
    except Exception as e:
        return f"ERROR_GENERATING_RECOMMENDATIONS: {e}"


# ==============================================================================
# 4. DATABASE INITIALIZATION CALL
# ==============================================================================
init_db()

# ==============================================================================
# 5. FLASK ROUTES
# ==============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_email" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/order_product', methods=['POST'])
@login_required
def order_product():
    product_name = request.form.get('product_name', 'Unknown Product')
    quantity = request.form.get('quantity', '1')
    address = request.form.get('address', '').strip()
    phone = request.form.get('phone', '').strip()

    user_name = session.get('user_name', 'Unknown User')
    user_email = session.get('user_email', 'No Email Provided')

    if not address or not phone:
        return jsonify({'success': False, 'message': 'Address and phone number are required.'})

    logo_url = "https://i.supaimg.com/dfa8394d-f6e0-4322-aab4-ee390fab1dd5.png"
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    email_body = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600&display=swap" rel="stylesheet">
        <title>New Product Order</title>
    </head>
    <body style="font-family: 'Poppins', sans-serif; background-color: #fdf6f7; margin: 0; padding: 0;">
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
            <tr>
                <td style="padding: 20px 0;">
                    <table align="center" role="presentation" border="0" cellpadding="0" cellspacing="0" width="600" style="max-width: 600px; width: 100%; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); margin: 0 auto; overflow: hidden; border: 1px solid #e1e1e1;">
                        <tr>
                            <td align="center" style="background: linear-gradient(135deg, #FF6B8B, #FFD194); padding: 30px 20px;">
                                <img src="{logo_url}" alt="MASIKA Logo" width="80" height="80" style="display: block; margin: 0 auto; border: 0;">
                                <h1 style="color: #ffffff; font-size: 28px; font-weight: 600; margin: 15px 0 0; letter-spacing: 0.5px; text-shadow: 1px 1px 2px rgba(0,0,0,0.1);">New Product Order</h1>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 35px 40px;">
                                <p style="font-size: 16px; color: #34495e; line-height: 1.6; margin-top: 0; font-weight: 400;">Hello, you've received a new order from the MASIKA app:</p>
                                <h2 style="color: #2c3e50; font-size: 20px; font-weight: 600; margin-top: 30px; margin-bottom: 20px; border-bottom: 2px solid #f2f2f2; padding-bottom: 12px;">Order Summary</h2>
                                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="font-size: 16px; color: #34495e; line-height: 1.7;">
                                    <tr>
                                        <td style="padding: 10px 0; font-weight: 600; width: 150px;">Product:</td>
                                        <td style="padding: 10px 0;">{product_name}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 10px 0; font-weight: 600;">Quantity:</td>
                                        <td style="padding: 10px 0;">{quantity}</td>
                                    </tr>
                                </table>
                                <h2 style="color: #2c3e50; font-size: 20px; font-weight: 600; margin-top: 35px; margin-bottom: 20px; border-bottom: 2px solid #f2f2f2; padding-bottom: 12px;">Customer Information</h2>
                                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="font-size: 16px; color: #34495e; line-height: 1.7;">
                                    <tr>
                                        <td style="padding: 10px 0; font-weight: 600; width: 150px;">Name:</td>
                                        <td style="padding: 10px 0;">{user_name}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 10px 0; font-weight: 600;">Email:</td>
                                        <td style="padding: 10px 0;"><a href="mailto:{user_email}" style="color: #FF6B8B; text-decoration: none; font-weight: 500;">{user_email}</a></td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 10px 0; font-weight: 600;">Phone:</td>
                                        <td style="padding: 10px 0;">{phone}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 10px 0; font-weight: 600;">Address:</td>
                                        <td style="padding: 10px 0;">{address}</td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        <tr>
                            <td align="center" style="background-color: #f7f9fa; color: #888888; padding: 25px 20px; font-size: 13px; border-top: 1px solid #e9ecef;">
                                <p style="margin: 0;">This is an automated notification from the MASIKA App.</p>
                                <p style="margin: 8px 0 0;">Timestamp: {current_time}</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = f"✨ New Product Order from {user_name}!"
    msg.attach(MIMEText(email_body, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return jsonify({'success': True, 'message': 'Order placed successfully! We will contact you shortly.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Could not send order confirmation. Please try again later. Error: {str(e)}'})

@app.route("/", methods=["GET"])
def index():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email").strip()
        password = request.form.get("password").strip() 
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT full_name, age, password FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        conn.close()
        if user:
            session["user_email"] = email
            session["user_name"] = user[0]
            session["user_age"] = user[1]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("User not found. Please sign up.", "danger")
            return redirect(url_for("signup"))
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = request.form.get("full_name").strip()
        email = request.form.get("email").strip()
        age = request.form.get("age").strip()
        password = request.form.get("password").strip()  

        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute(
                "INSERT INTO users (full_name, email, age, password) VALUES (?, ?, ?, ?)",
                (full_name, email, age, password)
            )
            conn.commit()
            conn.close()
            session["user_email"] = email
            session["user_name"] = full_name
            session["user_age"] = age
            flash("Signup successful! Logged in automatically.", "success")
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            flash("Email already exists. Please login.", "danger")
            return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    result = None
    pdf_link = None
    extracted_images = {}
    parsed_values = {}
    if request.method == "POST":
        patient_name = session.get("user_name", "Anonymous")
        age = session.get("user_age", "")
        cycle_days = request.form.get("cycle_days", "").strip()
        period_days = request.form.get("period_days", "").strip()
        description = request.form.get("description", "").strip()
        selected_language = request.form.get("selected_language", "en").strip()

        uploaded_files = request.files.getlist("report_images")
        for f in uploaded_files:
            if f and allowed_file(f.filename):
                fn = secure_filename(f.filename)
                fname = f"{int(time.time())}_{random.randint(1000,9999)}_{fn}"
                path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
                f.save(path)
                
                extracted = image_to_text_via_gemini(path)
                extracted_images[path] = extracted
                parsed = parse_lab_values_text(extracted)
                parsed_values.update(parsed) # Use update to merge dicts
        
        recommendations_text = generate_recommendations_from_inputs(
            age, cycle_days, period_days, description, parsed_values, selected_language
        )
        result = {
            "patient_name": patient_name,
            "age": age,
            "cycle_days": cycle_days,
            "period_days": period_days,
            "description": description,
            "parsed_values": parsed_values,
            "recommendations_raw": recommendations_text,
            "extracted_images": extracted_images
        }

        meta = {
            "Name": patient_name,
            "Age": age or "Not provided",
            "Cycle Length (days)": cycle_days or "Not provided",
            "Period Days": period_days or "Not provided",
            "Report Generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # === CHANGE STARTS HERE ===
        if selected_language == "en":
            pdf_path = create_pdf_report(patient_name, recommendations_text, meta)
            pdf_link = url_for("download_file", filename=os.path.basename(pdf_path))
        else:
            pdf_link = None
        # === CHANGE ENDS HERE ===

    return render_template("dashboard.html", result=result, pdf_link=pdf_link)

@app.route("/products")
@login_required
def products():
    return render_template("products.html")

@app.route("/videos")
@login_required
def videos():
    return render_template("videos.html")

@app.route("/consultation", methods=["GET", "POST"])
@login_required
def consultation():
    if request.method == "POST":
        flash("Consultation request submitted!", "success")
    return render_template("consultation.html")

@app.route("/download/<filename>")
@login_required
def download_file(filename):
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(path):
        flash("File not found", "danger")
        return redirect(url_for("dashboard"))
    return send_file(path, as_attachment=True)

@app.route("/ping")
def ping():
    return "OK", 200

@app.route("/logout")
@login_required
def logout():
    session.pop("user_email", None)
    session.pop("user_name", None)
    session.pop("user_age", None)
    flash("Logged out successfully!", "success")
    return redirect(url_for("login"))

# ==============================================================================
# 6. MAIN EXECUTION BLOCK
# ==============================================================================
if __name__ == "__main__":
    app.run(debug=True)
