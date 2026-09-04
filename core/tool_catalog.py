from __future__ import annotations

from typing import Any


# This allowlist is intentionally static. The application only detects known
# executables and opens vendor-owned HTTPS pages after an explicit user action.
# It never downloads packages or invokes a package manager.
EXTERNAL_TOOL_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "app": "PuTTY",
        "category": "SSH Client",
        "executables": ("putty.exe",),
        "summary": "Lightweight SSH and Telnet client for Windows.",
        "officialUrl": "https://www.chiark.greenend.org.uk/~sgtatham/putty/latest.html",
        "known_paths": (
            "%ProgramFiles%\\PuTTY\\putty.exe",
            "%ProgramFiles(x86)%\\PuTTY\\putty.exe",
            "%LOCALAPPDATA%\\Programs\\PuTTY\\putty.exe",
        ),
    },
    {
        "app": "Xshell",
        "category": "SSH Client",
        "executables": ("Xshell.exe",),
        "summary": "Tabbed SSH client with session management.",
        "officialUrl": "https://www.netsarang.com/en/xshell-download/",
        "uninstall_names": ("Xshell",),
        "known_paths": (
            "%ProgramFiles%\\NetSarang\\Xshell 9\\Xshell.exe",
            "%ProgramFiles%\\NetSarang\\Xshell 8\\Xshell.exe",
            "%ProgramFiles%\\NetSarang\\Xshell 7\\Xshell.exe",
            "%ProgramFiles(x86)%\\NetSarang\\Xshell 9\\Xshell.exe",
            "%ProgramFiles(x86)%\\NetSarang\\Xshell 8\\Xshell.exe",
            "%ProgramFiles(x86)%\\NetSarang\\Xshell 7\\Xshell.exe",
        ),
    },
    {
        "app": "MobaXterm",
        "category": "SSH Client",
        "executables": ("MobaXterm.exe",),
        "summary": "Remote terminal suite with SSH and file-transfer tools.",
        "officialUrl": "https://mobaxterm.mobatek.net/download.html",
        "uninstall_names": ("MobaXterm",),
        "known_paths": (
            "%ProgramFiles%\\Mobatek\\MobaXterm\\MobaXterm.exe",
            "%ProgramFiles(x86)%\\Mobatek\\MobaXterm\\MobaXterm.exe",
            "%LOCALAPPDATA%\\Programs\\MobaXterm\\MobaXterm.exe",
        ),
    },
    {
        "app": "Tera Term",
        "category": "SSH Client",
        "executables": ("ttermpro.exe",),
        "summary": "Open-source terminal emulator with SSH support.",
        "officialUrl": "https://teratermproject.github.io/index-en.html",
        "uninstall_names": ("Tera Term", "TeraTerm"),
        "known_paths": (
            "%ProgramFiles%\\teraterm5\\ttermpro.exe",
            "%ProgramFiles(x86)%\\teraterm5\\ttermpro.exe",
            "%ProgramFiles%\\teraterm\\ttermpro.exe",
            "%ProgramFiles(x86)%\\teraterm\\ttermpro.exe",
        ),
    },
    {
        "app": "SecureCRT",
        "category": "SSH Client",
        "executables": ("SecureCRT.exe",),
        "summary": "Commercial terminal client for managed remote access.",
        "officialUrl": "https://www.vandyke.com/products/securecrt/",
        "known_paths": (
            "%ProgramFiles%\\VanDyke Software\\SecureCRT\\SecureCRT.exe",
            "%ProgramFiles(x86)%\\VanDyke Software\\SecureCRT\\SecureCRT.exe",
            "%LOCALAPPDATA%\\VanDyke Software\\SecureCRT\\SecureCRT.exe",
        ),
    },
    {
        "app": "Windows Terminal",
        "category": "Terminal",
        "executables": ("wt.exe",),
        "summary": "Microsoft's modern terminal host for Windows.",
        "officialUrl": "https://aka.ms/terminal",
        "known_paths": ("%LOCALAPPDATA%\\Microsoft\\WindowsApps\\wt.exe",),
    },
    {
        "app": "DB Browser for SQLite",
        "category": "DB Browser",
        "executables": ("DB Browser for SQLite.exe", "sqlitebrowser.exe"),
        "summary": "Visual editor and browser for SQLite databases.",
        "officialUrl": "https://sqlitebrowser.org/dl/",
        "known_paths": (
            "%ProgramFiles%\\DB Browser for SQLite\\DB Browser for SQLite.exe",
            "%ProgramFiles(x86)%\\DB Browser for SQLite\\DB Browser for SQLite.exe",
            "%LOCALAPPDATA%\\Programs\\DB Browser for SQLite\\DB Browser for SQLite.exe",
        ),
    },
    {
        "app": "Letos",
        "category": "DB Browser",
        "executables": ("Letos.exe", "letos.exe", "letos"),
        "summary": "Cross-platform manager for browsing and editing SQLite databases.",
        "officialUrl": "https://letos.org/",
        "uninstall_names": ("Letos",),
        "known_paths": (
            "%ProgramFiles%\\Letos\\Letos.exe",
            "%LOCALAPPDATA%\\Programs\\Letos\\Letos.exe",
            "/usr/bin/letos",
            "/usr/local/bin/letos",
        ),
    },
    {
        "app": "WinSCP",
        "category": "SFTP Client",
        "executables": ("WinSCP.exe",),
        "summary": "Graphical SFTP and SCP client for Windows.",
        "officialUrl": "https://winscp.net/eng/download.php",
        "uninstall_names": ("WinSCP",),
        "known_paths": (
            "%ProgramFiles%\\WinSCP\\WinSCP.exe",
            "%ProgramFiles(x86)%\\WinSCP\\WinSCP.exe",
            "%LOCALAPPDATA%\\Programs\\WinSCP\\WinSCP.exe",
        ),
    },
    {
        "app": "Wireshark",
        "category": "Packet Capture",
        "executables": ("Wireshark.exe", "tshark.exe"),
        "summary": "Packet analyzer; TShark enables new Device Logs captures.",
        "officialUrl": "https://www.wireshark.org/download.html",
        "uninstall_names": ("Wireshark",),
        "known_paths": (
            "%ProgramFiles%\\Wireshark\\Wireshark.exe",
            "%ProgramFiles%\\Wireshark\\tshark.exe",
            "%ProgramFiles(x86)%\\Wireshark\\Wireshark.exe",
            "%ProgramFiles(x86)%\\Wireshark\\tshark.exe",
        ),
    },
)
