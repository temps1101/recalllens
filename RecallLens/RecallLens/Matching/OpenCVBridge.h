#import <CoreVideo/CoreVideo.h>
#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

@interface WBOpenCVMatch : NSObject

@property(nonatomic, readonly) float similarity;
@property(nonatomic, readonly) float meanDistance;
@property(nonatomic, readonly) NSInteger goodMatchCount;
@property(nonatomic, readonly) NSInteger inlierCount;

- (instancetype)init NS_UNAVAILABLE;

@end

@interface WBOpenCVBridge : NSObject

+ (NSString *)versionString;
+ (nullable NSData *)featureDataForImage:(UIImage *)image
                                   error:(NSError **)error;
+ (nullable NSData *)featureDataForPixelBuffer:(CVPixelBufferRef)pixelBuffer
                                          error:(NSError **)error;
+ (nullable WBOpenCVMatch *)matchFeatureData:(NSData *)queryData
                              toFeatureData:(NSData *)referenceData
                                       error:(NSError **)error;

@end

NS_ASSUME_NONNULL_END
