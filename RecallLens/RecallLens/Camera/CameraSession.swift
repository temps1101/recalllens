import AVFoundation
import Foundation

protocol CameraSessionDelegate: AnyObject {
    func cameraSession(_ session: CameraSession, didOutput pixelBuffer: CVPixelBuffer)
    func cameraSession(_ session: CameraSession, didCapture data: Data)
    func cameraSession(_ session: CameraSession, didFail error: Error)
}

final class CameraSession: NSObject, @unchecked Sendable {
    enum CameraError: LocalizedError {
        case unavailable
        case cannotAddInput
        case cannotAddOutput
        case captureFailed

        var errorDescription: String? {
            switch self {
            case .unavailable: String(localized: "カメラを利用できません。")
            case .cannotAddInput: String(localized: "カメラ入力を構成できません。")
            case .cannotAddOutput: String(localized: "カメラ出力を構成できません。")
            case .captureFailed: String(localized: "撮影した画像を取得できません。")
            }
        }
    }

    let captureSession = AVCaptureSession()
    weak var delegate: CameraSessionDelegate?

    private let sessionQueue = DispatchQueue(label: "camera.session", qos: .userInitiated)
    private let videoQueue = DispatchQueue(label: "camera.frames", qos: .userInitiated)
    private let photoOutput = AVCapturePhotoOutput()
    private let videoOutput = AVCaptureVideoDataOutput()
    private var configured = false
    private var photoDelegates: [Int64: PhotoCaptureDelegate] = [:]

    func requestAccessAndStart() async -> Bool {
        let authorized: Bool
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            authorized = true
        case .notDetermined:
            authorized = await AVCaptureDevice.requestAccess(for: .video)
        default:
            authorized = false
        }
        guard authorized else { return false }
        sessionQueue.async { [weak self] in
            self?.configureAndStart()
        }
        return true
    }

    func stop() {
        sessionQueue.async { [weak self] in
            guard let self, captureSession.isRunning else { return }
            captureSession.stopRunning()
        }
    }

    func capturePhoto() {
        sessionQueue.async { [weak self] in
            guard let self else { return }
            let settings = AVCapturePhotoSettings()
            settings.photoQualityPrioritization = .quality
            let uniqueID = settings.uniqueID
            let photoDelegate = PhotoCaptureDelegate { [weak self] result in
                guard let self else { return }
                self.sessionQueue.async {
                    self.photoDelegates[uniqueID] = nil
                }
                switch result {
                case .success(let data): self.delegate?.cameraSession(self, didCapture: data)
                case .failure(let error): self.delegate?.cameraSession(self, didFail: error)
                }
            }
            photoDelegates[uniqueID] = photoDelegate
            photoOutput.capturePhoto(with: settings, delegate: photoDelegate)
        }
    }

    private func configureAndStart() {
        do {
            if !configured { try configure() }
            if !captureSession.isRunning { captureSession.startRunning() }
        } catch {
            delegate?.cameraSession(self, didFail: error)
        }
    }

    private func configure() throws {
        captureSession.beginConfiguration()
        defer { captureSession.commitConfiguration() }
        captureSession.sessionPreset = .photo

        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
            throw CameraError.unavailable
        }
        let input = try AVCaptureDeviceInput(device: device)
        guard captureSession.canAddInput(input) else { throw CameraError.cannotAddInput }
        captureSession.addInput(input)

        guard captureSession.canAddOutput(photoOutput), captureSession.canAddOutput(videoOutput) else {
            throw CameraError.cannotAddOutput
        }
        captureSession.addOutput(photoOutput)
        photoOutput.maxPhotoQualityPrioritization = .quality
        videoOutput.alwaysDiscardsLateVideoFrames = true
        videoOutput.videoSettings = [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA
        ]
        videoOutput.setSampleBufferDelegate(self, queue: videoQueue)
        captureSession.addOutput(videoOutput)

        for connection in [photoOutput.connection(with: .video), videoOutput.connection(with: .video)] {
            if let connection, connection.isVideoRotationAngleSupported(90) {
                connection.videoRotationAngle = 90
            }
        }
        configured = true
    }
}

extension CameraSession: AVCaptureVideoDataOutputSampleBufferDelegate {
    func captureOutput(
        _ output: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        delegate?.cameraSession(self, didOutput: pixelBuffer)
    }
}

private final class PhotoCaptureDelegate: NSObject, AVCapturePhotoCaptureDelegate, @unchecked Sendable {
    private let completion: (Result<Data, Error>) -> Void

    init(completion: @escaping (Result<Data, Error>) -> Void) {
        self.completion = completion
    }

    func photoOutput(
        _ output: AVCapturePhotoOutput,
        didFinishProcessingPhoto photo: AVCapturePhoto,
        error: Error?
    ) {
        if let error {
            completion(.failure(error))
        } else if let data = photo.fileDataRepresentation() {
            completion(.success(data))
        } else {
            completion(.failure(CameraSession.CameraError.captureFailed))
        }
    }
}

