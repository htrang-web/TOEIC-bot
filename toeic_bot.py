#!/usr/bin/env python3
"""
TOEIC Daily Bot -> Telegram
----------------------------
- Mỗi ngày gửi 10 từ vựng mới, chia đều 2 từ/lần vào các mốc 8h-10h-12h-14h-16h (giờ VN).
- Lệnh /check bất kỳ lúc nào: gửi bài kiểm tra trắc nghiệm cho các từ đã học TRONG NGÀY tính đến thời điểm gọi lệnh.
- Mỗi ngày tự động gửi 10 câu hỏi ngữ pháp vào 1 giờ ngẫu nhiên trong khoảng 8h-23h.
- Trả lời bài kiểm tra (vocab hoặc ngữ pháp) bằng 1 tin nhắn dạng: A C B D A B C D A B
- Lệnh /addword và /addquiz để tự bổ sung dữ liệu qua Telegram.

Biến môi trường bắt buộc:
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
"""

import argparse
import json
import os
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

VN_TZ = timezone(timedelta(hours=7))
VOCAB_SLOTS = [8, 10, 12, 14, 16]   # giờ VN, mỗi mốc gửi 2 từ
GRAMMAR_WINDOW_START = 8 * 60        # phút, tính từ 0h
GRAMMAR_WINDOW_END = 23 * 60
LETTERS = ["A", "B", "C", "D"]


# ---------- Tiện ích chung ----------

