import Foundation

enum FeatureSignature {
    static func keypointCount(_ data: Data) -> Int {
        guard data.count >= 28 else { return 0 }
        return data.withUnsafeBytes { bytes in
            guard UInt32(littleEndian: bytes.loadUnaligned(fromByteOffset: 0, as: UInt32.self)) == 0x57424f35,
                  UInt32(littleEndian: bytes.loadUnaligned(fromByteOffset: 4, as: UInt32.self)) == 1 else { return 0 }
            let count = Int(Int32(littleEndian: bytes.loadUnaligned(fromByteOffset: 16, as: Int32.self)))
            guard count > 0, count <= 1600, data.count == 28 + count * 40 else { return 0 }
            return count
        }
    }
}
