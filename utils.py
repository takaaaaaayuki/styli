# utils.py

def rgb_string_to_tuple(rgb_str):
    # 例: "RGB(255, 100, 50)" → (255, 100, 50)
    try:
        r, g, b = map(int, rgb_str.strip("RGB()").split(","))
        return r, g, b
    except:
        return None

def rgb_to_color_category(r, g, b):
    if r > 200 and g < 80 and b < 80:
        return "赤系"
    elif r < 80 and g < 80 and b > 200:
        return "青系"
    elif r < 80 and g > 200 and b < 80:
        return "緑系"
    elif r > 200 and g > 200 and b < 80:
        return "黄系"
    elif r < 50 and g < 50 and b < 50:
        return "黒系"
    elif r > 230 and g > 230 and b > 230:
        return "白系"
    elif 180 < r < 230 and 160 < g < 210 and 120 < b < 170:
        return "ベージュ系"
    elif abs(r - g) < 20 and abs(g - b) < 20:
        return "グレー系"
    else:
        return "その他"

color_compatibility = {
    "赤系": ["白系", "黒系", "ベージュ系", "青系"],
    "青系": ["白系", "黒系", "グレー系", "赤系"],
    "緑系": ["ベージュ系", "茶系", "白系"],
    "黄系": ["ベージュ系", "茶系", "白系"],
    "黒系": ["赤系", "青系", "緑系", "黄系", "白系", "ベージュ系", "グレー系"],
    "白系": ["赤系", "青系", "緑系", "黄系", "黒系", "ベージュ系", "グレー系"],
    "ベージュ系": ["緑系", "茶系", "黄系", "白系"],
    "グレー系": ["青系", "黒系", "白系"]
}

label_compatibility = {
    "jacket": ["shirt", "t-shirt", "hoodie", "pants"],
    "shirt": ["jacket", "vest", "pants", "skirt"],
    "pants": ["shirt", "jacket", "shoes"],
    "skirt": ["blouse", "shirt", "shoes"],
    "shoes": ["pants", "skirt", "dress"],
    "dress": ["shoes", "cardigan", "coat"]
}
