#include <arpa/inet.h>
#include <csignal>
#include <cstring>
#include <dlfcn.h>
#include <fcntl.h>
#include <netdb.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <ctime>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <optional>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

struct sqlite3;
struct sqlite3_stmt;

namespace {

constexpr int SQLITE_OK = 0;
constexpr int SQLITE_ROW = 100;
constexpr int SQLITE_DONE = 101;
constexpr int SQLITE_OPEN_READONLY = 0x00000001;
constexpr int SQLITE_OPEN_READWRITE = 0x00000002;
constexpr int SQLITE_OPEN_FULLMUTEX = 0x00010000;
const auto SQLITE_TRANSIENT = reinterpret_cast<void (*)(void*)>(-1);

std::atomic_bool running{true};

void stop_signal(int) { running = false; }

std::string json_escape(const std::string& value) {
    std::ostringstream out;
    for (unsigned char ch : value) {
        switch (ch) {
        case '\\': out << "\\\\"; break;
        case '"': out << "\\\""; break;
        case '\n': out << "\\n"; break;
        case '\r': out << "\\r"; break;
        case '\t': out << "\\t"; break;
        default:
            if (ch < 0x20) {
                const char* hex = "0123456789abcdef";
                out << "\\u00" << hex[(ch >> 4) & 0xf] << hex[ch & 0xf];
            } else {
                out << static_cast<char>(ch);
            }
        }
    }
    return out.str();
}

void emit_error(const std::string& message) {
    std::cout << "{\"type\":\"error\",\"message\":\""
              << json_escape(message) << "\"}" << std::endl;
}

std::string read_file(const std::string& path) {
    std::ifstream stream(path);
    if (!stream) throw std::runtime_error("Could not read settings file: " + path);
    return {std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()};
}

std::string json_string(const std::string& json, const std::string& key, const std::string& fallback) {
    const std::regex expression("\\\"" + key + "\\\"\\s*:\\s*\\\"([^\\\"]*)\\\"");
    std::smatch match;
    return std::regex_search(json, match, expression) ? match[1].str() : fallback;
}

int json_int(const std::string& json, const std::string& key, int fallback) {
    const std::regex expression("\\\"" + key + "\\\"\\s*:\\s*([0-9]+)");
    std::smatch match;
    return std::regex_search(json, match, expression) ? std::stoi(match[1].str()) : fallback;
}

struct Config {
    std::string bind_ip{"0.0.0.0"};
    int port{5514};
    int max_message_bytes{16384};
    int max_tcp_clients{64};
};

Config load_config(const std::string& path) {
    const auto json = read_file(path);
    Config config;
    config.bind_ip = json_string(json, "bind_ip", config.bind_ip);
    config.port = json_int(json, "port", config.port);
    config.max_message_bytes = json_int(json, "max_message_bytes", config.max_message_bytes);
    config.max_tcp_clients = json_int(json, "max_tcp_clients", config.max_tcp_clients);
    if (config.port < 1 || config.port > 65535) throw std::runtime_error("Invalid Syslog port in JSON settings");
    if (config.max_message_bytes < 256 || config.max_message_bytes > 1024 * 1024)
        throw std::runtime_error("Invalid max_message_bytes in JSON settings");
    if (config.max_tcp_clients < 1 || config.max_tcp_clients > 4096)
        throw std::runtime_error("Invalid max_tcp_clients in JSON settings");
    return config;
}

class SqliteApi {
public:
    using Open = int (*)(const char*, sqlite3**, int, const char*);
    using Close = int (*)(sqlite3*);
    using BusyTimeout = int (*)(sqlite3*, int);
    using Prepare = int (*)(sqlite3*, const char*, int, sqlite3_stmt**, const char**);
    using Step = int (*)(sqlite3_stmt*);
    using Finalize = int (*)(sqlite3_stmt*);
    using BindText = int (*)(sqlite3_stmt*, int, const char*, int, void (*)(void*));
    using BindInt = int (*)(sqlite3_stmt*, int, int);
    using BindNull = int (*)(sqlite3_stmt*, int);
    using ColumnText = const unsigned char* (*)(sqlite3_stmt*, int);
    using LastId = std::int64_t (*)(sqlite3*);
    using Errmsg = const char* (*)(sqlite3*);

