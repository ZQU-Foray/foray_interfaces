# 安装冒烟夹具：模拟下游仓库用「已安装」的 foray_interfaces 消费生成物头文件。
# CI 的 build-cmake 作业与本地验证跑同一份，避免两套脚本各自漂移。
cmake_minimum_required(VERSION 3.16)

project(foray_interfaces_consumer LANGUAGES CXX)

find_package(foray_interfaces REQUIRED)

add_executable(consumer main.cpp)
target_link_libraries(consumer PRIVATE foray_interfaces::lower_link)
