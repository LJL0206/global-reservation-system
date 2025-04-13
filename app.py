from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from models import db, User, Service, Booking  # 確保 models.py 有定義這些模型
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
# 設定 Secret Key (請更換成你自己的複雜字串)
app.secret_key = "supersecretkey"
CORS(app, supports_credentials=True)

# 設定資料庫
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# 初始化資料表與初始服務資料
with app.app_context():
    db.create_all()
    if Service.query.count() == 0:
        services = [
            Service(name='按摩', description='全身舒壓按摩'),
            Service(name='美甲', description='基礎保養與彩繪'),
            Service(name='剪髮', description='設計師剪髮與造型')
        ]
        db.session.add_all(services)
        db.session.commit()
        print("✅ 初始服務資料已建立")

# -------------------- API 路由 --------------------

# 註冊 API
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data['name']
    email = data['email']
    password = generate_password_hash(data['password'])
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email 已經註冊過了"}), 409
    new_user = User(name=name, email=email, password=password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "註冊成功"})

# 登入 API
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data['email']
    password = data['password']
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password, password):
        return jsonify({"message": "登入成功", "user": {"name": user.name, "email": user.email}})
    else:
        return jsonify({"error": "帳號或密碼錯誤"}), 401

# 模擬 Chat API（用來解析自然語言，返回服務、日期、時間）
from datetime import datetime, timedelta
import re

@app.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.get_json()
    msg = data.get("message", "")

    services = ['剪髮', '美甲', '按摩']
    times_map = {
        '早上': '09:00',
        '中午': '12:00',
        '下午': '14:00',
        '晚上': '18:00'
    }

    weekdays = {
        '一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6
    }

    # 解析服務
    service = next((s for s in services if s in msg), None)

    # 解析時間
    time_key = next((key for key in times_map if key in msg), None)
    time = times_map.get(time_key, None)

    # 解析日期
    today = datetime.today()
    if "今天" in msg:
        date = today
    elif "明天" in msg:
        date = today + timedelta(days=1)
    elif "後天" in msg:
        date = today + timedelta(days=2)
    else:
        match = re.search(r'下週([一二三四五六日])', msg)
        if match:
            target_weekday = weekdays[match.group(1)]
            days_ahead = (7 - today.weekday() + target_weekday) % 7 + 7
            date = today + timedelta(days=days_ahead)
        else:
            date = None

    # 檢查欄位完整性
    if not all([service, time, date]):
        return jsonify({
            "error": "我不太確定您的預約內容，請再試一次，例如：明天下午剪髮"
        })

    return jsonify({
        "service": service,
        "time": time,
        "date": date.strftime('%Y-%m-%d')
    })


# 預約 API
@app.route('/api/book', methods=['POST'])
def make_booking():
    data = request.get_json()
    new_booking = Booking(
        user_email=data['email'],
        service_id=data['service_id'],
        date=data['date'],
        time=data['time']
    )
    db.session.add(new_booking)
    db.session.commit()
    return jsonify({"message": "預約成功"})

@app.route('/api/services', methods=['GET'])
def get_services():
    services = Service.query.all()
    return jsonify([{'id': s.id, 'name': s.name} for s in services])


# 查詢使用者預約紀錄
@app.route('/api/my-bookings', methods=['GET'])
def get_user_bookings():
    email = request.args.get('email')
    bookings = Booking.query.filter_by(user_email=email).all()
    results = []
    for b in bookings:
        results.append({
            'id': b.id,  # 加入 id 方便刪除
            'service': b.service.name,
            'date': b.date,
            'time': b.time
        })
    return jsonify(results)

# 查詢所有預約（後台管理用）
@app.route('/api/all-bookings', methods=['GET'])
def get_all_bookings():
    bookings = Booking.query.all()
    results = []
    for b in bookings:
        results.append({
            'id': b.id,
            'email': b.user_email,
            'service': b.service.name,
            'date': b.date,
            'time': b.time
        })
    return jsonify(results)

# 刪除預約 API
@app.route('/api/delete-booking', methods=['POST'])
def delete_booking():
    data = request.get_json()
    booking_id = data.get("booking_id")
    booking = Booking.query.get(booking_id)
    if booking:
        db.session.delete(booking)
        db.session.commit()
        return jsonify({"message": "預約已刪除"})
    else:
        return jsonify({"error": "找不到預約"}), 404

# -------------------- 管理員登入驗證 --------------------

# 管理員登入 API (簡單檢查硬編碼憑證)

# 假設 admin 帳號直接寫死（可後續改用資料庫）
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin123"

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    if data['email'] == ADMIN_EMAIL and data['password'] == ADMIN_PASSWORD:
        session['admin_logged_in'] = True  # ✅ 設定登入狀態
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "帳號或密碼錯誤"}), 401
# 管理員登入頁面（前端呈現）
@app.route('/admin_login.html')
def admin_login_page():
    return render_template('admin_login.html')

# 管理員後台頁面（受保護）
@app.route('/admin.html')
def admin_page():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login_page'))
    return render_template('admin.html')

@app.route('/debug/session')
def debug_session():
    return jsonify(dict(session))


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login_page'))

# -------------------- 普通頁面路由 --------------------

@app.route('/register.html')
def register_page():
    return render_template('register.html')

@app.route('/login.html')
def login_page():
    return render_template('login.html')

@app.route('/booking.html')
def booking_page():
    return render_template('booking.html')

@app.route('/my_bookings.html')
def my_bookings_page():
    return render_template('my_bookings.html')

@app.route('/chat.html')
def chat_page():
    return render_template('chat.html')

# -------------------- 啟動應用 --------------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Render 會提供 PORT 環境變數
    app.run(host="0.0.0.0", port=port, debug=True)
