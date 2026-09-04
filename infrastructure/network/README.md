# Network infrastructure

Cập nhật: **2026-08-16**.

`running_config_collector.py` owns Cisco running-config collection. It keeps the
current privileged prompt instead of forcing configuration mode, disables paging,
buffers channel chunks, and completes only when that exact prompt returns; partial
output is never returned. After the full output reaches the application host, it
locally removes repeated trailing prompts such as `R2(config)#^@` before the
snapshot can be stored, while preserving Cisco config lines `!` and `end`. The
device receives an unfiltered `show running-config`.

Nơi đặt connector, registry session, bounded batch executor, ping adapter và
command runner dùng chung. Connector phải che giấu thư viện transport.

`DeviceSessionRegistry` là owner duy nhất của session theo host. Mỗi
`SessionEntry` giữ state, generation, thời điểm sử dụng và `operation_lock`;
`execute()` tuần tự hóa mọi thao tác trên cùng CLI channel nhưng các host khác
vẫn chạy song song. Session đóng khi Disconnect, app shutdown hoặc lifecycle
thiết bị yêu cầu; đóng/chuyển tab không đóng session.

Terminal companion hiện mở SSH child riêng và không dùng registry automation.
`features/terminal/worker.py` chỉ thuộc compatibility embedded terminal; nếu
compatibility path được dùng trong test/adapter, nó phải giữ khóa registry trong
toàn bộ phiên để input không xen vào push cùng host.
Registry trả warning trước khi tạo connector cho host ở development mode hoặc protocol
không hỗ trợ, và chỉ gọi operation sau khi xác nhận connector còn sống.

`BatchExecutor` giới hạn mặc định 5 worker, cô lập exception theo host và chỉ
cancel tác vụ chưa bắt đầu tại safe boundary. Không log password/private key;
lỗi trả về dạng có cấu trúc. Worker feature không tạo cache session riêng.

`DeviceConnector.collect_running_config()` chỉ thu thập output; feature `config_backup` quyết định path, ghi file và commit. `save_running_config()` là adapter tương thích cho interactive CLI cũ.
