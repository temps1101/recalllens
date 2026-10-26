import Foundation
import UIKit

final class PhotoRepository: @unchecked Sendable {
    enum RepositoryError: Error {
        case invalidImage
        case invalidFeaturePrint
    }

    private let fileManager: FileManager
    private let rootURL: URL
    private let capturesURL: URL
    private let indexURL: URL
    private let lock = NSLock()
    private var cachedRecords: [PhotoRecord] = []

    init(fileManager: FileManager = .default) {
        self.fileManager = fileManager
        let support = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let legacyRoot = support.appendingPathComponent("WeirdBoots", isDirectory: true)
        let recallLensRoot = support.appendingPathComponent("RecallLens", isDirectory: true)
        if !fileManager.fileExists(atPath: recallLensRoot.path),
           fileManager.fileExists(atPath: legacyRoot.path) {
            try? fileManager.moveItem(at: legacyRoot, to: recallLensRoot)
        }
        rootURL = recallLensRoot
        capturesURL = rootURL.appendingPathComponent("Captures", isDirectory: true)
        indexURL = rootURL.appendingPathComponent("photo-index.json")
        try? prepareDirectories()
        cachedRecords = (try? readIndex()) ?? []
    }

    func records() -> [PhotoRecord] {
        lock.withLock { cachedRecords.sorted { $0.capturedAt > $1.capturedAt } }
    }

    func imageURL(for record: PhotoRecord) -> URL {
        capturesURL.appendingPathComponent(record.filename)
    }

    func imageData(for record: PhotoRecord) -> Data? {
        try? Data(contentsOf: imageURL(for: record), options: .mappedIfSafe)
    }

    func save(jpegData: Data, featureData: Data, featureAlgorithm: String,
              id: UUID = UUID(), capturedAt: Date = Date(), sourceShareID: String? = nil) throws -> PhotoRecord {
        try lock.withLock {
        if let sourceShareID, let existing = cachedRecords.first(where: { $0.sourceShareID == sourceShareID }) {
            return existing
        }
        guard !cachedRecords.contains(where: { $0.id == id }) else { throw RepositoryError.invalidImage }
        guard UIImage(data: jpegData) != nil else { throw RepositoryError.invalidImage }
        let filename = "\(id.uuidString).jpg"
        let destination = capturesURL.appendingPathComponent(filename)
        try jpegData.write(to: destination, options: [.atomic, .completeFileProtection])
        var resourceValues = URLResourceValues()
        resourceValues.isExcludedFromBackup = true
        var mutableDestination = destination
        try? mutableDestination.setResourceValues(resourceValues)

        let record = PhotoRecord(
            id: id,
            filename: filename,
            capturedAt: capturedAt,
            featureData: featureData,
            featureAlgorithm: featureAlgorithm,
            sourceShareID: sourceShareID
        )
        do {
            let updated = cachedRecords + [record]
            try writeIndex(updated)
            cachedRecords = updated
        } catch {
            try? fileManager.removeItem(at: destination)
            throw error
        }
        return record
        }
    }

    func rebuildIndex(extractor: OpenCVFeatureExtractor) throws {
        let current = records()
        var rebuilt: [PhotoRecord] = []
        for var record in current {
            guard
                let data = imageData(for: record),
                let image = UIImage(data: data)
            else { continue }
            record.featureData = try extractor.featureData(for: image)
            record.featureAlgorithm = OpenCVFeatureExtractor.algorithm
            rebuilt.append(record)
        }
        try lock.withLock {
            cachedRecords = rebuilt
            try writeIndex(rebuilt)
        }
    }

    func needsIndexRebuild() -> Bool {
        records().contains { $0.featureAlgorithm != OpenCVFeatureExtractor.algorithm }
    }

    func reset() throws {
        let current = records()
        for record in current {
            try? fileManager.removeItem(at: imageURL(for: record))
        }
        try lock.withLock {
            cachedRecords = []
            try writeIndex([])
        }
    }

    private func prepareDirectories() throws {
        try fileManager.createDirectory(at: capturesURL, withIntermediateDirectories: true)
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        var mutableRoot = rootURL
        try? mutableRoot.setResourceValues(values)
    }

    private func readIndex() throws -> [PhotoRecord] {
        guard fileManager.fileExists(atPath: indexURL.path) else { return [] }
        return try JSONDecoder.recallLens.decode([PhotoRecord].self, from: Data(contentsOf: indexURL))
    }

    private func writeIndex(_ records: [PhotoRecord]) throws {
        let data = try JSONEncoder.recallLens.encode(records)
        try data.write(to: indexURL, options: [.atomic, .completeFileProtection])
    }
}

private extension JSONEncoder {
    static var recallLens: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return encoder
    }
}

private extension JSONDecoder {
    static var recallLens: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }
}

extension NSLocking {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}