    SqliteApi() {
        handle = dlopen("libsqlite3.so.0", RTLD_NOW | RTLD_LOCAL);
        if (!handle) throw std::runtime_error("Could not load libsqlite3.so.0");
        open = symbol<Open>("sqlite3_open_v2");
        close = symbol<Close>("sqlite3_close");
        busy_timeout = symbol<BusyTimeout>("sqlite3_busy_timeout");
        prepare = symbol<Prepare>("sqlite3_prepare_v2");
        step = symbol<Step>("sqlite3_step");
        finalize = symbol<Finalize>("sqlite3_finalize");
        bind_text = symbol<BindText>("sqlite3_bind_text");
        bind_int = symbol<BindInt>("sqlite3_bind_int");
        bind_null = symbol<BindNull>("sqlite3_bind_null");
        column_text = symbol<ColumnText>("sqlite3_column_text");
        last_id = symbol<LastId>("sqlite3_last_insert_rowid");
        errmsg = symbol<Errmsg>("sqlite3_errmsg");
    }

    ~SqliteApi() { if (handle) dlclose(handle); }
    SqliteApi(const SqliteApi&) = delete;
    SqliteApi& operator=(const SqliteApi&) = delete;

    Open open{}; Close close{}; BusyTimeout busy_timeout{}; Prepare prepare{};
    Step step{}; Finalize finalize{}; BindText bind_text{}; BindInt bind_int{};
    BindNull bind_null{}; ColumnText column_text{}; LastId last_id{}; Errmsg errmsg{};

private:
    void* handle{};
    template<typename T> T symbol(const char* name) {
        auto value = reinterpret_cast<T>(dlsym(handle, name));
        if (!value) throw std::runtime_error(std::string("Missing SQLite symbol: ") + name);
        return value;
    }
};

class Database {
public:
    Database(SqliteApi& api, const std::string& info_path, const std::string& device_path) : api(api) {
        if (api.open(info_path.c_str(), &info, SQLITE_OPEN_READWRITE | SQLITE_OPEN_FULLMUTEX, nullptr) != SQLITE_OK)
            throw std::runtime_error("Could not open Syslog database: " + info_path);
        if (api.open(device_path.c_str(), &device, SQLITE_OPEN_READONLY | SQLITE_OPEN_FULLMUTEX, nullptr) != SQLITE_OK)
            throw std::runtime_error("Could not open device database: " + device_path);
        api.busy_timeout(info, 10000);
        api.busy_timeout(device, 10000);
    }
    ~Database() { if (device) api.close(device); if (info) api.close(info); }

    std::string resolve_host(const std::string& source) {
        const char* direct = "SELECT host FROM t01_devices WHERE host = ? LIMIT 1";
        if (auto value = select_host(direct, source); !value.empty()) return value;
        const char* interface =
            "SELECT host FROM t02_interface_name WHERE ip_address = ? "
            "ORDER BY CASE sync_status WHEN 'synchronized' THEN 0 "
            "WHEN 'pending_apply' THEN 1 WHEN 'pending_delete' THEN 2 ELSE 3 END LIMIT 1";
        if (auto value = select_host(interface, source); !value.empty()) return value;
        return source;
    }

