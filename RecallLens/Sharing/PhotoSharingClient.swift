import Foundation
import UIKit

struct CreatedShare: Codable {
    let shareId: String
    let url: URL
    let expiresAt: Double
}

struct ReceivedShare: Decodable {
    let shareId: String
    let recordId: UUID
    let photo: Data
    let featureData: Data
    let featureAlgorithm: String
    let capturedAt: Double
    let expiresAt: Double
}

final class PhotoSharingClient {
    enum SharingError: LocalizedError {
        case unavailable, invalid, expired, network(Int)
        var errorDescription: String? {
            switch self {
            case .unavailable: String(localized: "共有の接続先が設定されていません。")
            case .invalid: String(localized: "写真の共有データを読み込めませんでした。")
            case .expired: String(localized: "この共有リンクは期限切れか、見つかりません。")
            case .network: String(localized: "写真を受け渡しできませんでした。通信を確認して、もう一度お試しください。")
            }
        }
    }

    let baseURL: URL?
    private let token: String
    init(bundle: Bundle = .main) {
        baseURL = (bundle.object(forInfoDictionaryKey: "WBCloudVerificationURL") as? String)
            .flatMap(URL.init(string:))?.deletingLastPathComponent()
        token = bundle.object(forInfoDictionaryKey: "WBCloudVerificationToken") as? String ?? ""
    }

    func create(record: PhotoRecord, jpeg: Data) async throws -> CreatedShare {
        let key = "recallLens.sentShare.\(record.id.uuidString)"
        if let data = UserDefaults.standard.data(forKey: key),
           let saved = try? JSONDecoder().decode(CreatedShare.self, from: data),
           saved.expiresAt > Date().timeIntervalSince1970 + 60,
           RecallShareLink.identifier(from: saved.url, baseURL: baseURL) == saved.shareId { return saved }
        guard let baseURL, baseURL.scheme == "https", token.count >= 24 else { throw SharingError.unavailable }
        var request = URLRequest(url: baseURL.appendingPathComponent("shares"))
        request.httpMethod = "POST"
        request.setValue(token, forHTTPHeaderField: "x-api-key")
        request.setValue("application/json", forHTTPHeaderField: "content-type")
        request.httpBody = try JSONSerialization.data(withJSONObject: [
            "photo": jpeg.base64EncodedString(),
            "featureData": record.featureData.base64EncodedString(),
            "featureAlgorithm": record.featureAlgorithm,
            "capturedAt": record.capturedAt.timeIntervalSince1970
        ])
        let share = try JSONDecoder().decode(CreatedShare.self, from: await send(request))
        guard RecallShareLink.validID(share.shareId), RecallShareLink.identifier(from: share.url, baseURL: baseURL) == share.shareId else { throw SharingError.invalid }
        UserDefaults.standard.set(try JSONEncoder().encode(share), forKey: key)
        return share
    }

    func receive(id: String) async throws -> ReceivedShare {
        guard RecallShareLink.validID(id), let baseURL, baseURL.scheme == "https" else { throw SharingError.invalid }
        let request = URLRequest(url: baseURL.appendingPathComponent("shares").appendingPathComponent(id))
        let share = try JSONDecoder().decode(ReceivedShare.self, from: await send(request))
        guard share.shareId == id, share.photo.count <= 1_500_000,
              share.featureData.count <= 256_000,
              share.featureAlgorithm == OpenCVFeatureExtractor.algorithm,
              FeatureSignature.keypointCount(share.featureData) >= 8,
              share.capturedAt.isFinite, share.capturedAt >= 0 else { throw SharingError.invalid }
        guard share.expiresAt > Date().timeIntervalSince1970 else { throw SharingError.expired }
        return share
    }

    private func send(_ input: URLRequest) async throws -> Data {
        var request = input
        request.timeoutInterval = 30
        request.cachePolicy = .reloadIgnoringLocalCacheData
        // Retry only explicit throttling/service-unavailable replies, not ambiguous POST timeouts.
        for attempt in 0..<3 {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse else { throw SharingError.invalid }
            if [429, 503].contains(http.statusCode), attempt < 2 {
                try await Task.sleep(for: .seconds(Double(attempt + 1) * 1.5)); continue
            }
            if [404, 410].contains(http.statusCode) { throw SharingError.expired }
            guard (200..<300).contains(http.statusCode) else { throw SharingError.network(http.statusCode) }
            guard data.count <= 2_500_000 else { throw SharingError.invalid }
            return data
        }
        throw SharingError.network(429)
    }
}

extension UIImage {
    func sharingJPEG(maximumDimension: CGFloat = 1600) -> Data? {
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
