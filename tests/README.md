# Tests

Cập nhật: **2026-08-16**. Chạy từ root repository:

```bash
uv run python -m unittest discover -s tests -v
```

`unit/` dành cho validation/repository nhỏ, `integration/` dùng SQLite tạm,
`syslog/` gom test chuyên đề và `qml/` chứa harness. Nhiều integration test hiện
nằm trực tiếp dưới `tests/`. Test không được mở kết nối thiết bị thật; dev mode
phải dùng fake/session giả.

Config backup có unit test repository Dulwich trong `tests/unit/` và integration test migration trong `tests/integration/`; toàn bộ dùng thư mục tạm.

`test_core_refactor_contracts.py` khóa các ranh giới refactor: import tương thích vẫn hoạt động, terminal không phụ thuộc `DatabaseManager`, và chỉ có một implementation `DeviceSessionRegistry`. `scripts/validate_structure.py` cũng giới hạn `runtime.py` ở dạng shim ngắn để monolith không quay lại.

Các regression test cho sidebar/session nhiều thiết bị:

- `test_device_selection_contracts.py`: action dùng host, context target là
  snapshot và đóng tab không đóng session.
- `test_session_registry_concurrency.py`: cùng host được serialize, host khác
  được chạy overlap và session vẫn sống sau operation.
- `test_multi_device_batch.py`: deduplicate, giới hạn concurrency và partial
  failure không dừng cả batch.
- `test_terminal_multi_host.py`: contract tương thích của API nhiều host cũ.
- `unit/test_internal_terminal.py`: stream normalization, policy preflight,
  registry-owned interactive worker và Pyte screen.
- `unit/test_qtpy_terminal_adapter.py`: external transport vendored
  `qtpyTerminal-main`, cursor, dirty render, Tab/navigation và clear không fork
  local process.
- `unit/test_managed_terminal.py`: contract terminal ngoài app, UUID registry,
  OpenSSH argv không chứa secret, QProcess lifecycle, NTTP/1 framing/limits,
  socket permission, duplicate focus và crash cleanup. Hai test socket cần môi
  trường cho phép tạo Unix domain socket.

Hai test internal-terminal ở trên bảo vệ compatibility code trong thời gian di
chuyển; composition root không còn khởi tạo widget/Netmiko interactive worker.
