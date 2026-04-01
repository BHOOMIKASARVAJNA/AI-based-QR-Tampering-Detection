# from fastapi import FastAPI, UploadFile, File
# from fastapi.responses import HTMLResponse
# from fastapi.middleware.cors import CORSMiddleware
# from inference import analyze_qr

# app = FastAPI(title="AI QR Tampering Detector")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# @app.get("/", response_class=HTMLResponse)
# async def home():
#     with open("index.html", "r", encoding="utf-8") as f:
#         return f.read()

# @app.post("/analyze-qr")
# async def analyze_qr_endpoint(file: UploadFile = File(...)):
#     # analyze_qr is now async — must be awaited
#     result = await analyze_qr(file)
#     return result
import streamlit as st
from PIL import Image
import numpy as np
import cv2

st.set_page_config(page_title="QR Tampering Detection", layout="centered")

st.title("🔍 AI-based QR Tampering Detection")
st.write("Upload a QR code image to check if it is tampered or original.")

uploaded_file = st.file_uploader("Upload QR Image", type=["png", "jpg", "jpeg"])

def predict(img):
    img = np.array(img)

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    # Edge detection
    edges = cv2.Canny(gray, 100, 200)

    # Calculate edge density
    edge_density = np.sum(edges) / edges.size

    return edge_density

if uploaded_file:
    img = Image.open(uploaded_file)
    st.image(img, caption="Uploaded Image", use_column_width=True)

    score = predict(img)

    st.write(f"Edge Score: {score:.4f}")

    # Decision logic (tunable threshold)
    if score > 0.15:
        st.error("Possible Tampered QR Code")
    else:
        st.success("Original QR Code")

    st.caption("Note: This is a lightweight demo using image analysis heuristics.")