def load_json(path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def now_vn():
    return datetime.now(VN_TZ)


def today_str():
    return now_vn().strftime("%Y-%m-%d")


# ---------- Telegram ----------

def tg_api(token, method):
    return f"https://api.telegram.org/bot{token}/{method}"


def send_telegram(token, chat_id, text):
    resp = requests.post(
        tg_api(token, "sendMessage"),
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"[ERROR] Gửi Telegram lỗi: {resp.status_code} {resp.text}", file=sys.stderr)


def get_updates(token, offset):
    resp = requests.get(
        tg_api(token, "getUpdates"),
        params={"offset": offset, "timeout": 0},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("result", [])


# ---------- Sinh ngày mới ----------

def pick_grammar_time():
    total_min = random.randint(GRAMMAR_WINDOW_START, GRAMMAR_WINDOW_END)
    total_min = round(total_min / 15) * 15  # làm tròn theo mốc 15 phút
    h, m = divmod(total_min, 60)
    return f"{h:02d}:{m:02d}"


def reset_day_if_needed(state, vocab_bank, quiz_bank):
    today = today_str()
    if state.get("current_day") == today:
        return False  # không cần reset

    n_vocab = len(vocab_bank)
    cursor = state.get("vocab_cursor", 0) % max(n_vocab, 1)
    today_words = []
    if n_vocab > 0:
        for i in range(10):
            idx = (cursor + i) % n_vocab
            w = vocab_bank[idx]
            today_words.append({"index": idx, "word": w["word"], "meaning": w["meaning"], "example": w["example"]})
        state["vocab_cursor"] = (cursor + 10) % n_vocab

    n_quiz = len(quiz_bank)
    k = min(10, n_quiz)
    grammar_indices = random.sample(range(n_quiz), k) if n_quiz > 0 else []

    state["current_day"] = today
    state["today"] = {
        "vocab_words": today_words,
        "vocab_slots_sent": [],
        "grammar_send_time": pick_grammar_time(),
        "grammar_sent": False,
        "grammar_quiz_indices": grammar_indices,
    }
    state["pending_quizzes"] = []  # bỏ lỡ bài kiểm tra chưa hoàn thành hôm qua
    return True


# ---------- Gửi từ vựng theo khung giờ ----------

def maybe_send_vocab_slots(state, token, chat_id):
    today = state["today"]
    words = today.get("vocab_words", [])
    if not words:
        return

    now = now_vn()
    sent_slots = set(today.get("vocab_slots_sent", []))

    for i, slot_hour in enumerate(VOCAB_SLOTS):
        if slot_hour in sent_slots:
            continue
        slot_time_today = now.replace(hour=slot_hour, minute=0, second=0, microsecond=0)
        if now < slot_time_today:
            continue  # chưa tới giờ

        pair = words[i * 2: i * 2 + 2]
        if not pair:
            continue

        lines = [f"📚 2 từ mới (đợt {slot_hour}h):\n"]
        for j, w in enumerate(pair, start=1):
            lines.append(f"{j}. {w['word']} — {w['meaning']}\n   Ví dụ: {w['example']}")
        send_telegram(token, chat_id, "\n".join(lines))

        sent_slots.add(slot_hour)
        today["vocab_slots_sent"] = sorted(sent_slots)


# ---------- Gửi quiz ngữ pháp ngẫu nhiên trong ngày ----------

def maybe_send_grammar_quiz(state, quiz_bank, token, chat_id):
    today = state["today"]
    if today.get("grammar_sent"):
        return
    send_time = today.get("grammar_send_time")
    if not send_time:
        return

    now = now_vn()
    h, m = map(int, send_time.split(":"))
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if now < target:
        return

    indices = today.get("grammar_quiz_indices", [])
    if not indices:
        today["grammar_sent"] = True
        return

    items = []
    lines = ["📝 10 câu hỏi ngữ pháp hôm nay!\n"
             "Trả lời bằng 1 tin nhắn duy nhất, cách nhau bởi dấu cách. Ví dụ:\nA C B D A B C D A B\n"]
    for i, qi in enumerate(indices, start=1):
        q = quiz_bank[qi]
        correct_letter = LETTERS[q["answer_index"]]
        items.append({
            "correct_letter": correct_letter,
            "question": q["question"],
            "choices": q["choices"],
            "explanation": q["explanation"],
        })
        opts = "  ".join(f"{LETTERS[k]}. {c}" for k, c in enumerate(q["choices"]))
        lines.append(f"{i}. {q['question']}\n   {opts}")

    send_telegram(token, chat_id, "\n".join(lines))

    state.setdefault("pending_quizzes", []).append({
        "type": "grammar",
        "created_at": now.isoformat(),
        "count": len(items),
        "items": items,
    })
    today["grammar_sent"] = True


# ---------- Lệnh /check: tạo quiz kiểm tra từ vựng đã học hôm nay ----------

def build_vocab_check(state, vocab_bank):
    today = state["today"]
    now = now_vn()
    sent_slots = today.get("vocab_slots_sent", [])
    n_words_available = len(sent_slots) * 2  # mỗi mốc giờ đã gửi tương ứng 2 từ
    words = today.get("vocab_words", [])[:n_words_available]

    if not words:
        return None, "Chưa có từ vựng nào được gửi hôm nay, hãy chờ tới 8h nhé."

    all_indices = set(range(len(vocab_bank)))
    items = []
    lines = [f"📖 Kiểm tra {len(words)} từ vựng đã học hôm nay!\n"
             "Trả lời bằng 1 tin nhắn duy nhất, cách nhau bởi dấu cách. Ví dụ:\nA C B D...\n"]

    for i, w in enumerate(words, start=1):
        target_idx = w["index"]
        distractor_pool = list(all_indices - {target_idx})
        distractor_idx = random.sample(distractor_pool, min(3, len(distractor_pool)))
        choice_words = [vocab_bank[j]["word"] for j in distractor_idx] + [w["word"]]
        random.shuffle(choice_words)
        correct_letter = LETTERS[choice_words.index(w["word"])]

        items.append({
            "correct_letter": correct_letter,
            "word": w["word"],
            "meaning": w["meaning"],
            "choices": choice_words,
        })
        opts = "  ".join(f"{LETTERS[k]}. {c}" for k, c in enumerate(choice_words))
        lines.append(f"{i}. Từ nào có nghĩa là: \"{w['meaning']}\"?\n   {opts}")

    quiz = {
        "type": "vocab_check",
        "created_at": now.isoformat(),
        "count": len(items),
        "items": items,
    }
    return quiz, "\n".join(lines)


# ---------- Chấm bài ----------

def grade_pending_quiz(quiz, answer_text):
    tokens = re.findall(r"[A-Da-d]", answer_text)
    letters = [t.upper() for t in tokens]

    if len(letters) != quiz["count"]:
        return None  # không khớp số lượng, sẽ báo lỗi ở nơi gọi

    correct_count = 0
    lines = ["📊 Kết quả:\n"]
    for i, (item, given) in enumerate(zip(quiz["items"], letters), start=1):
        is_correct = given == item["correct_letter"]
        if is_correct:
            correct_count += 1
            mark = "✅"
        else:
            mark = "❌"

        if quiz["type"] == "grammar":
            detail = f"đáp án đúng: {item['correct_letter']} — {item['explanation']}"
        else:  # vocab_check
            detail = f"đáp án đúng: {item['correct_letter']} ({item['word']} = {item['meaning']})"

        if is_correct:
            lines.append(f"{i}. {mark} Đúng")
        else:
            lines.append(f"{i}. {mark} Bạn chọn {given}, {detail}")

    lines.append(f"\nĐiểm: {correct_count}/{quiz['count']}")
    return "\n".join(lines)


# ---------- Xử lý lệnh Telegram ----------

def process_commands(token, owner_chat_id, state, vocab_bank, quiz_bank):
    updates = get_updates(token, state.get("telegram_offset", 0))
    bank_changed = False

    for update in updates:
        state["telegram_offset"] = update["update_id"] + 1
        msg = update.get("message") or update.get("channel_post")
        if not msg:
            continue

        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = (msg.get("text") or "").strip()

        if chat_id != str(owner_chat_id):
            print(f"[INFO] Bỏ qua tin nhắn từ chat_id lạ: {chat_id}")
            continue
        if not text:
            continue

        if text.startswith("/check"):
            quiz, message = build_vocab_check(state, vocab_bank)
            send_telegram(token, owner_chat_id, message)
            if quiz:
                state.setdefault("pending_quizzes", []).append(quiz)

        elif text.startswith("/addword"):
            body = text[len("/addword"):].strip()
            parts = [p.strip() for p in body.split(";")]
            if len(parts) != 3 or not all(parts):
                send_telegram(
                    token, owner_chat_id,
                    "Cú pháp: /addword từ ; nghĩa ; câu ví dụ"
                )
                continue
            word, meaning, example = parts
            vocab_bank.append({"word": word, "meaning": meaning, "example": example})
            bank_changed = True
            send_telegram(token, owner_chat_id, f"✅ Đã thêm từ vựng: {word} — {meaning}")

        elif text.startswith("/addquiz"):
            body = text[len("/addquiz"):].strip()
            parts = [p.strip() for p in body.split(";")]
            if len(parts) != 7 or not all(parts):
                send_telegram(
                    token, owner_chat_id,
                    "Cú pháp: /addquiz câu hỏi ; đáp án A ; đáp án B ; đáp án C ; đáp án D ; "
                    "đáp án đúng (A/B/C/D) ; giải thích"
                )
                continue
            question, a, b, c, d, correct, explanation = parts
            correct = correct.upper()
            if correct not in LETTERS:
                send_telegram(token, owner_chat_id, "Đáp án đúng phải là A, B, C hoặc D.")
                continue
            quiz_bank.append({
                "question": question,
                "choices": [a, b, c, d],
                "answer_index": LETTERS.index(correct),
                "explanation": explanation,
            })
            bank_changed = True
            send_telegram(token, owner_chat_id, f"✅ Đã thêm câu hỏi ngữ pháp mới.")

        elif text.startswith("/help"):
            send_telegram(
                token, owner_chat_id,
                "📌 Các lệnh:\n"
                "/check — kiểm tra các từ đã học hôm nay\n"
                "/addword từ ; nghĩa ; câu ví dụ — thêm từ vựng mới\n"
                "/addquiz câu hỏi ; A ; B ; C ; D ; đáp án đúng ; giải thích — thêm câu hỏi ngữ pháp\n"
                "Trả lời bài kiểm tra bằng 1 tin nhắn dạng: A C B D..."
            )

        elif text.startswith("/"):
            send_telegram(token, owner_chat_id, "Lệnh không hợp lệ. Gõ /help để xem danh sách lệnh.")

        else:
            # Không phải lệnh -> coi như câu trả lời cho bài kiểm tra đang chờ lâu nhất
            pending = state.get("pending_quizzes", [])
            if not pending:
                send_telegram(token, owner_chat_id, "Hiện không có bài kiểm tra nào đang chờ trả lời.")
                continue

            quiz = pending[0]
            result_text = grade_pending_quiz(quiz, text)
            if result_text is None:
                send_telegram(
                    token, owner_chat_id,
                    f"Số đáp án chưa khớp — bài này có {quiz['count']} câu, "
                    f"hãy gửi đúng {quiz['count']} chữ cái cách nhau bởi dấu cách."
                )
                continue

            send_telegram(token, owner_chat_id, result_text)
            pending.pop(0)
            state["pending_quizzes"] = pending

    return bank_changed


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="state.json")
    parser.add_argument("--vocab-bank", default="vocab_bank.json")
    parser.add_argument("--quiz-bank", default="quiz_bank.json")
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    owner_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not owner_chat_id:
        print("[FATAL] Thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID.", file=sys.stderr)
        sys.exit(1)

    state = load_json(args.state, {
        "telegram_offset": 0,
        "current_day": None,
        "vocab_cursor": 0,
        "today": {"vocab_words": [], "vocab_slots_sent": [], "grammar_send_time": None,
                   "grammar_sent": False, "grammar_quiz_indices": []},
        "pending_quizzes": [],
    })
    vocab_bank = load_json(args.vocab_bank, [])
    quiz_bank = load_json(args.quiz_bank, [])

    is_new_day = reset_day_if_needed(state, vocab_bank, quiz_bank)
    if is_new_day:
        print(f"[INFO] Ngày mới ({state['current_day']}) — đã chọn 10 từ vựng + 10 câu hỏi ngữ pháp, "
              f"giờ gửi ngữ pháp: {state['today']['grammar_send_time']}")

    bank_changed = process_commands(token, owner_chat_id, state, vocab_bank, quiz_bank)

    maybe_send_vocab_slots(state, token, owner_chat_id)
    maybe_send_grammar_quiz(state, quiz_bank, token, owner_chat_id)

    save_json(args.state, state)
    if bank_changed:
        save_json(args.vocab_bank, vocab_bank)
        save_json(args.quiz_bank, quiz_bank)

    print("[DONE] Hoàn tất lượt chạy.")


if __name__ == "__main__":
    main()
