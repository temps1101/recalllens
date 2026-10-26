#import "OpenCVBridge.h"

#import <opencv2/core.hpp>
#import <opencv2/features.hpp>
#import <opencv2/geometry.hpp>
#import <opencv2/imgproc.hpp>

namespace {

NSString *const WBOpenCVErrorDomain = @"RecallLens.OpenCV";
constexpr uint32_t featureMagic = 0x57424f35; // WBO5
constexpr uint32_t featureFormatVersion = 1;
constexpr int maximumDimension = 960;
constexpr int maximumFeatures = 1600;

struct Header {
    uint32_t magic;
    uint32_t version;
    int32_t width;
    int32_t height;
    int32_t rows;
    int32_t columns;
    int32_t type;
};

struct PackedKeyPoint {
    float x;
    float y;
};

struct Features {
    cv::Size imageSize;
    std::vector<cv::KeyPoint> keypoints;
    cv::Mat descriptors;
};

NSError *makeError(NSInteger code, NSString *message) {
    return [NSError errorWithDomain:WBOpenCVErrorDomain
                               code:code
                           userInfo:@{NSLocalizedDescriptionKey: NSLocalizedString(message, nil)}];
}

cv::Mat normalizedGray(const cv::Mat &source) {
    cv::Mat gray;
    if (source.channels() == 4) {
        cv::cvtColor(source, gray, cv::COLOR_BGRA2GRAY);
    } else if (source.channels() == 3) {
        cv::cvtColor(source, gray, cv::COLOR_BGR2GRAY);
    } else {
        gray = source;
    }

    const int largest = std::max(gray.cols, gray.rows);
    if (largest <= maximumDimension) {
        return gray.clone();
    }
    const double scale = static_cast<double>(maximumDimension) / largest;
    cv::Mat resized;
    cv::resize(gray, resized, cv::Size(), scale, scale, cv::INTER_AREA);
    return resized;
}

Features extract(const cv::Mat &source) {
    cv::Mat gray = normalizedGray(source);
    auto orb = cv::ORB::create(maximumFeatures, 1.2f, 8, 31, 0, 2, cv::ORB::HARRIS_SCORE, 31, 12);
    Features features;
    features.imageSize = gray.size();
    orb->detectAndCompute(gray, cv::noArray(), features.keypoints, features.descriptors);
    return features;
}

NSData *encode(const Features &features) {
    if (features.descriptors.empty() || features.keypoints.empty()) {
        return nil;
    }
    cv::Mat descriptors = features.descriptors.isContinuous()
        ? features.descriptors
        : features.descriptors.clone();
    Header header = {
        featureMagic,
        featureFormatVersion,
        features.imageSize.width,
        features.imageSize.height,
        descriptors.rows,
        descriptors.cols,
        descriptors.type()
    };
    NSMutableData *data = [NSMutableData dataWithBytes:&header length:sizeof(header)];
    std::vector<PackedKeyPoint> points;
    points.reserve(features.keypoints.size());
    for (const auto &keypoint : features.keypoints) {
        points.push_back({keypoint.pt.x, keypoint.pt.y});
    }
    [data appendBytes:points.data() length:points.size() * sizeof(PackedKeyPoint)];
    [data appendBytes:descriptors.data length:descriptors.total() * descriptors.elemSize()];
    return data;
}

bool decode(NSData *data, Features &features) {
    if (data.length < sizeof(Header)) {
        return false;
    }
    Header header;
    [data getBytes:&header length:sizeof(header)];
    if (header.magic != featureMagic || header.version != featureFormatVersion ||
        header.width <= 0 || header.height <= 0 || header.rows <= 0 ||
        header.columns <= 0 || header.type != CV_8U) {
        return false;
    }
    const size_t pointBytes = static_cast<size_t>(header.rows) * sizeof(PackedKeyPoint);
    const size_t descriptorBytes = static_cast<size_t>(header.rows) * header.columns;
    const size_t expected = sizeof(Header) + pointBytes + descriptorBytes;
    if (data.length != expected) {
        return false;
    }
    const auto *bytes = static_cast<const uint8_t *>(data.bytes);
    const auto *points = reinterpret_cast<const PackedKeyPoint *>(bytes + sizeof(Header));
    features.imageSize = cv::Size(header.width, header.height);
    features.keypoints.reserve(header.rows);
    for (int index = 0; index < header.rows; ++index) {
        features.keypoints.emplace_back(points[index].x, points[index].y, 31.0f);
    }
    const void *descriptorStart = bytes + sizeof(Header) + pointBytes;
    cv::Mat wrapped(header.rows, header.columns, CV_8U, const_cast<void *>(descriptorStart));
    features.descriptors = wrapped.clone();
    return true;
}

cv::Mat imageMatrix(UIImage *image) {
    UIImage *normalized = image;
    if (image.imageOrientation != UIImageOrientationUp) {
        UIGraphicsBeginImageContextWithOptions(image.size, NO, 1.0);
        [image drawInRect:CGRectMake(0, 0, image.size.width, image.size.height)];
        normalized = UIGraphicsGetImageFromCurrentImageContext();
        UIGraphicsEndImageContext();
    }
    CGImageRef cgImage = normalized.CGImage;
    if (!cgImage) {
        return {};
    }
    const size_t width = CGImageGetWidth(cgImage);
    const size_t height = CGImageGetHeight(cgImage);
    cv::Mat bgra(static_cast<int>(height), static_cast<int>(width), CV_8UC4);
    CGColorSpaceRef colorSpace = CGColorSpaceCreateDeviceRGB();
    const CGBitmapInfo bitmapInfo = static_cast<CGBitmapInfo>(
        static_cast<uint32_t>(kCGImageAlphaPremultipliedLast) |
        static_cast<uint32_t>(kCGBitmapByteOrder32Big)
    );
    CGContextRef context = CGBitmapContextCreate(
        bgra.data,
        width,
        height,
        8,
        bgra.step[0],
        colorSpace,
        bitmapInfo
    );
    CGColorSpaceRelease(colorSpace);
    if (!context) {
        return {};
    }
    CGContextDrawImage(context, CGRectMake(0, 0, width, height), cgImage);
    CGContextRelease(context);
    cv::cvtColor(bgra, bgra, cv::COLOR_RGBA2BGRA);
    return bgra;
}

float convexHullCoverage(const std::vector<cv::Point2f> &points, cv::Size size) {
    if (points.size() < 3 || size.area() <= 0) {
        return 0;
    }
    std::vector<cv::Point2f> hull;
    cv::convexHull(points, hull);
    return static_cast<float>(std::min(1.0, cv::contourArea(hull) / size.area()));
}

} // namespace

