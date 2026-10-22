import os
from PIL import Image

def main():
    poster_path = r"C:\Users\user\.gemini\antigravity-ide\brain\d524a711-ef05-4f56-8594-6a3510c90488\.user_uploaded\media_1792652221534.jpg"
    if not os.path.exists(poster_path):
        print("Poster not found:", poster_path)
        return

    img = Image.open(poster_path)
    W, H = img.size
    print(f"Loaded poster: {W}x{H}")

    row_y = [
        (45, 187),   # Row 1
        (192, 335),  # Row 2
        (339, 482),  # Row 3
        (486, 629),  # Row 4
    ]

    col_x_5 = [
        (9, 205),
        (212, 408),
        (415, 611),
        (618, 814),
        (821, 1017),
    ]

    row_5_y = (633, 680)
    col_x_6 = [
        (9, 172),
        (179, 342),
        (349, 512),
        (519, 682),
        (689, 852),
        (859, 1022),
    ]

    cards_meta = [
        # Row 1
        {"id": "pocra", "row": 0, "col": 0, "name": "POCRA", "label": "Climate Resilient Agriculture"},
        {"id": "namo_shetkari", "row": 0, "col": 1, "name": "Namo Shetkari", "label": "Namo Shetkari Mahasanman"},
        {"id": "pm_kisan", "row": 0, "col": 2, "name": "PM-KISAN", "label": "PM Kisan Samman Nidhi"},
        {"id": "pmfby", "row": 0, "col": 3, "name": "PMFBY", "label": "Pradhan Mantri Fasal Bima"},
        {"id": "soil_health_card", "row": 0, "col": 4, "name": "Soil Health Card", "label": "Soil Health Card Scheme"},
        # Row 2
        {"id": "scholarship", "row": 1, "col": 0, "name": "Scholarship", "label": "Scholarship Schemes"},
        {"id": "mahila_kalyan", "row": 1, "col": 1, "name": "Mahila Kalyan", "label": "Mahila Kalyan & Ladki Bahin"},
        {"id": "lakhpati_didi", "row": 1, "col": 2, "name": "Lakhpati Didi", "label": "Lakhpati Didi Yojana"},
        {"id": "udyogini", "row": 1, "col": 3, "name": "Udyogini", "label": "Mukhyamantri Udyogini Yojana"},
        {"id": "startup_india", "row": 1, "col": 4, "name": "Startup India", "label": "Startup / Stand-Up India"},
        # Row 3
        {"id": "ayushman_bharat", "row": 2, "col": 0, "name": "Ayushman Bharat", "label": "Ayushman Bharat PM-JAY"},
        {"id": "pm_awas", "row": 2, "col": 1, "name": "PM Awas", "label": "Pradhan Mantri Awas Yojana"},
        {"id": "mgnrega", "row": 2, "col": 2, "name": "MGNREGA", "label": "Rural Guaranteed Employment"},
        {"id": "pm_ujjwala", "row": 2, "col": 3, "name": "PM Ujjwala", "label": "Clean Cooking Gas Scheme"},
        {"id": "digital_india", "row": 2, "col": 4, "name": "Digital India", "label": "Digital India Services"},
        # Row 4
        {"id": "pm_matru_vandana", "row": 3, "col": 0, "name": "PM Matru Vandana", "label": "PMMVY Maternal Benefit"},
        {"id": "janani_suraksha", "row": 3, "col": 1, "name": "Janani Suraksha", "label": "Janani Suraksha Yojana"},
        {"id": "pmkvy", "row": 3, "col": 2, "name": "PMKVY", "label": "Kaushal Vikas Yojana"},
        {"id": "nrlm", "row": 3, "col": 3, "name": "NRLM Umeed", "label": "Deen Dayal Antyodaya"},
        {"id": "atal_pension", "row": 3, "col": 4, "name": "Atal Pension", "label": "Atal Pension Yojana (APY)"},
        # Row 5
        {"id": "kcc", "row": 4, "col": 0, "name": "KCC", "label": "Kisan Credit Card"},
        {"id": "fisheries", "row": 4, "col": 1, "name": "Fisheries", "label": "Fisheries and Aquaculture"},
        {"id": "sericulture", "row": 4, "col": 2, "name": "Sericulture", "label": "Sericulture Scheme (Silk)"},
        {"id": "horticulture", "row": 4, "col": 3, "name": "Horticulture", "label": "Horticulture Mission"},
        {"id": "animal_husbandry", "row": 4, "col": 4, "name": "Animal Husbandry", "label": "Livestock & Dairy Development"},
        {"id": "matsya_sampada", "row": 4, "col": 5, "name": "Matsya Sampada", "label": "PM Matsya Sampada Yojana"},
    ]

    out_dirs = [
        r"c:\Users\user\Downloads\ai-government-research-agent\frontend\public\assets",
        r"c:\Users\user\Downloads\ai-government-research-agent\frontend\dist\assets"
    ]

    saved = []
    for c in cards_meta:
        r_idx = c["row"]
        c_idx = c["col"]
        cid = c["id"]
        if r_idx < 4:
            y1, y2 = row_y[r_idx]
            x1, x2 = col_x_5[c_idx]
        else:
            y1, y2 = row_5_y
            x1, x2 = col_x_6[c_idx]

        card_crop = img.crop((x1, y1, x2, y2))

        for od in out_dirs:
            os.makedirs(od, exist_ok=True)
            # Full card
            # Normalize card to standard (196, 142) canvas if height is short
            if card_crop.height < 100:
                from PIL import ImageFilter
                target_w, target_h = 196, 142
                bg = card_crop.resize((target_w, target_h), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=8))
                scale = min(target_w / card_crop.width, target_h / card_crop.height)
                nw, nh = int(card_crop.width * scale), int(card_crop.height * scale)
                im_res = card_crop.resize((nw, nh), Image.Resampling.LANCZOS)
                bg.paste(im_res, ((target_w - nw) // 2, (target_h - nh) // 2))
                card_to_save = bg
            else:
                card_to_save = card_crop

            fn_card = os.path.join(od, f"card_{cid}.jpg")
            card_to_save.save(fn_card, quality=95)

            # Photo crop
            if r_idx < 4:
                ch = y2 - y1
                photo_crop = card_crop.crop((0, int(ch * 0.22), card_crop.width, int(ch * 0.77)))
                fn_photo = os.path.join(od, f"photo_{cid}.jpg")
                photo_crop.save(fn_photo, quality=95)
            else:
                fn_photo = os.path.join(od, f"photo_{cid}.jpg")
                card_to_save.save(fn_photo, quality=95)

        saved.append(cid)

    print(f"Successfully cropped and exported {len(saved)} scheme cards to public and dist assets!")

if __name__ == "__main__":
    main()
