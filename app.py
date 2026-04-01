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

st.set_page_config(page_title="QR Tampering Detection", layout="centered")

st.title("🔍 AI-based QR Tampering Detection")
st.write("Upload a QR code image to check if it is tampered or original.")

uploaded_file = st.file_uploader("Upload QR Image", type=["png", "jpg", "jpeg"])

def predict(img):
    img = np.array(img)

    # Convert to grayscale
    gray = np.mean(img, axis=2)

    # Variance (MAIN SIGNAL)
    variance = np.var(gray)

    return variance

if uploaded_file:
    img = Image.open(uploaded_file).convert("RGB")
    st.image(img, caption="Uploaded Image", use_column_width=True)

    score = predict(img)

    st.write(f"**Variance Score:** {score:.2f}")

    # ✅ FINAL LOGIC (based on your actual results)
    if score < 7000:
        st.error("⚠️ Possible Tampered QR Code")
    else:
        st.success("✅ Original QR Code")

    st.caption("Demo version using statistical image variance.")
