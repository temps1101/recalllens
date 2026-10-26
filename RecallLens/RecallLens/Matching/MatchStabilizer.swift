import Foundation

final class MatchStabilizer {
    private var smoothedScores: [UUID: Float] = [:]
    private var entryCounts: [UUID: Int] = [:]
    private var exitCounts: [UUID: Int] = [:]
    private var visibleSince: [UUID: Date] = [:]
    private(set) var visibleIDs = Set<UUID>()

    func update(
        candidates: [MatchCandidate],
        configuration: MatchingConfiguration,
        authorizedIDs: Set<UUID>? = nil,
        now: Date = Date()
    ) -> Set<UUID> {
        // Temporal smoothing must never extend a cloud authorization after revocation.
        if let authorizedIDs {
            visibleIDs.formIntersection(authorizedIDs)
            visibleSince = visibleSince.filter { authorizedIDs.contains($0.key) }
            prune(keeping: authorizedIDs)
        }
        let eligible = candidates.filter { authorizedIDs?.contains($0.id) ?? true }
        let raw = Dictionary(uniqueKeysWithValues: eligible.map { ($0.id, $0.similarity) })
        let allIDs = Set(smoothedScores.keys).union(raw.keys).union(visibleIDs)

        for id in allIDs {
            let previous = smoothedScores[id] ?? raw[id] ?? 0
            let current = raw[id] ?? 0
            let score = configuration.smoothingAlpha * current
                + (1 - configuration.smoothingAlpha) * previous
            smoothedScores[id] = score

            if visibleIDs.contains(id) {
                if score < configuration.exitThreshold {
                    exitCounts[id, default: 0] += 1
                } else {
                    exitCounts[id] = 0
                }
                let heldLongEnough = now.timeIntervalSince(visibleSince[id] ?? now)
                    >= configuration.minimumHoldSeconds
                if heldLongEnough, exitCounts[id, default: 0] >= configuration.exitFrames {
                    visibleIDs.remove(id)
                    visibleSince[id] = nil
                    exitCounts[id] = 0
                }
            } else {
                if score >= configuration.entryThreshold {
                    entryCounts[id, default: 0] += 1
                } else {
                    entryCounts[id] = 0
                }
                if entryCounts[id, default: 0] >= configuration.entryFrames {
                    visibleIDs.insert(id)
                    visibleSince[id] = now
                    entryCounts[id] = 0
                }
            }
        }

        prune(keeping: Set(raw.keys).union(visibleIDs))
        return visibleIDs
    }

    func reset() {
        smoothedScores.removeAll()
        entryCounts.removeAll()
        exitCounts.removeAll()
        visibleSince.removeAll()
        visibleIDs.removeAll()
    }

    private func prune(keeping ids: Set<UUID>) {
        smoothedScores = smoothedScores.filter { ids.contains($0.key) }
        entryCounts = entryCounts.filter { ids.contains($0.key) }
        exitCounts = exitCounts.filter { ids.contains($0.key) }
    }
}

