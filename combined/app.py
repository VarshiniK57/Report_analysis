from flask import Flask, render_template, request, redirect, url_for, session
import pytesseract
from PIL import Image
import os
import cv2
import numpy as np
import tensorflow as tf
import re
import time
import mysql.connector
import random
import smtplib
from email.mime.text import MIMEText
import google.generativeai as genai
from werkzeug.utils import secure_filename

# Flask app
app = Flask(__name__)
app.secret_key = 'SOLDIERS_GET_READY_WITH_COMMANDER'

# Upload settings
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Ensure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Google Gemini API
genai.configure(api_key='PUT_YOUR_GOOGLE_GENAI_API_KEY')

# MySQL DB Config
DB_CONFIG = {
    'user': 'sql12772919',
    'password': '2AJ7HJjAcQ',
    'host': 'sql12.freesqldatabase.com',
    'database': 'sql12772919',
    'port': 3306
}

# Email credentials
EMAIL_USER = "cyrusbyte.in@gmail.com"
EMAIL_PASS = "mysbesxffdzworkx"

# MRI Model settings
MRI_MODEL_PATH = "combined/model/final_tumor_model.keras"
mri_model = tf.keras.models.load_model(MRI_MODEL_PATH)
mri_labels = {0: 'glioma', 1: 'meningioma', 2: 'notumor', 3: 'pituitary'}
image_size = 150

# Tesseract config
pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract'

# ==================== ROUTES ====================

@app.route('/')
def root():
    return render_template('home1.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE username=%s AND password=%s", (username, password))
        result = cursor.fetchone()
        if result:
            otp = str(random.randint(100000, 999999))
            session['user'] = username
            session['login_verified'] = True
            session['otp_verified'] = False
            send_otp_email(result[0], otp)
            cursor.execute("UPDATE users SET otp=%s WHERE username=%s", (otp, username))
            conn.commit()
            return redirect('/otp')
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/otp', methods=['GET', 'POST'])
def otp_verification():
    if 'user' not in session or not session.get('login_verified'):
        return redirect('/login')
    if request.method == 'POST':
        entered_otp = request.form['otp']
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT otp FROM users WHERE username=%s", (session['user'],))
        stored_otp = cursor.fetchone()
        if stored_otp and entered_otp == stored_otp[0]:
            cursor.execute("UPDATE users SET otp=NULL WHERE username=%s", (session['user'],))
            conn.commit()
            session['otp_verified'] = True
            return redirect('/home')
        else:
            return render_template('otp.html', error="Invalid OTP")
    return render_template('otp.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/home')
def home():
    if not session.get('otp_verified'):
        return redirect('/login')
    return render_template('home.html')

@app.route('/details')
def details():
    return render_template('details.html')  # Make sure this exists

@app.route('/scan', methods=['GET', 'POST'])
def upload_image():
    if not session.get('otp_verified'):
        return redirect('/login')
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            extracted_text = pytesseract.image_to_string(Image.open(file_path))
            model = genai.GenerativeModel("gemini-1.5-flash")
            chat = model.start_chat()
            response = chat.send_message(["Extract insights from this medical scan report:", extracted_text])
            return render_template('scan.html', extracted_text=extracted_text, generated_output=response.text, image_path=file_path)
    return render_template('scan.html')

@app.route('/xray', methods=['GET', 'POST'])
def process_xray():
    if not session.get('otp_verified'):
        return redirect('/login')
    analysis = None
    image_url = None
    if request.method == "POST":
        file = request.files.get("file")
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            image_url = "/" + file_path
            model = genai.GenerativeModel(model_name="gemini-1.5-flash")
            chat = model.start_chat()
            response = chat.send_message(["Analyze this X-ray.", Image.open(file_path)])
            analysis = highlight_issues(response.text)
    return render_template("xindex.html", image_url=image_url, analysis=analysis)

def highlight_issues(text):
    patterns = [
        r"\b(fracture.*?radius.*?ulna.*?bones)\b",
        r"\b(displacement.*?fractured fragments)\b",
        r"\b(complete fracture)\b",
        r"\b(bone.*?broken)\b",
        r"\b(fracture.*?midshaft)\b",
        r"\b(clear fracture)\b"
    ]
    for pattern in patterns:
        text = re.sub(pattern, r"<b><u>\1</u></b>", text, flags=re.IGNORECASE)
    return text

@app.route("/mri", methods=["GET", "POST"])
def upload_mri():
    if not session.get('otp_verified'):
        return redirect('/login')
    if request.method == "POST":
        file = request.files.get("file")
        if file:
            timestamp = int(time.time())
            filename = f"{timestamp}_{secure_filename(file.filename)}"
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)
            return redirect(url_for('show_mri_result', filename=filename))
    return render_template("upload.html")

@app.route("/result/<filename>")
def show_mri_result(filename):
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(file_path):
        return "File not found", 404
    predicted_label, medical_info = predict_mri(file_path)
    return render_template("result.html", image_url=file_path, tumor_type=predicted_label, medical_info=medical_info)

def predict_mri(image_path):
    img = cv2.imread(image_path)
    img = cv2.resize(img, (image_size, image_size))
    img = img / 255.0
    img = np.expand_dims(img, axis=0)
    prediction = mri_model.predict(img)
    predicted_class = np.argmax(prediction, axis=1)[0]
    predicted_label = mri_labels[predicted_class]
    if predicted_label != "notumor":
        return predicted_label, get_medical_info(predicted_label)
    return predicted_label, "No tumor detected."

def get_medical_info(tumor_type):
    prompt = f"""
    Provide medical details about {tumor_type} brain tumor:
    - Affected area
    - Symptoms
    - Treatments & risks
    """
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(prompt)
    return response.text

# ========== EMAIL FUNCTION ========== #
def send_otp_email(receiver_email, otp):
    msg = MIMEText(f"Your OTP code is: {otp}")
    msg["Subject"] = "Your OTP Code"
    msg["From"] = EMAIL_USER
    msg["To"] = receiver_email
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, receiver_email, msg.as_string())
        server.quit()
        print(f"OTP email sent to {receiver_email}")
    except Exception as e:
        print(f"Email error: {e}")

# ========== RUN FLASK APP ========== #
if __name__ == '__main__':
    app.run(debug=True)
