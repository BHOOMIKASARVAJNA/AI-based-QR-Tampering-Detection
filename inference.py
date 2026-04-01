"""
inference.py — QR Tampering Detection + UPI Merchant Verification

Model output convention (set by train_model.py):
    Alphabetical folder order: fake=0, real=1
    prediction[0][0] → probability of being REAL (index 1)
    So tamper_prob = 1 - prediction[0][0]

    HOWEVER: Due to small dataset size, the model sometimes learns
    labels in reverse. This file auto-detects the correct polarity
    at startup by testing against a known real QR from the dataset,
    so it self-corrects regardless of which way training went.
"""

import io
import os
import json
import numpy as np
import cv2
from PIL import Image
import tensorflow as tf

# ─────────────────────────────────────────
# Startup: load model & merchant registry once
# ─────────────────────────────────────────

try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    MODEL_PATH = os.path.join(BASE_DIR, "qr_tampering_model.keras")
    print("Current dir:", BASE_DIR)
    print("Files in dir:", os.listdir(BASE_DIR))
    print("Looking for model at:", MODEL_PATH)
    print("Model loaded successfully.")
except Exception as e:
    model = None
    print(f"Could not load model: {e}")

try:
    REG_PATH = os.path.join(os.path.dirname(__file__), "merchant_registry.json")
    with open(REG_PATH, "r", encoding="utf-8") as f:
        raw_registry = json.load(f)
    VERIFIED_UPI_IDS = {entry["verified_upi_id"].strip().lower() for entry in raw_registry}
    UPI_TO_NAME = {
        entry["verified_upi_id"].strip().lower(): entry["merchant_name"]
        for entry in raw_registry
    }
    print(f"Merchant registry loaded: {len(VERIFIED_UPI_IDS)} verified UPI IDs.")
except Exception as e:
    VERIFIED_UPI_IDS = set()
    UPI_TO_NAME = {}
    print(f"Could not load merchant registry: {e}")


# ─────────────────────────────────────────
# Auto-detect label polarity at startup
# ─────────────────────────────────────────
# We test the model against the first image in the real/ folder.
# If prediction[0][0] is LOW for a real image, labels are flipped.
# LABEL_FLIPPED = True  → tamper_prob = prediction[0][0]
# LABEL_FLIPPED = False → tamper_prob = 1 - prediction[0][0]

LABEL_FLIPPED = False  # default

DATASET_REAL_PATH = os.path.join(os.path.dirname(__file__), "dataset", "real")

def _auto_detect_polarity():
    global LABEL_FLIPPED
    if model is None:
        print("Skipping polarity check — model not loaded.")
        return

    # Find first real image in dataset
    real_img_path = None
    if os.path.isdir(DATASET_REAL_PATH):
        for fname in os.listdir(DATASET_REAL_PATH):
            if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                real_img_path = os.path.join(DATASET_REAL_PATH, fname)
                break

    if real_img_path is None:
        print("Could not find real/ dataset folder for polarity check.")
        print("Defaulting to LABEL_FLIPPED = False")
        return

    try:
        img = Image.open(real_img_path).convert("RGB")
        arr = np.array(img)
        resized = cv2.resize(arr, (128, 128))
        normalized = resized / 255.0
        tensor = np.expand_dims(normalized, axis=0).astype(np.float32)
        pred = model(tensor, training=False).numpy()
        raw = float(pred[0][0])

        print(f"Polarity check — real image raw prediction: {raw:.4f}")

        if raw < 0.5:
            # Model output is LOW for a real image → labels are flipped
            LABEL_FLIPPED = True
            print("Labels appear FLIPPED — auto-correcting (tamper_prob = prediction[0][0])")
        else:
            # Model output is HIGH for a real image → labels are correct
            LABEL_FLIPPED = False
            print("Labels are CORRECT — (tamper_prob = 1 - prediction[0][0])")

    except Exception as e:
        print(f"Polarity check failed: {e} — defaulting to LABEL_FLIPPED = False")

_auto_detect_polarity()

# ─────────────────────────────────────────
# Helper: decode QR code from image array
# ─────────────────────────────────────────
def decode_qr(img_array: np.ndarray) -> str | None:
    """
    Try OpenCV QRCodeDetector first, then pyzbar as fallback.
    Returns decoded string or None.
    """
    # ── Attempt 1: OpenCV ──
    try:
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(img_array)
        if data:
            return data.strip()
    except Exception:
        pass

    # ── Attempt 2: pyzbar (more robust for distorted/printed QRs) ──
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        results = pyzbar_decode(gray)
        if results:
            return results[0].data.decode("utf-8").strip()
    except Exception:
        pass

    return None

