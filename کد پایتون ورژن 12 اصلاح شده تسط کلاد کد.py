# ============================================
# ربات روانشناس همراه - نسخه v12.0 (کامل)
# قابلیت‌ها:
#   - خودارزیابی افسردگی (PHQ-9)
#   - خودارزیابی اضطراب (GAD-7)
#   - خودارزیابی وسواس (Y-BOCS)
#   - ثبت حال روزانه با ذخیره در JSON
#   - گزارش هفتگی خودکار
#   - جملات انگیزشی تصادفی
#   - چالش ۷ روزه سلامت روان
#   - کمک فوری (اورژانس اجتماعی، مشاوره، اورژانس)
#   - ارسال نتایج و ثبت حال به کانال تلگرام
#   - دکمه‌های فارسی
# ============================================

import os
import sys
import json
import random
from datetime import datetime

from flask import Flask, request
import requests

app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    print("ERROR: لطفا متغیر محیطی BOT_TOKEN را تنظیم کنید.")
    sys.exit(1)

URL = f"https://api.telegram.org/bot{TOKEN}/"
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003288738296"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MOOD_FILE = os.environ.get("MOOD_FILE", os.path.join(BASE_DIR, "moods.json"))
SESSIONS_FILE = os.environ.get("SESSIONS_FILE", os.path.join(BASE_DIR, "sessions.json"))

QUOTES = [
    "🌸 هر روز فرصتی تازه برای رشد است.",
    "💪 تو قوی‌تر از چیزی هستی که فکر می‌کنی.",
    "🌱 کوچک‌ترین قدم‌ها هم تو را به جلو می‌برند.",
    "🕊️ آرامش، مقصد نیست، مسیر است.",
    "✨ امروز می‌تواند شروع یک تغییر بزرگ باشد.",
    "🌙 بعد از هر شب تاریک، طلوعی هست.",
    "🧠 مراقبت از ذهن، شجاعانه‌ترین کار دنیاست.",
]

CHALLENGE = [
    "✍️ ۳ چیز که بابتش شکرگزار هستی رو <b>بنویس</b> (می‌تونی همینجا تایپ کنی).",
    "🚶 ۱۰ دقیقه <b>پیاده‌روی</b> بدون گوشی. فقط به اطرافت نگاه کن.",
    "📱 به یه <b>دوست قدیمی</b> پیام بده و حالش رو بپرس.",
    "🫁 ۵ دقیقه <b>نفس عمیق</b> بکش (۴ ثانیه دم، ۴ ثانیه نگه دار، ۴ ثانیه بازدم).",
    "✅ یه <b>کار کوچیک</b> که عقب انداختی رو امروز انجام بده.",
    "🎵 یه <b>آهنگ بی‌کلام</b> گوش کن و ۵ دقیقه هیچ کاری نکن.",
    "🎁 امروز به خودت یه <b>جایزه کوچیک</b> بده. لیاقتش رو داری!",
]

CHALLENGE_TITLES = ["شکرگزاری", "پیاده‌روی", "ارتباط", "تنفس", "انجام کار", "آرامش", "خودتشویقی"]

Q = {
    "افسردگی": ["بی‌علاقگی", "احساس غم", "مشکل خواب", "خستگی", "تغییر اشتها", "احساس شکست", "عدم تمرکز", "کندی/بی‌قراری", "افکار خودکشی"],
    "اضطراب": ["احساس عصبی", "ناتوانی در کنترل نگرانی", "نگرانی زیاد", "مشکل آرامش", "بی‌قراری", "زودرنجی", "احساس ترس"],
    "وسواس": ["زمان افکار وسواسی", "اختلال(افکار)", "ناراحتی از افکار", "مقاومت(افکار)", "کنترل افکار", "زمان رفتارهای وسواسی", "اختلال(رفتارها)", "ناراحتی(منع)", "مقاومت(رفتار)", "کنترل رفتار"]
}

ANSWER_MAP = {"۰-هرگز": 0, "۱-چند روز": 1, "۲-بیشتر": 2, "۳-همیشه": 3}

sessions = {}
_seen_updates = set()


def send(cid, text, btns=None):
    try:
        d = {"chat_id": cid, "text": text, "parse_mode": "HTML"}
        if btns:
            d["reply_markup"] = {"keyboard": btns, "resize_keyboard": True}
        requests.post(URL + "sendMessage", json=d, timeout=5)
    except Exception:
        pass


