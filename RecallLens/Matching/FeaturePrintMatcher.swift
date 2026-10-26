import Foundation
import UIKit

protocol MatchingEngine: AnyObject, Sendable {
    var name: String { get }
    func findMatches(for pixelBuffer: CVPixelBuffer, among records: [PhotoRecord], topK: Int) throws -> [MatchCandidate]
}

final class OpenCVFeatureExtractor: @unchecked Sendable {
    static let algorithm = "opencv-5-orb-v1"

    func featureData(for image: UIImage) throws -> Data {
        try WBOpenCVBridge.featureData(for: image)
    }

    func featureData(for pixelBuffer: CVPixelBuffer) throws -> Data {
        try WBOpenCVBridge.featureData(for: pixelBuffer)
    }
}

final class OpenCVGeometricMatcher: MatchingEngine, @unchecked Sendable {
    let name = "OpenCV \(WBOpenCVBridge.versionString()) ORB + RANSAC"
    private let repository: PhotoRepository
    private let extractor: OpenCVFeatureExtractor

    init(repository: PhotoRepository, extractor: OpenCVFeatureExtractor = OpenCVFeatureExtractor()) {
        self.repository = repository
        self.extractor = extractor
    }

    func findMatches(
        for pixelBuffer: CVPixelBuffer,
        among records: [PhotoRecord],
        topK: Int
    ) throws -> [MatchCandidate] {
        let liveFeature = try extractor.featureData(for: pixelBuffer)
        return try records.compactMap { record in
            guard
                record.featureAlgorithm == OpenCVFeatureExtractor.algorithm
            else { return nil }
            let result = try WBOpenCVBridge.matchFeatureData(
                liveFeature,
                toFeatureData: record.featureData
            )
            return MatchCandidate(
                record: record,
                similarity: result.similarity,
                distance: result.meanDistance
            )
        }
        .sorted { $0.similarity > $1.similarity }
        .prefix(max(1, topK))
        .map { $0 }
    }

}

enum MatcherRegistry {
    static func makeDefault(repository: PhotoRepository) -> MatchingEngine {
        OpenCVGeometricMatcher(repository: repository)
    }
}

extension UIImage {
    var normalizedCGImage: CGImage? {
        if imageOrientation == .up, let cgImage { return cgImage }
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        let rendered = UIGraphicsImageRenderer(size: size, format: format).image { _ in
            draw(in: CGRect(origin: .zero, size: size))
        }
        return rendered.cgImage
    }
}

