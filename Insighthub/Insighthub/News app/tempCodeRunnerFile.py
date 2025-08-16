import os
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from dotenv import load_dotenv
import bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import json
import uuid
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Configure rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# MongoDB setup
client = MongoClient(os.getenv('MONGO_URI'))
db = client.get_database()
users = db.users
articles_collection = db.articles
quiz_attempts = db.quiz_attempts
quiz_results = db.quiz_results

@app.route('/')
def home():
    if 'email' in session:
        return redirect(url_for('dashboard'))
    return render_template('intro.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email'].lower()
        password = request.form['password']

        existing_user = users.find_one({'email': email})
        if existing_user:
            flash('Email already exists', 'danger')
            return redirect(url_for('register'))

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        users.insert_one({'name': name, 'email': email, 'password': hashed})
        flash('Registration successful! Please login', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10/minute")  # Brute-force protection
def login():
    if request.method == 'POST':
        email = request.form['email'].lower()
        password = request.form['password']

        user = users.find_one({'email': email})
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            session['email'] = email
            session['name'] = user['name']
            return redirect(url_for('dashboard'))

        flash('Invalid email or password', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect(url_for('login'))
    try:
        with open(os.path.join(app.root_path, 'today_articles.json'), "r", encoding="utf-8") as f:
            news_data = json.load(f)
    except:
        news_data = []

    progress_data = {'daily_streak': 5, 'accuracy': 82, 'completed_tests': 3}
    return render_template('dashboard.html', news=news_data[:3], progress=progress_data)

@app.route('/daily_quiz')
def daily_quiz():
    if 'email' not in session:
        return redirect(url_for('login'))
    
    # Get latest articles with MCQs
    articles = articles_collection.find({"MCQ": {"$exists": True, "$ne": []}})
    mcqs = []
    for article in articles:
        mcqs.extend(article.get('MCQ', []))
    
    if not mcqs:
        flash('No questions available for quiz right now', 'info')
        return redirect(url_for('dashboard'))
    
    # Shuffle and select questions
    random.shuffle(mcqs)
    selected_mcqs = mcqs[:10]  # Take first 10 questions
    
    # Shuffle options for each question
    for mcq in selected_mcqs:
        options = [mcq['Answer']] + mcq['Other_Options']
        random.shuffle(options)
        mcq['options'] = options  # Add shuffled options to the mcq

    # Create quiz attempt
    quiz_id = str(uuid.uuid4())
    quiz_attempts.insert_one({
        'quiz_id': quiz_id,
        'user_email': session['email'],
        'questions': selected_mcqs,
        'timestamp': datetime.utcnow(),
        'expire_at': datetime.utcnow() + timedelta(minutes=15)
    })
    
    return render_template('quiz.html', mcqs=selected_mcqs, quiz_id=quiz_id)

@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    if 'email' not in session:
        return redirect(url_for('login'))
    
    quiz_id = request.form.get('quiz_id')
    attempt = quiz_attempts.find_one({'quiz_id': quiz_id})
    
    if not attempt or attempt['user_email'] != session['email']:
        flash('Invalid quiz submission', 'danger')
        return redirect(url_for('dashboard'))
    
    score = 0
    for idx, question in enumerate(attempt['questions']):
        user_answer = request.form.get(f'q{idx}')
        if user_answer == question['Answer']:
            score += 1

    # Clean up attempt
    quiz_attempts.delete_one({'quiz_id': quiz_id})
    
    # Redirect to results page
    return redirect(url_for('quiz_results_page', score=score, total=len(attempt['questions'])))

@app.route('/quiz_results')
def quiz_results_page():
    score = request.args.get('score', 0, type=int)
    total = request.args.get('total', 0, type=int)
    return render_template('quiz_results.html', score=score, total=total)

@app.template_filter('shuffle')
def shuffle_filter(seq):
    random.shuffle(seq)
    return seq

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/news')
def news():
    if 'email' not in session:
        return redirect(url_for('login'))
    
    try:
        articles = list(articles_collection.find().sort("published", -1))
        if not articles:
            flash("No news articles available.", "info")
    except Exception as e:
        flash(f"Error loading news: {str(e)}", "danger")
        articles = []
    
    return render_template('news.html', news=articles)

if __name__ == '__main__':
    app.run(debug=True)