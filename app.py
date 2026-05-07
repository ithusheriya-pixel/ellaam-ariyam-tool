import streamlit as st
import feedparser
from google import genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import datetime
import requests
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

# 1. Initialize session state for trends and results
if 'trends' not in st.session_state:
    st.session_state['trends'] = []
if 'results' not in st.session_state:
    st.session_state['results'] = {} # Stores results for each topic

if st.button("🔍 Scan for New Trends"):
    with st.spinner("Fetching latest news..."):
        # This keeps the list in memory even after clicking other buttons
        st.session_state['trends'] = get_malayalam_trends()

# 2. Display the persistent list
for i, t in enumerate(st.session_state['trends']):
    # Each news item gets its own bordered box
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader(t)
            # If this specific title has already been generated, show the result here
            if t in st.session_state['results']:
                res = st.session_state['results'][t]
                st.image(res['image'], caption="Generated Visual")
                st.info(res['caption'])
        
        with col2:
            if is_redundant(t):
                st.error("Posted")
            else:
                # Clicking this button will NOT clear the other titles
                if st.button("Generate", key=f"gen_{i}"):
                    with st.status("🚀 Processing...", expanded=True) as status:
                        st.write("🧠 Crafting caption...")
                        content = generate_ai_content(t)
                        
                        st.write("🎨 Creating visual...")
                        img_obj = generate_visual(f"Graphic for: {t}")
                        
                        st.write("📁 Saving to Drive & Sheets...")
                        save_assets(t, content, img_obj)
                        
                        # SAVE result to session state so it stays on screen
                        st.session_state['results'][t] = {
                            'caption': content,
                            'image': img_obj
                        }
                        status.update(label="✅ Ready!", state="complete")
                    
                    # Force a refresh to show the result in the UI
                    st.rerun()
