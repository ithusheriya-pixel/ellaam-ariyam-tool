import streamlit as st
import feedparser
from google import genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import datetime
import io
from PIL import Image

# --- 1. ACCESS SECRETS FROM CLOUD ---
# We will set these up in the Streamlit Dashboard later
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
DRIVE_FOLDER_ID = st.secrets["DRIVE_FOLDER_ID"]
SHEET_NAME = st.secrets["SHEET_NAME"]
GOOGLE_CREDS = dict(st.secrets["google_auth"])

# --- 2. AUTHENTICATION ---
client = genai.Client(api_key=GEMINI_API_KEY)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
gc = gspread.authorize(creds)
drive_service = build('drive', 'v3', credentials=creds)

# --- 3. CORE LOGIC ---
def get_malayalam_trends():
    """Fetches news with a real-browser header to avoid being blocked."""
    feeds = [
        "https://malayalam.news18.com/rss/latest-news.xml", 
        "https://www.mathrubhumi.com/rss/latest",
        "https://news.google.com/rss?hl=ml&gl=IN&ceid=IN:ml"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    titles = []
    for url in feeds:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                for entry in feed.entries[:5]:
                    titles.append(entry.title)
        except Exception as e:
            st.error(f"Error fetching from {url}: {e}")
            
    return list(set(titles))

def is_redundant(topic):
    sheet = gc.open(SHEET_NAME).sheet1
    return topic in sheet.col_values(1)

def generate_content(topic):
    prompt = f"Topic: {topic}. Create a catchy Malayalam FB caption with 5 hashtags and a prompt for a vibrant AI image including text '{topic[:15]}'."
    response = client.models.generate_content(model="gemini-1.5-flash", contents=[prompt])
    return response.text

# --- 4. UI ---
st.title("📱 Ellaam Ariyam Content Engine")

if st.button("Check Latest Trends"):
    trends = get_malayalam_trends()
    for t in trends:
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            col1.write(t)
            if is_redundant(t):
                col2.error("Posted")
            else:
                if col2.button("Generate", key=t):
                    with st.status("Generating...", expanded=True):
                        content = generate_content(t)
                        # The image generation and Drive saving logic goes here
                        st.write(content)
                        st.success("Done!")