def menu():
    return [
        [{"text": "😔 افسردگی"}, {"text": "😥 اضطراب"}, {"text": "🌀 وسواس"}],
        [{"text": "📊 ثبت حال"}, {"text": "📈 گزارش"}, {"text": "💬 انگیزشی"}],
        [{"text": "🎯 چالش ۷ روزه"}, {"text": "🆘 کمک فوری"}, {"text": "📞 تماس"}]
    ]


def challenge_btn(day):
    if day >= 7:
        return [[{"text": "🏆 پایان چالش"}, {"text": "🔙 بازگشت"}]]
    return [
        [{"text": f"✅ روز {day+1} انجام شد"}],
        [{"text": "🔙 بازگشت"}]
    ]


def ans():
    return [
        [{"text": "۰-هرگز"}, {"text": "۱-چند روز"}],
        [{"text": "۲-بیشتر"}, {"text": "۳-همیشه"}],
        [{"text": "🔙 بازگشت"}]
    ]


def mood():
    return [
        [{"text": "۱😞"}, {"text": "۲😔"}, {"text": "۳😐"}, {"text": "۴🙂"}, {"text": "۵😊"}],
        [{"text": "۶😃"}, {"text": "۷😄"}, {"text": "۸😍"}, {"text": "۹🤩"}, {"text": "۱۰🌟"}],
        [{"text": "🔙 بازگشت"}]
    ]


def result(t, total, mx):
    if t == "افسردگی":
        if total <= 4: return "🟢 کم", "خوبید"
        elif total <= 9: return "🟡 متوسط", "مراقبت بیشتر"
        elif total <= 14: return "🟠 قابل توجه", "مشاوره مفید است"
        elif total <= 19: return "🔴 زیاد", "به روانشناس مراجعه کنید"
        else: return "🔴 بسیار زیاد", "فوری اقدام کنید"
    elif t == "اضطراب":
        if total <= 4: return "🟢 کم", "طبیعی"
        elif total <= 9: return "🟡 متوسط", "تکنیک تنفس"
        elif total <= 14: return "🟠 قابل توجه", "مشاوره کنید"
        else: return "🔴 زیاد", "روانشناس مراجعه کنید"
    else:
        if total <= 7: return "🟢 کم", "طبیعی"
        elif total <= 15: return "🟡 متوسط", "پیگیری"
        elif total <= 23: return "🟠 قابل توجه", "مشاوره تخصصی"
        else: return "🔴 زیاد", "روانپزشک مراجعه کنید"


def num(txt):
    return ANSWER_MAP.get(txt)


