# Order API: xây dựng bởi một team 4 agent Claude Code

REST API quản lý đơn hàng (FastAPI + SQLAlchemy + SQLite) được **4 subagent Claude Code** xây dựng nối tiếp nhau.
Mỗi agent có một vai trò, một bộ quyền hạn riêng và bàn giao công việc cho agent sau **qua file**, giống một nhóm phát triển thật.

> Điểm đáng xem ở repo này không chỉ là API, mà là **cách tổ chức đội agent**: xem `.claude/agents/`, `CLAUDE.md` và `docs/`.

**Kết quả:** 150 test tự động pass. QA đã tìm ra 3 bug thật qua 3 vòng kiểm tra, backend sửa, QA kiểm tra lại (xem [`docs/qa-report.md`](docs/qa-report.md)).

---

## Pipeline

```
docs/requirements.md   (đề bài do con người viết)
        │
        ▼
  ┌─────────────┐   docs/architecture.md, docs/api-contract.yaml
  │  architect  │   Thiết kế kiến trúc và "hợp đồng" API. Không viết code.
  └──────┬──────┘
         ▼
  ┌─────────────┐   docs/data-model.md, app/models, app/db
  │  database   │   Thiết kế bảng, viết lớp dữ liệu. Không viết API.
  └──────┬──────┘
         ▼
  ┌─────────────┐   app/schemas, app/services, app/api, app/main.py
  │   backend   │   Cài đặt API đúng hợp đồng. Không sửa model, không viết test.
  └──────┬──────┘
         ▼
  ┌─────────────┐   tests/, docs/qa-report.md
  │     qa      │   Viết test, soi lỗi và bảo mật. Không được sửa code trong app/.
  └──────┬──────┘
         │  có bug?  ──►  quay lại backend sửa, rồi qa chạy lại (tối đa 2 lần)
         ▼
   ALL CHECKS PASSED
```

### Nguyên tắc thiết kế đội agent
- **Quyền hạn tối thiểu.** Mỗi agent chỉ có đúng công cụ nó cần (dòng `tools:` trong `.claude/agents/*.md`). Ví dụ `qa` không có công cụ sửa file, nên không thể "tự sửa cho test pass".
- **Bàn giao bằng file, không bằng trí nhớ.** Agent không thấy cuộc trò chuyện của nhau. Mỗi agent đọc file của agent trước và ghi `docs/handoff-<agent>.md` khi xong.
- **Một "hợp đồng" chung.** `docs/api-contract.yaml` là chuẩn mà mọi agent phải tuân theo.
- **Người làm và người kiểm tra tách riêng.** Tester chỉ báo lỗi, không được sửa.

| Agent | File định nghĩa | Đầu ra chính |
|---|---|---|
| architect | [`.claude/agents/architect.md`](.claude/agents/architect.md) | `docs/architecture.md`, `docs/api-contract.yaml` |
| database | [`.claude/agents/database.md`](.claude/agents/database.md) | `docs/data-model.md`, `app/models`, `app/db` |
| backend | [`.claude/agents/backend.md`](.claude/agents/backend.md) | `app/schemas`, `app/services`, `app/api` |
| qa | [`.claude/agents/qa.md`](.claude/agents/qa.md) | `tests/`, `docs/qa-report.md` |

---

## Kết quả QA qua 3 vòng

| Vòng | Kết quả | Chuyện gì xảy ra |
|---|---|---|
| 1 | 125 pass, 3 fail | QA tìm ra BUG-1 (số quá lớn gây lỗi 500) và BUG-2 (tổng đơn hàng bị tràn gây lỗi 500). |
| 2 | 148 pass | Backend sửa hai bug. QA kiểm tra lại, rồi phát hiện thêm BUG-3 do chính bản sửa gây ra: mọi lỗi DB đều bị báo nhầm là "hết hàng". |
| 3 | **150 pass** | Backend sửa BUG-3. QA xác nhận không còn bug mở. |

---

## API

Chạy server rồi mở **http://127.0.0.1:8000/docs** để thử trực tiếp bằng Swagger.

