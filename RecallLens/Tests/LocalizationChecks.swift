import Foundation

@main
struct LocalizationChecks {
    static func main() {
        let appPath = CommandLine.arguments[1]
        let en = Bundle(path: appPath + "/en.lproj")!
        let ja = Bundle(path: appPath + "/ja.lproj")!
        for (key, english) in [("保存", "Save"), ("共有", "Share"), ("破棄", "Discard"), ("受け取った写真", "Received photo"), ("閉じる", "Close")] {
            precondition(en.localizedString(forKey: key, value: nil, table: nil) == english)
            precondition(ja.localizedString(forKey: key, value: nil, table: nil) == key)
        }
        precondition(en.localizedString(forKey: "NSCameraUsageDescription", value: nil, table: "InfoPlist").contains("camera"))
        precondition(ja.localizedString(forKey: "NSCameraUsageDescription", value: nil, table: "InfoPlist").contains("カメラ"))
        precondition(Bundle.preferredLocalizations(from: ["en", "ja"], forPreferences: ["ja-JP"]).first == "ja")
        precondition(Bundle.preferredLocalizations(from: ["en", "ja"], forPreferences: ["en-US"]).first == "en")
        print("Built app: English/Japanese actions, receipt label, permission text and locale selection passed")
    }
}
