cmake_minimum_required(VERSION 3.8)
project(locobot_urdf_export)

find_package(ament_cmake REQUIRED)
install(DIRECTORY urdf resources DESTINATION share/${PROJECT_NAME})
ament_package()
