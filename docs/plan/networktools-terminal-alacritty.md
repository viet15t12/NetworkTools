# Kế hoạch hoàn tất CAMS Terminal

Cập nhật: **2026-08-16**. CAMS manager, NTTP/1 server và source companion
Alacritty đã có trong repository. Tài liệu này chỉ giữ các gate còn mở; kiến trúc
đã quyết định nằm ở
[`../decisions/0001-external-networktools-terminal.md`](../decisions/0001-external-networktools-terminal.md).

## 1. Baseline đã có

- `features/terminal/`: UUID session, safe launch spec, QProcess lifecycle,
  NTTP/1 validation/server, focus/close/restart và crash cleanup.
- `vendor/alacritty/`: binary `cams-terminal`, managed `--nt-*` CLI,
  Unix NTTP/1 client/dispatcher và hold behavior.
- OpenSSH child cho thiết bị hiện đại; Paramiko PTY riêng cho Cisco IOS legacy,
  không truyền password qua argv/environment/IPC/log.
- `cams.sh terminal-build` và `terminal-check`; launcher tìm binary qua
  env/PATH/vendored release path.
- Fake/contract test cho protocol, permission, duplicate session, lifecycle và
  launcher.

## 2. Gate còn mở

| Gate | Kết quả cần có | Trạng thái |
| --- | --- | --- |
| Branding | Tên/icon/about/package metadata nhất quán, license upstream đầy đủ | In progress |
| Fedora Wayland | Open/focus/close/restart, clipboard, resize, IME và crash behavior | Pending lab |
| EVE-NG/Cisco | Modern OpenSSH và legacy Paramiko PTY trên thiết bị được cấp quyền | Pending lab |
| Packaging | Artifact reproducible, checksum, source/license notice và upgrade path | Planned |
| Windows transport | Local IPC tương đương permission/auth contract Unix | Planned |
| Compatibility cleanup | Xóa embedded terminal và qtpyTerminal sau acceptance | Blocked by gates above |

## 3. Ma trận nghiệm thu Linux

Chạy trên Fedora/Wayland với binary release:

1. host hợp lệ mở đúng một window; mở lại chỉ focus;
2. hai host tạo hai session UUID độc lập;
3. focus/close/title/ping/get-info dùng NTTP/1 và request ID;
4. SSH child exit giữ window đủ để đọc lỗi;
5. terminal crash dọn registry và cho phép restart;
6. app exit yêu cầu close, timeout rồi terminate/kill có giới hạn;
7. socket nằm dưới runtime dir user-owned, directory `0700`, endpoint `0600`;
8. message >64 KiB, unknown event/command/session và malformed JSON bị từ chối;
9. không xuất hiện password, terminal output hay arbitrary command trong IPC/log;
10. copy/paste, scrollback, resize, unicode/IME và keyboard hoạt động dưới Wayland.

## 4. Ma trận thiết bị

Ghi rõ model, OS/image, protocol và thuật toán cần override. Tối thiểu:

- Cisco IOS hiện đại dùng system OpenSSH;
- Cisco IOS legacy dùng Paramiko PTY mà không hạ crypto policy toàn hệ thống;
- auth failure, timeout, host-key mismatch và child exit có message đọc được;
- `Up (Dev)`, Telnet, host/user/port không an toàn và inventory thiếu đều
  fail-closed trước spawn.

Không đưa host thật hoặc credential vào ảnh/log/fixture công khai.

## 5. Packaging và cập nhật fork

- Ghi commit/tag upstream trong release metadata.
- Build từ clean checkout bằng Rust toolchain được pin/ghi phiên bản.
- Giữ Apache-2.0/MIT notice và công bố CAMS delta.
- Không đóng gói `target/`; phát hành binary/checksum riêng.
- Rebase upstream phải chạy Cargo test phù hợp, terminal contract Python và ma
  trận manual tối thiểu.

## 6. Điều kiện xóa compatibility code

Chỉ xóa `features/terminal/manager.py`, `window.py`, `worker.py`, `stream.py`,
`qtpyTerminal-main` và dependency liên quan khi:

1. Linux acceptance đạt và artifact cài đặt được phát hành;
2. không còn import/composition consumer;
3. test contract được chuyển sang companion path;
4. license/README/launcher được cập nhật trong cùng change;
5. rollback về bản companion trước có hướng dẫn.

## 7. Lệnh kiểm tra

```bash
./cams.sh terminal-build
./cams.sh terminal-check
uv run python -m unittest tests.unit.test_managed_terminal tests.test_launcher_contracts -v
```

Automated test không thay thế Wayland/device acceptance. Kết quả phải được ghi ở
release/PR evidence, không ghi số pass cố định vào tài liệu kế hoạch này.
