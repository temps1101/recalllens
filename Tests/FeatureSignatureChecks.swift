import Foundation

@main
struct FeatureSignatureChecks {
    static func main() {
        func fixture(_ count: Int32) -> Data {
            let header: [UInt32] = [0x57424f35, 1, 960, 720, UInt32(bitPattern: count), 32, 0]
            var data = Data()
            for var value in header.map({ $0.littleEndian }) { withUnsafeBytes(of: &value) { data.append(contentsOf: $0) } }
            data.append(Data(count: max(0, Int(count)) * 40))
            return data
        }
        for count: Int32 in [1, 7, 8, 1600] { precondition(FeatureSignature.keypointCount(fixture(count)) == Int(count)) }
        for bad in [Data(), fixture(0), fixture(-1), fixture(1601), Data(fixture(8).dropLast())] {
            precondition(FeatureSignature.keypointCount(bad) == 0)
        }
        var corrupt = fixture(8);corrupt[0] = 0
        precondition(FeatureSignature.keypointCount(corrupt) == 0)
        print("Capture readiness: signature counts, threshold boundaries and malformed inputs passed")
    }
}
