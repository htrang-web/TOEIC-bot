# TOEIC Daily Bot → Telegram

Bot tự động gửi 10 từ vựng mới mỗi ngày (chia đều 5 mốc giờ), kiểm tra từ vựng
theo yêu cầu, và mỗi ngày gửi 10 câu hỏi ngữ pháp vào giờ ngẫu nhiên — tất cả
qua Telegram, chạy trên GitHub Actions (máy bạn tắt vẫn hoạt động).

## Bot làm được gì
- **8h, 10h, 12h, 14h, 16h** (giờ VN): mỗi mốc gửi 2 từ vựng mới → đủ 10 từ/ngày.
- **`/check`**: bất kỳ lúc nào, gửi bài trắc nghiệm kiểm tra các từ đã học
  trong ngày *tính đến thời điểm gọi lệnh*.
- Mỗi ngày tự động gửi **10 câu hỏi ngữ pháp** (dạng Part 5 TOEIC) vào 1 giờ
  ngẫu nhiên trong khoảng 8h-23h.
- Trả lời bài kiểm tra (vocab hoặc ngữ pháp) bằng **1 tin nhắn duy nhất**,
  dạng: `A C B D A B C D A B` — bot chấm đúng/sai kèm đáp án + giải thích.
- **`/addword từ ; nghĩa ; câu ví dụ`** — tự thêm từ vựng mới vào kho.
- **`/addquiz câu hỏi ; A ; B ; C ; D ; đáp án đúng ; giải thích`** — tự thêm
  câu hỏi ngữ pháp mới.
- **`/help`** — xem lại danh sách lệnh.
- Bot kiểm tra tin nhắn mới mỗi ~15 phút, nên độ trễ phản hồi tối đa ~15 phút.
- Nếu có 2 bài kiểm tra đang chờ cùng lúc (vd `/check` rồi tới giờ quiz ngữ
  pháp), tin nhắn trả lời tiếp theo luôn được chấm cho bài **gửi trước**.
- Bài kiểm tra chưa trả lời sẽ **tự huỷ khi sang ngày mới**.

## ⚠️ Về nguồn nội dung
Từ vựng và câu hỏi ngữ pháp trong kho khởi tạo (`vocab_bank.json`,
`quiz_bank.json`) là nội dung **tự biên soạn**, bám sát chủ đề và định dạng
TOEIC thực tế (Part 5: chọn từ đúng điền vào câu), **không sao chép** từ đề
thi hay tài liệu có bản quyền nào — vì việc đó vi phạm bản quyền của ETS/đơn
vị sở hữu nội dung. Kho khởi tạo có **60 từ vựng + 59 câu hỏi ngữ pháp** (đủ
dùng khoảng 6 ngày trước khi lặp lại); bạn có thể mở rộng thêm bất cứ lúc nào
qua lệnh `/addword` / `/addquiz`, hoặc sửa trực tiếp 2 file JSON này trên
GitHub.

---

## Bước 1 — Tạo Telegram Bot (bỏ qua nếu đã có sẵn từ dự án trước)
1. Chat với **@BotFather** trên Telegram → `/newbot` → lấy **token**.
2. Chat với **@userinfobot** → lấy **chat_id** (dòng `Id: ...`).
3. Nhớ bấm **Start** trên bot bạn vừa tạo.

*(Bạn có thể dùng lại bot Telegram cũ từng tạo cho dự án Shopee, hoặc tạo bot mới riêng cho việc học TOEIC — tuỳ bạn.)*

## Bước 2 — Tạo repo GitHub mới, upload file
1. Tạo repo mới trên GitHub (Private tuỳ chọn).
2. Upload toàn bộ file trong bộ này, **giữ đúng cấu trúc thư mục**:
   ```
   .github/workflows/daily.yml
   toeic_bot.py
   vocab_bank.json
   quiz_bank.json
   state.json
   requirements.txt
   README.md
   ```
   Lưu ý giống lần trước: khi tạo file `daily.yml`, phải gõ **đầy đủ đường
   dẫn** `.github/workflows/daily.yml` vào ô tên file, không chỉ `daily.yml`.

## Bước 3 — Khai báo Secrets
Settings → Secrets and variables → Actions → New repository secret:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Bước 4 — Bật và chạy thử
Tab **Actions** → chọn workflow **"TOEIC Daily Bot"** → **Run workflow**.
Sau khi chạy thành công (✓ xanh), nếu đang trong khung 8h-16h (giờ VN) và
đã qua mốc giờ gần nhất, bạn sẽ nhận được 2 từ vựng đầu tiên ngay.

---

## Cách dùng hàng ngày
- Cứ để bot tự chạy theo lịch (~15 phút/lần) — không cần làm gì thêm.
- Muốn kiểm tra ngay: nhắn `/check` cho bot, đợi tối đa ~15 phút để nhận câu hỏi.
- Trả lời bằng 1 tin nhắn, ví dụ: `A C B D`
- Muốn thêm từ/câu hỏi: dùng `/addword` hoặc `/addquiz` theo đúng cú pháp ở trên.

## Cấu trúc file
| File | Vai trò |
|---|---|
| `toeic_bot.py` | Script chính: gửi từ vựng/quiz, xử lý lệnh, chấm bài |
| `vocab_bank.json` | Kho từ vựng (có thể mở rộng qua `/addword` hoặc sửa trực tiếp) |
| `quiz_bank.json` | Kho câu hỏi ngữ pháp (mở rộng qua `/addquiz` hoặc sửa trực tiếp) |
| `state.json` | Bot tự lưu: tiến trình trong ngày, offset Telegram, bài đang chờ chấm |
| `.github/workflows/daily.yml` | Lịch chạy tự động mỗi 15 phút |

## Chạy thử local (tuỳ chọn, để debug)
```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="xxxx"
export TELEGRAM_CHAT_ID="xxxx"
python toeic_bot.py --state state.json --vocab-bank vocab_bank.json --quiz-bank quiz_bank.json
```