| Phương thức | Đường dẫn | Chức năng |
|---|---|---|
| POST / GET | `/products` | Tạo / liệt kê sản phẩm |
| GET / PUT / DELETE | `/products/{id}` | Xem / sửa / xóa sản phẩm |
| POST | `/customers` | Tạo khách hàng (email duy nhất) |
| GET | `/customers/{id}` | Xem khách hàng |
| POST / GET | `/orders` | Tạo đơn / liệt kê đơn (lọc theo `status`, `customer_id`, có phân trang) |
| GET | `/orders/{id}` | Xem đơn hàng |
| PATCH | `/orders/{id}/status` | Đổi trạng thái đơn |

### Quy tắc nghiệp vụ
- Tổng tiền do **server tính**, client không được gửi lên.
- Tạo đơn trừ kho; **hủy đơn (khi PENDING hoặc PAID) hoàn lại kho**.
- Đơn lưu **giá tại thời điểm mua**, sửa giá sản phẩm sau đó không làm đổi đơn cũ.
- Trạng thái chỉ chuyển theo: `PENDING → PAID → SHIPPED → DELIVERED`, và `PENDING/PAID → CANCELLED`. Các kiểu chuyển khác bị từ chối (409).
- Mọi lỗi dùng một định dạng: `{"error": {"code": "...", "message": "..."}}`.

---

## Cấu trúc code (phân tầng)

Gọi từ trên xuống dưới: **API → Service → Repository → DB**.

```
app/
  api/            Router: chỉ nhận request và trả kết quả
  services/       Luật nghiệp vụ, quản lý transaction
  repositories/   Các câu truy vấn DB
  models/         Cấu trúc bảng (SQLAlchemy)
  schemas/        Kiểm tra dữ liệu vào/ra (Pydantic)
  db/             Kết nối DB, dữ liệu mẫu
  core/errors.py  Các loại lỗi
  main.py         Gắn router, gom mọi lỗi về một định dạng
tests/            150 test (pytest)
docs/             Tài liệu và file bàn giao giữa các agent
.claude/agents/   Định nghĩa 4 agent
```

Chi tiết: [`docs/architecture.md`](docs/architecture.md), [`docs/data-model.md`](docs/data-model.md), [`docs/api-contract.yaml`](docs/api-contract.yaml).

---

## Chạy dự án

Yêu cầu: Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS/Linux
pip install -r requirements.txt

python -m app.db.seed           # (tùy chọn) nạp dữ liệu mẫu
uvicorn app.main:app --reload   # chạy server
pytest -q                       # chạy test
```

---

## Tự chạy lại pipeline agent

Yêu cầu: [Claude Code](https://claude.com/claude-code) và một tài khoản Claude trả phí.
Xóa `app/`, `tests/` và các file trong `docs/` (chỉ giữ `docs/requirements.md`), mở `claude` trong thư mục dự án, gõ `/agents` để kiểm tra đủ 4 agent, rồi chạy từng bước:

```
@agent-architect Đọc docs/requirements.md và thiết kế API.
@agent-database Thiết kế database theo contract của architect.
@agent-backend Implement API theo contract.
@agent-qa Kiểm thử toàn bộ API.
```

Nếu `qa` báo lỗi:

```
@agent-backend Sửa các lỗi trong docs/qa-report.md
@agent-qa Chạy lại kiểm thử.
```

Hoặc chạy cả chuỗi bằng một câu:

```
Làm theo pipeline trong CLAUDE.md: dùng lần lượt các subagent architect,
database, backend, qa để xây Order API từ docs/requirements.md.
Nếu qa báo lỗi thì giao lại cho backend sửa rồi chạy qa lại.
```

> Kết quả mỗi lần chạy có thể khác nhau (số bug, cách đặt tên...).

---

## Giới hạn đã biết

Đây là dự án demo, chưa dành cho môi trường thật:
- Chưa có xác thực (authentication): ai gọi API cũng xem được dữ liệu.
- Dùng SQLite: không phù hợp khi nhiều người ghi cùng lúc.
- Email phân biệt hoa thường (`A@x.com` và `a@x.com` là hai tài khoản).
- `docs/api-contract.yaml` chưa ghi các giới hạn bổ sung sau khi sửa bug (tối đa 100 item mỗi đơn, trần tổng tiền, cận số nguyên).
