import AVFoundation
import Foundation
import UIKit

@MainActor
final class CameraModel: ObservableObject {
    @Published private(set) var permissionDenied = false
    @Published private(set) var isCapturing = false
    @Published private(set) var matchedRecords: [PhotoRecord] = []
    private let configuration = MatchingConfiguration()
    @Published var errorMessage: String?
    @Published var shareNotice: String?
    @Published private(set) var pendingCapture: PendingCapture?
    @Published private(set) var isSavingCapture = false
    @Published private(set) var captureSaveError: String?
    @Published private(set) var shareRetryRecord: PhotoRecord?
    @Published private(set) var isSharing = false
    @Published private(set) var isReceiving = false
    @Published private(set) var captureFeatureCount: Int?
    @Published private(set) var captureHintOverride: String?
    private let qualityQueue = DispatchQueue(label: "capture.readiness", qos: .userInitiated)
    private var qualityInFlight = false
    private var lastQualityCheck = Date.distantPast
    private var lastQualityResult = Date.distantPast

    var canCapture: Bool {
        isActive && pendingCapture == nil && !isCapturing && !permissionDenied && (captureFeatureCount ?? 0) >= 8
            && Date().timeIntervalSince(lastQualityResult) < 1.5
    }

    var captureHint: String? {
        if let captureHintOverride { return captureHintOverride }
        guard !permissionDenied else { return nil }
        guard let captureFeatureCount else { return String(localized: "風景を確認しています…") }
        return captureFeatureCount < 8 ? String(localized: "風景の特徴が少ないため撮影できません。\n模様や輪郭のある場所に向けてください。") : nil
    }
    private let sharing = PhotoSharingClient()
    private var pendingShares: [String] = []
    private var receivingID: String?

    let camera = CameraSession()
    let repository: PhotoRepository

    private let matcher: MatchingEngine
    private let extractor = OpenCVFeatureExtractor()
    private let stabilizer = MatchStabilizer()
    private let matchingQueue = DispatchQueue(label: "matching.analysis", qos: .userInitiated)
    private var analysisInFlight = false
    private var analysisGeneration = 0
    private var isActive = false
    private var lastAnalysisTime = Date.distantPast
    private let analysisInterval: TimeInterval = 0.65
    init(repository: PhotoRepository = PhotoRepository()) {
        self.repository = repository
        matcher = MatcherRegistry.makeDefault(repository: repository)
        camera.delegate = self
    }

    func start() async {
        let generation = analysisGeneration
        rebuildLegacyIndexIfNeeded()
        permissionDenied = !(await camera.requestAccessAndStart())
        guard generation == analysisGeneration else {
            camera.stop()
            return
        }
        isActive = !permissionDenied
    }

    func stop() {
        isActive = false
        captureFeatureCount = nil
        qualityInFlight = false
        lastQualityResult = .distantPast
        analysisGeneration += 1
        analysisInFlight = false
        stabilizer.reset()
        matchedRecords = []
        camera.stop()
    }

    func capture() {
        guard canCapture else { return }
        isCapturing = true
        camera.capturePhoto()
    }

    func imageData(for record: PhotoRecord) -> Data? {
        repository.imageData(for: record)
    }

    func copyShareLink(for record: PhotoRecord) {
        guard !isSharing, !record.isReceived else { return }
        isSharing = true
        shareRetryRecord = nil
        Task {
            defer { isSharing = false }
            do {
                guard let data = repository.imageData(for: record), let image = UIImage(data: data),
                      let jpeg = image.sharingJPEG() else {
                    throw PhotoSharingClient.SharingError.invalid
                }
                let share = try await sharing.create(record: record, jpeg: jpeg)
                UIPasteboard.general.url = share.url
                shareNotice = String(localized: "リンクをコピーしました。リンクは30日間有効です。")
            } catch {
                shareRetryRecord = record
                errorMessage = String(localized: "写真は保存しましたが、共有できませんでした。通信を確認して再試行してください。")
            }
        }
    }

