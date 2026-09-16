cmake_minimum_required(VERSION 3.16)
project(CppHub VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 轻量 C++ 量化工具试点（Cpp_Hub，D6 第二试点）
# 目标：验证全链路（中文路径 scp / 跨站 venv 预置 / golden 独立验收），编译非硬性。
add_library(cpphub 因子计算_核心.cpp)

add_executable(cpphub_run 因子计算_run.cpp)

target_link_libraries(cpphub_run PRIVATE cpphub)

# 测试（B 站真实 venv pytest 在远端执行，主控侧 golden 在 host 侧独立验收）
enable_testing()
add_test(NAME golden NAME 占位)