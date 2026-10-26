import Foundation

struct PendingCapture: Identifiable {
    let id = UUID()
    let capturedAt = Date()
    let jpegData: Data
    let featureData: Data
}