def save_mood(chat_id, score):
    try:
        data = {}
        if os.path.exists(MOOD_FILE):
            with open(MOOD_FILE) as f:
                c = f.read().strip()
                if c:
                    data = json.loads(c)
        cid = str(chat_id)
        if cid not in data:
            data[cid] = []
        data[cid].append({"date": datetime.now().strftime("%Y-%m-%d"), "score": score})
        if len(data[cid]) > 30:
            data[cid] = data[cid][-30:]
        with open(MOOD_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def weekly(cid):
    try:
        if not os.path.exists(MOOD_FILE):
            return None
        with open(MOOD_FILE) as f:
            c = f.read().strip()
            if not c:
                return None
            data = json.loads(c)
        cid = str(cid)
        if cid not in data or len(data[cid]) < 1:
            return None
        recent = data[cid][-7:]
        em = {1: "🔴", 2: "🔴", 3: "🟠", 4: "🟠", 5: "🟡", 6: "🟡", 7: "🟢", 8: "🟢", 9: "🟢", 10: "🟢"}
        r = "📈 <b>گزارش هفتگی</b>\n━━━━━━━━\n"
        for e in recent:
            bar = "█" * e['score']
            r += f"{em.get(e['score'],'⚪')} {e['date']}: {e['score']}/۱۰ {bar}\n"
        avg = sum(e['score'] for e in recent) / len(recent)
        if avg >= 7: m = "🌟 عالی! ادامه بده"
        elif avg >= 5: m = "😊 خوبه، بهترم میشه"
        else: m = "💙 روزهای سخت می‌گذرن"
        r += f"━━━━━━━━\n💡 میانگین: {avg:.1f}/۱۰\n{m}"
        return r
    except Exception:
        return None


# state زنده روی دیسک ذخیره می‌شه تا با ری‌استارت پروسه (رایج روی هاست‌های رایگان) تست وسط راه گم نشه
def load_sessions():
    try:
        if os.path.exists(SESSIONS_FILE):
            with open(SESSIONS_FILE) as f:
                c = f.read().strip()
                if c:
                    return {int(k): v for k, v in json.loads(c).items()}
    except Exception:
        pass
    return {}


def save_sessions():
    try:
        with open(SESSIONS_FILE, "w") as f:
            json.dump({str(k): v for k, v in sessions.items()}, f, ensure_ascii=False)
    except Exception:
        pass


def set_session(cid, data):
    sessions[cid] = data
    save_sessions()


def clear_session(cid):
    sessions.pop(cid, None)
    save_sessions()


sessions = load_sessions()


@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        d = request.get_json()
        if not d or "message" not in d:
            return "OK", 200

        # جلوگیری از پردازش دوباره‌ی همون آپدیت وقتی تلگرام به‌خاطر کندی پاسخ، دوباره ارسال می‌کنه
        update_id = d.get("update_id")
        if update_id is not None:
            if update_id in _seen_updates:
                return "OK", 200
            _seen_updates.add(update_id)
            if len(_seen_updates) > 2000:
                _seen_updates.clear()

        cid = d["message"]["chat"]["id"]
        txt = d["message"].get("text", "")
        nm = d["message"]["chat"].get("first_name", "کاربر")
        un = d["message"]["chat"].get("username", "")

        if txt == "/start":
            clear_session(cid)
            q = random.choice(QUOTES)
            send(cid, f"🌟 سلام {nm}!\n💬 {q}\n\n🧠 خودارزیابی\n📊 ثبت حال\n📈 گزارش\n🎯 چالش ۷ روزه\n🆘 کمک فوری\n\n👇 انتخاب کنید:", menu())
            return "OK", 200

        # حالت چالش
        if cid in sessions and sessions[cid].get('m') == 'challenge':
            s = sessions[cid]
            if txt == "🔙 بازگشت":
                clear_session(cid)
                send(cid, "برگشتید. هر وقت خواستی ادامه بده.", menu())
                return "OK", 200
            if txt == "🏆 پایان چالش":
                clear_session(cid)
                send(cid, "🎉 <b>آفرین! چالش ۷ روزه رو کامل کردی!</b>\n\n💪 تو فوق‌العاده‌ای. حالا می‌تونی دوباره از اول شروع کنی.", menu())
                return "OK", 200
            if f"روز {s['day']+1}" in txt:
                s['day'] += 1
                if s['day'] >= 7:
                    send(cid, f"🎉 <b>تبریک! چالش ۷ روزه تمام شد!</b>\n\n🏆 تو ۷ روز برای خودت وقت گذاشتی. این یعنی خودت رو دوست داری.\n\n💙 آماده‌ای برای دور بعد؟ دوباره بزن 🎯 چالش ۷ روزه", menu())
                    clear_session(cid)
                    return "OK", 200
                save_sessions()
                send(cid, f"🌟 عالی! روز {s['day']} انجام شد.\n\n📅 <b>روز {s['day']+1} از ۷: {CHALLENGE_TITLES[s['day']]}</b>\n\n{CHALLENGE[s['day']]}", challenge_btn(s['day']))
                return "OK", 200
            send(cid, f"📅 <b>روز {s['day']+1} از ۷: {CHALLENGE_TITLES[s['day']]}</b>\n\n{CHALLENGE[s['day']]}\n\nوقتی انجامش دادی، دکمه زیر رو بزن:", challenge_btn(s['day']))
            return "OK", 200

        # حالت ثبت حال
        if cid in sessions and sessions[cid].get('m') == 'mood':
            if txt == "🔙 بازگشت":
                clear_session(cid)
                send(cid, "برگشتید.", menu())
                return "OK", 200
            if txt and txt[0].isdigit():
                s = int(txt[0])
                if 1 <= s <= 10:
                    save_mood(cid, s)
                    clear_session(cid)
                    e = "🟢" if s >= 7 else "🟡" if s >= 5 else "🟠" if s >= 3 else "🔴"
                    send(cid, f"{e} ثبت شد: {s}/۱۰", menu())
                    send(CHANNEL_ID, f"📊 {nm} - حال: {s}/۱۰ {e}")
                    w = weekly(cid)
                    if w:
                        send(cid, w, menu())
                    return "OK", 200
            send(cid, "۱ تا ۱۰ انتخاب کن.", mood())
            return "OK", 200

        # وسط تست
        if cid in sessions and sessions[cid].get('m') == 'test':
            s = sessions[cid]
            if txt == "🔙 بازگشت":
                clear_session(cid)
                send(cid, "برگشتید.", menu())
                return "OK", 200
            a = num(txt)
            if a is not None:
                s['a'].append(a)
                s['n'] += 1
                if s['n'] < s['t']:
                    save_sessions()
                    send(cid, f"سوال {s['n']+1} از {s['t']}\n\n{s['q'][s['n']]}", ans())
                    return "OK", 200
                total = sum(s['a'])
                mx = s['t'] * 3
                lvl, rec = result(s['type'], total, mx)
                send(cid, f"📊 {s['type']}\n━━━━\nنمره: {total}/{mx}\n{lvl}\n\n💡 {rec}\n\n⚠️ خودارزیابی تشخیص نیست.", menu())
                adm = f"📋 {s['type']} - {nm}"
                if un:
                    adm += f" (@{un})"
                adm += f"\nنمره: {total}/{mx} - {lvl}"
                send(CHANNEL_ID, adm)
                clear_session(cid)
                return "OK", 200
            send(cid, f"⚠️ به سوال {s['n']+1} جواب بده. یکی از دکمه‌های زیر رو انتخاب کن.", ans())
            return "OK", 200

        if txt in ["😔 افسردگی", "😥 اضطراب", "🌀 وسواس"]:
            mp = {"😔 افسردگی": "افسردگی", "😥 اضطراب": "اضطراب", "🌀 وسواس": "وسواس"}
            t = mp[txt]
            ql = Q[t]
            set_session(cid, {'m': 'test', 'type': t, 'q': ql, 't': len(ql), 'n': 0, 'a': []})
            send(cid, f"🧠 {t}\n━━━━\n📌 {len(ql)} سوال\n━━━━\n۰-هرگز ۱-چند روز ۲-بیشتر ۳-همیشه\n━━━━\nسوال ۱:\n\n{ql[0]}", ans())
            return "OK", 200

        if txt == "📊 ثبت حال":
            set_session(cid, {'m': 'mood'})
            send(cid, "🌟 حال امروز ۱ تا ۱۰؟\n👇 انتخاب کن:", mood())
            return "OK", 200

        if txt == "📈 گزارش":
            w = weekly(cid)
            if w:
                send(cid, w, menu())
            else:
                send(cid, "📈 هنوز کافی ثبت نکردی!\nهر روز حالت رو ثبت کن تا نمودار ببینی.", menu())
            return "OK", 200

        if txt == "💬 انگیزشی":
            send(cid, f"💬 {random.choice(QUOTES)}\n\n✨ روز خوبی داشته باشی!", menu())
            return "OK", 200

        if txt == "🎯 چالش ۷ روزه":
            set_session(cid, {'m': 'challenge', 'day': 0})
            send(cid, f"🎯 <b>چالش ۷ روزه سلامت روان</b>\n━━━━━━━━\nهر روز یه تمرین ساده برای حال خوب.\n\n📅 <b>روز ۱ از ۷: {CHALLENGE_TITLES[0]}</b>\n\n{CHALLENGE[0]}\n\nوقتی انجامش دادی، دکمه زیر رو بزن:", challenge_btn(0))
            return "OK", 200

        if txt == "🆘 کمک فوری":
            send(cid,
                 "🆘 <b>کمک فوری</b>\n━━━━━━━━\n"
                 "💙 تو تنها نیستی:\n\n"
                 "📲 اورژانس اجتماعی: <b>۱۲۳</b>\n"
                 "📲 مشاوره بهزیستی: <b>۱۴۸۰</b>\n"
                 "📲 اورژانس: <b>۱۱۵</b>\n\n"
                 "🫂 یه نفس عمیق بکش.",
                 menu())
            return "OK", 200

        if txt == "📞 تماس":
            send(cid, "📞 تماس\n\n🌐 ravandarman.com/doctor/90685-mohammad-mahdizadeh\n📢 @charkheshzehn", menu())
            return "OK", 200

        send(cid, "❌ نامعتبر. از منو استفاده کن.", menu())
        return "OK", 200
    except Exception as e:
        print(f"⚠️ خطا: {e}")
        return "OK", 200


@app.route('/')
def home():
    return "OK"


# برای ثبت وب‌هوک کافیه بعد از دیپلوی، همین آدرس رو یه بار توی مرورگر باز کنی
@app.route('/setwebhook')
def set_webhook_route():
    base = request.url_root.rstrip('/')
    r = requests.get(URL + "setWebhook", params={"url": f"{base}/webhook"}, timeout=10)
    return r.text, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
