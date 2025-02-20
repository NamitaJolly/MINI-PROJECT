from flask import Flask, request, jsonify
import json
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler


from news_extractor import news_summarization
import pytz
from flask_cors import CORS


app = Flask(__name__)
CORS(app)




def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=news_summarization,
        trigger="interval",
        hours=1,
        timezone=pytz.UTC
    )
    scheduler.start()
news_summarization()
@app.route("/")
def home():
    return "Flask app is running!"




@app.route("/api/news", methods=["GET"])
def get_news():
    try:
        with open("today_articles.json", "r") as f:
            news_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        news_data = []


    last_published_time = request.args.get("lastPublishedTime", None)


    if last_published_time:
        try:
            last_published_time = datetime.strptime(
                last_published_time, "%a, %d %b %Y %H:%M:%S %Z"
            )
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400


    filtered_news = []
    if news_data:  # Only process if we have data
        news_data.sort(
            key=lambda x: datetime.strptime(x["published"], "%a, %d %b %Y %H:%M:%S %Z"),
            reverse=True,
        )


        for article in news_data:
            published_time = datetime.strptime(
                article["published"], "%a, %d %b %Y %H:%M:%S %Z"
            )
            if not last_published_time or published_time < last_published_time:
                filtered_news.append(article)
            if len(filtered_news) == 5:
                break


    return jsonify(filtered_news)




@app.route("/scrape-news", methods=["POST"])
def scrape_news():
    # news_summarization()
    return jsonify({"status": "success", "message": "News scraped successfully"})




if __name__ == "__main__":
    app.run(debug=True)


