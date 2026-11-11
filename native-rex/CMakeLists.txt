# ben10 - ReXGlue Recompiled Project
#
# SDK boilerplate lives in generated/rexglue.cmake.

cmake_minimum_required(VERSION 3.25)
project(ben10 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(generated/rexglue.cmake)

# Sources
set(BEN10_SOURCES
    src/main.cpp
    src/frame_metrics.cpp
    src/albedo_textures.cpp
)

if(WIN32)
    enable_language(RC)
    add_executable(ben10 WIN32 ${BEN10_SOURCES} ../launcher/cosmic_icon.rc)
    target_sources(ben10 PRIVATE src/default_prompt_sprites.rc src/cinematic_player.cpp src/music_session.cpp)
    target_link_libraries(ben10 PRIVATE mfplat mfuuid windowscodecs oleaut32 d3d12 d3dcompiler windowsapp)
    target_include_directories(ben10 PRIVATE "$<$<COMPILE_LANGUAGE:RC>:${CMAKE_CURRENT_SOURCE_DIR}/../launcher>" "$<$<COMPILE_LANGUAGE:RC>:${CMAKE_CURRENT_SOURCE_DIR}/src>")
    set_source_files_properties(src/default_prompt_sprites.rc PROPERTIES
        OBJECT_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/default_prompt_sprites.bin;${CMAKE_CURRENT_SOURCE_DIR}/src/keyboard_prompt_sprites.bin;${CMAKE_CURRENT_SOURCE_DIR}/src/keyboard_prompt_icons.bin;${CMAKE_CURRENT_SOURCE_DIR}/src/xbox_prompt_sprites.bin;${CMAKE_CURRENT_SOURCE_DIR}/src/modern_face_icons.bin")
    set_source_files_properties(../launcher/cosmic_icon.rc PROPERTIES
        OBJECT_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/../launcher/cosmic_icon.ico")
else()
    add_executable(ben10 ${BEN10_SOURCES})
endif()

rexglue_setup_target(ben10 GPU_PLUGINS xenos)
target_compile_options(ben10 PRIVATE /EHsc)
target_compile_options(ben10_recomp PRIVATE "/FI${CMAKE_CURRENT_SOURCE_DIR}/src/frame_metrics.h")

# The SDK enables SSE4.1 for GNU-style Clang, but its helper skips clang-cl.
# Keep SIMDe's nearest-even vector rounding native rather than introducing a
# roundevenf CRT dependency unavailable in the Windows runtime.
if(MSVC AND CMAKE_CXX_COMPILER_ID STREQUAL "Clang" AND
   CMAKE_SYSTEM_PROCESSOR MATCHES "^(AMD64|x86_64)$")
    target_compile_options(ben10 PRIVATE /clang:-msse4.1)
    target_compile_options(ben10_recomp PRIVATE /clang:-msse4.1)
endif()

# Optional isolated equivalence target. It reuses the original-byte oracle
# corpus; it is deliberately separate from gameplay compatibility checks.
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/../build/rex-leaf-tests/main.cpp")
    add_executable(ben10_leaf_tests EXCLUDE_FROM_ALL
        ../build/rex-leaf-tests/main.cpp ../build/rex-leaf-tests/selected.cpp)
    target_include_directories(ben10_leaf_tests PRIVATE generated/default)
    target_link_libraries(ben10_leaf_tests PRIVATE rex::runtime)
    rexglue_apply_target_settings(ben10_leaf_tests)
endif()
