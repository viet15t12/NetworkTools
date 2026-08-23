cmake_minimum_required(VERSION 3.20)
project(networktools_syslog_collector LANGUAGES CXX)

add_executable(networktools-syslog-collector main.cpp)
target_compile_features(networktools-syslog-collector PRIVATE cxx_std_20)
target_compile_options(networktools-syslog-collector PRIVATE -Wall -Wextra -Wpedantic)
target_link_libraries(networktools-syslog-collector PRIVATE dl pthread)

install(TARGETS networktools-syslog-collector RUNTIME DESTINATION bin)