@implementation WBOpenCVMatch {
    float _similarity;
    float _meanDistance;
    NSInteger _goodMatchCount;
    NSInteger _inlierCount;
}

- (instancetype)initWithSimilarity:(float)similarity
                      meanDistance:(float)meanDistance
                    goodMatchCount:(NSInteger)goodMatchCount
                       inlierCount:(NSInteger)inlierCount {
    self = [super init];
    if (self) {
        _similarity = similarity;
        _meanDistance = meanDistance;
        _goodMatchCount = goodMatchCount;
        _inlierCount = inlierCount;
    }
    return self;
}

- (float)similarity { return _similarity; }
- (float)meanDistance { return _meanDistance; }
- (NSInteger)goodMatchCount { return _goodMatchCount; }
- (NSInteger)inlierCount { return _inlierCount; }

@end

@implementation WBOpenCVBridge

+ (NSString *)versionString {
    return [NSString stringWithUTF8String:CV_VERSION];
}

+ (NSData *)featureDataForImage:(UIImage *)image error:(NSError **)error {
    try {
        cv::Mat matrix = imageMatrix(image);
        if (matrix.empty()) {
            if (error) *error = makeError(1, @"画像をOpenCV形式へ変換できませんでした。");
            return nil;
        }
        NSData *data = encode(extract(matrix));
        if (!data && error) *error = makeError(2, @"画像から十分な特徴点を検出できませんでした。");
        return data;
    } catch (const cv::Exception &exception) {
        if (error) *error = makeError(3, [NSString stringWithUTF8String:exception.what()]);
        return nil;
    }
}