    std::int64_t insert(const struct Message& row);

private:
    std::string select_host(const char* sql, const std::string& source) {
        sqlite3_stmt* statement{};
        if (api.prepare(device, sql, -1, &statement, nullptr) != SQLITE_OK) return {};
        api.bind_text(statement, 1, source.c_str(), -1, SQLITE_TRANSIENT);
        std::string result;
        if (api.step(statement) == SQLITE_ROW) {
            if (const auto* value = api.column_text(statement, 0))
                result = reinterpret_cast<const char*>(value);
        }
        api.finalize(statement);
        return result;
    }
    SqliteApi& api;
    sqlite3* info{};
    sqlite3* device{};
};

struct Message {
    std::string device_host;
    std::string source_ip;
    std::optional<std::string> device_time;
    std::optional<int> sequence_number;
    bool clock_unsynchronized{false};
    std::string received_at;
    std::optional<int> syslog_pri;
    std::optional<int> syslog_facility;
    std::optional<std::string> cisco_facility;
    std::optional<std::string> cisco_subfacility;
    int severity{6};
    std::optional<std::string> mnemonic;
    std::string message;
    std::string raw_message;
    std::string protocol;
    std::string parse_status{"raw"};
};

void bind_optional_text(SqliteApi& api, sqlite3_stmt* statement, int index, const std::optional<std::string>& value) {
    if (value) api.bind_text(statement, index, value->c_str(), -1, SQLITE_TRANSIENT);
    else api.bind_null(statement, index);
}

void bind_optional_int(SqliteApi& api, sqlite3_stmt* statement, int index, const std::optional<int>& value) {
    if (value) api.bind_int(statement, index, *value);
    else api.bind_null(statement, index);
}

std::int64_t Database::insert(const Message& row) {
    static const char* sql =
        "INSERT INTO t12_syslog_messages "
        "(device_host,source_ip,device_time,sequence_number,clock_unsynchronized,received_at,"
        "syslog_pri,syslog_facility,cisco_facility,cisco_subfacility,facility,severity,mnemonic,"
        "message,raw_message,protocol,parse_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)";
    sqlite3_stmt* statement{};
    if (api.prepare(info, sql, -1, &statement, nullptr) != SQLITE_OK)
        throw std::runtime_error(api.errmsg(info));
    int i = 1;
    api.bind_text(statement, i++, row.device_host.c_str(), -1, SQLITE_TRANSIENT);
    api.bind_text(statement, i++, row.source_ip.c_str(), -1, SQLITE_TRANSIENT);
    bind_optional_text(api, statement, i++, row.device_time);
    bind_optional_int(api, statement, i++, row.sequence_number);
    api.bind_int(statement, i++, row.clock_unsynchronized ? 1 : 0);
    api.bind_text(statement, i++, row.received_at.c_str(), -1, SQLITE_TRANSIENT);
    bind_optional_int(api, statement, i++, row.syslog_pri);
    bind_optional_int(api, statement, i++, row.syslog_facility);
    bind_optional_text(api, statement, i++, row.cisco_facility);
    bind_optional_text(api, statement, i++, row.cisco_subfacility);
    const std::optional<std::string> facility = row.cisco_facility
        ? row.cisco_facility
        : (row.syslog_facility ? std::optional<std::string>(std::to_string(*row.syslog_facility)) : std::nullopt);
    bind_optional_text(api, statement, i++, facility);
    api.bind_int(statement, i++, row.severity);
    bind_optional_text(api, statement, i++, row.mnemonic);
    api.bind_text(statement, i++, row.message.c_str(), -1, SQLITE_TRANSIENT);
    api.bind_text(statement, i++, row.raw_message.c_str(), -1, SQLITE_TRANSIENT);
    api.bind_text(statement, i++, row.protocol.c_str(), -1, SQLITE_TRANSIENT);
    api.bind_text(statement, i++, row.parse_status.c_str(), -1, SQLITE_TRANSIENT);
    const int result = api.step(statement);
    api.finalize(statement);
    if (result != SQLITE_DONE) throw std::runtime_error(api.errmsg(info));
    return api.last_id(info);
}

std::string utc_now() {
    using namespace std::chrono;
    const auto now = system_clock::now();
    const auto milliseconds = duration_cast<std::chrono::milliseconds>(now.time_since_epoch()) % 1000;
    const std::time_t current = system_clock::to_time_t(now);
    std::tm tm{};
    gmtime_r(&current, &tm);
    char buffer[32]{};
    std::strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%S", &tm);
    std::ostringstream out;
    out << buffer << '.';
    out.width(3); out.fill('0'); out << milliseconds.count() << 'Z';
    return out.str();
}

Message parse_message(std::string raw, const std::string& source, const std::string& protocol) {
    raw.erase(std::remove(raw.begin(), raw.end(), '\0'), raw.end());
    while (!raw.empty() && (raw.back() == '\r' || raw.back() == '\n' || raw.back() == ' ')) raw.pop_back();
    Message row;
    row.source_ip = source;
    row.protocol = protocol;
    row.raw_message = raw;
    row.received_at = utc_now();
    std::string remainder = raw;

    std::smatch match;
    if (std::regex_search(remainder, match, std::regex("^<([0-9]{1,3})>"))) {
        const int pri = std::stoi(match[1].str());
        if (pri <= 191) {
            row.syslog_pri = pri;
            row.syslog_facility = pri / 8;
            row.severity = pri % 8;
            remainder = remainder.substr(match.length());
            while (!remainder.empty() && remainder.front() == ' ') remainder.erase(remainder.begin());
            row.parse_status = "partial";
        }
    }
    if (std::regex_search(remainder, match, std::regex("^([0-9]+):\\s*"))) {
        row.sequence_number = std::stoi(match[1].str());
        remainder = remainder.substr(match.length());
    }
    const std::regex stamp("^(\\*)?([A-Z][a-z]{2}\\s+[0-9]{1,2}\\s+[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\\.[0-9]{1,6})?)(?:\\s+[A-Z][A-Z0-9+-]*)?\\s*:?\\s*(.*)$");
    if (std::regex_match(remainder, match, stamp)) {
        row.clock_unsynchronized = !match[1].str().empty();
        row.device_time = match[2].str();
        remainder = match[3].str();
        row.parse_status = "partial";
    }
    const std::regex cisco("%([A-Z0-9_]+(?:-[A-Z0-9_]+)*)-([0-7])-([A-Z0-9_]+):\\s*(.*)");
    if (std::regex_search(remainder, match, cisco)) {
        std::string prefix = match[1].str();
        const auto separator = prefix.find('-');
        row.cisco_facility = prefix.substr(0, separator);
        if (separator != std::string::npos) row.cisco_subfacility = prefix.substr(separator + 1);
        row.severity = std::stoi(match[2].str());
        row.mnemonic = match[3].str();
        row.message = match[4].str();
        row.parse_status = "parsed";
    } else {
        row.message = remainder.empty() ? raw : remainder;
    }
    return row;
}

std::string json_optional(const std::optional<std::string>& value) {
    return value ? "\"" + json_escape(*value) + "\"" : "null";
}

std::string json_optional(const std::optional<int>& value) {
    return value ? std::to_string(*value) : "null";
}

void emit_message(std::int64_t id, const Message& row) {
    const auto facility = row.cisco_facility
        ? json_optional(row.cisco_facility)
        : (row.syslog_facility ? "\"" + std::to_string(*row.syslog_facility) + "\"" : "null");
    std::cout
        << "{\"type\":\"message\",\"row\":{"
        << "\"id\":" << id
        << ",\"device_host\":\"" << json_escape(row.device_host) << "\""
        << ",\"source_ip\":\"" << json_escape(row.source_ip) << "\""
        << ",\"device_time\":" << json_optional(row.device_time)
        << ",\"sequence_number\":" << json_optional(row.sequence_number)
        << ",\"clock_unsynchronized\":" << (row.clock_unsynchronized ? "true" : "false")
        << ",\"received_at\":\"" << row.received_at << "\""
        << ",\"syslog_pri\":" << json_optional(row.syslog_pri)
        << ",\"syslog_facility\":" << json_optional(row.syslog_facility)
        << ",\"cisco_facility\":" << json_optional(row.cisco_facility)
        << ",\"cisco_subfacility\":" << json_optional(row.cisco_subfacility)
        << ",\"facility\":" << facility
        << ",\"severity\":" << row.severity
        << ",\"mnemonic\":" << json_optional(row.mnemonic)
        << ",\"message\":\"" << json_escape(row.message) << "\""
        << ",\"raw_message\":\"" << json_escape(row.raw_message) << "\""
        << ",\"protocol\":\"" << row.protocol << "\""
        << ",\"parse_status\":\"" << row.parse_status << "\"}}"
        << std::endl;
}

int make_server(const Config& config, int socket_type) {
    addrinfo hints{};
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = socket_type;
    hints.ai_flags = AI_PASSIVE;
    addrinfo* addresses{};
    const std::string port = std::to_string(config.port);
    const char* node = (config.bind_ip == "0.0.0.0" || config.bind_ip == "::") ? nullptr : config.bind_ip.c_str();
    const int lookup = getaddrinfo(node, port.c_str(), &hints, &addresses);
    if (lookup != 0) throw std::runtime_error(gai_strerror(lookup));
    int server = -1;
    for (auto* address = addresses; address; address = address->ai_next) {
        server = socket(address->ai_family, address->ai_socktype, address->ai_protocol);
        if (server < 0) continue;
        int enabled = 1;
        setsockopt(server, SOL_SOCKET, SO_REUSEADDR, &enabled, sizeof(enabled));
        if (bind(server, address->ai_addr, address->ai_addrlen) == 0) break;
        close(server); server = -1;
    }
    freeaddrinfo(addresses);
    if (server < 0) throw std::runtime_error("Could not bind native Syslog socket: " + std::string(std::strerror(errno)));
    fcntl(server, F_SETFL, fcntl(server, F_GETFL, 0) | O_NONBLOCK);
    return server;
}

std::string peer_ip(const sockaddr_storage& address, socklen_t length) {
    char host[NI_MAXHOST]{};
    if (getnameinfo(reinterpret_cast<const sockaddr*>(&address), length, host, sizeof(host), nullptr, 0, NI_NUMERICHOST) != 0)
        return "unknown";
    return host;
}

struct Client { std::string source_ip; std::string buffer; };

class Collector {
public:
    Collector(const Config& config, Database& database) : config(config), database(database) {}
    ~Collector() { close_all(); }

