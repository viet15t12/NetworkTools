# Cisco IOS — Mã giao thức định tuyến (Protocol Codes)

> Tham chiếu cho cột `protocol_code` và `protocol_name` trong bảng canonical
> `data/info_collected.db`, bảng `t08_info_routing_table` (hoặc database của
> workspace `.ntp` đang mở).
>
> Đây là bảng tra cứu cho collector/UI, không phải bằng chứng rằng parser hiện đã
> thu thập đủ mọi code bên dưới. Trong runtime hiện chưa có test parser
> `show ip route` bao phủ đầy đủ danh sách này.

---

## Kết nối trực tiếp

| Mã  | protocol_name | Ý nghĩa                                        | AD mặc định |
|-----|---------------|------------------------------------------------|-------------|
| `C` | connected     | Directly connected — interface đang UP/UP      | 0           |
| `L` | local         | Local — địa chỉ IP chính của interface (IOS 15+) | 0         |

---

## Static

| Mã   | protocol_name | Ý nghĩa                                              | AD mặc định |
|------|---------------|------------------------------------------------------|-------------|
| `S`  | static        | Static route — cấu hình tay bằng `ip route`         | 1           |
| `S*` | static        | Static default route (candidate default)             | 1           |

---

## Interior Gateway Protocols (IGP)

| Mã      | protocol_name | Ý nghĩa                                                              | AD mặc định |
|---------|---------------|----------------------------------------------------------------------|-------------|
| `R`     | rip           | RIP (Routing Information Protocol) — distance-vector                 | 120         |
| `D`     | eigrp         | EIGRP internal — Enhanced IGRP, Cisco proprietary                    | 90          |
| `D EX`  | eigrp         | EIGRP external — redistribute từ giao thức khác vào EIGRP           | 170         |
| `O`     | ospf          | OSPF intra-area — cùng area                                          | 110         |
| `O IA`  | ospf          | OSPF inter-area — qua ABR sang area khác                             | 110         |
| `O E1`  | ospf          | OSPF external type 1 — metric tích lũy qua domain                   | 110         |
| `O E2`  | ospf          | OSPF external type 2 — metric cố định (mặc định khi redistribute)   | 110         |
| `O N1`  | ospf          | OSPF NSSA external type 1                                            | 110         |
| `O N2`  | ospf          | OSPF NSSA external type 2                                            | 110         |
| `i`     | isis          | IS-IS — link-state, dùng nhiều trong ISP                             | 115         |

---

## Exterior Gateway Protocol (EGP)

| Mã  | protocol_name | Ý nghĩa                                         | AD mặc định |
|-----|---------------|-------------------------------------------------|-------------|
| `B` | bgp           | BGP — Border Gateway Protocol, giao thức Internet | 20 / 200  |

> **Lưu ý:** AD = 20 cho eBGP, AD = 200 cho iBGP.

---

## Multicast / Đặc biệt

| Mã  | protocol_name | Ý nghĩa                                                       | AD mặc định |
|-----|---------------|---------------------------------------------------------------|-------------|
| `M` | mobile        | Mobile — Mobile IP route                                      | 254         |
| `P` | periodic      | Periodic downloaded static route (DHCP on-demand)             | —           |
| `H` | nhrp          | NHRP — Next Hop Resolution Protocol (DMVPN)                   | 250         |
| `+` | —             | Replicated route (multicast)                                  | —           |

---

## Ký hiệu bổ sung (prefix, không phải giao thức)

| Ký hiệu | Ý nghĩa                                                                      |
|---------|------------------------------------------------------------------------------|
| `*`     | Best / candidate default — route được chọn (ECMP: xuất hiện nhiều lần)      |
| `>`     | Best path (BGP/EIGRP) — kết hợp với `*` thành `*>`                          |
| `via`   | Next-hop IP hoặc exit interface của route đó                                 |

---

## Ghi chú triển khai

- **`O E2`** là mặc định khi redistribute vào OSPF — metric không cộng dồn, chỉ lấy seed metric từ ASBR. Nếu thấy `O E1` tức là đã dùng `metric-type 1` tường minh.
- **`S*`** thường xuất hiện kèm dòng `Gateway of last resort is X.X.X.X to network 0.0.0.0`. Schema hiện không có `is_default_route`; có thể suy ra bằng `destination = '0.0.0.0'` và `prefix_length = 0`, hoặc bổ sung cột khi có migration.
- **`L` (Local)** chỉ có từ IOS 15+ — thiết bị cũ hơn sẽ không có dòng này, chỉ có `C`.
- **BGP AD = 20/200** — 20 cho eBGP (external), 200 cho iBGP (internal). Cân nhắc thêm cột `bgp_type` nếu cần phân biệt.
- `prefix_length` trong schema cho phép 0–128 để dùng chung IPv4/IPv6; collector phải xác minh destination và prefix theo address family thay vì chỉ tin `CHECK` hiện có.
