import Foundation
import UIKit

struct CloudVerificationResult: Decodable, Sendable {
    let authorized: Bool
    let referenceId: String
    let similarity: Float
    let goodMatches: Int
    let inliers: Int
    let inlierRatio: Float
    let engine: String
    let durationMs: Double
    let imagesRetained: Bool
}

final class CloudVerificationClient: @unchecked Sendable {
    enum VerificationError: LocalizedError {
        case invalidConfiguration
        case invalidResponse
        case rejected(Int)

        var errorDescription: String? {
            switch self {
            case .invalidConfiguration: String(localized: "AWS検証APIが設定されていません。")
            case .invalidResponse: String(localized: "AWS検証APIから不正な応答を受信しました。")
            case .rejected(let status): String(format: NSLocalizedString("AWS検証APIがリクエストを拒否しました（HTTP %d）。", comment: "Verification error"), status)
            }
        }
    }

    private struct RequestBody: Encodable {
        let queryImage: String
        let referenceId: String
    }

    private struct EnrollmentBody: Encodable {
        let referenceId: String
        let featureData: String
    }

    private let endpoint: URL?
    private let token: String
    private let session: URLSession

    var isConfigured: Bool {
        endpoint?.scheme == "https" && token.count >= 24
    }

    init(bundle: Bundle = .main, session: URLSession = .shared) {
        let endpointString = bundle.object(forInfoDictionaryKey: "WBCloudVerificationURL") as? String
        endpoint = endpointString.flatMap(URL.init(string:))
        token = bundle.object(forInfoDictionaryKey: "WBCloudVerificationToken") as? String ?? ""
        self.session = session
    }

    func enroll(referenceID: UUID, featureData: Data) async throws {
        guard isConfigured, let endpoint else { throw VerificationError.invalidConfiguration }
        let enrollmentEndpoint = endpoint.deletingLastPathComponent().appendingPathComponent("references")
        var request = URLRequest(url: enrollmentEndpoint)
        request.httpMethod = "POST"
        request.timeoutInterval = 20
        request.setValue("application/json", forHTTPHeaderField: "content-type")
        request.setValue(token, forHTTPHeaderField: "x-api-key")
        request.httpBody = try JSONEncoder().encode(EnrollmentBody(
            referenceId: referenceID.uuidString.lowercased(),
            featureData: featureData.base64EncodedString()
        ))
        // Registration is idempotent by UUID. Retry transient failures, including a cold-start timeout.
        for attempt in 0..<3 {
            do {
                let (_, response) = try await session.data(for: request)
                guard let httpResponse = response as? HTTPURLResponse else { throw VerificationError.invalidResponse }
                if [429, 502, 503, 504].contains(httpResponse.statusCode), attempt < 2 {
                    try await Task.sleep(for: .seconds(Double(attempt + 1) * 1.5)); continue
                }
                guard httpResponse.statusCode == 200 || httpResponse.statusCode == 201 else {
                    throw VerificationError.rejected(httpResponse.statusCode)
                }
                return
            } catch let error as URLError where attempt < 2 && [.timedOut, .networkConnectionLost].contains(error.code) {
                try await Task.sleep(for: .seconds(Double(attempt + 1) * 1.5))
            }
        }
    }

    func verify(queryJPEG: Data, referenceID: UUID) async throws -> CloudVerificationResult {
        guard isConfigured, let endpoint else { throw VerificationError.invalidConfiguration }
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.timeoutInterval = 5
        request.setValue("application/json", forHTTPHeaderField: "content-type")
        request.setValue(token, forHTTPHeaderField: "x-api-key")
        request.httpBody = try JSONEncoder().encode(RequestBody(
            queryImage: queryJPEG.base64EncodedString(),
            referenceId: referenceID.uuidString.lowercased()
        ))
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw VerificationError.invalidResponse
        }
        guard httpResponse.statusCode == 200 else {
            throw VerificationError.rejected(httpResponse.statusCode)
        }
        return try JSONDecoder().decode(CloudVerificationResult.self, from: data)
    }
}

extension UIImage {
    func cloudVerificationJPEG(maximumDimension: CGFloat = 960) -> Data? {
        let largest = max(size.width, size.height)
        guard largest > 0 else { return nil }
        let scale = min(1, maximumDimension / largest)
        let target = CGSize(width: size.width * scale, height: size.height * scale)
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        let rendered = UIGraphicsImageRenderer(size: target, format: format).image { _ in
            draw(in: CGRect(origin: .zero, size: target))
        }
        return rendered.jpegData(compressionQuality: 0.62)
    }
}