+ (NSData *)featureDataForPixelBuffer:(CVPixelBufferRef)pixelBuffer error:(NSError **)error {
    CVPixelBufferLockBaseAddress(pixelBuffer, kCVPixelBufferLock_ReadOnly);
    try {
        const int width = static_cast<int>(CVPixelBufferGetWidth(pixelBuffer));
        const int height = static_cast<int>(CVPixelBufferGetHeight(pixelBuffer));
        const size_t stride = CVPixelBufferGetBytesPerRow(pixelBuffer);
        void *base = CVPixelBufferGetBaseAddress(pixelBuffer);
        cv::Mat bgra(height, width, CV_8UC4, base, stride);
        NSData *data = encode(extract(bgra));
        CVPixelBufferUnlockBaseAddress(pixelBuffer, kCVPixelBufferLock_ReadOnly);
        if (!data && error) *error = makeError(4, @"カメラ画像から十分な特徴点を検出できませんでした。");
        return data;
    } catch (const cv::Exception &exception) {
        CVPixelBufferUnlockBaseAddress(pixelBuffer, kCVPixelBufferLock_ReadOnly);
        if (error) *error = makeError(5, [NSString stringWithUTF8String:exception.what()]);
        return nil;
    }
}

+ (WBOpenCVMatch *)matchFeatureData:(NSData *)queryData
                      toFeatureData:(NSData *)referenceData
                               error:(NSError **)error {
    try {
        Features query;
        Features reference;
        if (!decode(queryData, query) || !decode(referenceData, reference)) {
            if (error) *error = makeError(6, @"OpenCV特徴データの形式が不正です。");
            return nil;
        }

        cv::BFMatcher matcher(cv::NORM_HAMMING);
        std::vector<std::vector<cv::DMatch>> pairs;
        matcher.knnMatch(query.descriptors, reference.descriptors, pairs, 2);
        std::vector<cv::DMatch> good;
        for (const auto &pair : pairs) {
            if (pair.size() == 2 && pair[0].distance < 0.75f * pair[1].distance) {
                good.push_back(pair[0]);
            }
        }

        if (good.size() < 8) {
            const float support = std::min(1.0f, static_cast<float>(good.size()) / 24.0f);
            return [[WBOpenCVMatch alloc] initWithSimilarity:0.18f * support
                                               meanDistance:good.empty() ? 256.0f : good.front().distance
                                             goodMatchCount:good.size()
                                                inlierCount:0];
        }

        std::vector<cv::Point2f> queryPoints;
        std::vector<cv::Point2f> referencePoints;
        queryPoints.reserve(good.size());
        referencePoints.reserve(good.size());
        float distanceTotal = 0;
        for (const auto &match : good) {
            queryPoints.push_back(query.keypoints[match.queryIdx].pt);
            referencePoints.push_back(reference.keypoints[match.trainIdx].pt);
            distanceTotal += match.distance;
        }

        cv::Mat inlierMask;
        cv::findHomography(queryPoints, referencePoints, cv::RANSAC, 4.0, inlierMask);
        const int inliers = inlierMask.empty() ? 0 : cv::countNonZero(inlierMask);
        std::vector<cv::Point2f> inlierQueryPoints;
        for (int index = 0; index < inlierMask.rows; ++index) {
            if (inlierMask.at<uchar>(index)) inlierQueryPoints.push_back(queryPoints[index]);
        }

        const float inlierRatio = static_cast<float>(inliers) / good.size();
        const float support = std::min(1.0f, static_cast<float>(inliers) / 36.0f);
        const float coverage = std::min(1.0f, convexHullCoverage(inlierQueryPoints, query.imageSize) / 0.22f);
        const float similarity = std::clamp(
            0.52f * inlierRatio + 0.33f * support + 0.15f * coverage,
            0.0f,
            1.0f
        );
        return [[WBOpenCVMatch alloc] initWithSimilarity:similarity
                                           meanDistance:distanceTotal / good.size()
                                         goodMatchCount:good.size()
                                            inlierCount:inliers];
    } catch (const cv::Exception &exception) {
        if (error) *error = makeError(7, [NSString stringWithUTF8String:exception.what()]);
        return nil;
    }
}

@end
