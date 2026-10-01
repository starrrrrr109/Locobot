#!/bin/bash
# Export a portable Locobot URDF ROS 2 package, including its mesh resources.

set -eo pipefail

if [ -f /workspace/environment.sh ]; then
    source /workspace/environment.sh 150
else
    source /opt/ros/humble/setup.bash
    if [ -f /interbotix_ws/install/setup.bash ]; then
        source /interbotix_ws/install/setup.bash
    fi
    if [ -f /workspace/ros2_ws/install/setup.bash ]; then
        source /workspace/ros2_ws/install/setup.bash
    fi
fi

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ROBOT_MODEL="${ROBOT_MODEL:-locobot_wx200}"
ROBOT_NAME="${ROBOT_NAME:-locobot}"
BASE_TYPE="${BASE_TYPE:-kobuki}"
EXPORT_PACKAGE="locobot_urdf_export"

if [ -d /workspace/ros2_ws ]; then
    DEFAULT_OUTPUT_DIR="/workspace/${EXPORT_PACKAGE}"
else
    DEFAULT_OUTPUT_DIR="${REPO_ROOT}/${EXPORT_PACKAGE}"
fi
OUTPUT_DIR="${1:-${DEFAULT_OUTPUT_DIR}}"
ARCHIVE_PATH="${OUTPUT_DIR}.tar.gz"

case "${ROBOT_MODEL}" in
    locobot_base)
        ARM_MODEL="mobile_base"
        ;;
    locobot_*)
        ARM_MODEL="mobile_${ROBOT_MODEL#locobot_}"
        ;;
    *)
        echo "Unsupported ROBOT_MODEL: ${ROBOT_MODEL}" >&2
        echo "Expected locobot_base, locobot_wx200, locobot_px100, or locobot_wx250s." >&2
        exit 2
        ;;
esac

for command_name in xacro ros2 tar; do
    if ! command -v "${command_name}" >/dev/null 2>&1; then
        echo "Required command not found: ${command_name}" >&2
        exit 1
    fi
done

DESCRIPTION_SHARE="$(ros2 pkg prefix --share interbotix_xslocobot_descriptions)"
XACRO_FILE="${DESCRIPTION_SHARE}/urdf/locobot.urdf.xacro"
if [ ! -f "${XACRO_FILE}" ]; then
    echo "Locobot xacro not found: ${XACRO_FILE}" >&2
    exit 1
fi

OUTPUT_PARENT="$(dirname "${OUTPUT_DIR}")"
OUTPUT_NAME="$(basename "${OUTPUT_DIR}")"
mkdir -p "${OUTPUT_PARENT}"
STAGING_DIR="$(mktemp -d "${OUTPUT_PARENT}/.${OUTPUT_NAME}.tmp.XXXXXX")"
trap 'rm -rf -- "${STAGING_DIR}"' EXIT

mkdir -p "${STAGING_DIR}/urdf" "${STAGING_DIR}/resources"
URDF_FILE="${STAGING_DIR}/urdf/${ROBOT_MODEL}.urdf"

echo "[export] Generating ${ROBOT_MODEL} URDF..."
xacro "${XACRO_FILE}" \
    robot_model:="${ROBOT_MODEL}" \
    robot_name:="${ROBOT_NAME}" \
    arm_model:="${ARM_MODEL}" \
    base_model:="${BASE_TYPE}" \
    -o "${URDF_FILE}"

mapfile -t RESOURCE_URIS < <(grep -oE 'package://[^"<[:space:]]+' "${URDF_FILE}" | sort -u)
if [ "${#RESOURCE_URIS[@]}" -eq 0 ]; then
    echo "No package resources were found in the generated URDF." >&2
    exit 1
fi

declare -A REFERENCED_PACKAGES=()

for uri in "${RESOURCE_URIS[@]}"; do
    package_and_path="${uri#package://}"
    package_name="${package_and_path%%/*}"
    resource_path="${package_and_path#*/}"

    if [ "${resource_path}" = "${package_and_path}" ]; then
        echo "Invalid package URI in URDF: ${uri}" >&2
        exit 1
    fi

    package_share="$(ros2 pkg prefix --share "${package_name}")"
    source_resource="${package_share}/${resource_path}"
    if [ ! -e "${source_resource}" ]; then
        echo "Referenced resource does not exist: ${source_resource}" >&2
        exit 1
    fi

    destination_resource="${STAGING_DIR}/resources/${package_name}/${resource_path}"
    mkdir -p "$(dirname "${destination_resource}")"
    # Installed description packages can contain symlinks when built with
    # --symlink-install. Dereference them so the exported archive is portable.
    cp -aL "${source_resource}" "${destination_resource}"

    # Collada files can reference image files relative to the .dae file.
    if [[ "${resource_path}" == *.dae ]] && [ -d "$(dirname "${source_resource}")/images" ]; then
        cp -aL \
            "$(dirname "${source_resource}")/images" \
            "$(dirname "${destination_resource}")/"
    fi
    REFERENCED_PACKAGES["${package_name}"]=1
done

for package_name in "${!REFERENCED_PACKAGES[@]}"; do
    sed -i \
        "s#package://${package_name}/#package://${EXPORT_PACKAGE}/resources/${package_name}/#g" \
        "${URDF_FILE}"
done

cat >"${STAGING_DIR}/package.xml" <<EOF
<?xml version="1.0"?>
<package format="3">
  <name>${EXPORT_PACKAGE}</name>
  <version>0.1.0</version>
  <description>Portable ${ROBOT_MODEL} URDF and mesh resources.</description>
  <maintainer email="locobot@example.com">Locobot</maintainer>
  <license>BSD-3-Clause</license>
  <buildtool_depend>ament_cmake</buildtool_depend>
  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
EOF

cat >"${STAGING_DIR}/CMakeLists.txt" <<EOF
cmake_minimum_required(VERSION 3.8)
project(${EXPORT_PACKAGE})

find_package(ament_cmake REQUIRED)
install(DIRECTORY urdf resources DESTINATION share/\${PROJECT_NAME})
ament_package()
EOF

cat >"${STAGING_DIR}/README.md" <<EOF
# ${ROBOT_MODEL} portable URDF

This package was generated with:

- robot_model: \`${ROBOT_MODEL}\`
- arm_model: \`${ARM_MODEL}\`
- base_model: \`${BASE_TYPE}\`
- robot_name: \`${ROBOT_NAME}\`

Copy this directory into the Stretch ROS 2 workspace, then run:

\`\`\`bash
cd ~/ros2_ws
colcon build --symlink-install --packages-select ${EXPORT_PACKAGE}
source install/setup.bash
\`\`\`

URDF: \`urdf/${ROBOT_MODEL}.urdf\`
EOF

if [ -e "${OUTPUT_DIR}" ]; then
    rm -rf -- "${OUTPUT_DIR}"
fi
mv "${STAGING_DIR}" "${OUTPUT_DIR}"
trap - EXIT

rm -f -- "${ARCHIVE_PATH}"
tar -czf "${ARCHIVE_PATH}" -C "${OUTPUT_PARENT}" "${OUTPUT_NAME}"

echo "[export] Complete."
echo "[export] Package: ${OUTPUT_DIR}"
echo "[export] Archive: ${ARCHIVE_PATH}"
echo "[export] URDF: ${OUTPUT_DIR}/urdf/${ROBOT_MODEL}.urdf"
