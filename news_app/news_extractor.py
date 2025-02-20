import requests
import feedparser
from bs4 import BeautifulSoup
from urllib.robotparser import RobotFileParser
from datetime import datetime,timedelta
import json
import google.generativeai as genai
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import re  # Add this import

def summarize_news(text_to_summarize):
    genai.configure(api_key="AIzaSyCKVf8oDIs7AByx40Nj0-uqythTT8-bNBs")
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(
        f"""
        Summarize the following news and reduce it to 30% size efficiently. 
        Also, provide categories for the news.
        Additionally, generate 10 multiple-choice questions (MCQs) and 10 descriptive questions based on the news.
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
    
    summary_parts = response.text.split('\n')
    text = summary_parts
    print(text)
    data = {
        "Summary": "",
        "Categories": [],
        "MCQ": [],
        "Descriptive": []
    }

    current_section = None
    i = 0

    while i < len(text):
        raw_line = text[i]
        stripped_line = raw_line.strip()

        # Detect section headers
        if stripped_line.startswith("**Summary:**"):
            data["Summary"] = raw_line.replace("**Summary:**", "").strip()
        elif stripped_line.startswith("**Categories:**"):
            categories = raw_line.replace("**Categories:**", "").strip().split(", ")
            data["Categories"] = [cat.strip() for cat in categories]
        elif stripped_line == "**MCQ:**":
            current_section = "MCQ"
        elif stripped_line == "**Descriptive:**":
            current_section = "Descriptive"
        else:
            # Process MCQ section
            if current_section == "MCQ":
                # Remove numbering (e.g., "1. ") and check for "Question:"
                cleaned_line = re.sub(r'^\d+\.\s*', '', stripped_line)
                if cleaned_line.startswith("Question:"):
                    question = cleaned_line.replace("Question:", "").strip()
                    # Find Answer (skip empty lines)
                    i += 1
                    while i < len(text) and text[i].strip() == "":
                        i += 1
                    answer = text[i].strip().replace("Answer:", "").strip()
                    # Find Other_Options (skip empty lines)
                    i += 1
                    while i < len(text) and text[i].strip() == "":
                        i += 1
                    options_line = text[i].strip().replace("Other_Options:", "").strip()
                    other_options = [opt.strip() for opt in options_line.split(", ")]
                    # Append to MCQ
                    data["MCQ"].append({
                        "Question": question,
                        "Answer": answer,
                        "Other_Options": other_options
                    })
            # Process Descriptive section
            elif current_section == "Descriptive":
                cleaned_line = re.sub(r'^\d+\.\s*', '', stripped_line)
                if cleaned_line.startswith("Question:"):
                    question = cleaned_line.replace("Question:", "").strip()
                    # Find Answer (skip empty lines)
                    i += 1
                    while i < len(text) and text[i].strip() == "":
                        i += 1
                    answer = text[i].strip().replace("Answer:", "").strip()
                    # Append to Descriptive
                    data["Descriptive"].append({
                        "Question": question,
                        "Answer": answer
                    })
        i += 1
    print(data)
    return data

def is_path_allowed(base_url, path):
    """
    Check if scraping is allowed for a specific path using the site's robots.txt file.
    """
    robots_url = f"{base_url}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)
    rp.read()
    return rp.can_fetch("*", f"{base_url}{path}")


def get_bbc_rss_links():
    """
    Fetch the latest articles from the BBC RSS feed.
    """
    rss_url = "http://feeds.bbci.co.uk/news/rss.xml"
    feed = feedparser.parse(rss_url)
    
    
    articles = [
        {"title": entry.title, "link": entry.link, "published": entry.published}
        for entry in feed.entries
    ]
    return articles


def filter_articles_published_within_last_hour(articles):
    """
    Filter articles that are published within the last hour.
    """
    now = datetime.now()
    one_hour_ago = now - timedelta(hours=24)
    filtered_articles = []
    for article in articles:
        published_date = datetime.strptime(article['published'], "%a, %d %b %Y %H:%M:%S %Z")
        if one_hour_ago <= published_date <= now:
            filtered_articles.append(article)
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
    
    base_url = "https://www.bbc.com"
    rss_path = "/news/rss.xml"
    
    
    if is_path_allowed(base_url, rss_path):
        logger.info("Access to the RSS feed is allowed. Fetching articles...\n")
        
        
        articles = get_bbc_rss_links()
        
        today_articles = filter_articles_published_within_last_hour(articles)
        
        
        articles_with_content = []
        counter = 0
        for article in today_articles:
            if counter>8: 
                break
            counter=counter+1
            logger.info(f"Fetching content for: {article['title']}")
            try:
                content = fetch_article_content(article['link'])
                summary = summarize_news(content)
                article_data = {
                    "title": article['title'],
                    "link": article['link'],
                    "published": article['published'],
                    "content": content,
                    "summary": summary['Summary'],
                    "News Category": summary['Categories'],
                    "MCQ":summary['MCQ'],
                    "Descriptive":summary['Descriptive']
                }
                articles_with_content.append(article_data)
            except Exception as e:
                logger.info(f"Failed to fetch content for: {article['title']}. Error: {e}")
        
        '''-----------------------------------------------------------------------------------------'''
        with open("today_articles.json", "w", encoding="utf-8") as f:
            json.dump(articles_with_content, f, ensure_ascii=False, indent=4)

        '''---------------------------WRITE CODE TO UPDATE TO MONGODB--------------------------------''' 
        
        logger.info(f"Saved {len(articles_with_content)} articles to 'today_articles.json'.")
    else:
        logger.info(f"Access to the RSS feed path '{rss_path}' is not allowed according to robots.txt.")
