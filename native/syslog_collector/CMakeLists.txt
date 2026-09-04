cmake_minimum_required(VERSION 3.20)
project(cams_syslog_collector LANGUAGES CXX)

add_executable(cams-syslog-collector main.cpp)
target_compile_features(cams-syslog-collector PRIVATE cxx_std_20)
target_compile_options(cams-syslog-collector PRIVATE -Wall -Wextra -Wpedantic)
target_link_libraries(cams-syslog-collector PRIVATE dl pthread)

install(TARGETS cams-syslog-collector RUNTIME DESTINATION bin)
