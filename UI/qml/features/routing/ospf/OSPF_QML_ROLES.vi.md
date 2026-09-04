# Vai tro cac file QML OSPF

Da doi chieu: **2026-08-16**. Tai lieu tom tat cac component trong
`UI/qml/features/routing/ospf`; hanh vi backend nam trong README feature va tai
lieu schema.

## `OspfRoutingForm.qml`

Component dieu phoi chinh cho man hinh OSPF.

- Quan ly state tong: host hien tai, loading/saving, dirty state, section dang active.
- Load/save du lieu OSPF thong qua `dbManager`.
- Giu `processModel` va cac ham thao tac tren process dang chon.
- Dieu phoi cac section con bang cach truyen `form: ospfRoutingForm`.
- Render danh sach `OspfProcessCard` trong tab `Process`.

## `OspfProcessCard.qml`

Card cau hinh mot OSPF process.

- Nhap/sua process ID, router ID, reference bandwidth.
- Cau hinh cac option process-level: passive default, default originate, always.
- Giu cac model con cua process: networks, areas, redistribute, passive interfaces, interface settings.
- Tao snapshot payload de `OspfRoutingForm.qml` luu xuong database.
- Validate cac field process-level va network row neu co network.

## `OspfPinnedHeader.qml`

Header co dinh cua man hinh OSPF.

- Hien thi cac thong ke luon thay duoc: so process, so network, host, state.
- Hien thi tab dieu huong OSPF: Process, Networks, Areas, Distance, Redistribute, Interfaces, Passive iface, Tuning.
- Goi `form.selectRoutingSection(...)` khi user doi tab.

## `OspfAreasSection.qml`

Section cau hinh OSPF Areas.

- Them/xoa area cho process dang chon.
- Cau hinh area type, no-summary va authentication.
- Them/xoa area range cho area dang chon.
- Su dung cac ham area/range tu `OspfRoutingForm.qml`.

## `OspfNetworksSection.qml`

Section cau hinh OSPF Networks.

- Them network/wildcard/area vao process dang chon.
- Hien thi bang networks cua process dang chon.
- Xoa network row khoi process dang chon.
- Luu y: OSPF process khong bat buoc phai co network.

## `OspfDistanceSection.qml`

Section cau hinh OSPF administrative distance.

- Nhap external, intra-area va inter-area distance.
- Goi `form.setDistanceForSelectedProcess(...)` de cap nhat process dang chon.

## `OspfRedistributeSection.qml`

Section cau hinh redistribution cho OSPF.

- Them redistribute rule theo protocol.
- Ho tro process ID tuy chon, subnets, metric, metric type va route map.
- Hien thi/xoa redistribute rule cua process dang chon.

## `OspfInterfacesSection.qml`

Section cau hinh OSPF interface settings.

- Them interface setting cho process dang chon.
- Ho tro area, cost, hello/dead interval, MTU ignore, BFD, network type va auth type.
- Hien thi/xoa interface setting cua process dang chon.

## `OspfPassiveInterfacesSection.qml`

Section cau hinh passive-interface.

- Them interface vao danh sach passive/no-passive cua process dang chon.
- Hien thi/xoa passive-interface row.

## `OspfTuningSection.qml`

Section cau hinh cac tham so tuning OSPF.

- Cap nhat maximum paths, max LSA.
- Cap nhat SPF timers va LSA timers.
- Goi `form.setTuningForSelectedProcess(...)` de cap nhat process dang chon.
