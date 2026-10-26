import ImageIO
import SwiftUI

struct PhotoThumbnail: View {
    let record: PhotoRecord
    let repository: PhotoRepository
    var width: CGFloat
    var height: CGFloat
    @State private var thumbnail: UIImage?

    var body: some View {
        Group {
            if let thumbnail {
                Image(uiImage: thumbnail).resizable().scaledToFill()
            } else {
                Color.black.opacity(0.2).overlay(Image(systemName: "photo").foregroundStyle(.secondary))
            }
        }
        .frame(width: width, height: height)
        .clipShape(RoundedRectangle(cornerRadius: 9))
        .task(id: record.id) {
            let record = record
            let repository = repository
            thumbnail = await Task.detached(priority: .userInitiated) {
                guard let data = repository.imageData(for: record),
                      let source = CGImageSourceCreateWithData(data as CFData, nil),
                      let image = CGImageSourceCreateThumbnailAtIndex(source, 0, [
                        kCGImageSourceCreateThumbnailFromImageAlways: true,
                        kCGImageSourceCreateThumbnailWithTransform: true,
                        kCGImageSourceThumbnailMaxPixelSize: 280,
                        kCGImageSourceShouldCacheImmediately: true
                      ] as CFDictionary) else { return nil as UIImage? }
                return UIImage(cgImage: image)
            }.value
        }
    }
}