    func discardPendingCapture() {
        guard !isSavingCapture else { return }
        pendingCapture = nil
        captureSaveError = nil
    }

    func savePendingCapture(share: Bool) {
        guard let draft = pendingCapture, !isSavingCapture else { return }
        isSavingCapture = true
        captureSaveError = nil
        let repository = repository
        matchingQueue.async { [weak self] in
            do {
                let record = try repository.save(jpegData: draft.jpegData, featureData: draft.featureData,
                    featureAlgorithm: OpenCVFeatureExtractor.algorithm, id: draft.id, capturedAt: draft.capturedAt)
                Task { @MainActor in
                    guard let self else { return }
                    self.isSavingCapture = false
                    self.pendingCapture = nil
                    if share {
                        Task { @MainActor [weak self] in
                            // Let the review close before presenting a copy/retry alert.
                            try? await Task.sleep(for: .seconds(0.45))
                            self?.copyShareLink(for: record)
                        }
                    }
                }
            } catch {
                Task { @MainActor in
                    self?.isSavingCapture = false
                    self?.captureSaveError = String(localized: "写真を保存できませんでした。もう一度お試しください。")
                }
            }
        }
    }

    func receiveShare(_ url: URL) {
        guard let id = RecallShareLink.identifier(from: url, baseURL: sharing.baseURL) else {
            errorMessage = String(localized: "この共有リンクは読み込めません。"); return
        }
        guard id != receivingID, !pendingShares.contains(id) else { return }
        pendingShares.append(id)
        guard !isReceiving else { return }
        isReceiving = true
        Task {
            defer { isReceiving = false; receivingID = nil }
            while !pendingShares.isEmpty {
                let id = pendingShares.removeFirst()
                receivingID = id
                if repository.records().contains(where: { $0.sourceShareID == id }) {
                    shareNotice = String(localized: "この写真は受け取り済みです。風景が一致すると表示されます。")
                    continue
                }
                do {
                    let payload = try await sharing.receive(id: id)
                    let repository = repository
                    let _: PhotoRecord = try await withCheckedThrowingContinuation { continuation in
                        matchingQueue.async {
                            do {
                                guard UIImage(data: payload.photo) != nil else { throw PhotoSharingClient.SharingError.invalid }
                                let record = try repository.save(jpegData: payload.photo, featureData: payload.featureData,
                                    featureAlgorithm: payload.featureAlgorithm, id: payload.recordId,
                                    capturedAt: Date(timeIntervalSince1970: payload.capturedAt), sourceShareID: id)
                                continuation.resume(returning: record)
                            } catch { continuation.resume(throwing: error) }
                        }
                    }
                    shareNotice = String(localized: "写真を受け取りました。その風景にカメラを向けると表示されます。")
                } catch { errorMessage = error.localizedDescription }
            }
        }
    }

    private func analyze(_ pixelBuffer: CVPixelBuffer) {
        let now = Date()
        updateCaptureReadiness(pixelBuffer, now: now)
        guard isActive, pendingCapture == nil, !isSharing, !isReceiving, !analysisInFlight, now.timeIntervalSince(lastAnalysisTime) >= analysisInterval else { return }
        analysisInFlight = true
        lastAnalysisTime = now
        let records = repository.records()
        let configuration = configuration
        let matcher = matcher
        let generation = analysisGeneration
        let frame = SendablePixelBuffer(pixelBuffer)

        matchingQueue.async { [weak self] in
            guard let self else { return }
            do {
                let candidates = try matcher.findMatches(
                    for: frame.value,
                    among: records,
                    topK: configuration.topK
                )
                Task { @MainActor in
                    await self.finishAnalysis(
                        candidates: candidates,
                        records: records,
                        configuration: configuration,
                        generation: generation
                    )
                }
            } catch {
                Task { @MainActor in
                    guard self.isActive, generation == self.analysisGeneration else { return }
                    self.analysisInFlight = false
                    self.stabilizer.reset()
                    self.matchedRecords = []
                    let failure = error as NSError
                    if failure.domain != "RecallLens.OpenCV" || failure.code != 4 {
                        self.errorMessage = error.localizedDescription
                    }
                }
            }
        }
    }

