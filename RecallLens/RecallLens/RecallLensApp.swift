import SwiftUI

@main
struct RecallLensApp: App {
    @StateObject private var model = CameraModel()

    var body: some Scene {
        WindowGroup {
            CameraScreen(model: model)
                .preferredColorScheme(.dark)
                .onOpenURL { model.receiveShare($0) }
        }
    }
}

