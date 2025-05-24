from fastapi import FastAPI, Request, Form, Depends, status, Response, Cookie, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from database import engine, Base, SessionLocal
from auth import register_user, authenticate_user
from models import Item
import os
from dotenv import load_dotenv
from google.cloud import vision
from collections import Counter
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import ActivityLog
from models import Coordinate, Item, UserProfile, Follow, User, ManualCoordinate

from utils import rgb_string_to_tuple, rgb_to_color_category, color_compatibility, label_compatibility
from datetime import datetime
from fastapi import UploadFile, File
import shutil
from models import UserProfile
from fastapi import Depends
from werkzeug.utils import secure_filename
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from fastapi import status, Form, Response
from fastapi import Cookie


load_dotenv()




UPLOAD_ITEM_DIR = "static/uploads"
UPLOAD_ICON_DIR = "static/profile_icons"
os.makedirs(UPLOAD_ITEM_DIR, exist_ok=True)
os.makedirs(UPLOAD_ICON_DIR, exist_ok=True)



app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

Base.metadata.create_all(bind=engine)

@app.get("/", response_class=HTMLResponse)
def home():
    return RedirectResponse(url="/login")

@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register_post(username: str = Form(...), password: str = Form(...)):
    register_user(username, password)
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login_post(response: Response, username: str = Form(...), password: str = Form(...)):
    if authenticate_user(username, password):
        db = SessionLocal()
        log = ActivityLog(username=username, action="ログイン", detail="")
        db.add(log)
        db.commit()
        db.close()

        # ✅ クッキーをJavaScriptからも利用できるように設定
        response = RedirectResponse(url="/mypage", status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="username",
            value=username,
            path="/",
            httponly=False,   # JavaScriptから読めるように
            samesite="lax"    # クロスサイト制限を緩める
        )
        return response
    else:
        return JSONResponse(status_code=401, content={"message": "ログイン失敗"})




@app.post("/upload-item")
async def upload_item(
    username: str = Form(...),
    name: str = Form(...),
    season: str = Form(...),
    tpo: str = Form(...),
    file: UploadFile = File(...)
):
    safe_filename = secure_filename(file.filename)
    filename = f"{UPLOAD_ITEM_DIR}/{safe_filename}"
    contents = await file.read()
    with open(filename, "wb") as f:
        f.write(contents)

    client = vision.ImageAnnotatorClient()
    with open(filename, "rb") as image_file:
        image = vision.Image(content=image_file.read())

    color_response = client.image_properties(image=image)
    props = color_response.image_properties_annotation
    rgb = "不明"
    if props.dominant_colors.colors:
        color = props.dominant_colors.colors[0].color
        rgb = f"RGB({int(color.red)}, {int(color.green)}, {int(color.blue)})"

    web_response = client.web_detection(image=image)
    web_entities = web_response.web_detection.web_entities
    label_list = [entity.description for entity in web_entities if entity.description]
    label_string = ", ".join(label_list[:3]) if label_list else "不明"

    db = SessionLocal()
    item = Item(
        name=name,
        image_path=filename,
        owner=username,
        color=rgb,
        labels=label_string,
        season=season,
        tpo=tpo
    )
    db.add(item)

    # ✅ アクティビティログ登録
    log = ActivityLog(username=username, action="アップロード", detail=name)
    db.add(log)

    db.commit()
    db.close()

    return {
        "message": "保存完了",
        "image_path": f"/static/uploads/{safe_filename}",
        "dominant_color": rgb,
        "labels": label_string
    }


@app.get("/items")
def get_items(username: str = Cookie(default=None)):
    db = SessionLocal()
    items = db.query(Item).filter(Item.owner == username).all()
    db.close()

    # ✅ color, labels を含めて返す
    result = [
        {
            "id": item.id,
            "name": item.name,
            "image_path": item.image_path.replace("static/", "/static/"),
            "dominant_color": item.color,
            "labels": item.labels,
            "season": item.season,
            "tpo": item.tpo
        }
        for item in items
    ]
    return JSONResponse(content=result)