    private func updateCaptureReadiness(_ buffer: CVPixelBuffer, now: Date) {
        guard isActive, pendingCapture == nil, !qualityInFlight, now.timeIntervalSince(lastQualityCheck) >= 0.4 else { return }
        qualityInFlight = true
        lastQualityCheck = now
        let generation = analysisGeneration
        let frame = SendablePixelBuffer(buffer)
        let extractor = extractor
        qualityQueue.async { [weak self] in
            let count: Int
            do {
                let data = try extractor.featureData(for: frame.value)
                count = FeatureSignature.keypointCount(data)
            } catch { count = 0 }
            Task { @MainActor in
                guard let self, self.isActive, self.analysisGeneration == generation else { return }
                self.lastQualityResult = Date()
                self.captureFeatureCount = count
                self.qualityInFlight = false
            }
        }
    }

    private func finishAnalysis(
        candidates: [MatchCandidate],
        records: [PhotoRecord],
        configuration: MatchingConfiguration,
        generation: Int
    ) async {
        guard isActive, generation == analysisGeneration else { return }
        let visibleIDs = stabilizer.update(
            candidates: candidates,
            configuration: configuration
        )
        matchedRecords = records
            .filter { visibleIDs.contains($0.id) }
            .sorted { $0.capturedAt > $1.capturedAt }
        analysisInFlight = false
    }

}

private struct SendablePixelBuffer: @unchecked Sendable {
    let value: CVPixelBuffer

    init(_ value: CVPixelBuffer) {
        self.value = value
    }
}

extension CameraModel: CameraSessionDelegate {
    nonisolated func cameraSession(_ session: CameraSession, didOutput pixelBuffer: CVPixelBuffer) {
        Task { @MainActor [weak self] in self?.analyze(pixelBuffer) }
    }

    nonisolated func cameraSession(_ session: CameraSession, didCapture data: Data) {
        Task { @MainActor [weak self] in
            guard let self else { return }
            self.persistCapture(data)
        }
    }

    nonisolated func cameraSession(_ session: CameraSession, didFail error: Error) {
        Task { @MainActor [weak self] in
            self?.isCapturing = false
            self?.errorMessage = error.localizedDescription
        }
    }

    private func persistCapture(_ data: Data) {
        let extractor = extractor
        matchingQueue.async { [weak self] in
            do {
                guard let image = UIImage(data: data) else {
                    throw PhotoRepository.RepositoryError.invalidImage
                }
                let feature = try extractor.featureData(for: image)
                guard FeatureSignature.keypointCount(feature) >= 8 else {
                    throw NSError(domain: "RecallLens.OpenCV", code: 2)
                }
                let draft = PendingCapture(jpegData: data, featureData: feature)
                Task { @MainActor in
                    guard let self else { return }
                    self.isCapturing = false
                    self.captureSaveError = nil
                    self.pendingCapture = draft
                }
            } catch {
                Task { @MainActor in
                    guard let self else { return }
                    self.isCapturing = false
                    let failure = error as NSError
                    if failure.domain == "RecallLens.OpenCV", failure.code == 2 {
                        self.captureFeatureCount = 0
                        self.captureHintOverride = String(localized: "写真の特徴を読み取れませんでした。\n少し向きを変えて撮り直してください。")
                        Task { @MainActor [weak self] in
                            try? await Task.sleep(for: .seconds(3))
                            self?.captureHintOverride = nil
                        }
                    } else {
                        self.errorMessage = error.localizedDescription
                    }
                }
            }
        }
    }

    private func rebuildLegacyIndexIfNeeded() {
        guard repository.needsIndexRebuild() else { return }
        let repository = repository
        let extractor = extractor
        matchingQueue.async { [weak self] in
            do {
                try repository.rebuildIndex(extractor: extractor)
                // The repository migration is complete; the next camera frame reads the updated index.
            } catch {
                Task { @MainActor in self?.errorMessage = error.localizedDescription }
            }
        }
    }
}

