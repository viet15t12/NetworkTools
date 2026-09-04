"""Minimal Peewee mappings for Switching lifecycle persistence.

These models deliberately expose only columns used while staging deletions or
acknowledging a successful Push.  Schema creation and complex desired-state
queries remain owned by the existing SQLite repositories.
"""

from __future__ import annotations

from dataclasses import dataclass

from peewee import AutoField, IntegerField, Model, SqliteDatabase, TextField


@dataclass(frozen=True)
class SwitchingModels:
    """Hold request-scoped models bound to one workspace database."""

    database: SqliteDatabase
    vlan: type[Model]
    svi: type[Model]
    switch_l3: type[Model]
    interface: type[Model]
    etherchannel: type[Model]
    stp: type[Model]
    l2_vlan: type[Model]
    trust_port: type[Model]
    static_mac: type[Model]
    port_security: type[Model]
    vtp: type[Model]


def build_switching_models(database: SqliteDatabase) -> SwitchingModels:
    """Build isolated model classes for one short-lived Peewee connection.

    Models are created per operation instead of rebinding global classes.  That
    keeps concurrent QML workers from accidentally sending a query to another
    workspace after the user switches projects.
    """

    orm_database = database

    class SwitchingModel(Model):
        class Meta:
            database = orm_database
            legacy_table_names = False

    class Vlan(SwitchingModel):
        id = AutoField()
        success = TextField()
        device_present = IntegerField()

        class Meta:
            table_name = "t06_vlan_db"

    class Svi(SwitchingModel):
        id = AutoField()
        sync_status = TextField()
        device_present = IntegerField()

        class Meta:
            table_name = "t06_svi_interface"

    class SwitchL3(SwitchingModel):
        host = TextField(primary_key=True)
        sync_status = TextField()

        class Meta:
            table_name = "t06_switch_l3_config"

    class SwitchInterface(SwitchingModel):
        id = AutoField()
        host = TextField()
        success = TextField()

        class Meta:
            table_name = "t06_interface_l2"

    class Etherchannel(SwitchingModel):
        id = AutoField()
        success = TextField()
        device_present = IntegerField()
        cleanup_member_ports = TextField()

        class Meta:
            table_name = "t06_etherchannel"

    class Stp(SwitchingModel):
        id = AutoField()
        host = TextField()
        success = TextField()

        class Meta:
            table_name = "t06_stp_config"

    class L2VlanSecurity(SwitchingModel):
        id = AutoField()
        host = TextField()
        success = TextField()

        class Meta:
            table_name = "t06_security_l2"

    class TrustPort(SwitchingModel):
        id = AutoField()
        host = TextField()
        success = TextField()

        class Meta:
            table_name = "t06_dhcp_trust_ports"

    class StaticMac(SwitchingModel):
        id = AutoField()
        iface_id = IntegerField()
        mac_type = TextField()
        success = TextField()

        class Meta:
            table_name = "t06_iface_mac_table"

    class PortSecurity(SwitchingModel):
        iface_id = IntegerField(primary_key=True)
        success = TextField()
        sync_status = TextField()

        class Meta:
            table_name = "t06_iface_port_security"

    class VtpSwitch(SwitchingModel):
        vtp_switch_id = AutoField()
        success = TextField()
        sync_status = TextField()

        class Meta:
            table_name = "t09_vtp_switches"

    return SwitchingModels(
        database=database,
        vlan=Vlan,
        svi=Svi,
        switch_l3=SwitchL3,
        interface=SwitchInterface,
        etherchannel=Etherchannel,
        stp=Stp,
        l2_vlan=L2VlanSecurity,
        trust_port=TrustPort,
        static_mac=StaticMac,
        port_security=PortSecurity,
        vtp=VtpSwitch,
    )


__all__ = ["SwitchingModels", "build_switching_models"]
