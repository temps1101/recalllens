import SwiftUI

struct MatchedPhotosView: View {
    @ObservedObject var model: CameraModel
    // A deliberate open keeps this snapshot visible until the user closes it.
    // The camera's match badges continue to track the live scene independently.
    let records: [PhotoRecord]
    @Environment(\.dismiss) private var dismiss
    @State private var selection = 0

    var body: some View {
        ZStack(alignment: .topTrailing) {
            Color.black.ignoresSafeArea()
            TabView(selection: $selection) {
                ForEach(Array(records.enumerated()), id: \.element.id) { index, record in
                    photo(record)
                        .tag(index)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: records.count > 1 ? .automatic : .never))

            Button { dismiss() } label: {
                Image(systemName: "xmark")
                    .font(.system(size: 16, weight: .semibold))
                    .frame(width: 42, height: 42)
                    .background(.ultraThinMaterial, in: Circle())
            }
            .foregroundStyle(.white)
            .padding(18)
            .accessibilityLabel(String(localized: "閉じる"))
        }
    }

    @ViewBuilder
    private func photo(_ record: PhotoRecord) -> some View {
        if let data = model.imageData(for: record), let image = UIImage(data: data) {
            VStack(spacing: 12) {
                Spacer()
                Text(record.isReceived ? String(localized: "受け取った写真") : String(localized: "自分の写真"))
                    .font(.subheadline.weight(.semibold)).foregroundStyle(.white)
                Image(uiImage: image)
                    .resizable()
                    .scaledToFit()
                Text(record.capturedAt.formatted(date: .abbreviated, time: .shortened))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
            }
        } else {
            ContentUnavailableView(String(localized: "写真を読み込めません"), systemImage: "photo")
        }
    }
}

