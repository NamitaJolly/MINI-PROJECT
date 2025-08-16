import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import google.generativeai as genai
import logging
from dotenv import load_dotenv
import os
import re
from pymongo import MongoClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB connection
client = MongoClient(os.getenv("MONGO_URI"))  # MongoDB connection string
news_db= client["insightHub"]  # Database
articles_collection = news_db["articles"]  # Collection

def summarize_news(text_to_summarize):
    """
    Summarize the news content using Gemini API.
    """
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    response = model.generate_content(
        f"""
        Summarize the following news and reduce it to 30% size efficiently.
        Also, provide categories for the news.
        Additionally, generate 10 multiple-choice questions (MCQs) and 10 descriptive questions based on the news.
        also categorize news and assign them with appropriate category from following:[Sports,Politics,Current Affairs, Economy,Health,International Trade,Climate,Wars,Bussiness,Technology,Others]
        Use the following format:
        
        Summary: <summary_here>
        Categories: <category_1>, <category_2>, ...
        
        MCQ:
        1. Question: <MCQ question>
           Answer: <Correct Answer>
           Other_Options: <Option1>, <Option2>, <Option3>
        
        Descriptive:
        1. Question: <Descriptive question>
           Answer: <Answer>
        
        Text is below:
        {text_to_summarize}
        """
    )
    
    # Log the response for debugging
    logger.info(f"Response from Gemini API: {response.text}")

    summary_parts = response.text.split('\n')
    data = {
        "Summary": "",
        "Categories": [],
        "MCQ": [],
        "Descriptive": []
    }

    current_section = None
    i = 0
    mcq_no=1
    desc_no=1
    while i < len(summary_parts):
        raw_line = summary_parts[i]
        stripped_line = raw_line.strip()
        stripped_line =stripped_line.replace('*','')
        logger.info(f"Processing line: {stripped_line}")  # Log each line being processed

        if stripped_line.startswith("Summary:"):
            data["Summary"] = stripped_line.replace("Summary:", "").strip()
        elif stripped_line.startswith("Categories:"):
            categories = stripped_line.replace("Categories:", "").strip().split(", ")
            data["Categories"] = [cat.strip() for cat in categories]
        elif stripped_line.startswith("MCQ:"):
            current_section = "MCQ"
        elif stripped_line.startswith("Descriptive:"):
            current_section = "Descriptive"
        else:
            if current_section == "MCQ":
                cleaned_line = re.sub(r'^\d+\.\s*', '', stripped_line)
                if cleaned_line.startswith("Question:"):
                    question = cleaned_line.replace("Question:", "").strip()
                    i += 1
                    while i < len(summary_parts) and summary_parts[i].strip() == "":
                        i += 1
                    if i < len(summary_parts):
                        answer = summary_parts[i].strip().replace("Answer:", "").strip()
                        answer = answer.replace("*", "") 
                        i += 1
                        while i < len(summary_parts) and summary_parts[i].strip() == "":
                            i += 1
                        if i < len(summary_parts):
                            options_line = summary_parts[i].strip().replace("Other_Options:", "").strip()
                            options_line = options_line.replace("*", "") 
                            other_options = [opt.strip() for opt in options_line.split(", ")]
                            data["MCQ"].append({"Qno":mcq_no,"Question": question, "Answer": answer, "Other_Options": other_options})
                            mcq_no+=1
            elif current_section == "Descriptive":
                cleaned_line = re.sub(r'^\d+\.\s*', '', stripped_line)
                if cleaned_line.startswith("Question:"):
                    question = cleaned_line.replace("Question:", "").strip()
                    i += 1
                    while i < len(summary_parts) and summary_parts[i].strip() == "":
                        i += 1
                    if i < len(summary_parts):
                        answer = summary_parts[i].strip().replace("Answer:", "").strip()
                        answer = answer.replace("*", "") 
                        data["Descriptive"].append({"Question": question, "Answer": answer})
        i += 1

    logger.info(f"Extracted data: {data}")  # Log the extracted data
    return data

def get_bbc_rss_links():
    """
    Fetch the latest articles from the BBC RSS feed.
    """
    rss_url = "http://feeds.bbci.co.uk/news/rss.xml"
    feed = feedparser.parse(rss_url)
    articles = [{"title": entry.title, "link": entry.link, "published": entry.published} for entry in feed.entries]
    return articles

def filter_articles_published_within_last_hour(articles):
    """
    Filter articles that are published within the last 1
      hour.
    """
    now = datetime.utcnow()
    one_hour_ago = now - timedelta(hours=8)
    filtered_articles = []
    for article in articles:
        try:
            published_date = datetime.strptime(article['published'], "%a, %d %b %Y %H:%M:%S %Z")
            if one_hour_ago <= published_date <= now:
                filtered_articles.append(article)
        except ValueError as e:
            logger.warning(f"Skipping article due to date parsing issue: {e}")
    return filtered_articles

def fetch_article_content(article_url):
    """
    Fetch the main content of an article given its URL.
    """
    response = requests.get(article_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    paragraphs = soup.find_all('p')
    content = "\n".join(paragraph.text for paragraph in paragraphs if paragraph.text)
    return content

def news_summarization():
    """
    Fetch, summarize, and save BBC news articles to MongoDB.
    Add comprehensive logging and error handling.
    """
    try:
        articles = get_bbc_rss_links()
        today_articles = filter_articles_published_within_last_hour(articles)
        
        logger.info(f"Found {len(today_articles)} articles published within last hour")

        saved_articles = []
        for article in today_articles[8:]:
            try:
                content = fetch_article_content(article['link'])
                summary = summarize_news(content)
                
                article_data = {
                    "title": article['title'],
                    "link": article['link'],
                    "published": article['published'],
                    "content": content,
                    "summary": summary['Summary'],
                    "News Category": summary.get('Categories', []),
                    "MCQ": summary.get('MCQ', []),
                    "Descriptive": summary.get('Descriptive', [])
                }
                
                # Use replace_one with upsert to avoid duplicates
                result = articles_collection.replace_one(
                    {"link": article['link']},  # Unique identifier
                    article_data,
                    upsert=True
                )

                if not(result.matched_count!=0 or result.modified_count!=0 or result.upserted_id):
                    result = articles_collection.insert_one(article_data)
                    logger.info(f"Inserted new article: {article['title']}")


                logger.info(f"Saved/Updated article: {article['title']}")
                saved_articles.append(article_data)
                
            except Exception as article_error:
                logger.error(f"Failed to process article {article['title']}: {article_error}")
        
        logger.info(f"Total articles saved: {len(saved_articles)}")
        return saved_articles
    
    except Exception as overall_error:
        logger.error(f"Overall news summarization error: {overall_error}")
        return []

#news_summarization()