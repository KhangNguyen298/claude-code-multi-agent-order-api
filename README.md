# Demo: Multi-agent với Claude Code (REST API quản lý đơn hàng)

## Bước 1: Chuẩn bị
1. Cài Python 3.11+ và VS Code.
2. Cài Claude Code (theo hướng dẫn chính thức của Anthropic), đăng nhập bằng tài khoản Claude trả phí.
3. Giải nén thư mục này, mở bằng VS Code (File > Open Folder).
4. Mở terminal trong VS Code:
   ```
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   source .venv/bin/activate     # macOS/Linux
   pip install -r requirements.txt
   ```

## Bước 2: Mở Claude Code
Trong terminal, tại thư mục project, gõ: `claude`
Gõ `/agents` để kiểm tra đã thấy đủ 4 agent: architect, database, backend, qa.

## Bước 3: Chạy demo từng bước (để khán giả thấy rõ việc chuyển giao)
```
@agent-architect Đọc docs/requirements.md và thiết kế API.
@agent-database Thiết kế database theo contract của architect.
@agent-backend Implement API theo contract.
@agent-qa Kiểm thử toàn bộ API.
```
Nếu qa báo lỗi:
```
@agent-backend Sửa các lỗi trong docs/qa-report.md
@agent-qa Chạy lại kiểm thử.
```

## Bước 3 (cách khác): Chạy tự động cả chuỗi bằng 1 câu
```
Làm theo pipeline trong CLAUDE.md: dùng lần lượt các subagent architect,
database, backend, qa để xây Order API từ docs/requirements.md.
Nếu qa báo lỗi thì giao lại cho backend sửa rồi chạy qa lại.
```

## Bước 4: Xem kết quả
- `uvicorn app.main:app --reload` rồi mở http://127.0.0.1:8000/docs để thử API.
- `pytest -q` để chạy test.
- Mở thư mục `docs/` để cho xem các file handoff mà các agent truyền cho nhau.
