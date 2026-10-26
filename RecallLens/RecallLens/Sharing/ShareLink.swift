import Foundation

enum RecallShareLink {
    static func validID(_ value: String) -> Bool {
        value.range(of: "^[A-Za-z0-9_-]{32}$", options: .regularExpression) != nil
    }

    static func identifier(from url: URL, baseURL: URL?) -> String? {
        guard url.user == nil, url.password == nil, url.query == nil, url.fragment == nil else { return nil }
        let parts = url.pathComponents.filter { $0 != "/" }
        if url.scheme == "recalllens", url.host == "receive", url.port == nil,
           parts.count == 1, validID(parts[0]) { return parts[0] }
        if let baseURL, url.scheme == "https", url.host == baseURL.host, url.port == baseURL.port {
            let expected = baseURL.pathComponents.filter { $0 != "/" } + ["s"]
            if parts.count == expected.count + 1, Array(parts.dropLast()) == expected,
               let id = parts.last, validID(id) { return id }
        }
        return nil
    }
}