@app.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request, username: str = Cookie(default=None)):
    if username is None:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("upload.html", {"request": request, "username": username})

@app.post("/delete-item/{item_id}")
def delete_item_post(item_id: int, username: str = Cookie(default=None)):
    db = SessionLocal()
    item = db.query(Item).filter(Item.id == item_id, Item.owner == username).first()

    if item is None:
        db.close()
        raise HTTPException(status_code=404, detail="アイテムが見つかりません")

    if os.path.exists(item.image_path):
        os.remove(item.image_path)

    db.delete(item)
    db.commit()
    db.close()

    return RedirectResponse(url="/closet", status_code=302)




@app.get("/mypage", response_class=HTMLResponse)
def mypage(request: Request, username: str = Cookie(default=None)):
    if username is None:
        return RedirectResponse(url="/login")

    db = SessionLocal()

    # 登録アイテム数
    item_count = db.query(Item).filter(Item.owner == username).count()

    # コーディネート数
    coordinate_count = db.query(Coordinate).filter(Coordinate.owner == username).count()

    # よく使うカテゴリ・色
    all_labels = db.query(Item.labels).filter(Item.owner == username).all()
    flat_labels = [label for labels in all_labels for label in labels[0].split(", ") if labels[0]]
    top_category = Counter(flat_labels).most_common(1)[0][0] if flat_labels else "不明"

    all_colors = db.query(Item.color).filter(Item.owner == username).all()
    flat_colors = [color[0] for color in all_colors if color[0]]
    common_color = Counter(flat_colors).most_common(1)[0][0] if flat_colors else "不明"

    # 最近アイテム・アクティビティ
    recent_items = db.query(Item).filter(Item.owner == username).order_by(Item.id.desc()).limit(3).all()
    activity_logs = db.query(ActivityLog).filter(ActivityLog.username == username).order_by(ActivityLog.timestamp.desc()).limit(5).all()
    activity_logs_for_view = [
        f"{log.timestamp.strftime('%Y-%m-%d %H:%M:%S')} に {log.action}しました" +
        (f'：「{log.detail}」' if log.detail else "")
        for log in activity_logs
    ]

    # ⭐ プロフィール情報取得
    profile = db.query(UserProfile).filter(UserProfile.username == username).first()

    db.close()

    return templates.TemplateResponse("mypage.html", {
        "request": request,
        "username": username,
        "item_count": item_count,
        "coordinate_count": coordinate_count,
        "top_category": top_category,
        "common_color": common_color,
        "recent_items": [
            {
                "name": item.name,
                "image_url": f"/static/uploads/{os.path.basename(item.image_path)}"
            } for item in recent_items
        ],
        "activity_logs": activity_logs_for_view,
        "profile": profile  # ← これをテンプレートへ渡す
    })

@app.get("/closet", response_class=HTMLResponse)
def closet(request: Request, username: str = Cookie(default=None), season: str = "", tpo: str = ""):
    if username is None:
        return RedirectResponse(url="/login")

    db = SessionLocal()

    query = db.query(Item).filter(Item.owner == username)

    if season:
        query = query.filter(Item.season == season)
    if tpo:
        query = query.filter(Item.tpo == tpo)

    items = query.all()
    db.close()

    return templates.TemplateResponse("closet.html", {
        "request": request,
        "username": username,
        "items": items,
        "season": season,
        "tpo": tpo
    })

@app.post("/toggle-favorite/{item_id}")
def toggle_favorite(item_id: int, request: Request, username: str = Cookie(default=None)):
    db: Session = SessionLocal()
    item = db.query(Item).filter(Item.id == item_id, Item.owner == username).first()
    if item:
        item.favorite = not item.favorite
        db.commit()
    db.close()
    referer = request.headers.get("referer", "/closet")
    return RedirectResponse(url=referer, status_code=302)





from utils import rgb_string_to_tuple, rgb_to_color_category, color_compatibility, label_compatibility

@app.get("/coordinate", response_class=HTMLResponse)
def coordinate_page(request: Request, username: str = Cookie(default=None)):
    if username is None:
        return RedirectResponse(url="/login")

    db: Session = SessionLocal()
    items = db.query(Item).filter(Item.owner == username).all()
    db.close()

    priority_rules = request.query_params.getlist("priority_rules")
    pairs = []

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            item1 = items[i]
            item2 = items[j]

            match_count = 0

            # --- 条件1: カラー相性チェック ---
            if "color" in priority_rules:
                rgb1 = rgb_string_to_tuple(item1.color)
                rgb2 = rgb_string_to_tuple(item2.color)
                if rgb1 and rgb2:
                    cat1 = rgb_to_color_category(*rgb1)
                    cat2 = rgb_to_color_category(*rgb2)
                    if cat2 in color_compatibility.get(cat1, []):
                        match_count += 1

            # --- 条件2: ラベル相性チェック ---
            if "labels" in priority_rules:
                labels1 = item1.labels.split(", ") if item1.labels else []
                labels2 = item2.labels.split(", ") if item2.labels else []
                label_match = False
                for l1 in labels1:
                    for l2 in labels2:
                        if l2 in label_compatibility.get(l1, []):
                            label_match = True
                if label_match:
                    match_count += 1

            # --- 条件3: シーズン一致 ---
            if "season" in priority_rules and item1.season == item2.season:
                match_count += 1

            # --- 条件4: TPO一致 ---
            if "tpo" in priority_rules and item1.tpo == item2.tpo:
                match_count += 1

            # --- いずれかの条件に一致すれば候補に含める ---
            if match_count > 0:
                # カテゴリ情報をテンプレートに渡す用に拡張
                rgb1 = rgb_string_to_tuple(item1.color)
                rgb2 = rgb_string_to_tuple(item2.color)
                item1.color_category = rgb_to_color_category(*rgb1) if rgb1 else "不明"
                item2.color_category = rgb_to_color_category(*rgb2) if rgb2 else "不明"
                pairs.append((item1, item2))

    return templates.TemplateResponse("coordinate.html", {
        "request": request,
        "username": username,
        "coordinates": pairs,
        "priority_rules": priority_rules
    })


@app.post("/create-coordinate")
def create_coordinate(
    request: Request,
    username: str = Cookie(default=None),
    title: str = Form(...),
    description: str = Form(...),
    items: list[str] = Form(...)
):
    if username is None:
        return RedirectResponse(url="/login", status_code=302)

    item_ids = ",".join(items)

    db = SessionLocal()
    new_coord = Coordinate(
        owner=username,
        title=title,
        description=description,
        item_ids=item_ids
    )
    db.add(new_coord)
    db.commit()
    db.close()

    return RedirectResponse(url="/mypage", status_code=302)


@app.get("/coordinates", response_class=HTMLResponse)
def view_coordinates(request: Request, username: str = Cookie(default=None)):
    if username is None:
        return RedirectResponse(url="/login")

    db = SessionLocal()

    coordinates = db.query(Coordinate).filter(Coordinate.owner == username).order_by(Coordinate.created_at.desc()).all()
    manual_coordinates = db.query(ManualCoordinate).filter(ManualCoordinate.owner == username).order_by(ManualCoordinate.created_at.desc()).all()

    items = db.query(Item).filter(Item.owner == username).all()
    item_dict = {str(item.id): item for item in items}

    db.close()

    return templates.TemplateResponse("coordinates.html", {
        "request": request,
        "username": username,
        "coordinates": coordinates,
        "manual_coordinates": manual_coordinates,
        "item_dict": item_dict
    })


@app.post("/save-coordinate")
def save_coordinate(
    request: Request,
    item_ids: str = Form(...),
    title: str = Form(""),
    description: str = Form(""),
    username: str = Cookie(default=None)
):
    if username is None:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    coordinate = Coordinate(
        owner=username,
        title=title.strip() or "無題コーディネート",
        description=description.strip(),
        item_ids=item_ids,
        created_at=datetime.utcnow()
    )
    db.add(coordinate)
    db.commit()
    db.close()

    return RedirectResponse(url="/mypage", status_code=302)

@app.post("/delete-coordinate/{coord_id}")
def delete_coordinate(coord_id: int, username: str = Cookie(default=None)):
    if username is None:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    coord = db.query(Coordinate).filter(Coordinate.id == coord_id, Coordinate.owner == username).first()
    if coord:
        db.delete(coord)
        db.commit()
    db.close()

    return RedirectResponse(url="/coordinates", status_code=302)


from fastapi import File, UploadFile
import shutil

UPLOAD_DIR = "static/profile_icons"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/profile/edit", response_class=HTMLResponse)
def edit_profile(request: Request, username: str = Cookie(default=None)):
    if username is None:
        return RedirectResponse(url="/login")

    db = SessionLocal()
    profile = db.query(UserProfile).filter(UserProfile.username == username).first()
    db.close()

    return templates.TemplateResponse("edit_profile.html", {
        "request": request,
        "username": username,
        "profile": profile
    })

@app.post("/profile/edit")
async def update_profile(
    request: Request,
    username: str = Cookie(default=None),
    bio: str = Form(""),
    icon: UploadFile = File(None)
):
    if username is None:
        return RedirectResponse(url="/login")

    db = SessionLocal()
    profile = db.query(UserProfile).filter(UserProfile.username == username).first()

    icon_path = None
    if icon and icon.filename:
        safe_icon_filename = secure_filename(icon.filename)
        icon_filename = f"{UPLOAD_ICON_DIR}/{username}_{safe_icon_filename}"
        with open(icon_filename, "wb") as f:
            shutil.copyfileobj(icon.file, f)
        icon_path = icon_filename.replace("static/", "/static/")  # ← Web表示用に

    if profile:
        profile.bio = bio
        if icon_path:
            profile.icon_path = icon_path
    else:
        profile = UserProfile(
            username=username,
            bio=bio,
            icon_path=icon_path or ""
        )
        db.add(profile)

    db.commit()
    db.close()

    return RedirectResponse(url="/mypage", status_code=302)


@app.get("/user/{username}", response_class=HTMLResponse)
def view_user_profile(request: Request, username: str, me: str = Cookie(default=None)):
    db = SessionLocal()

    # 対象ユーザーのプロフィールとコーディネート取得
    profile = db.query(UserProfile).filter(UserProfile.username == username).first()
    coordinates = db.query(Coordinate).filter(Coordinate.owner == username).order_by(Coordinate.created_at.desc()).all()
    items = db.query(Item).filter(Item.owner == username).all()
    item_dict = {str(item.id): item for item in items}

    # フォロー状態
    is_following = False
    if me and me != username:
        is_following = db.query(Follow).filter(Follow.follower == me, Follow.following == username).first() is not None

    # ✅ フォロー数、フォロワー数のカウント
    follow_count = db.query(Follow).filter(Follow.follower == username).count()
    follower_count = db.query(Follow).filter(Follow.following == username).count()

    db.close()

    return templates.TemplateResponse("user_profile.html", {
        "request": request,
        "username": username,
        "profile": profile,
        "me": me,
        "is_following": is_following,
        "follow_count": follow_count,
        "follower_count": follower_count,
        "coordinates": coordinates,
        "item_dict": item_dict
    })
    
@app.post("/follow/{target}")
def follow_user(target: str, username: str = Cookie(None)):
    print("フォローボタン押下時の username:", username)

    if not username or username == target:
        return JSONResponse(content={"error": "無効な操作"}, status_code=400)

    db = SessionLocal()
    existing = db.query(Follow).filter(Follow.follower == username, Follow.following == target).first()

    if existing:
        db.delete(existing)
        db.commit()
        action = "unfollowed"
    else:
        db.add(Follow(follower=username, following=target))
        db.commit()
        action = "followed"

    follow_count = db.query(Follow).filter(Follow.follower == target).count()
    follower_count = db.query(Follow).filter(Follow.following == target).count()
    db.close()

    return JSONResponse(content={
        "success": True,
        "action": action,
        "follow_count": follow_count,
        "follower_count": follower_count
    })



@app.get("/users", response_class=HTMLResponse)
def list_users(request: Request, username: str = Cookie(default=None)):
    if username is None:
        return RedirectResponse(url="/login")
    db = SessionLocal()
    all_users = db.query(User).all()

    users = []
    for user in all_users:
        if user.username != username:
            is_following = db.query(Follow).filter(
                Follow.follower == username, Follow.following == user.username
            ).first() is not None
            user.is_following = is_following
        users.append(user)

    db.close()
    return templates.TemplateResponse("user_list.html", {
        "request": request,
        "username": username,
        "users": users
    })


from typing import Optional  # 追加が必要な場合

from fastapi import Request, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

@app.get("/profile/{username}", response_class=HTMLResponse)
def view_user_profile(
    request: Request,
    username: str,
    db: Session = Depends(SessionLocal),
    local_kw: Optional[str] = Query(None)  # ✅ ここをQuery(None)にするのが重要！
):
    user = db.query(UserProfile).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")

    me = request.cookies.get("username")
    is_self = (me == username)

    return templates.TemplateResponse("user_profile.html", {
        "request": request,
        "username": username,
        "profile": user,
        "is_self": is_self,
        "local_kw": local_kw  # ← 必要ならテンプレートに渡す
    })
    
@app.get("/profile/{username}/following", response_class=HTMLResponse)
def profile_following(request: Request, username: str, me: str = Cookie(default=None)):
    db = SessionLocal()
    follows = db.query(Follow).filter(Follow.follower == username).all()

    users = []
    for f in follows:
        user = db.query(User).filter(User.username == f.following).first()
        if user:
            user.is_following = db.query(Follow).filter(
                Follow.follower == me, Follow.following == user.username
            ).first() is not None
            users.append(user)

    db.close()
    return templates.TemplateResponse("user_list_common.html", {
        "request": request,
        "username": username,
        "me": me,
        "users": users,
        "title": "フォロー中"
    })




@app.get("/profile/{username}/followers", response_class=HTMLResponse)
def profile_followers(request: Request, username: str, me: str = Cookie(default=None)):
    db = SessionLocal()
    follows = db.query(Follow).filter(Follow.following == username).all()

    users = []
    for f in follows:
        user = db.query(User).filter(User.username == f.follower).first()
        if user:
            user.is_following = db.query(Follow).filter(
                Follow.follower == me, Follow.following == user.username
            ).first() is not None
            users.append(user)

    db.close()
    return templates.TemplateResponse("user_list_common.html", {
        "request": request,
        "username": username,
        "me": me,
        "users": users,
        "title": "フォロワー"
    })


@app.post("/delete-manual-coordinate/{coord_id}")
def delete_manual_coordinate(coord_id: int, username: str = Cookie(default=None)):
    if username is None:
        return RedirectResponse(url="/login")

    db = SessionLocal()
    coord = db.query(ManualCoordinate).filter(ManualCoordinate.id == coord_id, ManualCoordinate.owner == username).first()
    if coord:
        db.delete(coord)
        db.commit()
    db.close()

    return RedirectResponse(url="/coordinates", status_code=302)


@app.get("/create", response_class=HTMLResponse)
def create_coordinate_page(request: Request, username: str = Cookie(default=None)):
    if username is None:
        return RedirectResponse(url="/login")

    db = SessionLocal()
    items = db.query(Item).filter(Item.owner == username).all()
    db.close()

    return templates.TemplateResponse("create_coordinate.html", {
        "request": request,
        "username": username,
        "items": items
    })

@app.post("/create")
def create_coordinate_post(
    title: str = Form(...),
    description: str = Form(""),
    items: list[str] = Form(...),
    username: str = Cookie(default=None)
):
    if username is None:
        return RedirectResponse(url="/login")

    item_ids = ",".join(items)
    db = SessionLocal()
    new_manual = ManualCoordinate(
        owner=username,
        title=title,
        description=description,
        item_ids=item_ids
    )
    db.add(new_manual)
    db.commit()
    db.close()

    return RedirectResponse(url="/coordinates", status_code=302)

