#!/usr/bin/env ruby

require "xcodeproj"

root = File.expand_path("..", __dir__)
project_path = File.join(root, "RecallLens.xcodeproj")
project = Xcodeproj::Project.new(project_path)
project.root_object.attributes["LastSwiftUpdateCheck"] = "2700"
project.root_object.attributes["LastUpgradeCheck"] = "2700"
project.root_object.development_region = "en"
project.root_object.known_regions = ["en", "ja"]

app = project.new_target(:application, "RecallLens", :ios, "17.0")
app.product_name = "RecallLens"

sources_group = project.main_group.new_group("RecallLens", "RecallLens")
source_files = Dir.glob(File.join(root, "RecallLens", "**", "*.{swift,mm}")).sort
source_files.each do |path|
  relative = path.delete_prefix(File.join(root, "RecallLens") + "/")
  group = relative.split("/")[0...-1].reduce(sources_group) do |parent, component|
    parent.groups.find { |candidate| candidate.display_name == component } || parent.new_group(component, component)
  end
  reference = group.new_file(relative.split("/").last)
  app.source_build_phase.add_file_reference(reference)
end

header_files = Dir.glob(File.join(root, "RecallLens", "**", "*.h")).sort
header_files.each do |path|
  relative = path.delete_prefix(File.join(root, "RecallLens") + "/")
  group = relative.split("/")[0...-1].reduce(sources_group) do |parent, component|
    parent.groups.find { |candidate| candidate.display_name == component } || parent.new_group(component, component)
  end
  group.new_file(relative.split("/").last)
end

vendor_group = project.main_group.new_group("Vendor", "Vendor")
opencv = vendor_group.new_file("OpenCV/opencv2.framework")
app.frameworks_build_phase.add_file_reference(opencv)

config_group = project.main_group.new_group("Config", "Config")
cloud_config = config_group.new_file("Cloud.xcconfig")

assets = sources_group.new_file("Assets.xcassets")
app.resources_build_phase.add_file_reference(assets)
%w[Localizable.strings InfoPlist.strings].each do |filename|
  variant = sources_group.new_variant_group(filename)
  %w[en ja].each do |language|
    reference = variant.new_file("#{language}.lproj/#{filename}")
    reference.name = language
  end
  app.resources_build_phase.add_file_reference(variant)
end
sources_group.new_file("Info.plist")

app.build_configurations.each do |config|
  config.base_configuration_reference = cloud_config
  config.build_settings.update(
    "ASSETCATALOG_COMPILER_APPICON_NAME" => "AppIcon",
    "CODE_SIGN_STYLE" => "Automatic",
    "CURRENT_PROJECT_VERSION" => "1",
    "GENERATE_INFOPLIST_FILE" => "NO",
    "INFOPLIST_FILE" => "RecallLens/Info.plist",
    "IPHONEOS_DEPLOYMENT_TARGET" => "17.0",
    "MARKETING_VERSION" => "1.0",
    "PRODUCT_BUNDLE_IDENTIFIER" => "town.tsuru.recalllens",
    "PRODUCT_NAME" => "$(TARGET_NAME)",
    "SWIFT_OBJC_BRIDGING_HEADER" => "RecallLens/RecallLens-Bridging-Header.h",
    "SWIFT_VERSION" => "5.0",
    "TARGETED_DEVICE_FAMILY" => "1",
    "OTHER_LDFLAGS" => "$(inherited)",
    "EXCLUDED_ARCHS[sdk=iphonesimulator*]" => "arm64",
    "FRAMEWORK_SEARCH_PATHS" => "$(inherited) $(PROJECT_DIR)/Vendor/OpenCV",
  )
end

project.build_configurations.each do |config|
  config.build_settings.update(
    "CLANG_ANALYZER_NONNULL" => "YES",
    "CLANG_ANALYZER_NUMBER_OBJECT_CONVERSION" => "YES_AGGRESSIVE",
    "CLANG_CXX_LANGUAGE_STANDARD" => "gnu++20",
    "CLANG_WARN_DOCUMENTATION_COMMENTS" => "NO",
    "CLANG_WARN_QUOTED_INCLUDE_IN_FRAMEWORK_HEADER" => "NO",
    "DEVELOPMENT_TEAM" => ENV.fetch("RECALL_LENS_DEVELOPMENT_TEAM", ""),
    "ENABLE_STRICT_OBJC_MSGSEND" => "YES",
    "GCC_C_LANGUAGE_STANDARD" => "gnu17",
    "IPHONEOS_DEPLOYMENT_TARGET" => "17.0",
    "SWIFT_VERSION" => "5.0",
  )
end

project.save
puts "Generated #{project_path}"

