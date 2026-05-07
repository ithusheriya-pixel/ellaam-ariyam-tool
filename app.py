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
    headers = {'User-Agent': 'Mozilla/5.0'}
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
    """Checks if the topic is already in the Sheet catalog."""
    try:
        sheet = gc.open(SHEET_NAME).sheet1
        return topic in sheet.col_values(1)
    except:
        return False

def generate_ai_content(topic):
    """Generates Malayalam caption and image prompt using Gemini."""
    prompt = (
        f"Topic: {topic}. Create a catchy, high-energy Facebook caption in Malayalam "
        f"with 5 trending hashtags. Also, write a detailed image generation prompt "
        f"for a vibrant, eye-catchy graphic that includes the Malayalam text '{topic[:15]}'."
    )
    response = client.models.generate_content(model="gemini-1.5-flash", contents=[prompt])
    return response.text

def generate_visual(image_prompt):
    """Generates the actual image using Gemini's image model."""
    response = client.models.generate_content(
        model="gemini-3.1-flash-image-preview", 
        contents=[image_prompt]
    )
    for part in response.parts:
        if part.inline_data:
            return Image.open(io.BytesIO(part.inline_data.data))
    return None

def save_assets(topic, content, image):
    """Saves files to Google Drive and logs the entry in Google Sheets."""
    # 1. Save Image to Drive
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    file_metadata = {'name': f'{topic[:20]}.png', 'parents': [DRIVE_FOLDER_ID]}
    media = MediaFileUpload(io.BytesIO(img_byte_arr.read()), mimetype='image/png')
    drive_service.files().create(body=file_metadata, media_body=media).execute()

    # 2. Update Sheets
    sheet = gc.open(SHEET_NAME).sheet1
    sheet.append_row([topic, str(datetime.date.today()), content])

# --- 4. UI ---
st.title("📱 Ellaam Ariyam Content Engine")

# Initialize session state so the UI doesn't reset on every click
if 'trends' not in st.session_state:
    st.session_state['trends'] = []
if 'results' not in st.session_state:
    st.session_state['results'] = {} 

if st.button("🔍 Scan for New Trends"):
    with st.spinner("Fetching latest news..."):
        st.session_state['trends'] = get_malayalam_trends()

# Display each news item in a container
for i, t in enumerate(st.session_state['trends']):
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader(t)
            # Show the generated result if it exists in memory
            if t in st.session_state['results']:
                res = st.session_state['results'][t]
                st.image(res['image'], caption="Ready for Ellaam Ariyam")
                st.info(res['caption'])
        
        with col2:
            if is_redundant(t):
                st.error("Already Logged")
            else:
                if st.button("Generate", key=f"gen_{i}"):
                    with st.status("🚀 Processing...", expanded=True) as status:
                        st.write("🧠 Writing Malayalam caption...")
                        content = generate_ai_content(t)
                        
                        st.write("🎨 Generating vibrant visual...")
                        # We pass the content here so Gemini has the prompt it just wrote
                        img_obj = generate_visual(content)
                        
                        st.write("📁 Saving to Drive & Sheets...")
                        save_assets(t, content, img_obj)
                        
                        # Store in state so it stays visible
                        st.session_state['results'][t] = {
                            'caption': content,
                            'image': img_obj
                        }
                        status.update(label="✅ Content Created!", state="complete")
                    st.rerun()
