import SwiftUI

struct CameraScreen: View {
    @ObservedObject var model: CameraModel
    @Environment(\.scenePhase) private var scenePhase
    @State private var showingMatches = false
    @State private var openedRecords: [PhotoRecord] = []

    var body: some View {
        ZStack {
            CameraPreview(session: model.camera.captureSession)
                .ignoresSafeArea()

            LinearGradient(
                colors: [.clear, .black.opacity(0.58)],
                startPoint: .center,
                endPoint: .bottom
            )
            .ignoresSafeArea()
            .allowsHitTesting(false)

            VStack {
                topBar
                Spacer()
                if model.isSharing || model.isReceiving {
                    HStack(spacing: 10) {
                        ProgressView().tint(.white)
                        Text(model.isSharing ? String(localized: "共有リンクを準備しています") : String(localized: "写真を受け取っています"))
                    }
                    .padding(14).background(.ultraThinMaterial, in: Capsule())
                    .padding(.bottom, 16)
                }
                if let hint = model.captureHint {
                    Text(hint)
                        .font(.footnote).multilineTextAlignment(.center)
                        .foregroundStyle(.white.opacity(0.9))
                        .padding(.horizontal, 16).padding(.vertical, 10)
                        .background(.black.opacity(0.45), in: RoundedRectangle(cornerRadius: 12))
                        .padding(.bottom, 12)
                        .accessibilityIdentifier("captureGuidance")
                }
                HStack {
                    Group {
                        if let record = model.matchedRecords.first {
                            Button {
                                openedRecords = model.matchedRecords
                                showingMatches = true
                            } label: {
                                PhotoThumbnail(record: record, repository: model.repository, width: 52, height: 52)
                                    .overlay(RoundedRectangle(cornerRadius: 9).stroke(.white.opacity(0.7), lineWidth: 1))
                            }
                            .accessibilityLabel(String(localized: "見つかった写真を開く"))
                            .accessibilityValue(String(format: NSLocalizedString("%d枚", comment: "Matching photo count"), model.matchedRecords.count))
                        } else {
                            Color.clear.frame(width: 52, height: 52)
                        }
                    }
                    Spacer()
                    shutter
                    Spacer()
                    Color.clear.frame(width: 52, height: 52)
                }
                    .padding(.horizontal, 32)
                    .padding(.bottom, 30)
            }

            if model.permissionDenied {
                permissionMessage
            }
        }
        .task { await model.start() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active {
                Task { await model.start() }
            } else {
                model.stop()
            }
        }
        .fullScreenCover(isPresented: $showingMatches) {
            MatchedPhotosView(model: model, records: openedRecords)
        }
        .fullScreenCover(item: Binding(get: { model.pendingCapture }, set: { if $0 == nil { model.discardPendingCapture() } })) { capture in
            CaptureReviewView(model: model, capture: capture)
        }
        .alert(model.errorMessage != nil ? String(localized: "エラー") : "Recalllens", isPresented: errorBinding) {
            if let record = model.shareRetryRecord, model.errorMessage != nil {
                Button(String(localized: "再試行")) { model.errorMessage = nil; model.copyShareLink(for: record) }
            }
            Button(String(localized: "閉じる"), role: .cancel) { model.errorMessage = nil; model.shareNotice = nil }
        } message: {
            Text(model.errorMessage ?? model.shareNotice ?? "")
        }
    }

    private var topBar: some View {
        HStack {
            Spacer()
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 18)
        .animation(.easeOut(duration: 0.2), value: model.matchedRecords.count)
    }

    private var shutter: some View {
        Button(action: model.capture) {
            ZStack {
                Circle().stroke(.white, lineWidth: 4).frame(width: 76, height: 76)
                Circle().fill(.white).frame(width: 62, height: 62)
                    .scaleEffect(model.isCapturing ? 0.9 : 1)
            }
        }
        .disabled(!model.canCapture)
        .opacity(model.canCapture ? 1 : 0.35)
        .accessibilityLabel(String(localized: "撮影"))
        .accessibilityHint(model.captureHint ?? String(localized: "写真を保存します"))
    }

    private var permissionMessage: some View {
        VStack(spacing: 12) {
            Image(systemName: "camera.fill")
                .font(.largeTitle)
            Text(String(localized: "カメラへのアクセスが必要です"))
                .font(.headline)
            Text(String(localized: "設定で Recalllens のカメラアクセスを許可してください。"))
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(28)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 20))
        .padding(32)
    }

    private var errorBinding: Binding<Bool> {
        Binding(
            get: { model.errorMessage != nil || model.shareNotice != nil },
            set: { if !$0 { model.errorMessage = nil; model.shareNotice = nil } }
        )
    }
}

