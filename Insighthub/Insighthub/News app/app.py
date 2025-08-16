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
from logger import logger
from news_extractor import news_summarization
import news_extractor
from flask import session, redirect, url_for
import requests
# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.jinja_env.globals.update(zip=zip)


@app.template_filter("to_letter")
def to_letter(index):
    """Convert a 1-based index to a letter (1 -> A, 2 -> B, etc.)."""
    if index < 1:
        return ""
    return chr(64 + index)  # 65 is the ASCII value for 'A'


# Configure rate limiter
limiter = Limiter(
    app=app, key_func=get_remote_address, default_limits=["200 per day", "50 per hour"]
)

# MongoDB connection
client = MongoClient(os.getenv("MONGO_URI"))  # MongoDB connection string
news_db = client["insightHub"]  # Database
users_collection = news_db["users"]  # Users collection
articles_collection = news_db["articles"]  # Articles collection
quiz_attempts_collection = news_db["quiz_attempts"]  # Quiz attempts collection
quiz_results_collections = news_db["quiz_result"]  # Quiz results collection
test_attempts_collection = news_db["test_attempts"]  # Quiz attempts collection
test_results_collection = news_db["test_results"]  # Quiz results collection


@app.route("/intro")
def intro():
    return render_template("intro.html")


@app.route("/")
def home():
    if "email" in session:
        return redirect(url_for("login"))
    return render_template("intro.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"].lower()
        password = request.form["password"]

        existing_user = users_collection.find_one({"email": email})
        if existing_user:
            flash("Email already exists", "danger")
            return redirect(url_for("register"))

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
            "utf-8"
        )
        users_collection.insert_one({"name": name, "email": email, "password": hashed})
        flash("Registration successful! Please login", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10/minute")  # Brute-force protection
def login():
    if request.method == "POST":
        email = request.form["email"].lower()
        password = request.form["password"]

        # Check for admin credentials
        if email == "admin@gmail.com" and password == "admin@123":
            session["email"] = email
            session["role"] = "admin"
            return redirect(url_for("admin_dashboard"))  # Redirect to admin page

        # Regular user authentication
        user = users_collection.find_one({"email": email})
        if user and bcrypt.checkpw(
            password.encode("utf-8"), user["password"].encode("utf-8")
        ):
            session["email"] = email
            session["name"] = user["name"]
            return redirect(url_for("dashboard"))  # Redirect to user dashboard

        flash("Invalid email or password", "danger")

    return render_template("login.html")


@app.route("/admin_dashboard")
def admin_dashboard():
    if "email" in session and session.get("role") == "admin":
        return render_template(
            "admin_dashboard.html"
        )  # Create an admin dashboard template
    return redirect(url_for("login"))


@app.route("/user-management")
def user_management():
    users = list(users_collection.find())  # Fetch all users
    return render_template("user_management.html", users=users)


from bson.objectid import ObjectId


@app.route("/edit-user/<user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    user = users_collection.find_one({"_id": ObjectId(user_id)})

    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        role = request.form["role"]

        # Check for duplicate email
        existing_user = users_collection.find_one(
            {"email": email, "_id": {"$ne": ObjectId(user_id)}}
        )
        if existing_user:
            flash("Email already exists. Please use a different email.", "error")
            return render_template("edit_user.html", user=user)

        # Update user details
        users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"name": username, "email": email, "role": role}},
        )
        flash("User  updated successfully!", "success")
        return redirect(url_for("user_management"))

    return render_template("edit_user.html", user=user)


