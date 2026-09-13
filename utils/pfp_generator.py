import os
import random
import logging
from PIL import Image
from config import PFP_DIR

logger = logging.getLogger(__name__)

# Used local photos tracking (taaki photo repeat na ho)
used_local_pfps = set()

async def download_random_pfp(account_phone: str) -> str:
    """
    100% PURE LOCAL PFP PICKER (ZERO ONLINE APIs)
    Sirf aapke project ke 'pfp/' folder se photos uthata hai.
    70% Chance: No PFP (Default Clean Letter Avatar)
    30% Chance: Local 'pfp/' folder se unique photo
    """
    # 70% Accounts bina DP ke rahenge (Clean Letter Icon)
    if random.random() > 0.30:
        return None

    if not os.path.exists(PFP_DIR):
        return None

    valid_exts = (".jpg", ".jpeg", ".png", ".webp")
    all_photos = [
        os.path.abspath(os.path.join(PFP_DIR, f))
        for f in os.listdir(PFP_DIR)
        if f.lower().endswith(valid_exts) and not f.startswith(".") and not f.startswith("temp_")
    ]

    # Agar folder me koi photo nahi hai toh None return karein
    if not all_photos:
        return None

    global used_local_pfps
    available_photos = [p for p in all_photos if p not in used_local_pfps]

    # Agar saari photos use ho chuki hain, toh list reset karein
    if not available_photos:
        used_local_pfps.clear()
        available_photos = all_photos

    chosen_photo = random.choice(available_photos)
    used_local_pfps.add(chosen_photo)

    # Local Image ko Telegram ke 512x512 standard me convert karein
    try:
        clean_phone = account_phone.replace("+", "").replace(" ", "")
        temp_dest = os.path.abspath(os.path.join(PFP_DIR, f"temp_{clean_phone}.jpg"))

        with Image.open(chosen_photo) as img:
            img = img.convert("RGB")
            img = img.resize((512, 512), Image.Resampling.LANCZOS)
            img.save(temp_dest, "JPEG", quality=95)
        return temp_dest
    except Exception as e:
        logger.error(f"Local PFP Optimize Error: {e}")
        return chosen_photo

def cleanup_pfp(file_path: str):
    """Temporary processed photo ko delete karta hai"""
    if file_path and os.path.exists(file_path) and "temp_" in os.path.basename(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass