from sqlalchemy import Column, Integer, String, DateTime  # ★ 追加
from datetime import datetime                             # ★ 追加
from database import Base
from sqlalchemy import Boolean
from sqlalchemy import Column, Integer, String, DateTime, Text  # ← Text を追加

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    image_path = Column(String)
    owner = Column(String)
    color = Column(String)   # 🔴 追加：Vision APIのRGB情報
    labels = Column(String)  # 🔴 追加：Vision APIのラベル情報（カンマ区切り）
    season = Column(String)  # 🔥 追加：春夏秋冬のいずれか
    tpo = Column(String)     # 🔥 追加：TPO（ビジネス・デートなど）
    favorite = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)           # アクションをしたユーザー
    action = Column(String)                         # 例: "ログイン", "アップロード"
    detail = Column(String)                         # 例: "ネイビージャケット"
    timestamp = Column(DateTime, default=datetime.utcnow)  # 実行日時


class Coordinate(Base):
    __tablename__ = "coordinates"
    id = Column(Integer, primary_key=True)
    owner = Column(String)
    title = Column(String)
    description = Column(Text)
    item_ids = Column(String)  # カンマ区切りのIDでも、リレーションでもOK
    created_at = Column(DateTime, default=datetime.utcnow)

class CoordinateItem(Base):
    __tablename__ = "coordinate_items"

    id = Column(Integer, primary_key=True, index=True)
    coordinate_id = Column(Integer)
    item_id = Column(Integer)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)  # usersテーブルと連携
    display_name = Column(String)
    bio = Column(String)
    icon_path = Column(String, nullable=True)  # 例: /static/uploads/user_abc.png

class Follow(Base):
    __tablename__ = "follows"

    id = Column(Integer, primary_key=True)
    follower = Column(String, index=True)  # フォローする側
    following = Column(String, index=True)  # フォローされる側

class ManualCoordinate(Base):
    __tablename__ = "manual_coordinates"

    id = Column(Integer, primary_key=True)
    owner = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    item_ids = Column(String)  # カンマ区切りの item.id
    created_at = Column(DateTime, default=datetime.utcnow)