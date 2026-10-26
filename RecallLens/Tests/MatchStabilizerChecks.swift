import Foundation

@main
struct MatchStabilizerChecks {
    static func main() {
        let record = PhotoRecord(id: UUID(), filename: "test", capturedAt: Date(),
                                 featureData: Data(), featureAlgorithm: "test")
        let candidate = MatchCandidate(record: record, similarity: 1, distance: 0)
        let allowed: Set<UUID> = [record.id]
        let config = MatchingConfiguration()
        let now = Date()
        for reason in ["denied", "prefilter rejected", "network failed", "different candidate"] {
            let stabilizer = MatchStabilizer()
            assert(stabilizer.update(candidates: [candidate], configuration: config,
                                    authorizedIDs: allowed, now: now).isEmpty)
            assert(stabilizer.update(candidates: [candidate], configuration: config,
                                    authorizedIDs: allowed, now: now).contains(record.id))
            let nextAllowed: Set<UUID> = reason == "different candidate" ? [UUID()] : []
            assert(stabilizer.update(candidates: [candidate], configuration: config,
                                    authorizedIDs: nextAllowed, now: now).isEmpty,
                   "Revocation must override the minimum hold and smoothing: \(reason)")
            assert(stabilizer.update(candidates: [candidate], configuration: config,
                                    authorizedIDs: allowed, now: now).isEmpty,
                   "Reauthorization must require fresh consecutive matches")
        }
        let local = MatchStabilizer()
        _ = local.update(candidates: [candidate], configuration: config, now: now)
        assert(local.update(candidates: [candidate], configuration: config, now: now).contains(record.id))
        assert(local.update(candidates: [], configuration: config, now: now).contains(record.id))
        local.reset()
        assert(local.visibleIDs.isEmpty)
        print("MatchStabilizer: cloud revocation, fresh authorization, local smoothing, reset passed")
    }
}
