.pragma library

// ────────────────────────────────────────────────────────────────────────────
// IP ADDRESS
// ────────────────────────────────────────────────────────────────────────────

function isValidIPv4(value) {
    const str = String(value || "").trim()
    if (str === "") return false

    const parts = str.split(".")
    if (parts.length !== 4) return false

    for (let i = 0; i < 4; i++) {
        if (parts[i] === "" || !/^\d+$/.test(parts[i])) return false
        const num = parseInt(parts[i], 10)
        if (isNaN(num) || num < 0 || num > 255) return false
        if (parts[i].length > 1 && parts[i][0] === "0") return false
    }
    return true
}

function isPrivateIPv4(value) {
    if (!isValidIPv4(value)) return false
    const parts = String(value).trim().split(".").map(Number)
    const [a, b] = parts
    return (
        a === 10 ||
        (a === 172 && b >= 16 && b <= 31) ||
        (a === 192 && b === 168)
    )
}

function isValidWildcard(value) {
    return isValidIPv4(value)
}

function isValidSubnetMask(value) {
    if (!isValidIPv4(value)) return false
    const parts = String(value).trim().split(".").map(Number)
    let num = (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]
    num = num >>> 0
    const inverted = (~num) >>> 0
    return (inverted & (inverted + 1)) === 0
}

function prefixToSubnetMask(prefix) {
    const n = parseInt(prefix, 10)
    if (isNaN(n) || n < 0 || n > 32) return ""
    if (n === 0) return "0.0.0.0"
    if (n === 32) return "255.255.255.255"
    const mask = (~((1 << (32 - n)) - 1)) >>> 0
    return [
        (mask >>> 24) & 0xFF,
        (mask >>> 16) & 0xFF,
        (mask >>> 8)  & 0xFF,
         mask         & 0xFF
    ].join(".")
}

function prefixToWildcard(prefix) {
    const mask = prefixToSubnetMask(prefix)
    if (mask === "") return ""
    return mask.split(".").map(function(part) {
        return String(255 - parseInt(part, 10))
    }).join(".")
}

function parseCidrInput(text) {
    const str = String(text || "").trim()
    const cidrMatch = str.match(/^\/?\s*(\d{1,2})$/)
    if (cidrMatch) {
        const prefix = parseInt(cidrMatch[1], 10)
        if (prefix >= 0 && prefix <= 32) {
            return prefixToSubnetMask(prefix)
        }
        return ""
    }
    if (isValidSubnetMask(str)) return str
    return ""
}

// UI-P0-03: `-/24` is the explicit wildcard shorthand. Keeping the minus
// marker avoids interpreting `/24` differently depending on which form owns
// the field.
function parseWildcardInput(text) {
    const str = String(text || "").trim()
    const prefixMatch = str.match(/^-\s*\/\s*(\d{1,2})$/)
    if (prefixMatch) {
        const prefix = parseInt(prefixMatch[1], 10)
        return prefix >= 0 && prefix <= 32 ? prefixToWildcard(prefix) : ""
    }
    if (isValidWildcard(str)) return str
    return ""
}

// ────────────────────────────────────────────────────────────────────────────
// HOST (IP hoặc DOMAIN)
// ────────────────────────────────────────────────────────────────────────────

function isValidHostname(value) {
    const str = String(value || "").trim()
    if (str === "" || str.length > 253) return false
    const reDomain = /^(?=.{1,253}$)(?!-)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$/i
    return reDomain.test(str)
}

function isValidHost(value) {
    const str = String(value || "").trim()
    if (str === "") {
        return { ok: false, isIPv4: false, isDomain: false, reason: "Host is required." }
    }
    const ipv4 = isValidIPv4(str)
    const domain = isValidHostname(str)
    if (!ipv4 && !domain) {
        return {
            ok:       false,
            isIPv4:   false,
            isDomain: false,
            reason:   "Host must be a valid IPv4 address or domain name."
        }
    }
    return { ok: true, isIPv4: ipv4, isDomain: domain, reason: "" }
}

function isValidPrivateHost(value) {
    const result = isValidHost(value)
    if (!result.ok) return result
    if (result.isIPv4 && !isPrivateIPv4(value)) {
        return {
            ok:     false,
            reason: "IPv4 address must be private (10.x.x.x, 172.16–31.x.x, 192.168.x.x)."
        }
    }
    return { ok: true, reason: "" }
}

// ────────────────────────────────────────────────────────────────────────────
// CREDENTIALS
// ────────────────────────────────────────────────────────────────────────────

function isValidUsername(value) {
    const str = String(value || "").trim()
    if (str === "") return true
    return /^[A-Za-z0-9_.-]+$/.test(str)
}

function isValidPassword(value) {
    const str = String(value || "")
    if (str === "") return true
    return /^[^\s]+$/.test(str)
}

// ────────────────────────────────────────────────────────────────────────────
// PORT
// ────────────────────────────────────────────────────────────────────────────

var DEFAULT_PORTS = {
    "SSH":      22,
    "TELNET":   23,
    "NETCONF":  830,
    "RESTCONF": 443
}

function isValidPort(value) {
    const n = parseInt(String(value), 10)
    return !isNaN(n) && n >= 1 && n <= 65535
}

function normalizePort(portText, method) {
    const n = parseInt(String(portText || ""), 10)
    if (!isNaN(n) && n >= 1 && n <= 65535) return n
    const upper = String(method || "").toUpperCase()
    return DEFAULT_PORTS[upper] !== undefined ? DEFAULT_PORTS[upper] : 22
}

// ────────────────────────────────────────────────────────────────────────────
// ROUTING
// ────────────────────────────────────────────────────────────────────────────

function parseMetricWeights(value) {
    const str = String(value || "").trim()
    const tokens = str.split(/\s+/)
    if (tokens.length !== 6) {
        return { ok: false, reason: "Metric weights must have exactly 6 values (0 k1 k2 k3 k4 k5)." }
    }
    if (tokens[0] !== "0") {
        return { ok: false, reason: "First metric weight value must be 0." }
    }
    const result = { ok: true, k1: 0, k2: 0, k3: 0, k4: 0, k5: 0 }
    const keys = ["k1", "k2", "k3", "k4", "k5"]
    for (let i = 1; i <= 5; i++) {
        const n = parseInt(tokens[i], 10)
        if (isNaN(n) || n < 0 || n > 255) {
            return {
                ok:     false,
                reason: "Metric weight values k1–k5 must be integers between 0 and 255."
            }
        }
        result[keys[i - 1]] = n
    }
    return result
}

function isValidAsNumber(value) {
    const n = parseInt(String(value || ""), 10)
    return !isNaN(n) && n >= 1 && n <= 65535
}

function isValidOspfProcessId(value) {
    const raw = String(value === undefined || value === null ? "" : value).trim()
    if (!/^\d+$/.test(raw)) return false
    const n = Number(raw)
    return Number.isSafeInteger(n) && n >= 1 && n <= 65535
}

function isValidAdValue(value) {
    const n = parseInt(String(value || ""), 10)
    return !isNaN(n) && n >= 1 && n <= 255
}

function normalizeAd(value, fallback) {
    const n = parseInt(String(value || ""), 10)
    if (!isNaN(n) && n >= 1 && n <= 255) return n
    return fallback !== undefined ? fallback : 1
}
