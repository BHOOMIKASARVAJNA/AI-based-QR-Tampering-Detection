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

st.title("AI-based QR Tampering Detection")

uploaded_file = st.file_uploader("Upload QR Image", type=["png","jpg","jpeg"])

if uploaded_file:
    img = Image.open(uploaded_file)
    st.image(img, caption="Uploaded Image")

    img_arr = np.array(img)

    # dummy logic
    if img_arr.mean() < 100:
        st.error("Possible Tampered QR Code")
    else:
        st.success("Original QR Code")