    void run() {
        udp = make_server(config, SOCK_DGRAM);
        tcp = make_server(config, SOCK_STREAM);
        if (listen(tcp, config.max_tcp_clients) != 0) throw std::runtime_error(std::strerror(errno));
        std::cout << "{\"type\":\"ready\",\"message\":\"Listening on "
                  << json_escape(config.bind_ip) << ':' << config.port
                  << "/UDP+TCP (native C++)\"}" << std::endl;
        while (running) poll_once();
    }

private:
    void poll_once() {
        std::vector<pollfd> descriptors{{udp, POLLIN, 0}, {tcp, POLLIN, 0}};
        for (const auto& [fd, _] : clients) descriptors.push_back({fd, POLLIN, 0});
        const int result = poll(descriptors.data(), descriptors.size(), 500);
        if (result < 0) { if (errno == EINTR) return; throw std::runtime_error(std::strerror(errno)); }
        if (descriptors[0].revents & POLLIN) receive_udp();
        if (descriptors[1].revents & POLLIN) accept_tcp();
        std::vector<int> closed;
        for (std::size_t i = 2; i < descriptors.size(); ++i) {
            if (descriptors[i].revents & (POLLIN | POLLHUP | POLLERR)) receive_tcp(descriptors[i].fd, closed);
        }
        for (int fd : closed) { close(fd); clients.erase(fd); }
    }

