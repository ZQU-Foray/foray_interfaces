cmake_minimum_required(VERSION 3.16)

# 本仓是 **header-only 的契约层**：不编译任何实现源文件，只导出一个 INTERFACE
# target。被所有仓依赖、自身零自研依赖（见 .foray-layer 与 decision.md「构建形态」）。
project(foray_interfaces VERSION 0.1.0 LANGUAGES CXX)

# ---- INTERFACE target ----
# 生成物 `#include "lower_link.hpp"` 里的 include 路径是相对 generated/ 写的，
# 所以 BUILD_INTERFACE 的 include 根必须是 generated/，不是仓库根。
# 安装时把同一个头文件装到 include/ 根下，保证下游 `#include "lower_link.hpp"` 不变。
add_library(foray_interfaces_lower_link INTERFACE)
add_library(foray_interfaces::lower_link ALIAS foray_interfaces_lower_link)

# 导出到下游的名字是 foray_interfaces::lower_link；安装树里不再暴露内部的
# foray_interfaces_lower_link 这个名字。
set_target_properties(foray_interfaces_lower_link PROPERTIES
    EXPORT_NAME lower_link
)

target_include_directories(foray_interfaces_lower_link INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/generated>
    $<INSTALL_INTERFACE:include>
)

# 生成物只依赖标准库（<cstddef> / <cstdint> / <cstring>），但用到了 constexpr 与
# 定宽整数，最低 C++17——把要求挂在 INTERFACE 上，下游不必各自再写一遍。
target_compile_features(foray_interfaces_lower_link INTERFACE cxx_std_17)

# ---- 安装与导出 ----
include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

# 生成物禁止手改（见 README / tree.md），但它就是本包要交付的头文件。
install(FILES generated/lower_link.hpp
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(TARGETS foray_interfaces_lower_link
    EXPORT foray_interfacesTargets
)

install(EXPORT foray_interfacesTargets
    FILE foray_interfacesTargets.cmake
    NAMESPACE foray_interfaces::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/foray_interfaces
)

configure_package_config_file(
    cmake/foray_interfacesConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/foray_interfacesConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/foray_interfaces
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/foray_interfacesConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/foray_interfacesConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/foray_interfacesConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/foray_interfaces
)

# ---- 测试 ----
# 生成物的契约测试（tests/lower_link_test.cpp）不依赖外部测试框架：失败时返回
# 非零。CI 的 build-cmake 作业与本地 `ctest` 都跑同一个可执行文件。
include(CTest)

if(BUILD_TESTING)
    add_executable(lower_link_test tests/lower_link_test.cpp)
    target_link_libraries(lower_link_test PRIVATE foray_interfaces::lower_link)

    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(lower_link_test PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    add_test(NAME lower_link_test COMMAND lower_link_test)
endif()
