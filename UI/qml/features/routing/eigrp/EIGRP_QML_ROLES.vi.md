# Vai tro cac file QML EIGRP

Da doi chieu: **2026-08-16**. Tai lieu tom tat cac component trong
`UI/qml/features/routing/eigrp`; hanh vi backend nam trong README feature va tai
lieu schema.

## `EigrpRoutingForm.qml`

Component dieu phoi chinh cho man hinh EIGRP.

- Quan ly state tong: host hien tai, loading/saving, dirty state, section dang active.
- Load/save du lieu EIGRP thong qua `dbManager`.
- Giu `processModel` va cac ham thao tac tren process dang chon.
- Dieu phoi cac section con bang cach truyen `form: eigrpRoutingForm`.
- Render danh sach `EigrpProcessCard` trong tab `Process`.

## `EigrpProcessCard.qml`

Card cau hinh mot EIGRP process.

- Nhap/sua AS number, router ID va cac option process-level.
- Cau hinh auto summary, passive default, BFD all interfaces, metric weights, distance, variance, maximum paths va stub options.
- Giu cac model con cua process: networks, interface settings, passive interfaces, distribute lists, offset lists, redistribute va key chains.
- Tao snapshot payload de `EigrpRoutingForm.qml` luu xuong database.
- Validate cac field process-level va network row neu co network.
- Luu y: EIGRP process khong bat buoc phai co network.

## `EigrpPinnedHeader.qml`

Header co dinh cua man hinh EIGRP.

- Hien thi cac thong ke luon thay duoc: so process, so network, host, state.
- Hien thi tab dieu huong EIGRP: Process, Networks, Interfaces, Passive iface, Redistribute, Distribute list, Offset list, Key chains.
- Goi `form.selectRoutingSection(...)` khi user doi tab.

## `EigrpNetworksSection.qml`

Section cau hinh EIGRP Networks.

- Them network vao process dang chon.
- Ho tro wildcard va interface name tuy chon.
- Hien thi bang networks cua process dang chon.
- Xoa network row khoi process dang chon.

## `EigrpInterfacesSection.qml`

Section cau hinh EIGRP interface settings.

- Them interface setting cho process dang chon.
- Ho tro bandwidth, delay, hello/hold timer, auth key chain, summary address, split horizon, bandwidth percent, next-hop-self va BFD timers.
- Hien thi/xoa interface setting cua process dang chon.

## `EigrpPassiveInterfacesSection.qml`

Section cau hinh passive-interface EIGRP.

- Them interface vao danh sach `passive` hoac `no-passive` cua process dang chon.
- Hien thi/xoa passive-interface row.

## `EigrpRedistributeSection.qml`

Section cau hinh redistribution cho EIGRP.

- Them redistribute rule theo protocol.
- Ho tro route map va metric 5 thanh phan cua EIGRP: bandwidth, delay, reliability, load, MTU.
- Hien thi/xoa redistribute rule cua process dang chon.

## `EigrpDistributeListsSection.qml`

Section cau hinh EIGRP distribute lists.

- Them distribute-list theo list name va direction `in`/`out`.
- Ho tro interface name tuy chon.
- Hien thi/xoa distribute-list row cua process dang chon.

## `EigrpOffsetListsSection.qml`

Section cau hinh EIGRP offset lists.

- Them offset-list theo list name, direction va offset value.
- Ho tro interface name tuy chon.
- Hien thi/xoa offset-list row cua process dang chon.

## `EigrpKeyChainsSection.qml`

Section cau hinh EIGRP key chains.

- Them key chain theo chain name, key id va key string.
- Ho tro accept lifetime va send lifetime tuy chon.
- Hien thi/xoa key-chain row cua process dang chon.
- Luu y: key chains duoc luu theo host trong database, nhung UI gan vao process dang chon de thao tac nhat quan voi cac section EIGRP.
