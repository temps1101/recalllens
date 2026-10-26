import Foundation

struct PhotoRecord: Codable, Identifiable, Hashable {
    let id: UUID
    let filename: String
    let capturedAt: Date
    var featureData: Data
    var featureAlgorithm: String
    var sourceShareID: String?
    var isReceived: Bool { sourceShareID != nil }

    private enum CodingKeys: String, CodingKey {
        case id, filename, capturedAt, featureData, featureAlgorithm, sourceShareID
        case legacyFeaturePrint = "featurePrint"
    }

    init(
        id: UUID,
        filename: String,
        capturedAt: Date,
        featureData: Data,
        featureAlgorithm: String,
        sourceShareID: String? = nil
    ) {
        self.id = id
        self.filename = filename
        self.capturedAt = capturedAt
        self.featureData = featureData
        self.featureAlgorithm = featureAlgorithm
        self.sourceShareID = sourceShareID
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        id = try values.decode(UUID.self, forKey: .id)
        filename = try values.decode(String.self, forKey: .filename)
        capturedAt = try values.decode(Date.self, forKey: .capturedAt)
        featureData = try values.decodeIfPresent(Data.self, forKey: .featureData)
            ?? values.decode(Data.self, forKey: .legacyFeaturePrint)
        featureAlgorithm = try values.decodeIfPresent(String.self, forKey: .featureAlgorithm)
            ?? "vision-feature-print-v1"
        sourceShareID = try values.decodeIfPresent(String.self, forKey: .sourceShareID)
    }

    func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: CodingKeys.self)
        try values.encode(id, forKey: .id)
        try values.encode(filename, forKey: .filename)
        try values.encode(capturedAt, forKey: .capturedAt)
        try values.encode(featureData, forKey: .featureData)
        try values.encode(featureAlgorithm, forKey: .featureAlgorithm)
        try values.encodeIfPresent(sourceShareID, forKey: .sourceShareID)
    }
}

struct MatchCandidate: Identifiable {
    let record: PhotoRecord
    let similarity: Float
    let distance: Float

    var id: UUID { record.id }
}

struct MatchingConfiguration: Equatable {
    var entryThreshold: Float = 0.62
    var exitThreshold: Float = 0.56
    var smoothingAlpha: Float = 0.35
    var entryFrames = 2
    var exitFrames = 3
    var minimumHoldSeconds = 1.2
    var topK = 5
}