@app.route("/delete-user/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    users_collection.delete_one({"_id": ObjectId(user_id)})
    return "", 204


@app.route("/assign-role/<user_id>", methods=["POST"])
def assign_role(user_id):
    data = request.get_json()
    users_collection.update_one(
        {"_id": ObjectId(user_id)}, {"$set": {"role": data["role"]}}
    )
    return "", 204


@app.route("/news-management", methods=["GET", "POST"])
def news_management():
    if request.method == "POST":
        # Logic to add a new news article
        title = request.form["title"]
        content = request.form["content"]
        category = request.form["category"]
        published = request.form.get("published", False)  # Optional field

        # Add the new article to the database
        articles_collection.insert_one(
            {
                "title": title,
                "content": content,
                "category": category,
                "published": published,  # Store the published status
                "approved": False,  # Default to not approved
            }
        )
        flash("News article added successfully!", "success")
        return redirect(url_for("news_management"))

    # Fetch existing news articles with specified fields
    articles = list(
        articles_collection.find(
            {}, {"_id": 1, "title": 1, "published": 1, "category": 1}
        )
    )
    return render_template("news_management.html", articles=articles)


@app.route("/edit-article/<article_id>", methods=["GET", "POST"])
def edit_article(article_id):
    article = articles_collection.find_one({"_id": ObjectId(article_id)})

    if request.method == "POST":
        title = request.form["title"]
        category = request.form["category"]
       # published = (
            #request.form.get("published") == "true"
       # )  # Convert checkbox value to boolean

        # Update the article in the database
        articles_collection.update_one(
            {"_id": ObjectId(article_id)},
            {"$set": {"title": title, "category": category }},
        )
        flash("News article updated successfully!", "success")
        return redirect(url_for("news_management"))

    return render_template("edit_article.html", article=article)


@app.route("/quiz-management", methods=["GET", "POST"])
def quiz_management():
    if request.method == "POST":
        # Logic to create a new quiz question
        question = request.form["question"]
        options = request.form.getlist("options")  # Assuming options are sent as a list
        correct_answer = request.form["correct_answer"]

        # Add the new quiz question to the articles collection
        articles_collection.insert_one(
            {
                "MCQ": [
                    {
                        "Question": "What percentage tariff was initially imposed on all US imports?",
                        "Answer": "**** 10%",
                        "Other_Options": ["5%", "15%", "20%"],
                    },
                    {
                        "Question": "What economic action might the US need to take to counteract inflation?",
                        "Answer": "**** Raise interest rates.",
                        "Other_Options": [
                            "Lower taxes",
                            "Increase spending",
                            "Reduce imports",
                        ],
                    },
                ],
                "type": "quiz",  # Optional: to differentiate quiz questions from articles
            }
        )
        flash("Quiz question added successfully!", "success")
        return redirect(url_for("quiz_management"))

    # Fetch existing quiz questions from articles collection where MCQ field is present
    quiz_questions = list(
        articles_collection.find({"MCQ": {"$exists": True}}, {"_id": 1, "MCQ": 1})
    )
    result_questions=[]
    for questions in quiz_questions:
        for mcq in questions['MCQ']:
            temp_result={
                "Qno":mcq.get("Qno"),
                "id":questions.get("_id"),
                "Question":mcq.get("Question"),
                "Answer":mcq.get("Answer"),
                "Other_Options":mcq.get("Other_Options")
            }
            result_questions.append(temp_result)
    # Fetch quiz results from test_results collection
    quiz_results = list(
        test_results_collection.find({}, {"_id": 1, "user_id": 1, "score": 1})
    )

    return render_template(
        "quiz_management.html", quiz_questions=quiz_questions, quiz_results=quiz_results,result_questions=result_questions
    )


@app.route("/edit-question/<question_id>", methods=["GET", "POST"])
def edit_question(question_id):
    question = articles_collection.find_one({"_id": ObjectId(question_id)})

    if request.method == "POST":
        updated_question = request.form["question"]
        updated_options = request.form["options"].split(
            ","
        )  # Split the options by comma
        updated_correct_answer = request.form["correct_answer"]

        # Update the quiz question in the database
        articles_collection.update_one(
            {"_id": ObjectId(question_id)},
            {
                "$set": {
                    "MCQ.question": updated_question,
                    "MCQ.options": updated_options,
                    "MCQ.correct_answer": updated_correct_answer,
                }
            },
        )
        flash("Quiz question updated successfully!", "success")
        return redirect(url_for("quiz_management"))

    return render_template("edit_question.html", question=question)


@app.route("/delete-question/<question_id>", methods=["DELETE"])
def delete_question(question_id):
    articles_collection.delete_one({"_id": ObjectId(question_id)})
    return "", 204


# @app.route("/analytics-reports")
# def analytics_reports():
#     # Since 'last_login' is not present, count total users instead
#     total_users = users_collection.count_documents({})

#     # 'views' does not exist in articles_collection; you can count total articles instead
#     total_articles = articles_collection.count_documents({})

#     # Total quiz attempts (this should work correctly)
#     total_quiz_attempts = quiz_attempts_collection.count_documents({})

#     # Fetch trending topics (titles only)
#     trending_topics = list(articles_collection.find({}, {"title": 1}).limit(5))

#     # Fetch quiz participation stats properly
#     quiz_participation = list(
#         quiz_attempts_collection.aggregate(
#             [{"$group": {"_id": "$quiz_id", "attempts": {"$sum": 1}}}]
#         )
#     )

#     # Format data correctly
#     analytics_data = {
#         "total_users": total_users,
#         "total_articles": total_articles,
#         "total_quiz_attempts": total_quiz_attempts,
#         "trending_topics": [{"title": topic["title"]} for topic in trending_topics],
#         "quiz_participation": [
#             {"quiz_id": q["_id"], "attempts": q["attempts"]} for q in quiz_participation
#         ],
#     }

#     return render_template("analytics_reports.html", data=analytics_data)


@app.route("/dashboard")
def dashboard():
    if "email" not in session:
        return redirect(url_for("login"))
    # Define the API endpoint and parameters
    url = "https://api.metalpriceapi.com/v1/latest"
    params = {
        "api_key": "2be768486acf4d59cb14c03647eda91a",
        "base": "INR",
        "currencies": "USD,XAU,XAG"
    }

    # Make the GET request
    response = requests.get(url, params=params)

    # Check the status code and print the JSON response
    if response.status_code == 200:
        data = response.json()
        print("API Response:")
        print(data)
        gold_rate=data.get("rates").get("INRXAU")
        if gold_rate:
            gold_rate=gold_rate/31.1035 
            
        silver_rate=data.get("rates").get("INRXAG")
        if silver_rate:
            silver_rate=silver_rate/31.1035 
        dollar_rate=data.get("rates").get("INRUSD")
        if dollar_rate:
            dollar_rate=dollar_rate
    else:
        print(f"Failed to fetch data. Status code: {response.status_code}")
    email=session.get("email")
    user = users_collection.find_one({"email":email})
    daily_quiz_user_score=user.get("daily_quiz_score") if user.get("daily_quiz_score") else 0
    mock_test_user_attempts=user.get("mock_test_attempts") if user.get("mock_test_attempts") else 0
    mock_test_user_attempts_percentage=(mock_test_user_attempts/5)*100 
    try:
        filter_categories = ["Sports", "Health", "Politics"]
        with open(
            os.path.join(app.root_path, "today_articles.json"), "r", encoding="utf-8"
        ) as f:
            news_data = json.load(f)
    except:
        news_data = []

    progress_data = {"daily_streak": 5, "accuracy": 82, "completed_tests": 3}
    return render_template(
        "dashboard.html",
        news=news_data[:3],
        progress=progress_data,
        news_categories_input=filter_categories,
        daily_quiz_user_score=daily_quiz_user_score,
        mock_test_user_attempts=mock_test_user_attempts,
        mock_test_user_attempts_percentage=mock_test_user_attempts_percentage,
        gold_rate=gold_rate,
        silver_rate=silver_rate,
        dollar_rate=dollar_rate
    )


@app.route("/date-filter", methods=["POST"])
def date_filtered_news():
    selected_date_str = request.form.get(
        "selected_date"
    )  # Get the date string from form input

    if "email" not in session:
        return redirect(url_for("login"))

    try:
        # Convert selected_date to a datetime object
        selected_date = datetime.strptime(
            selected_date_str, "%Y-%m-%d"
        )  # Assuming input format is 'YYYY-MM-DD'
        selected_category = request.form.get(
            "category", "sports"
        )  # Get the category from form input, default to 'sports'

        # Create a regex pattern for the search query
       

        # Filter articles published on the selected date and matching the regex pattern
        articles = list(
            articles_collection.find(
                {
                    "published": {
                        "$gte": selected_date.strftime("%a, %d %b %Y 00:00:00 GMT"),
                        "$lt": selected_date.strftime("%a, %d %b %Y 23:59:59 GMT"),
                    },
                    
                }
            ).sort("published", -1)
        )
        if not articles:
            flash("No news articles available for the selected date.", "info")

    except ValueError:
        flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
        articles = []
    except Exception as e:
        flash(f"Error loading news: {str(e)}", "danger")
        articles = []

    return render_template("news.html", news=articles)


@app.route("/daily_quiz")
def daily_quiz():
    if "email" not in session:
        return redirect(url_for("login"))

    # Get today's date in the string format used in published field
    today = datetime.utcnow().date()
    start_time = today.strftime("%a, %d %b %Y 00:00:00 GMT")
    end_time = today.strftime("%a, %d %b %Y 23:59:59 GMT")

    # Fetch today's articles with MCQs
    articles = articles_collection.find(
        {
            "MCQ": {"$exists": True, "$ne": []},
            "published": {"$gte": start_time, "$lte": end_time},
        }
    )

    mcqs = []
    for article in articles:
        mcqs.extend(article.get("MCQ", []))

    if not mcqs:
        flash("No questions available for quiz today", "info")
        return redirect(url_for("dashboard"))

    random.shuffle(mcqs)
    selected_mcqs = mcqs[:10]  # Pick first 10 questions

    # Add temp_id and shuffle options
    for idx, mcq in enumerate(selected_mcqs):
        mcq["temp_id"] = idx
        options = [mcq["Answer"]] + mcq["Other_Options"]
        random.shuffle(options)
        mcq["options"] = options

    quiz_id = str(uuid.uuid4())
    quiz_attempts_collection.insert_one(
        {
            "quiz_id": quiz_id,
            "user_email": session["email"],
            "questions": selected_mcqs,
            "timestamp": datetime.utcnow(),
            "expire_at": datetime.utcnow() + timedelta(minutes=15),
        }
    )

    return render_template("quiz.html", mcqs=selected_mcqs, quiz_id=quiz_id)


@app.route("/submit_quiz", methods=["POST"])
def submit_quiz():

    if "email" not in session:
        return redirect(url_for("login"))
    
    
    quiz_id = request.form.get("quiz_id")
    attempt = quiz_attempts_collection.find_one({"quiz_id": quiz_id})

    if not attempt or attempt["user_email"] != session["email"]:
        flash("Invalid quiz submission", "danger")
        return redirect(url_for("dashboard"))

    score = 0
    user_answers = []
    correct_answers = []
    questions_list = []
    total_questions = len(attempt["questions"])  # Get actual total

    for question in attempt["questions"]:
        temp_id = question["temp_id"]
        user_answer = request.form.get(f"q{temp_id}")
        correct_answer = question["Answer"]
        questions_list.append(
            {  # type: ignore
                "text": question["Question"],
                "options": question.get("Options", []),
            }
        )
        # Collect answers for display
        user_answers.append(user_answer or "No Answer")  # Handle unanswered
        correct_answers.append(correct_answer)

        if user_answer == question["Answer"]:
            score += 1

    # Store in session instead of URL params
    session["quiz_questions"] = questions_list  # type: ignore
    session["quiz_user_answers"] = user_answers
    session["quiz_correct_answers"] = correct_answers

    # Clean up attempt
    
    quiz_attempts_collection.delete_one({"quiz_id": quiz_id})
    
    email=session.get("email")
    users_collection.update_one(
            {"email":email},
            {"$set": {"daily_quiz_score": score}},
        )
    # Redirect to results page with user answers and correct answers
    return redirect(
        url_for(
            "quiz_results_page",
            score=score,
            total=len(attempt["questions"]),
            user_answers=user_answers,
            correct_answers=correct_answers,
        )
    )


@app.route("/quiz_results")
def quiz_results_page():
    score = request.args.get("score", 0, type=int)
    total = request.args.get("total", 0, type=int)
    questions = session.pop("quiz_questions", [])  # NEW
    user_answers = session.pop("quiz_user_answers", [])
    correct_answers = session.pop("quiz_correct_answers", [])

    # Retrieve user_email from session
    user_email = session.get("user_email")

    # Insert quiz result into MongoDB if user_email exists
    if user_email:
        quiz_results_collections.insert_one(
            {"user_id": user_email, "score": score, "total_questions": total}
        )

    return render_template(
        "quiz_results.html",
        questions=questions,
        score=score,
        total=total,
        user_answers=user_answers,
        correct_answers=correct_answers,
    )


def get_daily_streak(email):
    streak = quiz_attempts_collection.aggregate(
        [
            {"$match": {"user_email": email}},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": -1}},
            {"$limit": 7},
        ]
    )
    return len(list(streak))


def calculate_accuracy(email):
    results = quiz_results_collections.find({"user_id": email})
    total = 0
    correct = 0
    for res in results:
        total += res["total_questions"]
        correct += res["score"]
    return round((correct / total) * 100, 1) if total > 0 else 0


def get_completed_tests(email):
    return test_results_collection.count_documents({"user_id": email})


@app.template_filter("zip")
def zip_filter(list1, list2):
    return zip(list1, list2)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/news")
def news():
    if "email" not in session:
        return redirect(url_for("login"))

    # Get today's date in the required format
    today = datetime.utcnow().date()

    try:
        # Filter articles published today
        articles = list(
            articles_collection.find(
                {
                    "published": {
                        "$gte": today.strftime("%a, %d %b %Y 00:00:00 GMT"),
                        "$lt": today.strftime("%a, %d %b %Y 23:59:59 GMT"),
                    }
                }
            ).sort("published", -1)
        )

        if not articles:
            flash("No news articles available for today.", "info")

    except Exception as e:
        flash(f"Error loading news: {str(e)}", "danger")
        articles = []
    return render_template("news.html", news=articles)


@app.route("/filtered-news")
def filtered_news():
    if "email" not in session:
        return redirect(url_for("login"))

    # Get category from query string
    category = request.args.get("category", "").strip().lower()
    logger.debug(f"Category : {category}")
    # Define subcategory to main category mapping
    # if category != "default_category":
    #     category_mapping = {
    #         "boxing": "sports",
    #         "football": "sports",
    #         "cricket": "sports",
    #         "tennis": "sports",
    #         category:category
    #         # Add more as needed
    #     }
    #     search_category = category_mapping.get(category, category)

    # Get the effective category (e.g., boxing → sports)
    search_category = category
    try:
        if search_category:
            print(f"The category is: {search_category}")
            articles = list(
                articles_collection.find(
                    {
                        "News Category": {
                            "$elemMatch": {"$regex": search_category, "$options": "i"}
                        }
                    }
                ).sort("published", -1)
            )
            logger.info(f"articles: {articles}")
        else:
            # No category specified → fetch articles not in "sports"
            articles = list(articles_collection.find().sort("published", -1))
            logger.info(f"Non-sports articles: {articles}")

        if not articles:
            flash(f"No news articles available for '{category or 'general'}'.", "info")

        print(
            f"Retrieved {len(articles)} articles for category: {search_category or 'general'}"
        )

    except Exception as e:
        flash(f"Error loading news: {str(e)}", "danger")
        articles = []

    return render_template("news.html", news=articles, selected_category=category)


@app.route("/mock_test")
def mock_test():
    if "email" not in session:
        return redirect(url_for("login"))
    
    email=session.get("email")
    user = users_collection.find_one({"email":email})
    attempts=user.get("mock_test_attempts")
    if not attempts:
        attempts=1
    elif attempts>=5:
        flash("You reached your test limit", "info")
        return redirect(url_for("dashboard"))
    
    # Get today's date in the string format used in published field
    today = datetime.utcnow().date()
    end_day = today - timedelta(days=6)
    start_time = end_day.strftime("%a, %d %b %Y 00:00:00 GMT")
    end_time = today.strftime("%a, %d %b %Y 23:59:59 GMT")

    # Fetch today's articles with MCQs
    articles = articles_collection.find(
        {
            "MCQ": {"$exists": True, "$ne": []},
            "published": {"$gte": start_time, "$lte": end_time},
        }
    )

    mcqs = []
    for article in articles:
        mcqs.extend(article.get("MCQ", []))

    if not mcqs:
        flash("No questions available for mock test right now", "info")
        return redirect(url_for("dashboard"))

    # Shuffle and select 10 questions
    random.shuffle(mcqs)
    selected_mcqs = mcqs[:10]

    # Shuffle options and assign temp_id
    for idx, mcq in enumerate(selected_mcqs):
        mcq["temp_id"] = idx
        options = [mcq["Answer"]] + mcq["Other_Options"]
        random.shuffle(options)
        mcq["options"] = options

    # ✅ Store question texts in session
    session["questions"] = [mcq["Question"] for mcq in selected_mcqs]

    # Create quiz attempt
    quiz_id = str(uuid.uuid4())
    test_attempts_collection.insert_one(
        {
            "quiz_id": quiz_id,
            "user_email": session["email"],
            "questions": selected_mcqs,
            "timestamp": datetime.utcnow(),
            "expire_at": datetime.utcnow() + timedelta(minutes=15),
        }
    )

    return render_template("mock_tests.html", mcqs=selected_mcqs, quiz_id=quiz_id)


# @app.route('/submit_mock_test', methods=['POST'])
# def submit_mock_test():
#     if 'email' not in session:
#         return redirect(url_for('login'))

#     user_email = session.get('email')
#     quiz_id = request.form.get('quiz_id')

#     if not quiz_id:
#         flash("Invalid quiz submission. No quiz ID provided.", "danger")
#         return redirect(url_for('dashboard'))

#     attempt = test_attempts_collection.find_one({'quiz_id': quiz_id})

#     if not attempt or attempt.get('user_email') != user_email:
#         flash('Invalid mock test submission', 'danger')
#         return redirect(url_for('dashboard'))

#     score = 0
#     user_answers = []
#     correct_answers = []

#     for question in attempt.get("questions", []):
#         temp_id = question.get("temp_id")
#         user_answer = request.form.get(f"q{temp_id}")
#         correct_answer = question.get("Answer")

#         if user_answer is not None:  # Ensure user selected an answer
#             user_answers.append(user_answer)
#         else:
#             user_answers.append("No Answer")  # Mark unanswered questions

#         correct_answers.append(correct_answer)

#         if user_answer == correct_answer:
#             score += 1

#     # Remove quiz attempt after submission
#     #test_attempts_collection.delete_one({'quiz_id': quiz_id})

#     # Store answers in session
#     session['user_answers'] = user_answers
#     session['correct_answers'] = correct_answers

#     # Store results in the database
#     test_results_collection.insert_one({
#         "user_id": user_email,
#         "quiz_id": quiz_id,
#         "score": score,
#         "total_questions": len(attempt["questions"]),
#         "user_answers": user_answers,
#         "correct_answers": correct_answers
#     })

#     return redirect(url_for('mock_test_results', score=score, total=len(attempt['questions'])))


@app.route("/submit_mock_test", methods=["POST"])
def submit_mock_test():
    if "email" not in session:
        return redirect(url_for("login"))

    user_email = session.get("email")
    logger.debug(f"User email from session: {user_email}")

    try:
        quiz_id = request.form.get("quiz_id")
        logger.debug(f"Received quiz_id: {quiz_id}")
    except Exception as e:
        logger.debug(f"Error retrieving quiz_id: {e}")
        flash("Error retrieving quiz ID.", "danger")
        return redirect(url_for("dashboard"))

    if not quiz_id:
        flash("Invalid quiz submission. No quiz ID provided.", "danger")
        return redirect(url_for("dashboard"))

    try:
        attempt = test_attempts_collection.find_one({"quiz_id": quiz_id})
        logger.debug(f"Quiz attempt fetched: {attempt}")
    except Exception as e:
        logger.debug(f"Error fetching quiz attempt: {e}")
        flash("Failed to retrieve quiz attempt.", "danger")
        return redirect(url_for("dashboard"))

    if not attempt or attempt.get("user_email") != user_email:
        logger.debug(
            "Invalid attempt: Either no attempt found or mismatched user email."
        )
        flash("Invalid mock test submission", "danger")
        return redirect(url_for("dashboard"))

    score = 0
    user_answers = []
    correct_answers = []

    try:
        for question in attempt.get("questions", []):
            temp_id = question.get("temp_id")
            user_answer = request.form.get(f"q{temp_id}")
            correct_answer = question.get("Answer")

            logger.debug(
                f"Q{temp_id} - User Answer: {user_answer}, Correct Answer: {correct_answer}"
            )

            if user_answer is not None:
                user_answers.append(user_answer)
            else:
                user_answers.append("No Answer")

            correct_answers.append(correct_answer)

            if user_answer == correct_answer:
                score += 1

        logger.debug(f"Final Score: {score} / {len(attempt['questions'])}")
        logger.debug(f"User Answers: {user_answers}")
        logger.debug(f"Correct Answers: {correct_answers}")
    except Exception as e:
        logger.debug(f"Error during scoring: {e}")
        flash("There was an error calculating your score.", "danger")
        return redirect(url_for("dashboard"))

    # Optionally remove quiz attempt after submission
    # try:
    #     test_attempts_collection.delete_one({'quiz_id': quiz_id})
    #     logger.debug(f"Deleted quiz attempt with ID: {quiz_id}")
    # except Exception as e:
    #     logger.debug(f"Failed to delete quiz attempt: {e}")

    # Store answers in session
    session["user_answers"] = user_answers
    session["correct_answers"] = correct_answers

    email=session.get("email")
    user = users_collection.find_one({"email":email})
    attempts=user.get("mock_test_attempts")
    if attempts:
        attempts+=1
    else:
        attempts=1   
    users_collection.update_one(
            {"email":email},
            {"$set": {"mock_test_attempts": attempts}},
        )
    try:
        result = {
            "user_id": user_email,
            "quiz_id": quiz_id,
            "score": score,
            "total_questions": len(attempt["questions"]),
            "user_answers": user_answers,
            "correct_answers": correct_answers,
            "time": datetime.utcnow(),
        }

        test_results_collection.insert_one(result)
        logger.debug(f"Result stored in DB: {result}")
    except Exception as e:
        logger.debug(f"Error inserting result to DB: {e}")
        flash("Failed to store test results.", "danger")
        return redirect(url_for("dashboard"))

    return redirect(
        url_for("mock_test_results", score=score, total=len(attempt["questions"]))
    )


@app.route("/mock_test_results")
def mock_test_results():
    score = request.args.get("score", 0, type=int)
    total = request.args.get("total", 0, type=int)

    user_answers = session.pop("user_answers", [])
    correct_answers = session.pop("correct_answers", [])
    questions = session.pop("questions", [])

    user_email = session.get("user_email")

    if user_email:
        test_results_collection.insert_one(
            {
                "user_id": user_email,
                "score": score,
                "total_questions": total,
                "time": datetime.utcnow(),
            }
        )

    # Zip the three lists together
    zipped_data = list(zip(user_answers, correct_answers, questions))

    return render_template(
        "mock_test_results.html", score=score, total=total, zipped_data=zipped_data
    )


@app.route("/category-quiz")
def category_quiz():
    if "email" not in session:
        return redirect(url_for("login"))

    category = request.args.get("category", "Current Affairs")

    # Get category-specific questions
    articles = (
        articles_collection.find(
            {"MCQ": {"$exists": True, "$ne": []}, "News Category": category}
        )
        .sort("published", -1)
        .limit(50)
    )

    mcqs = []
    for article in articles:
        mcqs.extend(article.get("MCQ", []))

    if not mcqs:
        flash(f"No questions available for {category} category", "info")
        return redirect(url_for("dashboard"))

    # Prepare quiz
    random.shuffle(mcqs)
    selected_mcqs = mcqs[:10]

    for idx, mcq in enumerate(selected_mcqs):
        mcq["temp_id"] = idx
        options = [mcq["Answer"]] + mcq["Other_Options"]
        random.shuffle(options)
        mcq["options"] = options

    # Create quiz attempt
    quiz_id = str(uuid.uuid4())
    quiz_attempts_collection.insert_one(
        {
            "quiz_id": quiz_id,
            "user_email": session["email"],
            "questions": selected_mcqs,
            "category": category,
            "timestamp": datetime.utcnow(),
            "expire_at": datetime.utcnow() + timedelta(minutes=10),
        }
    )

    return render_template(
        "category_quiz.html", mcqs=selected_mcqs, quiz_id=quiz_id, category=category
    )


@app.template_filter("zip")
def zip_filter(list1, list2):
    return zip(list1, list2)


if __name__ == "__main__":
    app.run(debug=False)