    void receive_udp() {
        std::vector<char> buffer(static_cast<std::size_t>(config.max_message_bytes) + 1);
        sockaddr_storage address{}; socklen_t length = sizeof(address);
        const auto size = recvfrom(udp, buffer.data(), buffer.size(), 0, reinterpret_cast<sockaddr*>(&address), &length);
        if (size > 0 && size <= config.max_message_bytes)
            store(std::string(buffer.data(), static_cast<std::size_t>(size)), peer_ip(address, length), "udp");
    }

    void accept_tcp() {
        sockaddr_storage address{}; socklen_t length = sizeof(address);
        const int fd = accept(tcp, reinterpret_cast<sockaddr*>(&address), &length);
        if (fd < 0) return;
        if (static_cast<int>(clients.size()) >= config.max_tcp_clients) { close(fd); return; }
        fcntl(fd, F_SETFL, fcntl(fd, F_GETFL, 0) | O_NONBLOCK);
        clients.emplace(fd, Client{peer_ip(address, length), {}});
    }

    void receive_tcp(int fd, std::vector<int>& closed) {
        auto found = clients.find(fd);
        if (found == clients.end()) return;
        char chunk[4096];
        const auto size = recv(fd, chunk, sizeof(chunk), 0);
        if (size <= 0) {
            if (!found->second.buffer.empty()) store(found->second.buffer, found->second.source_ip, "tcp");
            closed.push_back(fd); return;
        }
        found->second.buffer.append(chunk, static_cast<std::size_t>(size));
        std::size_t newline{};
        while ((newline = found->second.buffer.find('\n')) != std::string::npos) {
            auto frame = found->second.buffer.substr(0, newline);
            found->second.buffer.erase(0, newline + 1);
            if (!frame.empty() && frame.back() == '\r') frame.pop_back();
            if (!frame.empty()) store(frame, found->second.source_ip, "tcp");
        }
        if (found->second.buffer.size() > static_cast<std::size_t>(config.max_message_bytes)) closed.push_back(fd);
    }

    void store(const std::string& raw, const std::string& source, const std::string& protocol) {
        try {
            auto row = parse_message(raw, source, protocol);
            row.device_host = database.resolve_host(source);
            const auto id = database.insert(row);
            emit_message(id, row);
        } catch (const std::exception& error) {
            ++dropped;
            std::cout << "{\"type\":\"dropped\",\"count\":" << dropped << "}" << std::endl;
            emit_error(std::string("Could not persist Syslog message: ") + error.what());
        }
    }

    void close_all() {
        for (const auto& [fd, _] : clients) close(fd);
        clients.clear();
        if (udp >= 0) close(udp);
        if (tcp >= 0) close(tcp);
        udp = tcp = -1;
    }

    const Config& config; Database& database;
    int udp{-1}; int tcp{-1}; std::map<int, Client> clients; std::uint64_t dropped{0};
};

std::string argument(int argc, char** argv, const std::string& name) {
    for (int i = 1; i + 1 < argc; ++i) if (argv[i] == name) return argv[i + 1];
    throw std::runtime_error("Missing required argument: " + name);
}

} // namespace

int main(int argc, char** argv) {
    std::signal(SIGINT, stop_signal);
    std::signal(SIGTERM, stop_signal);
    try {
        const auto config = load_config(argument(argc, argv, "--settings"));
        SqliteApi sqlite;
        Database database(sqlite, argument(argc, argv, "--info-db"), argument(argc, argv, "--device-db"));
        Collector collector(config, database);
        collector.run();
        return 0;
    } catch (const std::exception& error) {
        emit_error(error.what());
        return 1;
    }
}
