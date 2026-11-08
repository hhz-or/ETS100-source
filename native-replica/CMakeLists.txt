cmake_minimum_required(VERSION 3.25)
project(EtsReplica LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_C_STANDARD 11)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

if(MSVC)
  # sources are UTF-8 (Chinese strings in UI/log); without this MSVC assumes GBK (CP936)
  add_compile_options(/utf-8 /W3)
  add_compile_definitions(UNICODE _UNICODE NOMINMAX)
endif()

# WebView2 SDK (default: local tool cache)
if(NOT DEFINED WEBVIEW2_SDK)
  set(WEBVIEW2_SDK "C:/rea_tools/webview2/build/native")
endif()
message(STATUS "WEBVIEW2_SDK=${WEBVIEW2_SDK}")

set(THIRD_PARTY "${CMAKE_SOURCE_DIR}/third_party")
set(SHARED "${CMAKE_SOURCE_DIR}/shared")

add_library(ets_common STATIC "${SHARED}/common.cpp")
target_include_directories(ets_common PUBLIC "${SHARED}" "${THIRD_PARTY}/include")
target_link_libraries(ets_common PUBLIC bcrypt ole32)

# ---------------- shell ----------------
file(GLOB SHELL_SRC "${CMAKE_SOURCE_DIR}/shell/*.cpp")
add_executable(EtsReplica WIN32 ${SHELL_SRC})
target_include_directories(EtsReplica PRIVATE
  "${SHARED}"
  "${THIRD_PARTY}/include"
  "${WEBVIEW2_SDK}/include")
target_link_libraries(EtsReplica PRIVATE
  ets_common
  "${WEBVIEW2_SDK}/x64/WebView2LoaderStatic.lib"
  winhttp ws2_32 ole32 shell32 shlwapi user32 gdi32 advapi32 crypt32 version)
set_target_properties(EtsReplica PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
  OUTPUT_NAME "EtsReplica")

# ---------------- plugins ----------------
function(add_ets_plugin name dllname outdir)
  file(GLOB PLUGIN_SRC "${CMAKE_SOURCE_DIR}/plugins/${name}/*.cpp" "${CMAKE_SOURCE_DIR}/plugins/${name}/*.c")
  add_library(plugin_${name} SHARED ${PLUGIN_SRC})
  target_include_directories(plugin_${name} PRIVATE
    "${SHARED}" "${THIRD_PARTY}/include" "${THIRD_PARTY}")
  target_link_libraries(plugin_${name} PRIVATE ets_common winhttp advapi32 psapi)
  set_target_properties(plugin_${name} PROPERTIES
    OUTPUT_NAME "${dllname}"
    PREFIX ""
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin/plugins/${outdir}")
endfunction()

add_ets_plugin(etshelper etshelper etshelper)
add_ets_plugin(filehelper filehelper filehelper)
add_ets_plugin(httphelper httphelper httphelper)
add_ets_plugin(shellhelper shellhelper shellhelper)
add_ets_plugin(sevenzip sevenzip sevenzip)
add_ets_plugin(sysconfig sysconfig sysconfig)

# sqlite plugin embeds the sqlite amalgamation
file(GLOB SQLITE_SRC "${CMAKE_SOURCE_DIR}/plugins/sqlitepln/*.cpp")
add_library(plugin_sqlitepln SHARED ${SQLITE_SRC} "${THIRD_PARTY}/sqlite3.c")
target_include_directories(plugin_sqlitepln PRIVATE
  "${SHARED}" "${THIRD_PARTY}/include" "${THIRD_PARTY}")
target_link_libraries(plugin_sqlitepln PRIVATE ets_common winhttp advapi32)
set_target_properties(plugin_sqlitepln PROPERTIES
  OUTPUT_NAME "sqlitepln" PREFIX ""
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin/plugins/sqlitepln")

# sevenzip plugin embeds miniz
file(GLOB SEVENZIP_SRC "${CMAKE_SOURCE_DIR}/plugins/sevenzip/*.cpp")
if(SEVENZIP_SRC)
  target_sources(plugin_sevenzip PRIVATE "${THIRD_PARTY}/miniz.c")
endif()

# copy plugin dependency: sqlite dll? (static amalgamation, none)

# ---------------- speex (audio encoding for soundhelper) ----------------
file(GLOB SPEEX_SRC "${THIRD_PARTY}/speex/libspeex/*.c")
add_library(speex STATIC ${SPEEX_SRC})
target_include_directories(speex PUBLIC "${THIRD_PARTY}/speex/include" "${THIRD_PARTY}/speex/include/speex")
target_compile_definitions(speex PUBLIC HAVE_CONFIG_H)

# soundhelper plugin: speex encode (recording pipeline)
file(GLOB SOUNDHELPER_SRC "${CMAKE_SOURCE_DIR}/plugins/soundhelper/*.cpp")
add_library(plugin_soundhelper SHARED ${SOUNDHELPER_SRC})
target_include_directories(plugin_soundhelper PRIVATE "${SHARED}" "${THIRD_PARTY}/include" "${THIRD_PARTY}/speex/include")
target_link_libraries(plugin_soundhelper PRIVATE ets_common speex)
set_target_properties(plugin_soundhelper PROPERTIES OUTPUT_NAME "soundhelper" PREFIX ""
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin/plugins/soundhelper")