# ─────────────────────────────────────────
# Helper: check UPI ID against registry
# ─────────────────────────────────────────
def verify_upi(upi_id: str | None) -> tuple[bool, str]:
    """
    Returns (is_verified, merchant_name_or_message).
    """
    if not upi_id:
        return False, "No UPI ID found in QR"

    # Extract UPI ID from UPI deep-link if present
    # e.g. upi://pay?pa=merchant1@upi&pn=Merchant1
    if "pa=" in upi_id.lower():
        import urllib.parse as urlparse
        try:
            parsed = urlparse.urlparse(upi_id)
            params = urlparse.parse_qs(parsed.query)
            upi_id = params.get("pa", [upi_id])[0].strip()
        except Exception:
            pass

    lookup_key = upi_id.lower()
    if lookup_key in VERIFIED_UPI_IDS:
        merchant = UPI_TO_NAME.get(lookup_key, "Unknown Merchant")
        return True, merchant
    return False, "UPI ID not in merchant registry"


# ─────────────────────────────────────────
# Main analysis function
# ─────────────────────────────────────────
async def analyze_qr(file) -> dict:
    """
    Accepts a FastAPI UploadFile.
    Returns structured analysis result.
    """

    result = {
        "status": "Unknown",
        "risk_score": 0,
        "extracted_upi": None,
        "merchant_name": None,
        "upi_verified": False,
        "tampering_probability": 0.0,
        "reasons": []
    }

    if model is None:
        result["status"] = "Error"
        result["reasons"].append("Model not loaded. Run train_model.py first.")
        return result

    try:
        # ── 1. Read file bytes (async-safe) ──
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")

        # ── Cap large images early to avoid slow processing ──
        image = image.resize((512, 512))

        img_array = np.array(image)

        # ── 2. Decode QR content ──
        qr_data = decode_qr(img_array)
        result["extracted_upi"] = qr_data

        # ── 3. UPI Merchant Verification ──
        upi_verified, upi_msg = verify_upi(qr_data)
        result["upi_verified"] = upi_verified
        if upi_verified:
            result["merchant_name"] = upi_msg
        else:
            result["reasons"].append(f"UPI check: {upi_msg}")

        # ── 4. CNN Tampering Detection ──
        resized      = cv2.resize(img_array, (128, 128))
        normalized   = resized / 255.0
        input_tensor = np.expand_dims(normalized, axis=0).astype(np.float32)

        # Direct model call — faster than model.predict()
        prediction = model(input_tensor, training=False).numpy()
        raw = float(prediction[0][0])

        # Use auto-detected polarity to get correct tamper probability
        if LABEL_FLIPPED:
            tamper_prob = raw              # model learned fake=1, real=0
        else:
            tamper_prob = 1.0 - raw       # model learned fake=0, real=1 (correct)

        real_prob = 1.0 - tamper_prob

        print(f"🔍 Raw: {raw:.4f} | LABEL_FLIPPED: {LABEL_FLIPPED} | tamper_prob: {tamper_prob:.4f}")

        result["tampering_probability"] = round(tamper_prob, 4)

        # ── 5. Combined Risk Score ──
        visual_risk = tamper_prob * 100   # 0–100

        if upi_verified:
            if visual_risk >= 80:
                risk = int(visual_risk)
            else:
                risk = int(visual_risk * 0.75)
        else:
            upi_penalty = 25
            risk = int(visual_risk * 1.0 + upi_penalty)

        risk = min(max(risk, 0), 100)
        result["risk_score"] = risk

        # ── 6. Verdict ──
        if risk < 20:
            result["status"] = "Safe QR Code"
        elif risk < 45:
            result["status"] = "Suspicious QR Code"
        else:
            result["status"] = "High Risk — Potentially Tampered"

        # ── 7. Supplementary reasons ──
        if tamper_prob >= 0.80:
            result["reasons"].append(f"CNN high confidence tampering ({tamper_prob*100:.1f}%)")
        elif tamper_prob >= 0.50:
            result["reasons"].append(f"CNN moderate tampering signs ({tamper_prob*100:.1f}%)")
        if qr_data is None:
            result["reasons"].append("QR content could not be decoded")
        if not upi_verified and qr_data is not None:
            result["reasons"].append("UPI not in merchant registry")

    except Exception as e:
        result["status"] = "Error analyzing QR"
        result["reasons"].append(str(e))

    return result
