import Foundation

@main
struct ShareLinkChecks {
    static func main() throws {
        let token = String(repeating: "a", count: 32)
        let base = URL(string: "https://example.com/prod")!
        func parse(_ value: String) -> String? { RecallShareLink.identifier(from: URL(string: value)!, baseURL: base) }
        precondition(parse("recalllens://receive/\(token)") == token)
        precondition(parse("https://example.com/prod/s/\(token)") == token)
        for bad in ["https://evil.example/prod/s/\(token)", "recalllens://wrong/\(token)",
                    "recalllens://receive/short", "recalllens://receive/\(token)?url=https://evil.example",
                    "https://example.com/other/s/\(token)", "https://user@example.com/prod/s/\(token)"] {
            precondition(parse(bad) == nil)
        }
        let old = """
        {"id":"96c95be0-8796-4d7b-b44c-bdf0be13ed46","filename":"photo.jpg","capturedAt":0,"featureData":"AQ==","featureAlgorithm":"opencv-5-orb-v1"}
        """.data(using: .utf8)!
        let record = try JSONDecoder().decode(PhotoRecord.self, from: old)
        precondition(!record.isReceived)
        var received = record; received.sourceShareID = token
        let roundTrip = try JSONDecoder().decode(PhotoRecord.self, from: JSONEncoder().encode(received))
        precondition(roundTrip.isReceived && roundTrip.sourceShareID == token)
        print("Share links reject foreign/malformed URLs; legacy and received records round-trip.")
    }
}
