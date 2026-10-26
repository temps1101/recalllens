import SwiftUI

struct CaptureReviewView: View {
    @ObservedObject var model: CameraModel
    let capture: PendingCapture

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            VStack(spacing: 20) {
                Spacer()
                if let image = UIImage(data: capture.jpegData) {
                    Image(uiImage: image).resizable().scaledToFit()
                }
                Spacer()
                if let error = model.captureSaveError {
                    Text(error).font(.footnote).foregroundStyle(.orange)
                        .multilineTextAlignment(.center).padding(.horizontal)
                }
                if model.isSavingCapture {
                    ProgressView(String(localized: "保存しています…")).tint(.white)
                }
                HStack(spacing: 28) {
                    Button(role: .destructive) { model.discardPendingCapture() } label: {
                        Label(String(localized: "破棄"), systemImage: "trash")
                    }
                    Button { model.savePendingCapture(share: false) } label: {
                        Label(String(localized: "保存"), systemImage: "checkmark")
                    }
                    .buttonStyle(.borderedProminent).tint(.white).foregroundStyle(.black)
                    Button { model.savePendingCapture(share: true) } label: {
                        Label(String(localized: "共有"), systemImage: "square.and.arrow.up")
                    }
                }
                .font(.body.weight(.semibold))
                .disabled(model.isSavingCapture)
                Text(String(localized: "共有すると写真をサーバーに保存し、リンクをコピーします。"))
                    .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    .padding(.horizontal, 24)
            }
            .foregroundStyle(.white).padding(.vertical, 24)
        }
        .interactiveDismissDisabled()
    }
}
